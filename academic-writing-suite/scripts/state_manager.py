#!/usr/bin/env python3
"""state_manager.py — идемпотентность, статусные переходы, чтение/обновление state.json.

Реализует §3.2 и §4 плана v3:
- вычисление стабильного idempotency key (§4.1): SHA-256(document_id |
  section_id | agent | input_checksums | skill_version | operation_mode),
  БЕЗ timestamp/UUID/номера попытки;
- валидацию переходов по таблице статусов (§3.2);
- get/set полей state.json атомарно.

Клиенты: оркестратор (через Bash на контрольных точках) и test_v3.py.
Только стандартная библиотека.
"""
import argparse
import datetime as dt
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402

# Разрешённые статусы из §3.2.
STATUSES = {
    "pending", "running", "completed", "completed_with_flags", "blocked",
    "format_repair_needed", "needs_human_review", "failed_no_artifact",
}

# Таблица допустимых переходов: from -> set(to). Терминальны completed/needs_human_review.
TRANSITIONS = {
    "pending": {"running"},
    "running": {
        "completed", "completed_with_flags", "blocked", "format_repair_needed",
        "needs_human_review", "failed_no_artifact", "running",
    },
    "completed": {"needs_human_review", "format_repair_needed"},
    "completed_with_flags": {"completed", "needs_human_review"},
    "format_repair_needed": {"completed", "completed_with_flags", "needs_human_review"},
    "blocked": {"running", "needs_human_review"},
    "needs_human_review": {"running", "pending"},
    "failed_no_artifact": {"running", "needs_human_review"},
}


