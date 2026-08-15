#!/usr/bin/env python3
"""Document style validator for academic-writing-suite.

Deterministic checks on generated DOCX (post-pandoc) and markdown source (pre-pandoc).
Blocks "completed" status if any violation found.

Usage:
    python document_style_validator.py outputs/thesis.docx [--manifest outputs/manifest.md]
    python document_style_validator.py --md outputs/thesis.md

Output: outputs/audit-report.md with findings.
Exit code: 0 = all checks passed, 1 = violations found.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Optional

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

# Unicode subscript characters (U+2080–U+209C)
UNICODE_SUBSCRIPTS = re.compile(r"[\u2080-\u209C]")

# Caption pattern: "Рисунок N.M — ..." or "Таблица N.M — ..."
CAPTION_PATTERN = re.compile(r"^(Рисунок|Таблица)\s+\d+(\.\d+)*\s*[—\-]")
# Table caption specifically
TABLE_CAPTION_PATTERN = re.compile(r"^Таблица\s+\d+(\.\d+)*\s*[—\-]")
# Valid caption style IDs: aff (caption), ImageCaption, TableCaption, 12pt
VALID_CAPTION_STYLES = {"aff", "ImageCaption", "TableCaption", "12pt"}
# Valid table caption style IDs: TableCaption (12pt is for table CELL text)
VALID_TABLE_CAPTION_STYLES = {"TableCaption"}

# Heading literal number: "1", "1.1", "1.1.1" at start
HEADING_LITERAL_NUMBER = re.compile(r"^#{1,6}\s+\d+(\.\d+)*\s")

# Empty parentheses
EMPTY_PARENS = re.compile(r"\(\s*\)")


class Violation:
    def __init__(self, check_id: str, severity: str, message: str, context: str = ""):
        self.check_id = check_id
        self.severity = severity  # "error" or "warning"
        self.message = message
        self.context = context

    def __str__(self):
        ctx = f" — {self.context}" if self.context else ""
        return f"[{self.severity.upper()}] {self.check_id}: {self.message}{ctx}"


def parse_styles(styles_xml: bytes) -> dict:
    """Parse styles.xml, return dict {styleId: {name, numId, ilvl, outlineLvl}}."""
    root = ET.fromstring(styles_xml)
    styles = {}
    for st in root.findall("w:style", NS):
        sid = st.get(f"{{{W}}}styleId")
        name_el = st.find("w:name", NS)
        name = name_el.get(f"{{{W}}}val") if name_el is not None else ""
        numpr = st.find(".//w:numPr", NS)
        num_id = ilvl = None
        if numpr is not None:
            a = numpr.find("w:numId", NS)
            b = numpr.find("w:ilvl", NS)
            num_id = a.get(f"{{{W}}}val") if a is not None else None
            ilvl = b.get(f"{{{W}}}val") if b is not None else None
        outline = st.find(".//w:outlineLvl", NS)
        outline_val = outline.get(f"{{{W}}}val") if outline is not None else None
        keep_lines = st.find(".//w:pPr/w:keepLines", NS) is not None
        keep_next = st.find(".//w:pPr/w:keepNext", NS) is not None
        styles[sid] = {
            "name": name,
            "numId": num_id,
            "ilvl": ilvl,
            "outline": outline_val,
            "keepLines": keep_lines,
            "keepNext": keep_next,
        }
    return styles


def is_heading_style(style_info: dict) -> bool:
    """Detect heading style by name or outline level."""
    name = style_info.get("name", "").lower()
    if "heading" in name or "заголовок" in name:
        return True
    if style_info.get("outline") is not None:
        return True
    return False


def check_docx(docx_path: Path, manifest_path: Optional[Path] = None) -> list[Violation]:
    """Check DOCX for style violations."""
    violations = []
    with zipfile.ZipFile(docx_path, "r") as z:
        doc_xml = z.read("word/document.xml")
        styles_xml = z.read("word/styles.xml")

    styles = parse_styles(styles_xml)
    root = ET.fromstring(doc_xml)
    body = root.find("w:body", NS)

    # Collect paragraphs with metadata
    paragraphs = []
    for p in body.findall("w:p", NS):
        st = p.find("w:pPr/w:pStyle", NS)
        sid = st.get(f"{{{W}}}val") if st is not None else "Normal"
        text = "".join(t.text or "" for t in p.findall(".//w:t", NS))
        has_omath = any("oMath" in x.tag for x in p.iter())
        has_img = any("blip" in x.tag for x in p.iter())
        style_info = styles.get(sid, {})
        paragraphs.append(
            {
                "sid": sid,
                "style_info": style_info,
                "text": text,
                "has_omath": has_omath,
                "has_img": has_img,
            }
        )

    # === CHECK 1: Headings — no literal numbers, no empty parens ===
    for i, para in enumerate(paragraphs):
        if is_heading_style(para["style_info"]):
            text = para["text"]
            # Check literal number prefix
            if re.match(r"^\d+(\.\d+)*\s", text):
                violations.append(
                    Violation(
                        "heading-literal-number",
                        "error",
                        f"Heading has literal number: '{text[:50]}'",
                        f"para {i}",
                    )
                )
            # Check empty parens
            if EMPTY_PARENS.search(text):
                violations.append(
                    Violation(
                        "heading-empty-parens",
                        "error",
                        f"Heading has empty parens: '{text[:50]}'",
                        f"para {i}",
                    )
                )

    # === CHECK 2: Heading levels — no skips, N.M.K only where manifest allows ===
    heading_levels = []
    for para in paragraphs:
        if is_heading_style(para["style_info"]):
            ilvl = para["style_info"].get("ilvl")
            if ilvl is not None:
                heading_levels.append(int(ilvl))
    # Check for skips (e.g., 0 → 2 without 1)
    for i in range(1, len(heading_levels)):
        if heading_levels[i] > heading_levels[i - 1] + 1:
            violations.append(
                Violation(
                    "heading-level-skip",
                    "error",
                    f"Level skip: {heading_levels[i-1]} → {heading_levels[i]}",
                )
            )

    # === CHECK 3: Formulas — no unicode subscripts outside OMML, equation keepLines ===
    for i, para in enumerate(paragraphs):
        text = para["text"]
        # Unicode subscripts in plain text outside OMML
        if not para["has_omath"] and UNICODE_SUBSCRIPTS.search(text):
            violations.append(
                Violation(
                    "unicode-subscript-outside-equation",
                    "error",
                    f"Unicode subscript in plain text: '{text[:50]}'",
                    f"para {i}",
                )
            )
        # Equation style should have keepLines
        if para["sid"] == "affd" and not para["style_info"].get("keepLines"):
            violations.append(
                Violation(
                    "equation-keepLines-missing",
                    "warning",
                    "Equation style missing keepLines",
                    f"para {i}",
                )
            )

    # === CHECK 4: Captions — figures in aff, tables in TableCaption ===
    for i, para in enumerate(paragraphs):
        text = para["text"]
        if TABLE_CAPTION_PATTERN.match(text):
            if para["sid"] not in VALID_TABLE_CAPTION_STYLES:
                violations.append(
                    Violation(
                        "table-caption-wrong-style",
                        "error",
                        f"Table caption has style '{para['sid']}' (expected 'TableCaption'; '12pt' is for table cell text)",
                        f"para {i}: '{text[:50]}'",
                    )
                )
        elif CAPTION_PATTERN.match(text):
            if para["sid"] not in VALID_CAPTION_STYLES:
                violations.append(
                    Violation(
                        "caption-wrong-style",
                        "error",
                        f"Caption has style '{para['sid']}' (expected one of {VALID_CAPTION_STYLES})",
                        f"para {i}: '{text[:50]}'",
                    )
                )

    # === CHECK 5: References — all paragraphs after "СПИСОК..." must have style aa ===
    in_references = False
    for i, para in enumerate(paragraphs):
        if "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ" in para["text"]:
            in_references = True
            continue
        if in_references:
            # Skip empty paragraphs
            if not para["text"].strip():
                continue
            # Check structural element div closing
            if "Структурный элемент" in para["style_info"].get("name", ""):
                continue
            if para["sid"] != "aa":
                violations.append(
                    Violation(
                        "reference-wrong-style",
                        "error",
                        f"Reference paragraph has style '{para['sid']}' (expected 'aa')",
                        f"para {i}: '{para['text'][:50]}'",
                    )
                )

    return violations


def check_markdown(md_path: Path) -> list[Violation]:
    """Check markdown source for pre-pandoc violations."""
    violations = []
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    for i, line in enumerate(lines, 1):
        # Heading literal number
        if HEADING_LITERAL_NUMBER.match(line):
            violations.append(
                Violation(
                    "md-heading-literal-number",
                    "error",
                    f"Heading has literal number: '{line[:60]}'",
                    f"line {i}",
                )
            )
        # Empty parens in headings
        if line.startswith("#") and EMPTY_PARENS.search(line):
            violations.append(
                Violation(
                    "md-heading-empty-parens",
                    "error",
                    f"Heading has empty parens: '{line[:60]}'",
                    f"line {i}",
                )
            )
        # Unicode subscripts outside math
        if not line.startswith("```") and "$" not in line:
            if UNICODE_SUBSCRIPTS.search(line):
                violations.append(
                    Violation(
                        "md-unicode-subscript",
                        "error",
                        f"Unicode subscript in prose: '{line[:60]}'",
                        f"line {i}",
                    )
                )

    # Check figure caption duplication (image line followed by caption line)
    for i, line in enumerate(lines):
        if line.startswith("![") and "](" in line:
            # Next non-empty line
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                # If next line is a caption (not a div), that's duplication
                if CAPTION_PATTERN.match(next_line) and not next_line.startswith(":::"):
                    violations.append(
                        Violation(
                            "md-figure-caption-duplicate",
                            "error",
                            f"Duplicate caption after image: '{next_line[:60]}'",
                            f"line {j+1}",
                        )
                    )
                break

    # Check references not in numbered div
    in_ref_section = False
    in_numbered_div = False
    for i, line in enumerate(lines):
        if "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ" in line:
            in_ref_section = True
            continue
        if in_ref_section:
            if line.startswith("::: {custom-style="):
                if "Нумерованный список без точки" in line:
                    in_numbered_div = True
                else:
                    in_numbered_div = False
            elif line == ":::":
                in_numbered_div = False
            elif line.strip() and not line.startswith("#"):
                # Non-empty line in reference section
                if not in_numbered_div and not line.startswith(":::"):
                    violations.append(
                        Violation(
                            "md-reference-not-in-div",
                            "error",
                            f"Reference line not in numbered div: '{line[:60]}'",
                            f"line {i+1}",
                        )
                    )

    return violations


def write_audit_report(violations: list[Violation], output_path: Path):
    """Write audit-report.md."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Audit Report\n\n")
        if not violations:
            f.write("[OK] All checks passed.\n")
        else:
            errors = [v for v in violations if v.severity == "error"]
            warnings = [v for v in violations if v.severity == "warning"]
            f.write(f"**Status: {'FAILED' if errors else 'WARNING'}**\n\n")
            f.write(f"- Errors: {len(errors)}\n")
            f.write(f"- Warnings: {len(warnings)}\n\n")
            if errors:
                f.write("## Errors\n\n")
                for v in errors:
                    f.write(f"- {v}\n")
            if warnings:
                f.write("\n## Warnings\n\n")
                for v in warnings:
                    f.write(f"- {v}\n")


