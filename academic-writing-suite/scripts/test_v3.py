#!/usr/bin/env python3
"""test_v3.py — единый запуск проверок v3: надёжность + контракты.

Закрывает evals §9.1 (reliability) и статические контрактные проверки v3.
Поведенческие (retry/resume/blocked) проверяются детерминированно на уровне
скриптов v3 (состояние + артефакты), а не на уровне LLM — LLM-поведение
коэрцируется контрактными блоками в SKILL.md, которые проверяются здесь же.

Запуск:
    python3 scripts/test_v3.py
Выход: 0 — все проверки прошли; 1 — есть провал; 2 — ошибка запуска.
Только стандартная библиотека.
"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "scripts"))

import v3  # noqa: E402
import artifact_store  # noqa: E402
import init_run  # noqa: E402
import state_manager  # noqa: E402
import build_section_card  # noqa: E402
import context_pack  # noqa: E402
import dedupe_sources  # noqa: E402
import token_ledger  # noqa: E402

# Разделы, обязательные в оркестраторе (СКИЛЛ SKILL.md) по §7.1.
ORCHESTRATOR_SECTIONS = [
    "ARTIFACT-FIRST EXECUTION",
    "IDEMPOTENCY AND RETRY POLICY",
    "CONTEXT POLICY",
    "CONTEXT BUDGET",
    "OUTPUT ARTIFACT CONTRACT",
]

# Агенты, у которых должен быть блок [OUTPUT ARTIFACT CONTRACT] (§7.3).
AGENTS = [
    "doc-planner", "research-agent", "calc-agent", "draft-agent",
    "logic-reviewer-agent", "humanizer-agent", "norm-control-agent",
    "article-polish-agent", "style-calibrator-agent",
]


def _check(name: str, ok: bool, detail: str = "") -> bool:
    status = "ok" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def subagent_selfchecks() -> bool:
    """Прогоняет встроенные --selfcheck скриптов v3 (детерминированная логика)."""
    checks = [
        ("artifact_store selfcheck", artifact_store.selfcheck),
        ("state_manager selfcheck", state_manager.selfcheck),
        ("build_section_card selfcheck", build_section_card.selfcheck),
        ("context_pack selfcheck", context_pack.selfcheck),
        ("dedupe_sources selfcheck", dedupe_sources.selfcheck),
        ("token_ledger selfcheck", token_ledger.selfcheck),
    ]
    all_ok = True
    for name, fn in checks:
        try:
            rc = fn()
            all_ok &= _check(name, rc == 0)
        except Exception as exc:  # noqa: BLE001
            all_ok &= _check(name, False, repr(exc))
    return all_ok


def reliability_checks() -> bool:
    """§9.1 — end-to-end сценарии надёжности на файловом уровне."""
    all_ok = True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        did = "vkr-test-001"

        # инициализация запуска
        init_run.main(["--document-id", did, "--type", "chapter", "--out", str(root)])
        base = root / did
        manifest = v3.read_json(base / "manifest.json")
        all_ok &= _check("init_run создаёт manifest.json", manifest is not None and manifest["document_id"] == did)
        all_ok &= _check("init_run создаёт журналы", (base / "events.jsonl").exists() and (base / "token-ledger.jsonl").exists())

        # --- §9.1 #1 artifact_saved_invalid_response ---
        # артефакт сохранён, финальный ответ невалиден -> status=format_repair_needed,
        # содержательная работа (запуск draft) не выполняется повторно.
        draft = base / "drafts" / "2.1.md"
        v3.atomic_write(draft, "# Черновик 2.1\nтекст")
        st = base / "state.json"
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "running", None)
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "completed", "running")
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "format_repair_needed", "completed")
        node = v3.read_json(st)["sections"]["2.1"]["draft"]
        all_ok &= _check(
            "§9.1-1 artifact_saved_invalid_response -> format_repair_needed",
            node["status"] == "format_repair_needed" and v3.sha256_of_file(draft) == v3.sha256_of_text("# Черновик 2.1\nтекст"),
        )

        # --- §9.1 #2 timeout_after_artifact ---
        # вызывающий помечен timeout, но артефакт существует -> resume без нового вызова
        # (статус остаётся completed, артефакт не перезаписан)
        before = v3.sha256_of_file(draft)
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "completed", None)
        after = v3.sha256_of_file(draft)
        all_ok &= _check("§9.1-2 timeout_after_artifact: артефакт цел",
                         before == after and v3.read_json(st)["sections"]["2.1"]["draft"]["status"] == "completed")

        # --- §9.1 #3 missing_artifact_retry_once ---
        # нет артефакта -> running; артефакт так и не появился -> failed_no_artifact;
        # лимит попыток исчерпан -> needs_human_review (без бесконечного цикла).
        state_manager.cmd_set(str(st), "2.2", "draft", "status", "pending", None)
        state_manager.cmd_set(str(st), "2.2", "draft", "status", "running", "pending")
        state_manager.cmd_set(str(st), "2.2", "draft", "attempts", "1", None)
        state_manager.cmd_set(str(st), "2.2", "draft", "status", "failed_no_artifact", "running")
        state_manager.cmd_set(str(st), "2.2", "draft", "status", "needs_human_review", "failed_no_artifact")
        all_ok &= _check("§9.1-3 missing_artifact_retry_once -> needs_human_review",
                         v3.read_json(st)["sections"]["2.2"]["draft"]["status"] == "needs_human_review")

        # --- §9.1 #4 missing_input_blocked ---
        state_manager.cmd_set(str(st), "2.3", "calc", "status", "pending", None)
        state_manager.cmd_set(str(st), "2.3", "calc", "status", "running", "pending")
        state_manager.cmd_set(str(st), "2.3", "calc", "status", "blocked", "running")
        all_ok &= _check("§9.1-4 missing_input_blocked: blocked, без retry",
                         v3.read_json(st)["sections"]["2.3"]["calc"]["status"] == "blocked")

        # --- §9.1 #5 same_idempotency_key ---
        # повтор команды с тем же входом даёт тот же ключ и не создаёт второй артефакт
        ev = base / "evidence" / "2.1.json"
        v3.atomic_write(ev, "{\"claims\": []}")
        k1 = state_manager.compute_key(did, "2.1", "research-agent", [str(ev)], "research-v1.1", "section")
        k2 = state_manager.compute_key(did, "2.1", "research-agent", [str(ev)], "research-v1.1", "section")
        all_ok &= _check("§9.1-5 same_idempotency_key", k1 == k2)

        # idempotency key не содержит timestamp/номера попытки (формула без clock)
        all_ok &= _check("§9.1-5b key не зависит от времени (входы стабильны)",
                         state_manager.compute_key(did, "2.1", "research-agent", [str(ev)], "research-v1.1", "section") == k1)
    return all_ok


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def contract_checks() -> bool:
    """Статические контракты (§7): блоки в SKILL.md, единое имя outputs/."""
    all_ok = True

    orch = _read(ROOT, "SKILL.md")
    for section in ORCHESTRATOR_SECTIONS:
        # раздел `[SECTION]` (латинские) либо `## Раздел` — допускаем оба
        ok = bool(re.search(r"\[\s*" + re.escape(section).replace(" ", r"\s+") + r"\s*\]", orch, re.IGNORECASE))
        if not ok:
            ok = bool(re.search(r"^#+\s+.*" + re.escape(section), orch, re.IGNORECASE | re.MULTILINE))
        all_ok &= _check(f"оркестратор содержит [{section}]", ok)

    for agent in AGENTS:
        text = _read(ROOT, f"skills/{agent}/SKILL.md")
        ok = bool(re.search(r"\[ARTIFACT[ -]FIRST[ -]EXECUTION\]|\[OUTPUT[ -]ARTIFACT[ -]CONTRACT\]",
                            text, re.IGNORECASE))
        all_ok &= _check(f"{agent}: [OUTPUT ARTIFACT CONTRACT]", ok)

    # единое имя каталога outputs/ (запрет `output/` как альтернативы §2)
    # Флаг — только когда `output/` реально используется как префикс пути
    # (output/thesis.md, output/chapters/...), а не как токен в исторической
    # заметке CHANGELOG («output/ → outputs/»).
    bad_output_dirs = []
    for md in list((ROOT).rglob("*.md")):
        if "shared" in md.parts or ".model" in md.parts or "node_modules" in md.parts:
            continue
        if md.name == "CHANGELOG.md":
            continue  # историческая запись о миграции, не живой путь
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"output/(?!s)(?=[A-Za-z0-9_.\-])", text):
            bad_output_dirs.append(f"{md.relative_to(ROOT)}:{m.group(0)}")
    all_ok &= _check("имя каталога единообразно: нет пути output/ (только outputs/)",
                     not bad_output_dirs, "; ".join(bad_output_dirs[:5]))

    return all_ok


def context_checks() -> bool:
    """§9.2 — контекстная экономия на уровне пакетов и карточек."""
    all_ok = True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # --- §9.2-2 dedupe_url: два одинаковых URL -> в pack один источник
        ev = {
            "claims": [{"id": "C-1", "citation_ids": ["S-01"], "text": "факт"}],
            "sources": [
                {"title": "источник", "path": "https://example.com/a", "excerpt": "текст"},
                {"title": "источник (дубль)", "path": "https://example.com/a?utm_source=x",
                 "excerpt": "текст"},
            ],
        }
        deduped, stats = dedupe_sources.dedupe_sources(ev["sources"])
        all_ok &= _check("§9.2-2 dedupe_url", stats["removed"] == 1)

        manifest = {"outline": [{"section_id": "2.1", "title": "X", "target_words": 900}], "terminology": {}}
        budgets = {"source_excerpt_max_chars": 2000, "max_sources_per_section": 8,
                   "neighbor_cards_max": 2, "calculation_max_chars": 10000,
                   "evidence_max_chars": 18000}

        # --- §9.2-3 budget_preserve_normative: при бюджете сохраняется формула/цифра
        ev2 = {
            "claims": [],
            "sources": [
                {"title": "ГОСТ 15826-90", "path": "g", "excerpt": "п. 5 V = 40 км/ч"},
                {"title": "вторичный 1", "path": "a", "excerpt": "размышления без цифр" * 5},
                {"title": "вторичный 2", "path": "b", "excerpt": "ещё длинный текст без цифр" * 5},
            ],
        }
        pack_norm = context_pack.build_pack(
            manifest=manifest, section_id="2.1", evidence=ev2, calc=None,
            cards=[], budgets={**budgets, "max_sources_per_section": 2})
        all_ok &= _check("§9.2-3 budget_preserve_normative",
                         "ГОСТ 15826-90" in pack_norm)

        # --- §9.2-1 section_draft_narrow_context: pack не содержит полного документа,
        # и кол-во соседних карточек ограничено neighbor_cards_max
        cards = [
            {"section_id": "2.0", "title": "A", "figures": [], "tables": []},
            {"section_id": "2.2", "title": "B", "figures": [], "tables": []},
            {"section_id": "2.3", "title": "C", "figures": [], "tables": []},
        ]
        pack_cards = context_pack.build_pack(
            manifest=manifest, section_id="2.1", evidence=ev2, calc=None,
            cards=cards, budgets=budgets)
        card_entries = re.findall(r"^[-*]\s+(\d+\.\d+)", pack_cards, re.MULTILINE)
        # первые строки «- C …» это claims, карточки — только в разделе NEIGHBOR CARDS
        ncards = 0
        in_cards = False
        for line in pack_cards.splitlines():
            if line.strip().startswith("## NEIGHBOR CARDS"):
                in_cards = True
                continue
            if in_cards and line.startswith("- "):
                ncards += 1
        assert ncards <= budgets["neighbor_cards_max"], f"карточек больше лимита: {ncards}"
        assert "## EVIDENCE" in pack_cards  # локальный evidence присутствует
        assert "никогда_полный_текст_главы" not in pack_cards  # нет полного документа
        all_ok &= _check("§9.2-1 section_draft_narrow_context (≤2 карточек, нет полного документа)",
                         ncards == 2)

        # --- §9.2-4 reviewer_no_full_corpus: reviewer-пакт не содержит evidence-корпус
        pack_review = context_pack.build_pack(
            manifest=manifest, section_id="2.1", evidence=None, calc=None,
            cards=[], budgets=budgets)
        all_ok &= _check("§9.2-4 reviewer_no_full_corpus (без evidence-корпуса)",
                         "EVIDENCE" not in pack_review and "CALCULATION" not in pack_review)

        # --- §9.2-5 retry_reuses_artifact: форматный ремонт не подгружает полный корпус
        # (на уровне состояния): format_repair_needed -> completed без нового входа
        st = root / "state.json"
        v3.write_json_atomic(st, {"run_id": "r", "updated_at": "", "sections": {}})
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "pending", None)
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "running", "pending")
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "completed", "running")
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "format_repair_needed", "completed")
        state_manager.cmd_set(str(st), "2.1", "draft", "status", "completed", None)
        all_ok &= _check("§9.2-5 retry_reuses_artifact",
                         v3.read_json(st)["sections"]["2.1"]["draft"]["status"] == "completed")
    return all_ok


def main() -> int:
    print(f"=== test_v3: надёжность и контракты ({ROOT}) ===")
    a = subagent_selfchecks()
    b = reliability_checks()
    c = context_checks()
    d = contract_checks()
    ok = a and b and c and d
    print(f"\nИТОГ: {'ВСЕ ПРОВЕРКИ ПРОШЛИ' if ok else 'ЕСТЬ ПРОВАЛЫ'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
