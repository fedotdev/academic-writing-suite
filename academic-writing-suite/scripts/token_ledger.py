#!/usr/bin/env python3
"""token_ledger.py — журнал токенов и сводные метрики (§6).

Каждый вызов субагента фиксируется одной строкой append-only в
`token-ledger.jsonl` (§6.1). Оценка токенов — индикатор по символам (не выдаётся
за реальный API usage); если провайдер вернул usage — поля provider_* дополняют.

Файл НЕ подаётся модели как контекст. Метрики §6.2 считает --summary.

Только стандартная библиотека.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402

# Русский текст ~ 0.25–0.3 токена/символ. Стартовая оценка 1/4 (консервативно).
TOKENS_PER_CHAR_IN = 0.25
TOKENS_PER_CHAR_OUT = 0.25


def append_entry(ledger_path: str | Path, entry: dict) -> None:
    entry.setdefault("timestamp", dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"))
    inp = entry.get("input_chars", 0)
    out = entry.get("output_chars", 0)
    entry.setdefault("estimated_input_tokens", int(inp * TOKENS_PER_CHAR_IN))
    entry.setdefault("estimated_output_tokens", int(out * TOKENS_PER_CHAR_OUT))
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def summary(ledger_path: str | Path) -> dict:
    """Метрики §6.2 из token-ledger.jsonl."""
    path = Path(ledger_path)
    if not path.exists():
        return {"error": "no ledger", "entries": 0}
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_agent: dict[str, list[int]] = {}
    cache_hits = 0
    full_retries = 0
    repairs = 0
    for r in rows:
        a = r.get("agent", "?")
        by_agent.setdefault(a, [0, 0])  # input, output
        by_agent[a][0] += r.get("input_chars", 0)
        by_agent[a][1] += r.get("output_chars", 0)
        if r.get("cache_hit"):
            cache_hits += 1
        if r.get("retry_kind") == "full":
            full_retries += 1
        if r.get("retry_kind") == "format_repair":
            repairs += 1
    per_agent = {a: {"input_chars": v[0], "output_chars": v[1]} for a, v in by_agent.items()}
    return {
        "entries": len(rows),
        "sum_input_chars": sum(v[0] for v in by_agent.values()),
        "sum_output_chars": sum(v[1] for v in by_agent.values()),
        "cache_hits": cache_hits,
        "full_retries": full_retries,
        "format_repairs": repairs,
        "per_agent": per_agent,
        "label": "estimated (indicator, не реальный API usage)",
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="token_ledger.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_append = sub.add_parser("append")
    p_append.add_argument("--ledger", required=True)
    p_append.add_argument("--run-id", default="")
    p_append.add_argument("--section", default="")
    p_append.add_argument("--agent", required=True)
    p_append.add_argument("--skill-version", default="")
    p_append.add_argument("--input-chars", type=int, default=0)
    p_append.add_argument("--output-chars", type=int, default=0)
    p_append.add_argument("--cache-hit", action="store_true")
    p_append.add_argument("--retry-kind", default=None)
    p_append.add_argument("--status", default="completed")
    p_append.add_argument("--artifact-refs", nargs="*", default=[])
    p_summary = sub.add_parser("summary")
    p_summary.add_argument("--ledger", required=True)
    p_self = sub.add_parser("selfcheck")
    args = ap.parse_args(argv)

    if args.cmd == "selfcheck":
        return selfcheck()
    if args.cmd == "append":
        entry = {
            "run_id": args.run_id, "section_id": args.section, "agent": args.agent,
            "skill_version": args.skill_version, "input_chars": args.input_chars,
            "output_chars": args.output_chars, "cache_hit": args.cache_hit,
            "retry_kind": args.retry_kind, "status": args.status,
            "artifact_refs": args.artifact_refs,
        }
        append_entry(args.ledger, entry)
        return 0
    if args.cmd == "summary":
        print(json.dumps(summary(args.ledger), ensure_ascii=False, indent=2))
        return 0
    ap.print_help(file=sys.stderr)
    return 2


def selfcheck() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        led = Path(td) / "token-ledger.jsonl"
        append_entry(led, {"run_id": "r", "section_id": "2.1", "agent": "draft-agent",
                           "input_chars": 4000, "output_chars": 800, "cache_hit": False})
        append_entry(led, {"run_id": "r", "section_id": "2.2", "agent": "draft-agent",
                           "input_chars": 4000, "output_chars": 700,
                           "retry_kind": "format_repair"})
        # append-only: повторы не перезаписывают историю
        assert len(led.read_text(encoding="utf-8").splitlines()) == 2
        s = summary(led)
        assert s["entries"] == 2, s
        assert s["per_agent"]["draft-agent"]["input_chars"] == 8000
        assert s["format_repairs"] == 1
        print("self-check OK: append-only журнал, метрики агregируются правильно")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
