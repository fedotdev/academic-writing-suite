#!/usr/bin/env python3
"""
Test the new document_style_validator.py against the updated template.
Generates a test DOCX with pandoc and runs all 5 validation checks.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

# Config
PANDOC = r"C:\Program Files\Pandoc\pandoc.exe"
SUITE_ROOT = Path(r"E:\akadem-text_agent\academic-writing-suite")
TEMPLATE = SUITE_ROOT / "references" / "Normal_GOST-7-32-2017.dotm"
VALIDATOR = SUITE_ROOT / "scripts" / "document_style_validator.py"
TEST_MD = SUITE_ROOT / "outputs" / "test_validation.md"
TEST_DOCX = SUITE_ROOT / "outputs" / "test_validation.docx"

# Ensure outputs dir exists
(SUITE_ROOT / "outputs").mkdir(exist_ok=True)

# Generate test markdown covering all 5 contracts
test_md = """# Эволюция систем управления движением

## От фиксированных блок-участков к подвижному

### Детализация пункта

Текст с инлайн-формулой $I = v \\cdot t$ и выносной:

::: {custom-style="Уравнение"}
$$S = \\frac{v \\cdot t}{3.6} \\qquad (1.1)$$
:::

Рисунок с правильной подписью:

![](E:/akadem-text_agent/academic-writing-suite/references/placeholder.png)

::: {custom-style="caption"}
Рисунок 1.1 — Схема виртуальной сцепки
:::

Таблица с подписью:

::: {custom-style="caption"}
Таблица 1.1 — Сравнение методов
:::

| Метод | Точность |
|-------|----------|
| A     | 95%      |
| B     | 92%      |

::: {custom-style="Структурный элемент обязательный 7.32"}
СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ
:::

::: {custom-style="Нумерованный список без точки"}
ГОСТ 7.32-2017. Отчёт о научно-исследовательской работе.

ГОСТ Р 7.0.100-2018. Библиографическая запись.
:::
"""

print("=" * 70)
print("TEST: document_style_validator.py against updated template")
print("=" * 70)

# Step 1: Write test markdown
print("\n[1/4] Writing test markdown...")
TEST_MD.write_text(test_md, encoding="utf-8")
print(f"   Written: {TEST_MD}")

# Step 2: Run pandoc to generate DOCX
print("\n[2/4] Generating DOCX with pandoc...")
cmd = [
    PANDOC,
    str(TEST_MD),
    "-o", str(TEST_DOCX),
    "--reference-doc=" + str(TEMPLATE),
    # NOTE: NO --number-sections, NO -f markdown-implicit_figures
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"   ERROR: pandoc failed\n{result.stderr}")
    sys.exit(1)
print(f"   Generated: {TEST_DOCX}")

# Step 3: Run validator (DOCX mode)
print("\n[3/4] Running validator (DOCX mode)...")
cmd = [sys.executable, str(VALIDATOR), str(TEST_DOCX)]
result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
print("   STDOUT:", result.stdout)
if result.stderr:
    print("   STDERR:", result.stderr)
docx_exit_code = result.returncode

# Step 4: Run validator (markdown mode)
print("\n[4/4] Running validator (markdown mode)...")
cmd = [sys.executable, str(VALIDATOR), str(TEST_MD), "--md"]
result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
print("   STDOUT:", result.stdout)
if result.stderr:
    print("   STDERR:", result.stderr)
md_exit_code = result.returncode

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"DOCX validation:      {'PASS' if docx_exit_code == 0 else 'FAIL'} (exit code {docx_exit_code})")
print(f"Markdown validation:  {'PASS' if md_exit_code == 0 else 'FAIL'} (exit code {md_exit_code})")

if docx_exit_code == 0 and md_exit_code == 0:
    print("\n✅ All checks passed — contracts enforced correctly")
    sys.exit(0)
else:
    print("\n❌ Some checks failed")
    # Read audit report if exists
    audit_report = TEST_DOCX.parent / "audit-report.md"
    if audit_report.exists():
        print(f"\nAudit report: {audit_report}")
        print("-" * 70)
        print(audit_report.read_text(encoding="utf-8"))
    sys.exit(1)
