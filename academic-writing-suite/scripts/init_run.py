#!/usr/bin/env python3
"""init_run.py — создаёт изолированный рабочий каталог запуска outputs/<document_id>/.

Для каждого запуска создания главы/статьи/ВКР doc-planner (или оркестратор)
создаёт собственный document_id и вызывает этот скрипт. Всё, что создают
субагенты конвейера, ложится в этот каталог — артефакты никогда не
смешиваются между запусками.

Структура — по §2 плана v3. Только стандартная библиотека.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402


EMPTY_MANIFEST = {
    "schema_version": "1.0",
    "document_id": "",
    "document_type": "",
    "language": "ru",
    "output_path": "",
    "outline": [],
    "terminology": {},
    "numbering": {"figures": "N.M", "tables": "N.M"},
    "context_policy_version": "1.0",
}

EMPTY_STATE = {"run_id": "", "updated_at": "", "sections": {}}


def build_directory(root: Path, document_id: str) -> None:
    """Создаёт дерево каталогов запуска (сам скрипт создаёт родителя)."""
    base = root / document_id
    dirs = [
        "final",
        "evidence",
        "calculations",
        "drafts",
        "sections",
        "cards",
        "reviews",
        "pack",
    ]
    for d in dirs:
        (base / d).mkdir(parents=True, exist_ok=True)


def stamp() -> str:
    return dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="init_run.py",
        description="Создаёт рабочий каталог запуска outputs/<document_id>/.",
    )
    ap.add_argument("--document-id", required=True)
    ap.add_argument("--type", required=True, choices=["chapter", "article", "thesis", "section"])
    ap.add_argument("--language", default="ru")
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args(argv)

    document_id = args.document_id
    base = Path(args.out) / document_id
    base.mkdir(parents=True, exist_ok=True)

    manifest = dict(EMPTY_MANIFEST)
    manifest["document_id"] = document_id
    manifest["document_type"] = args.type
    manifest["language"] = args.language
    manifest["output_path"] = f"outputs/{document_id}/final/{args.type}.md"

    state = dict(EMPTY_STATE)
    state["run_id"] = document_id
    state["updated_at"] = stamp()

    index = {"artifacts": []}

    # Пустые журналы — append-only.
    v3.atomic_write(base / "events.jsonl", "")
    v3.atomic_write(base / "token-ledger.jsonl", "")
    v3.atomic_write(base / "document-plan.md", "")
    v3.atomic_write(base / "figures-todo.md", "")
    v3.atomic_write(base / "tables-todo.md", "")

    v3.write_json_atomic(base / "manifest.json", manifest)
    v3.write_json_atomic(base / "state.json", state)
    v3.write_json_atomic(base / "index.json", index)

    build_directory(base, document_id)

    print(f"run initialized: {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
