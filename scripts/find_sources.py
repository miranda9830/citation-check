"""Map each cited source (first author + year) to a PDF on disk.

Usage:
    python find_sources.py claims.json -o sources.json [--zotero ~/Zotero] [--folder DIR ...] [--pdf PATH ...]

Lookup order: explicit --pdf files, then the Zotero library (reads a temporary copy of
zotero.sqlite so a running Zotero doesn't lock it), then --folder directories (matched
by author surname + year in the filename or first page). Reference-list titles from
claims.json are used to rank candidates when several match.
Every source ends up as found / ambiguous / missing. Never guess a PDF for a missing source.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def title_overlap(a, b):
    wa, wb = set(norm(a)) - {"the", "a", "of", "and", "in", "on", "for", "to"}, set(norm(b))
    return len(wa & wb) / len(wa) if wa else 0


def zotero_candidates(zdir):
    zdir = Path(zdir).expanduser()
    db = zdir / "zotero.sqlite"
    if not db.exists():
        return []
    tmp = Path(tempfile.gettempdir()) / "citation_check_zotero.sqlite"
    shutil.copyfile(db, tmp)
    con = sqlite3.connect(str(tmp))
    q = """
    SELECT i.itemID,
      (SELECT v.value FROM itemData d JOIN itemDataValues v USING(valueID) JOIN fields f USING(fieldID)
        WHERE d.itemID=i.itemID AND f.fieldName='title'),
      (SELECT v.value FROM itemData d JOIN itemDataValues v USING(valueID) JOIN fields f USING(fieldID)
        WHERE d.itemID=i.itemID AND f.fieldName='date')
    FROM items i
    WHERE i.itemID NOT IN (SELECT itemID FROM itemAttachments)
      AND i.itemID NOT IN (SELECT itemID FROM itemNotes)"""
    trashed = {r[0] for r in con.execute("SELECT itemID FROM deletedItems")}
    out = []
    for item_id, title, date in con.execute(q).fetchall():
        authors = [r[0] for r in con.execute(
            "SELECT cr.lastName FROM itemCreators ic JOIN creators cr USING(creatorID) WHERE ic.itemID=? ORDER BY ic.orderIndex",
            (item_id,))]
        pdfs = []
        for key, path in con.execute(
                "SELECT ai.key, ia.path FROM itemAttachments ia JOIN items ai ON ai.itemID=ia.itemID "
                "WHERE ia.parentItemID=? AND ia.contentType='application/pdf'", (item_id,)):
            if path and path.startswith("storage:"):
                p = zdir / "storage" / key / path[len("storage:"):]
            elif path:
                p = Path(path)
            else:
                continue
            if p.exists():
                pdfs.append(str(p))
        year = (re.search(r"(19|20)\d{2}", date or "") or [None])[0]
        out.append({"title": title, "year": year, "authors": authors, "pdfs": pdfs,
                    "origin": "zotero (in trash)" if item_id in trashed else "zotero"})
    con.close()
    return out


def folder_candidates(folders):
    out = []
    for f in folders:
        for root, _, files in os.walk(Path(f).expanduser()):
            for name in files:
                if name.lower().endswith(".pdf"):
                    out.append({"file": str(Path(root) / name), "name": name})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("claims")
    ap.add_argument("-o", "--out", default="sources.json")
    ap.add_argument("--zotero", default=str(Path.home() / "Zotero"))
    ap.add_argument("--no-zotero", action="store_true")
    ap.add_argument("--folder", action="append", default=[])
    ap.add_argument("--pdf", action="append", default=[], help="explicit PDF files supplied by the user")
    args = ap.parse_args()

    claims = json.loads(Path(args.claims).read_text(encoding="utf-8"))
    refs = claims.get("references", [])
    zot = [] if args.no_zotero else zotero_candidates(args.zotero)
    files = folder_candidates(args.folder) + [{"file": str(Path(p).resolve()), "name": Path(p).name} for p in args.pdf]

    result = {}
    for key in claims["unique_sources"]:
        author, year = key.split("|")
        a_norm = " ".join(norm(author))
        ref_title = next((r["title"] for r in refs
                          if " ".join(norm(r["first_author"])) == a_norm and r["year"].startswith(year)), None)
        cands = []
        for z in zot:
            if z["year"] == year and z["authors"] and " ".join(norm(z["authors"][0])) == a_norm:
                for p in z["pdfs"]:
                    cands.append({"pdf": p, "title": z["title"], "authors": z["authors"], "origin": z["origin"]})
                if not z["pdfs"]:
                    cands.append({"pdf": None, "title": z["title"], "authors": z["authors"], "origin": "zotero (no PDF attached)"})
        for f in files:
            words = norm(f["name"])
            if norm(author) and norm(author)[0] in words and year in f["name"]:
                cands.append({"pdf": f["file"], "title": f["name"], "authors": [author], "origin": "folder"})
        # dedupe: the same paper stored twice (duplicate Zotero items, or Zotero + folder copy)
        cands.sort(key=lambda c: (c["pdf"] is None, "trash" in c["origin"], c["origin"] != "zotero"))
        seen, uniq = set(), []
        for c in cands:
            k = " ".join(norm(re.sub(r"\.pdf$", "", c["title"] or "", flags=re.I)))[:80] if c["origin"] != "folder" else c["pdf"]
            if c["origin"] == "folder" and any(u["pdf"] and os.path.getsize(u["pdf"]) == os.path.getsize(c["pdf"]) for u in uniq):
                continue
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        if ref_title:
            for c in uniq:
                c["title_match"] = round(title_overlap(ref_title, c["title"] or ""), 2)
            uniq.sort(key=lambda c: -c.get("title_match", 0))
        with_pdf = [c for c in uniq if c["pdf"]]
        if not with_pdf:
            status = "missing"
        elif len(with_pdf) == 1 or (ref_title and with_pdf[0].get("title_match", 0) >= 0.6
                                    and (len(with_pdf) == 1 or with_pdf[1].get("title_match", 0) < 0.6)):
            status = "found"
        else:
            status = "ambiguous"
        result[key] = {"status": status, "reference_title": ref_title,
                       "pdf": with_pdf[0]["pdf"] if status == "found" else None, "candidates": uniq}

    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in result.items():
        print(f"[{v['status']:9}] {k:30} {v['pdf'] or ''}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
