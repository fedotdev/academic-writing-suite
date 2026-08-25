#!/usr/bin/env python3
"""fix_docx_numbering.py — рестарт нумерации списков в DOCX (v1.5.6).

Проблема: пункты div-списков «Нумерованный одноуровневый список» (a7) и
«Нумерованный список без точки» (aa) нумеруются Word'ом непрерывно по всему
документу (первый пункт очередного списка показывает «7)», «15)» вместо «1)»).

Решение: каждая непрерывная группа параграфов одного списочного стиля получает
СВОЙ numId (все numId ссылаются на один и тот же abstractNum формата стиля —
каждый numId ведёт независимый счётчик). Плюс в numbering.xml добавляются
определения numId 28 (a7) и 35 (aa), которые pandoc не переносит из
reference-шаблона (без них стилям вообще не на что ссылаться).

Usage:
    python fix_docx_numbering.py path/to/doc.docx [out.docx]
"""

import re
import sys
import zipfile
import shutil
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[1] / "references" / "Normal_GOST-7-32-2017.dotm"

STYLE_NUMID = {"a7": "28", "aa": "35"}
STYLE_ABS = {"a7": "7", "aa": "10"}

P_PATTERN = re.compile(r"<w:p\b.*?</w:p>", re.S)
PSTYLE_RE = re.compile(r'<w:pStyle w:val="(a7|aa)"\s*/>')
HAS_NUMPR_RE = re.compile(r"<w:numPr>")


def abstract_from_reference(abs_id: str) -> str:
    with zipfile.ZipFile(REFERENCE) as z:
        rnb = z.read("word/numbering.xml").decode("utf-8")
    m = re.search(
        r'<w:abstractNum w:abstractNumId="%s"[^>]*>.*?</w:abstractNum>' % abs_id,
        rnb, re.S,
    )
    if not m:
        raise RuntimeError(f"abstractNum {abs_id} not found in reference")
    return m.group(0)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src

    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        dx = zin.read("word/document.xml").decode("utf-8")
        nb = zin.read("word/numbering.xml").decode("utf-8")
        others = {n: zin.read(n) for n in names
                  if n not in ("word/document.xml", "word/numbering.xml")}

    # 1) abstractNum из reference (если нет в numbering.xml)
    for aid in set(STYLE_ABS.values()):
        if re.search(r'<w:abstractNum w:abstractNumId="%s"' % aid, nb) is None:
            nb = nb.replace("</w:numbering>",
                            abstract_from_reference(aid) + "</w:numbering>")

    # 2) numId 28/35 для самих стилей (если нет)
    for st, numid in STYLE_NUMID.items():
        if re.search(r'<w:num w:numId="%s"' % numid, nb) is None:
            nb = nb.replace("</w:numbering>",
                            f'<w:num w:numId="{numid}">'
                            f'<w:abstractNumId w:val="{STYLE_ABS[st]}"/></w:num>'
                            + "</w:numbering>")

    # 3) in-place: пройти все <w:p>, определить группы a7/aa, заменить
    all_matches = list(P_PATTERN.finditer(dx))
    # info: (start, end, full_match, style|None, has_numpr)
    info = []
    for m in all_matches:
        txt = m.group()
        st = PSTYLE_RE.search(txt)
        has_num = HAS_NUMPR_RE.search(txt) is not None
        info.append((m.start(), m.end(), txt,
                      st.group(1) if st else None, has_num))

    # группы: непрерывные a7/aa-параграфы (разрыв при НЕ-a7/aa параграфе)
    groups = []   # [(style, [(start, end, text)])]
    cur_st, cur_items = None, []
    for start, end, txt, st, has_num in info:
        if st:
            if st != cur_st:
                if cur_items:
                    groups.append((cur_st, cur_items))
                cur_st, cur_items = st, []
            cur_items.append((start, end, txt))
        else:
            if cur_items:
                groups.append((cur_st, cur_items))
                cur_st, cur_items = None, []
    if cur_items:
        groups.append((cur_st, cur_items))

    # 4) замена с конца (чтобы смещения не сдвигались)
    next_numid = 1006
    for st, items in reversed(groups):
        abs_id = STYLE_ABS[st]
        numid = str(next_numid)
        next_numid += 1
        nb = nb.replace("</w:numbering>",
                        f'<w:num w:numId="{numid}">'
                        f'<w:abstractNumId w:val="{abs_id}"/></w:num>'
                        + "</w:numbering>")
        for start, end, old_txt in reversed(items):
            if HAS_NUMPR_RE.search(old_txt):
                continue
            new_txt = re.sub(
                r'(<w:pStyle w:val="(?:a7|aa)"\s*/>)',
                (r'\1<w:numPr><w:ilvl w:val="0"/>'
                 r'<w:numId w:val="%s"/></w:numPr>' % numid),
                old_txt, count=1,
            )
            dx = dx[:start] + new_txt + dx[end:]

    # 5) запись
    tmp = dst.with_name(dst.stem + ".fix.docx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            if n == "word/document.xml":
                zout.writestr(n, dx.encode("utf-8"))
            elif n == "word/numbering.xml":
                zout.writestr(n, nb.encode("utf-8"))
            else:
                zout.writestr(n, others[n])
    shutil.move(tmp, dst)
    print(f"fix_docx_numbering: {len(groups)} групп списков, "
          f"{next_numid - 1006} numId создано -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
