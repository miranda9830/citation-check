"""PDF text access for citation checking: dump pages, keyword search, and verbatim quote verification.

Usage:
    python pdftool.py pages  PAPER.pdf [--from 3 --to 5]        # print page text (PDF page numbers, 1-based)
    python pdftool.py search PAPER.pdf "term one" "term two"     # hits with page + context, ranked by #terms matched
    python pdftool.py verify PAPER.pdf "exact sentence to check"  # does this sentence really occur in the PDF?

`verify` is the anti-hallucination gate: a quote may only be presented as the source's
original sentence if verify returns EXACT or NEAR. It tolerates PDF artefacts (line-break
hyphenation, ligatures, curly quotes, whitespace, dropped citation brackets) but not
changed words. It prints the matched text exactly as extracted from the PDF.

Text is cached next to the system temp dir so repeated calls are fast.
"""
import argparse
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
PUNCT = {"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"', "–": "-", "—": "-", "‐": "-", "‑": "-",
         "­": "", " ": " "}


def load_pages(pdf):
    pdf = Path(pdf)
    h = hashlib.md5(f"{pdf.resolve()}|{pdf.stat().st_size}|{pdf.stat().st_mtime}".encode()).hexdigest()
    cache = Path(tempfile.gettempdir()) / f"citation_check_{h}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception as e:  # damaged page: keep numbering intact
            pages.append(f"[page could not be extracted: {e}]")
    cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return pages


def normalize_with_map(text):
    """Normalized lowercase word string plus, for every char of it, the index in `text` it came from."""
    out, idx = [], []
    t = text
    i = 0
    prev_space = True
    while i < len(t):
        c = t[i]
        # pypdf often inserts spaces around ligatures: "de ﬁnition", "deﬁ nition" -> "definition"
        if c in " \t" and i > 0 and i + 1 < len(t) and (
                (t[i + 1] in LIGATURES and t[i - 1].isalpha()) or
                (t[i - 1] in LIGATURES and t[i + 1].islower())):
            i += 1
            continue
        # join words hyphenated across a line break: "trans-\nformation" -> "transformation"
        if c in "-‐­" and i > 0 and t[i - 1].isalpha() and re.match(r"[ \t]*\n", t[i + 1:i + 4]):
            j = i + 1
            while j < len(t) and t[j].isspace():
                j += 1
            i = j
            continue
        rep = LIGATURES.get(c) or PUNCT.get(c)
        if rep is None:
            rep = unicodedata.normalize("NFKC", c)
        for r in rep:
            r = r.lower()
            if r.isalnum():
                out.append(r)
                idx.append(i)
                prev_space = False
            elif not prev_space:  # any punctuation/space collapses to a single space
                out.append(" ")
                idx.append(i)
                prev_space = True
        i += 1
    return "".join(out), idx


def build_corpus(pages):
    """Concatenate pages so quotes spanning a page break can still match."""
    full, page_of = [], []
    for n, p in enumerate(pages, 1):
        full.append(p)
        full.append("\n")
        page_of.extend([n] * (len(p) + 1))
    raw = "".join(full)
    norm, idx = normalize_with_map(raw)
    return raw, norm, idx, page_of


def span_info(raw, idx, page_of, a, b):
    s, e = idx[a], idx[min(b, len(idx)) - 1] + 1
    pages = sorted({page_of[s], page_of[e - 1]})
    return re.sub(r"\s+", " ", raw[s:e]).strip(), pages


def cmd_pages(args):
    pages = load_pages(args.pdf)
    lo = args.frm or 1
    hi = args.to or len(pages)
    print(f"# {args.pdf} — {len(pages)} pages")
    if sum(len(p.strip()) for p in pages) < 200 * max(1, len(pages)) * 0.2:
        print("# WARNING: very little extractable text; this may be a scanned PDF. Say so instead of guessing.")
    for n in range(lo, hi + 1):
        print(f"\n===== PDF page {n} =====\n{pages[n - 1]}")


def cmd_search(args):
    pages = load_pages(args.pdf)
    terms = [normalize_with_map(t)[0].strip() for t in args.terms]
    hits = []
    for n, p in enumerate(pages, 1):
        norm, idx = normalize_with_map(p)
        for m in re.finditer(r"[^.!?]+[.!?]?", p.replace("\n", " ")):
            sent = m.group(0).strip()
            sn = normalize_with_map(sent)[0]
            sn_ns = sn.replace(" ", "")  # PDFs without word spaces
            found = [t for t in terms if t and (t in sn or t.replace(" ", "") in sn_ns)]
            if found:
                hits.append((len(found), n, sent, found))
    hits.sort(key=lambda h: (-h[0], h[1]))
    for k, n, sent, found in hits[: args.limit]:
        print(f"[p.{n}] ({k}/{len(terms)}: {', '.join(found)}) {sent}")
    if not hits:
        print("no hits")