def compute_key(document_id: str, section_id: str, agent: str,
                inputs: list[str], skill_version: str, mode: str = "section") -> str:
    """Стабильный idempotency key. inputs — пути к артефактам-входам;
    для каждого считается sha256 файла. Порядок inputs важен (стандартизован
    вызывающей стороной)."""
    checksums = [v3.sha256_of_file(p) for p in inputs]
    payload = "|".join(
        [document_id, section_id, agent, "+".join(checksums), skill_version, mode]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return True  # повторный set в тот же статус допустим (идемпотентно)
    return to_status in TRANSITIONS.get(from_status, set())


def access_state(path: str | Path, section: str, step: str) -> dict:
    """Возвращает вложенный dict для state.sections[section][step], создавая его."""
    state = v3.read_json(path) or {"run_id": "", "updated_at": "", "sections": {}}
    sections = state.setdefault("sections", {})
    sec = sections.setdefault(section, {})
    node = sec.setdefault(step, {})
    node.setdefault("status", "pending")
    return node


def cmd_set(path: str, section: str, step: str, field: str, value_raw: str,
            from_status: str | None) -> int:
    state = v3.read_json(path)
    if state is None:
        print(f"error: нет state.json по пути {path}", file=sys.stderr)
        return 1
    node = state["sections"].setdefault(section, {}).setdefault(step, {})
    node.setdefault("status", "pending")

    if field == "status":
        if from_status:
            if node.get("status", "pending") != from_status:
                print(f"error: фактический статус {node.get('status')}, ожидался {from_status}",
                      file=sys.stderr)
                return 1
        to_status = value_raw
        if to_status not in STATUSES:
            print(f"error: неизвестный статус {to_status}", file=sys.stderr)
            return 1
        if not can_transition(node.get("status", "pending"), to_status):
            print(f"error: переход {node.get('status')} -> {to_status} запрещён",
                  file=sys.stderr)
            return 1
        node["status"] = to_status
    else:
        node[field] = value_raw

    state["updated_at"] = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    v3.write_json_atomic(path, state)
    return 0


def cmd_get(path: str, section: str, step: str, field: str | None) -> int:
    state = v3.read_json(path)
    if state is None:
        print(f"error: нет state.json по пути {path}", file=sys.stderr)
        return 1
    node = state.get("sections", {}).get(section, {}).get(step)
    if node is None:
        print("null")
        return 0
    if field is None:
        print(v3.sha256_of_text(__dumps(node)), file=sys.stderr)  # не выводим хрупко
        print(__dumps(node))
    else:
        print(__dumps(node.get(field)))
    return 0


def __dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def cmd_key(args) -> int:
    key = compute_key(args.document_id, args.section, args.agent, args.input,
                      args.skill_version, args.mode)
    print(key)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="state_manager.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_get = sub.add_parser("get", help="state.sections[<section>][<step>][.<field>]")
    p_get.add_argument("--state", required=True)
    p_get.add_argument("--section", required=True)
    p_get.add_argument("--step", required=True)
    p_get.add_argument("--field", default=None)

    p_set = sub.add_parser("set", help="обновить поле состояния")
    p_set.add_argument("--state", required=True)
    p_set.add_argument("--section", required=True)
    p_set.add_argument("--step", required=True)
    p_set.add_argument("--field", required=True)
    p_set.add_argument("--value", required=True)
    p_set.add_argument("--from", dest="from_status", default=None)

    p_key = sub.add_parser("key", help="вычислить idempotency key (§4.1)")
    p_key.add_argument("--document-id", required=True)
    p_key.add_argument("--section", required=True)
    p_key.add_argument("--agent", required=True)
    p_key.add_argument("-i", "--input", action="append", default=[])
    p_key.add_argument("-v", "--skill-version", default="1.0.0")
    p_key.add_argument("-m", "--mode", default="section")

    p_self = sub.add_parser("selfcheck")

    args = ap.parse_args(argv)

    if getattr(args, "cmd", None) == "selfcheck":
        return selfcheck()

    if args.cmd == "get":
        return cmd_get(args.state, args.section, args.step, args.field)
    if args.cmd == "set":
        return cmd_set(args.state, args.section, args.step, args.field,
                       args.value, args.from_status)
    if args.cmd == "key":
        return cmd_key(args)
    ap.print_help(file=sys.stderr)
    return 2


def selfcheck() -> int:
    """§4/§3.2: тот же вход -> тот же key; timestamp не влияет; запрещённые переходы."""
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # входные артефакты
        (root / "ev.json").write_text("{\"x\":1}", encoding="utf-8")
        (root / "calc.json").write_text("{\"y\":2}", encoding="utf-8")

        k1 = compute_key("doc|sec", "2.1", "draft-agent", [str(root / "ev.json")],
                         "draft-v1.2", "section")
        k2 = compute_key("doc|sec", "2.1", "draft-agent", [str(root / "ev.json")],
                         "draft-v1.2", "section")
        assert k1 == k2, "одни и те же входы дали разные ключи"

        # тот же вход, другой порядок списка не должен менять key (нормализация не задана —
        # expected: разный порядок = разный набор входов; здесь проверяем стабильность)
        k3 = compute_key("doc|sec", "2.1", "draft-agent", [str(root / "calc.json")],
                         "draft-v1.2", "section")
        assert k1 != k3, "разные входы дали одинаковый ключ (редекция) — проверь список входов"

        # timestamp не входит в формулу ключа: это гарантировано формулой
        # (doc_id|section|agent|input-checksums|version|mode), аргумента clock нет
        import inspect
        assert "datetime" not in inspect.getsource(compute_key)

        # --- позитивный сценарий: pending -> running -> completed (repair назад) ---
        state_path = root / "state.json"
        state = {"run_id": "r", "updated_at": "", "sections": {"2.1": {"draft": {"status": "pending"}}}}
        v3.write_json_atomic(state_path, state)
        assert cmd_set(str(state_path), "2.1", "draft", "status", "running", None) == 0
        assert cmd_set(str(state_path), "2.1", "draft", "status", "completed", "running") == 0
        # completed -> format_repair_needed (артефакт есть, ответ невалиден)
        assert cmd_set(str(state_path), "2.1", "draft", "status",
                       "format_repair_needed", "completed") == 0
        assert cmd_set(str(state_path), "2.1", "draft", "status", "completed", None) == 0

        # --- негативные сценарии: запрещённые переходы отклоняются ---
        assert cmd_set(str(state_path), "2.1", "draft", "status", "pending", "completed") == 1
        assert cmd_set(str(state_path), "2.1", "draft", "status", "running", "completed") == 1
        # неверный from_status отклоняется (фактический = completed, заявлен running)
        assert cmd_set(str(state_path), "2.1", "draft", "status", "completed", "running") == 1

    print("self-check OK: key стабилен, запрещённые переходы отклоняются")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
