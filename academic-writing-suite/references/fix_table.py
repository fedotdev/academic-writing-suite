"""Post-process: tables full-width + centered; Enter after figure captions.

Usage: python fix_table.py <file.docx>
Modifies the docx in-place:
- tblW→pct 5000, adds tblPr jc=center (pandoc sets tblW=auto which a style cannot override).
- inserts an empty paragraph after a figure caption (pStyle=aff, starts with «Рисунок»)
  so the caption is separated from the following text by an Enter.
"""
import zipfile, sys, os
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
URI = W[1:-1]
ns = {'w': URI}
ET.register_namespace('w', URI)

path = sys.argv[1] if len(sys.argv) > 1 else r'E:\akadem-text_agent\test_gost_v11.docx'
tmp = path + '.fix'

changed = 0
with zipfile.ZipFile(path, 'r') as z:
    entries = {i.filename: z.read(i.filename) for i in z.infolist()}

doc = ET.fromstring(entries['word/document.xml'])
for tbl in doc.findall('.//w:tbl', ns):
    pr = tbl.find('w:tblPr', ns)
    if pr is None:
        pr = ET.fromstring('<w:tblPr xmlns:w="%s"><w:tblW w:type="pct" w:w="5000"/></w:tblPr>' % URI)
        tbl.insert(0, pr)
    # tblW → pct 5000
    tw = pr.find('w:tblW', ns)
    if tw is not None:
        tw.set(W+'type', 'pct')
        tw.set(W+'w', '5000')
    else:
        tw = ET.fromstring('<w:tblW xmlns:w="%s" w:type="pct" w:w="5000"/>' % URI)
        pr.insert(0, tw)
    # jc center
    if pr.find('w:jc', ns) is None:
        jc = ET.fromstring('<w:jc xmlns:w="%s" w:val="center"/>' % URI)
        # insert after tblStyle if present, else at start
        ts = pr.find('w:tblStyle', ns)
        idx = list(pr).index(ts) + 1 if ts is not None else 0
        pr.insert(idx, jc)
    # cell paragraphs → style 12pt («Таблица 12pt»); pandoc sets Compact
    for cell_p in tbl.findall('.//w:tc/w:p', ns):
        pstyle = cell_p.find('w:pPr/w:pStyle', ns)
        if pstyle is None:
            ppr = cell_p.find('w:pPr', ns)
            if ppr is None:
                ppr = ET.fromstring('<w:pPr xmlns:w="%s"/>' % URI)
                cell_p.insert(0, ppr)
            pstyle = ET.fromstring('<w:pStyle xmlns:w="%s" w:val="12pt"/>' % URI)
            ppr.insert(0, pstyle)
        else:
            pstyle.set(W+'val', '12pt')
    changed += 1

# --- empty paragraph (Enter) after figure captions: pStyle=aff, text starts with «Рисунок» ---
body = doc.find('w:body', ns)

def para_text(p):
    return ''.join(t.text or '' for t in p.findall('.//w:t', ns))

empty_para = ET.fromstring('<w:p xmlns:w="%s"/>' % URI)
inserted = 0
for child in list(body):
    if child.tag != W + 'p':
        continue
    pstyle = child.find('w:pPr/w:pStyle', ns)
    sid = pstyle.get(W + 'val') if pstyle is not None else None
    if sid == 'aff' and para_text(child).strip().startswith('Рисунок'):
        siblings = list(body)
        pos = siblings.index(child)
        nxt = siblings[pos + 1] if pos + 1 < len(siblings) else None
        # skip if next is already an empty paragraph
        if nxt is not None and nxt.tag == W + 'p':
            if not para_text(nxt).strip() and nxt.find('w:pPr/w:pStyle', ns) is None:
                continue
        body.insert(pos + 1, empty_para)
        inserted += 1

entries['word/document.xml'] = ET.tostring(doc, encoding='utf-8', xml_declaration=True)
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in entries.items():
        z.writestr(name, data)
os.replace(tmp, path)
print('fixed %d table(s), inserted %d empty paragraph(s) after figure captions in %s' % (changed, inserted, path))
