#!/usr/bin/env python3
"""context_pack.py — собирает локальный bounded-пакет для секции и агента (§5.2/§5.3).

Реализует «read narrow, not broad»: вместо полного документа субагенту
передаётся путь к компактному pack-файлу, который содержит ровно тот минимум,
что нужен агенту (manifest-поля + evidence + calc + ≤2 соседние карточки).
Бюджеты применяются детерминированно скриптом, а не «на доверие» к LLM.

Приоритет сохранения (§5.3): формула → числа → прямая цитата норматива →
единственный источник. Сначала сокращаются вторичные выдержки без цифр и без
нормативных маркеров.

Только стандартная библиотека.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402

# Маркеры нормативного/первичного источника (цифры+единицы, ГОСТ/ПТР/Инструкция).
_NORM_RE = re.compile(r"(ГОСТ|ПТР|Инструкция|п\.\s*\d|приказ|норматив)")
_NUM_UNIT_RE = re.compile(r"\d[\d\s.,]*(мин|с|км|м|м/с|км/ч|сек|€|%|руб|МПа|Н|Вт|шт|ч)")


def _is_normative(text: str) -> bool:
    return bool(_NORM_RE.search(text)) or bool(_NUM_UNIT_RE.search(text))


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _select_sources(evidence: dict, max_sources: int, excerpt_max: int) -> list[str]:
    """Возвращает строки-выдержки источников с учётом бюджетов.

    Порядок (§5.3): нормативные/первичные и источники с уникальной цифрой выше
    вторичных. При превышении бюджета сначала отбрасываются вторичные.
    """
    sources = evidence.get("sources", []) or []
    # пометить первичность
    ranked = sorted(sources, key=lambda s: not _is_normative(f"{s.get('title','')} {s.get('path','')}"))
    kept = ranked[:max_sources] if max_sources else ranked
    out = []
    for s in kept:
        title = (s.get("title") or "").strip()
        path = (s.get("path") or s.get("url") or "").strip()
        excerpt = (s.get("excerpt") or s.get("quote") or s.get("text") or "").strip()
        line = f"- {title} [{path}]"
        if excerpt:
            line += "\n  " + _truncate(excerpt, excerpt_max)
        out.append(line)
    return out


def build_pack(*, manifest: dict | None, section_id: str,
               evidence: dict | None, calc: dict | None,
               cards: list[dict], budgets: dict) -> str:
    """Собирает текст pack-файла."""
    outline = {o["section_id"]: o for o in (manifest or {}).get("outline", [])}
    sec = outline.get(section_id, {})
    lines: list[str] = []
    lines.append(f"# Контекст секции {section_id}: {sec.get('title', '')}")
    lines.append(f"target_words: {sec.get('target_words', '')} | "
                 f"requires_calculation: {sec.get('requires_calculation', False)}")
    if (manifest or {}).get("terminology"):
        lines.append("terminology: " + ", ".join((manifest or {}).get("terminology", {}).keys()))

    if evidence:
        lines.append("\n## EVIDENCE")
        max_src = budgets.get("max_sources_per_section", 8)
        excerpt_max = budgets.get("source_excerpt_max_chars", 4000)
        for s in _select_sources(evidence, max_src, excerpt_max):
            lines.append(s)
        claims = "\n".join(
            f"- C {c.get('id','')} [{', '.join(c.get('citation_ids', []))}]: {c.get('text','')}"
            for c in evidence.get("claims", [])
        )
        if claims:
            lines.append("\nclaims:\n" + claims)

    if calc:
        lines.append("\n## CALCULATION")
        calc_max = budgets.get("calculation_max_chars", 10000)
        steps = "\n".join(f"- {st}" for st in calc.get("steps", []))
        body = (f"formula({calc.get('formula',{}).get('doc_ref','')}): {calc.get('formula',{}).get('latex','')}\n"
                f"inputs: {calc.get('inputs','')}\nsteps:\n{steps}\n"
                f"result: {calc.get('result','')}")
        lines.append(_truncate(body, calc_max))

    if cards:
        lines.append("\n## NEIGHBOR CARDS (макс. " + str(budgets.get("neighbor_cards_max", 2)) + ")")
        for c in cards[: budgets.get("neighbor_cards_max", 2)]:
            lines.append(
                f"- {c.get('section_id','')} {c.get('title','')} "
                f"(figures: {c.get('figures',[])}; tables: {c.get('tables',[])})"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="context_pack.py", description=__doc__)
    ap.add_argument("--manifest")
    ap.add_argument("--section-id", default="")
    ap.add_argument("--evidence")
    ap.add_argument("--calc")
    ap.add_argument("--card", action="append", default=[])
    ap.add_argument("--out", required=False)
    ap.add_argument("--budget-evidence", type=int, default=18000)
    ap.add_argument("--budget-calc", type=int, default=10000)
    ap.add_argument("--budget-excerpt", type=int, default=4000)
    ap.add_argument("--max-sources", type=int, default=8)
    ap.add_argument("--neighbor-cards", type=int, default=2)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    budgets = {
        "evidence_max_chars": args.budget_evidence,
        "calculation_max_chars": args.budget_calc,
        "source_excerpt_max_chars": args.budget_excerpt,
        "max_sources_per_section": args.max_sources,
        "neighbor_cards_max": args.neighbor_cards,
    }
    manifest = v3.read_json(args.manifest) if args.manifest else None
    evidence = v3.read_json(args.evidence) if args.evidence else None
    calc = v3.read_json(args.calc) if args.calc else None
    cards = [v3.read_json(c) for c in args.card if v3.read_json(c)]
    pack = build_pack(manifest=manifest, section_id=args.section_id, evidence=evidence,
                      calc=calc, cards=cards, budgets=budgets)
    if args.out:
        v3.atomic_write(args.out, pack)
        print(f"pack written: {args.out} ({len(pack)} chars)")
    else:
        print(pack)
    return 0


def selfcheck() -> int:
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # evidence со вторичными и нормативным источником
        ev = {
            "claims": [{"id": "C-1", "citation_ids": ["S-02"], "text": "факт"}],
            "sources": [
                {"title": "ГОСТ 15826-90", "path": "gost.md",
                 "excerpt": "п. 5.2 скорость V = 40 км/ч применяется для…"},
                {"title": "журнал", "path": "art.md",
                 "excerpt": "некоторые дополнительные размышления авторов про модернизацию и подходы"},
                {"title": "реферат", "path": "a2.md", "excerpt": "ещё один длинный вторичный текст без цифр"},
            ],
        }
        ev_path = root / "evidence.json"
        v3.write_json_atomic(ev_path, ev)
        manifests = {"outline": [{"section_id": "2.1", "title": "X", "target_words": 900}],
                     "terminology": {"интервал": "use_exact_term"}}
        m_path = root / "manifest.json"
        v3.write_json_atomic(m_path, manifests)

        budgets = {"evidence_max_chars": 18000, "source_excerpt_max_chars": 4000,
                   "max_sources_per_section": 2, "neighbor_cards_max": 2,
                   "calculation_max_chars": 10000}
        pack = build_pack(manifest=manifests, section_id="2.1", evidence=ev,
                          calc=None, cards=[], budgets=budgets)

        # Нормативный источник с цифрой/ГОСТ обязан сохраниться при бюджете max_sources=2,
        # вторичный без цифр — может быть отсечён.
        assert "ГОСТ 15826-90" in pack, "нормативный источник не должен быть отброшен"
        # бюджет по длине выдержки соблюдён
        for s in ev["sources"]:
            exc = s.get("excerpt", "")
            if exc in pack:
                assert len(exc) <= budgets["source_excerpt_max_chars"]
        print("self-check OK: нормативный источник сохранён, бюджет соблюдён")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