def verify(pdf, quote):
    pages = load_pages(pdf)
    raw, norm, idx, page_of = build_corpus(pages)
    q = normalize_with_map(quote)[0].strip()
    if len(q) < 15:
        return {"verdict": "TOO_SHORT", "score": 0, "note": "quote too short to verify meaningfully"}
    pos = norm.find(q)
    if pos >= 0:
        text, pg = span_info(raw, idx, page_of, pos, pos + len(q))
        return {"verdict": "EXACT", "score": 1.0, "pages": pg, "pdf_text": text}
    # Some PDFs store no space characters (words are just positioned apart), so the extracted text reads
    # "digitaltechnologiesfuelnewforms". Compare with all spaces removed: every letter must still match.
    kept = [i for i, ch in enumerate(norm) if ch != " "]
    nospace = "".join(norm[i] for i in kept)
    q_ns = q.replace(" ", "")
    pos = nospace.find(q_ns)
    if pos >= 0:
        text, pg = span_info(raw, idx, page_of, kept[pos], kept[pos + len(q_ns) - 1] + 1)
        # letters are identical, so show the quote's spacing for readability and keep the raw run-on text
        return {"verdict": "NEAR", "score": 1.0, "pages": pg, "pdf_text": re.sub(r"\s+", " ", quote).strip(),
                "pdf_text_raw": text, "note": "matched letter-for-letter ignoring spaces (this PDF's text layer lacks word spaces)"}
    # fuzzy: slide a window of the quote's word length over the document words
    words = norm.split(" ")
    starts, c = [], 0
    for w in words:
        starts.append(c)
        c += len(w) + 1
    qw = q.split(" ")
    L = len(qw)
    best = (0, 0, 0)
    sm = SequenceMatcher(autojunk=False)
    sm.set_seq2(q)
    qset = set(qw)
    for w in range(0, max(1, len(words) - L + 1)):
        window = words[w:w + L]
        if len(qset.intersection(window)) < 0.6 * len(qset):
            continue
        for extra in range(-3, 16):  # PDF side may hold extra citation words
            end = min(len(words), w + L + extra)
            cand = " ".join(words[w:end])
            sm.set_seq1(cand)
            if sm.real_quick_ratio() < best[0] or sm.quick_ratio() < best[0]:
                continue
            r = sm.ratio()
            if r > best[0]:
                best = (r, w, end)
    r, w, end = best
    if r == 0:
        return {"verdict": "NOT_FOUND", "score": 0}
    a = starts[w]
    b = starts[end - 1] + len(words[end - 1])
    text, pg = span_info(raw, idx, page_of, a, b)
    if r < 0.75:
        return {"verdict": "NOT_FOUND", "score": round(r, 3), "closest_pdf_text": text, "pages": pg}
    diffs = word_diffs(qw, words[w:end])
    if not diffs:  # only PDF artefacts / dropped citations differ
        return {"verdict": "NEAR", "score": round(r, 3), "pages": pg, "pdf_text": text}
    return {"verdict": "DIFFERS", "score": round(r, 3), "pages": pg, "closest_pdf_text": text,
            "differences": diffs,
            "note": "The PDF has a similar sentence but the wording differs. Quote the PDF text exactly, "
                    "and check whether the difference changes the meaning."}


def word_diffs(qw, pw):
    """Word-level differences that are NOT mere PDF artefacts.

    Allowed (not reported): a word split/joined differently ("data driven" vs "datadriven"),
    and dropped in-text citation material (names/years/'et al') on either side.
    Anything else — a substituted, added or removed content word — is reported."""
    sm = SequenceMatcher(a=qw, b=pw, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        qa, pb = qw[i1:i2], pw[j1:j2]
        if "".join(qa) == "".join(pb):
            continue
        extra = qa if not pb else pb if not qa else None
        if extra is not None and any(re.fullmatch(r"(19|20)\d\d[a-z]?", x) for x in extra) and \
                all(re.fullmatch(r"(19|20)\d\d[a-z]?|et|al|and|p|pp|\d+|[a-z]+", x) for x in extra) and len(extra) <= 12:
            continue  # a citation like "(Smith et al., 2019)" dropped from one side
        out.append(f"quote: '{' '.join(qa) or '(none)'}'  |  pdf: '{' '.join(pb) or '(none)'}'")
    return out


def cmd_verify(args):
    res = verify(args.pdf, args.quote)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pages"); p.add_argument("pdf"); p.add_argument("--from", dest="frm", type=int); p.add_argument("--to", type=int)
    p.set_defaults(fn=cmd_pages)
    s = sub.add_parser("search"); s.add_argument("pdf"); s.add_argument("terms", nargs="+"); s.add_argument("--limit", type=int, default=25)
    s.set_defaults(fn=cmd_search)
    v = sub.add_parser("verify"); v.add_argument("pdf"); v.add_argument("quote")
    v.set_defaults(fn=cmd_verify)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
