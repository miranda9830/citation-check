"""Build the Word citation-check report from results.json — and re-verify every quote first.

Usage:
    python build_report.py results.json -o 引用核查报告.docx [--draft draft.docx --annotated-out draft_批注版.docx]

With --draft (a .docx; defaults to results["draft"]), also writes an annotated copy of the draft:
problem citations highlighted and explained in bilingual Word comments (annotate_draft.py).
The original draft is never modified.

Before anything is written, every evidence quote is re-checked against its PDF with
pdftool.verify. A quote that is not EXACT/NEAR is removed from the report and its claim is
downgraded to not_found, with a visible warning. This makes it impossible for an invented
"original sentence" to reach the report, no matter what the model wrote into results.json.

results.json schema:
{
  "draft": "path/to/draft.docx",
  "items": [
    {
      "id": 1,
      "sentence": "full English sentence from the draft",
      "citation": "Vial, 2019",
      "source_pdf": "path/to/pdf" | null,
      "source_title": "title of the matched paper" | null,
      "claims": [
        {
          "claim": "one checkable proposition in the sentence",
          "status": "supported|partial|contradicted|not_found|source_missing",
          "evidence": [{"quote": "sentence copied from the PDF"}],
          "issue_zh": "中文说明：哪里超出了原文（因果/人群/地区/数字/覆盖）",
          "issue_en": "the same explanation in English"
        }
      ],
      "suggested_rewrite": "English rewrite that stays inside the evidence" | "",
      "problem_phrase": "exact substring of `sentence` that is the problem, e.g. 'consistently improves'" | "",
      "sentence_zh": "the exact Chinese translation sentence in a bilingual draft, if any" | "",
      "problem_phrase_zh": "exact substring of `sentence_zh` that is the problem" | "",
      "suggested_rewrite_zh": "Chinese version of the rewrite, same evidence bounds" | ""
    }
  ]
}
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from pdftool import verify  # noqa: E402

STATUS = {
    "supported": ("🟢 有证据支持\nSupported", "C6EFCE"),
    "partial": ("🟡 原文只部分支持\nPartially supported", "FFEB9C"),
    "contradicted": ("🔴 与原文不一致\nContradicted", "FFC7CE"),
    "not_found": ("⚪ 未定位到原文，请自己确认\nNot located — please check", "EDEDED"),
    "source_missing": ("⚫ 找不到这篇文献\nSource PDF missing", "BFBFBF"),
}
ORDER = ["source_missing", "contradicted", "partial", "not_found", "supported"]


def overall(claims, has_pdf):
    if not has_pdf:
        return "source_missing"
    st = [c["status"] for c in claims] or ["not_found"]
    if "contradicted" in st:
        return "contradicted"
    if all(s == "supported" for s in st):
        return "supported"
    if all(s == "not_found" for s in st):
        return "not_found"
    return "partial"


def reverify(results):
    removed = 0
    for it in results["items"]:
        pdf = it.get("source_pdf")
        for c in it.get("claims", []):
            kept = []
            for ev in c.get("evidence", []):
                if not pdf or not Path(pdf).exists():
                    removed += 1
                    continue
                r = verify(pdf, ev["quote"])
                if r["verdict"] in ("EXACT", "NEAR"):
                    ev["pdf_text"] = r["pdf_text"]
                    ev["pages"] = r["pages"]
                    ev["verdict"] = r["verdict"]
                    ev["score"] = r["score"]
                    kept.append(ev)
                else:
                    removed += 1
                    c.setdefault("warnings", []).append(
                        f"⚠ 一条引文未通过逐字比对（相似度 {r.get('score', 0)}），已从报告中移除")
            c["evidence"] = kept
            if not kept and c["status"] in ("supported", "partial", "contradicted"):
                c.setdefault("warnings", []).append("⚠ 没有通过验证的原文证据，状态已降级为“未定位”")
                c["status"] = "not_found"
            if not pdf:
                c["status"] = "source_missing"
        it["overall"] = overall(it.get("claims", []), bool(pdf))
    return removed


def shade(cell, hex_color):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def build(results, out, removed):
    import docx
    from docx.enum.section import WD_ORIENT
    from docx.shared import Pt, Cm, RGBColor

    d = docx.Document()
    sec = d.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, m, Cm(1.5))
    style = d.styles["Normal"]
    style.font.size = Pt(9.5)
    style.font.name = "Calibri"
    style.element.rPr.rFonts.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", "微软雅黑")

    d.add_heading("引用核查报告 Citation Check Report", 0)
    d.add_paragraph(f"草稿 Draft：{results.get('draft', '')}\n生成时间 Generated：{datetime.datetime.now():%Y-%m-%d %H:%M}")
    items = results["items"]
    counts = {k: sum(1 for i in items if i["overall"] == k) for k in ORDER}
    p = d.add_paragraph()
    p.add_run(f"共核查 {len(items)} 条引用 / {len(items)} citations checked：").bold = True
    p.add_run("   ".join(f"{STATUS[k][0].replace(chr(10), ' / ')} {counts[k]}" for k in ORDER if counts[k]))
    note = d.add_paragraph(
        "说明：表中每条“原文原句”都已由脚本在 PDF 中逐字比对确认（EXACT = 完全一致；NEAR = 仅有 PDF 排版差异）。"
        "页码为 PDF 文件的页序，可能与期刊印刷页码不同。⚪ 表示没有找到对应段落，不代表原文不支持，请自己翻原文确认。\n"
        "Note: every source quote below was matched word-for-word against the PDF by script (EXACT = identical; "
        "NEAR = PDF layout differences only). Page numbers follow PDF page order and may differ from printed journal pages. "
        "⚪ means the passage was not located, not that the source disagrees — please check the original yourself.")
    note.runs[0].font.size = Pt(8.5)
    if removed:
        w = d.add_paragraph(f"⚠ 生成报告时有 {removed} 条引文未能在 PDF 中逐字找到，已自动移除，对应条目已降级。"
                            f" / {removed} quote(s) were not found verbatim in the PDF and were removed; affected items were downgraded.")
        w.runs[0].font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    headers = ["#", "草稿句子\nDraft sentence", "引用\nCitation", "逐个论点 → 原文原句（PDF 页码）\nClaims → source quotes (PDF page)",
               "状态\nStatus", "问题说明\nIssue", "建议改写\nSuggested rewrite"]
    widths = [Cm(0.8), Cm(5.2), Cm(2.4), Cm(7.6), Cm(2.4), Cm(4.2), Cm(4.4)]
    t = d.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
        t.rows[0].cells[i].paragraphs[0].runs[0].bold = True
        shade(t.rows[0].cells[i], "D9E1F2")

    for it in sorted(items, key=lambda i: (ORDER.index(i["overall"]), i["id"])):
        row = t.add_row().cells
        row[0].text = str(it["id"])
        row[1].text = it["sentence"]
        row[2].text = it.get("citation", "") + (f"\n{it['source_title']}" if it.get("source_title") else "")
        ev_cell = row[3]
        ev_cell.text = ""
        issues = []
        for n, c in enumerate(it.get("claims", []), 1):
            para = ev_cell.add_paragraph() if n > 1 else ev_cell.paragraphs[0]
            para.add_run(f"{n}. {c['claim']}  [{STATUS[c['status']][0].split(chr(10))[0]}]").bold = True
            for ev in c.get("evidence", []):
                ep = ev_cell.add_paragraph()
                r = ep.add_run(f"“{ev['pdf_text']}” (p.{'-'.join(map(str, ev['pages']))}, {ev['verdict']})")
                r.italic = True
            for w in c.get("warnings", []):
                wp = ev_cell.add_paragraph()
                wr = wp.add_run(w)
                wr.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
            text = "\n".join(x for x in (c.get("issue_zh"), c.get("issue_en")) if x)
            if text:
                issues.append(f"{n}. {text}" if len(it["claims"]) > 1 else text)
        supported = sum(1 for c in it.get("claims", []) if c["status"] == "supported")
        label, color = STATUS[it["overall"]]
        row[4].text = label + (f"\n覆盖 Coverage {supported}/{len(it['claims'])}" if len(it.get("claims", [])) > 1 else "")
        shade(row[4], color)
        row[5].text = "\n".join(issues)
        row[6].text = "\n\n".join(x for x in (it.get("suggested_rewrite"), it.get("suggested_rewrite_zh")) if x)

    for r in t.rows:
        for i, w in enumerate(widths):
            r.cells[i].width = w
    d.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("-o", "--out", default="引用核查报告.docx")
    ap.add_argument("--draft", help="the user's draft .docx (defaults to results['draft']); an annotated copy is written")
    ap.add_argument("--annotated-out")
    args = ap.parse_args()
    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    removed = reverify(results)
    build(results, args.out, removed)
    Path(args.results).with_suffix(".verified.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    c = {k: sum(1 for i in results["items"] if i["overall"] == k) for k in ORDER}
    print(f"report -> {args.out}  | {c}  | quotes removed by verification: {removed}")
    draft = args.draft or results.get("draft")
    if draft and str(draft).lower().endswith(".docx") and Path(draft).exists():
        from annotate_draft import annotate
        out = args.annotated_out or str(Path(args.out).with_name(Path(draft).stem + "_批注版.docx"))
        done, missed = annotate(results, draft, out)
        print(f"annotated draft -> {out} | marked {done} | could not locate in draft: {missed}")


if __name__ == "__main__":
    main()
