"""Post-process: make all tables full-width + centered.

Usage: python fix_table.py <file.docx>
Modifies the docx in-place: tblW→pct 5000, adds tblPr jc=center.
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
    changed += 1

entries['word/document.xml'] = ET.tostring(doc, encoding='utf-8', xml_declaration=True)
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in entries.items():
        z.writestr(name, data)
os.replace(tmp, path)
print('fixed %d table(s) in %s' % (changed, path))