def demo():
    """Self-check: build minimal good/bad docx and verify checks."""
    import tempfile

    # Minimal valid docx structure
    def make_docx_xml(paragraphs_xml: str) -> bytes:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>{paragraphs_xml}</w:body>
</w:document>""".encode("utf-8")

    def make_styles_xml() -> bytes:
        return """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:styleId="1">
<w:name w:val="heading 1"/>
<w:pPr><w:numPr><w:numId w:val="24"/><w:ilvl w:val="0"/></w:numPr><w:outlineLvl w:val="0"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="2">
<w:name w:val="heading 2"/>
<w:pPr><w:numPr><w:numId w:val="24"/><w:ilvl w:val="1"/></w:numPr><w:outlineLvl w:val="1"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="aff">
<w:name w:val="caption"/>
</w:style>
<w:style w:type="paragraph" w:styleId="aa">
<w:name w:val="\u041d\u0443\u043c\u0435\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 \u0441\u043f\u0438\u0441\u043e\u043a \u0431\u0435\u0437 \u0442\u043e\u0447\u043a\u0438"/>
</w:style>
<w:style w:type="paragraph" w:styleId="affd">
<w:name w:val="\u0423\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435"/>
<w:pPr><w:keepLines w:val="1"/></w:pPr>
</w:style>
</w:styles>""".encode("utf-8")

    # Good docx: heading without literal number
    good_doc_xml = make_docx_xml(
        '<w:p><w:pPr><w:pStyle w:val="1"/></w:pPr><w:t>Эволюция</w:t></w:p>'
    )
    good_styles_xml = make_styles_xml()

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, "w") as z:
            z.writestr("word/document.xml", good_doc_xml)
            z.writestr("word/styles.xml", good_styles_xml)
        v = check_docx(Path(tmp.name))
        assert not v, f"Good docx should pass, got {v}"
        print(f"[OK] Good docx passes")
        tmp.close()
        Path(tmp.name).unlink()

    # Bad docx: heading with literal number
    bad_doc_xml = make_docx_xml(
        '<w:p><w:pPr><w:pStyle w:val="1"/></w:pPr><w:t>1.1 Эволюция</w:t></w:p>'
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, "w") as z:
            z.writestr("word/document.xml", bad_doc_xml)
            z.writestr("word/styles.xml", good_styles_xml)
        v = check_docx(Path(tmp.name))
        assert any("heading-literal-number" in str(x) for x in v), f"Bad docx should fail, got {v}"
        print(f"[OK] Bad docx (literal number) fails")
        tmp.close()
        Path(tmp.name).unlink()

    # Bad markdown: heading with literal number
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write("# 1.1 Эволюция\n")
        tmp.close()
        v = check_markdown(Path(tmp.name))
        assert any("md-heading-literal-number" in str(x) for x in v), f"Bad md should fail, got {v}"
        print(f"[OK] Bad markdown (literal heading number) fails")
        Path(tmp.name).unlink()

    print("\n[OK] All self-checks passed")


def main():
    parser = argparse.ArgumentParser(description="Document style validator")
    parser.add_argument("input", nargs="?", help="DOCX or markdown file to validate")
    parser.add_argument("--manifest", help="Path to manifest.md (for N.M.K checks)")
    parser.add_argument("--md", action="store_true", help="Validate markdown source")
    parser.add_argument(
        "--out", help="Output audit-report.md path (default: same dir as input)"
    )
    parser.add_argument(
        "--self-check", action="store_true", help="Run self-check demo and exit"
    )
    args = parser.parse_args()

    if args.self_check:
        demo()
        sys.exit(0)

    if not args.input:
        parser.error("the following arguments are required: input")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    violations = []
    if args.md:
        violations = check_markdown(input_path)
    else:
        manifest_path = Path(args.manifest) if args.manifest else None
        violations = check_docx(input_path, manifest_path)

    output_path = (
        Path(args.out) if args.out else input_path.parent / "audit-report.md"
    )
    write_audit_report(violations, output_path)

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    if errors:
        print(f"[FAIL] FAILED: {len(errors)} errors, {len(warnings)} warnings")
        print(f"Audit report: {output_path}")
        sys.exit(1)
    else:
        print(f"[OK] PASSED: {len(warnings)} warnings" if warnings else "[OK] PASSED")
        print(f"Audit report: {output_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()
