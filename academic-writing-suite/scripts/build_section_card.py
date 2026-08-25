#!/usr/bin/env python3
"""build_section_card.py — детерминированная section card без LLM (§3.5).

Карточка секции — не LLM-summary и не пересказ. Собирается из metadata и
проверяемых полей: claims/citation_ids берутся из evidence-артефакта, figures и
tables — regex-сканированием финального markdown секции, terms — из manifest.
Цель: ≤ 2500 символов.

Вход: evidence-артефакт (JSON), финальный markdown секции, manifest.json.
Выход: JSON-карточка в stdout или --out.
Только стандартная библиотека.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402

# Рисунок/таблица N.M внутри секции; ловим и подпись («Рисунок 2.1 —»),
# и отсылку в тексте («на рисунке 2.1 показано»).
_FIG_RE = re.compile(r"[Рр]исун\w*\s+(\d+(?:\.\d+)+)")
_TAB_RE = re.compile(r"[Тт]аблиц\w*\s+(\d+(?:\.\d+)+)")
_TERM_RE = re.compile(r"«([^»]{2,64})»")


def build_card(section_id: str, title: str, evidence: dict | None,
               section_md: str, manifest: dict | None,
               artifact_path: str = "") -> dict:
    claims = []
    for c in (evidence or {}).get("claims", []):
        cites = c.get("citation_ids") or ([c["cite_id"]] if c.get("cite_id") else [])
        claims.append({"id": c.get("id", ""), "citation_ids": cites})

    figures = sorted(set(_FIG_RE.findall(section_md)))
    tables = sorted(set(_TAB_RE.findall(section_md)))

    # термины: сначала из manifest, затем из кавычек-ёлочек в тексте
    terms = list((manifest or {}).get("terminology", {}).keys())
    if not terms:
        terms = sorted(set(_TERM_RE.findall(section_md)))

    payload = {
        "section_id": section_id,
        "title": title,
        "status": "completed",
        "terms_introduced": terms,
        "claims": claims,
        "figures": figures,
        "tables": tables,
        "open_dependencies": [],
        "artifact": artifact_path,
        "checksum": v3.sha256_of_text(section_md),
    }
    return payload


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="build_section_card.py", description=__doc__)
    ap.add_argument("--section-id", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--evidence", help="путь к evidence-артефакту (JSON)")
    ap.add_argument("--section-md", help="путь к финальному markdown секции")
    ap.add_argument("--manifest", help="путь к manifest.json")
    ap.add_argument("--out", help="куда записать карточку (по умолчанию stdout)")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args(argv)
    if args.selfcheck:
        return selfcheck()
    evidence = v3.read_json(args.evidence) if args.evidence else None
    section_md = Path(args.section_md).read_text(encoding="utf-8") if args.section_md else ""
    manifest = v3.read_json(args.manifest) if args.manifest else None
    card = build_card(args.section_id, args.title, evidence, section_md, manifest,
                      artifact_path=args.section_md or "")
    if args.out:
        v3.write_json_atomic(args.out, card)
        print(f"card written: {args.out} ({len(str(card))} chars)")
    else:
        import json
        print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0


def selfcheck() -> int:
    evidence = {
        "claims": [
            {"id": "C-2.1-01", "cite_id": "S-04"},
            {"id": "C-2.1-02", "citation_ids": ["S-01", "S-02"]},
        ]
    }
    md = "На рисунке 2.1 показана схема. Таблица 2.2 — сравнение. Термин «межпоездной интервал»."
    manifest = {"terminology": {"пропускная способность": "use_exact_term"}}
    card = build_card("2.1", "Заголовок", evidence, md, manifest, artifact_path="sections/2.1.md")
    assert card["claims"][0]["citation_ids"] == ["S-04"], "cite_id должен попасть в citation_ids"
    assert card["claims"][1]["citation_ids"] == ["S-01", "S-02"]
    assert card["figures"] == ["2.1"], f"figures: {card['figures']}"
    assert card["tables"] == ["2.2"]
    # термины из manifest имеют приоритет
    assert card["terms_introduced"] == ["пропускная способность"]
    assert len(str(card)) <= 2500, f"карточка превысила лимит: {len(str(card))}"
    print("self-check OK: card собирается из метаданных и regex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
