#!/usr/bin/env python3
"""Общие утилиты v3: атомарная запись, SHA-256, чтение/запись JSON.

Используется скриптами v3 (init_run.py, artifact_store.py, state_manager.py,
context_pack.py, token_ledger.py) для единообразной работы с артефактами.
Только стандартная библиотека.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def sha256_of_text(text: str) -> str:
    """SHA-256 текста (hex)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_file(path: str | Path) -> str:
    """SHA-256 содержимого файла (hex)."""
    return sha256_of_text(Path(path).read_text(encoding="utf-8"))


def atomic_write(path: str | Path, data: str) -> None:
    """Атомарная запись: write .tmp -> fsync -> rename.

    Контракт §8.1 плана v3: оркестратор не должен принять частично
    записанный файл за успешный артефакт при обрыве вызова.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        # newline="\n": на Windows text-mode по умолчанию пишет \r\n, что
        # ломает канонический LF и sha256-контракт артефактов.
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: str | Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json_atomic(path: str | Path, obj) -> None:
    """Атомарная запись JSON с отступами, ensure_ascii=False."""
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
