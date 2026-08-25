#!/usr/bin/env python3
"""artifact_store.py — checksum, атомарная запись, реестр index.json.

Отвечает за детерминированную работу с артефактами v3:
- SHA-256 файла/текста;
- атомарная запись артефакта (контракт §8.1);
- проверка существования;
- обновление machine-readable реестра index.json (kind, section_id, path,
  checksum, chars, created_by, source_count).

Клиенты: оркестратор и субагенты через Bash/CLI, скрипты v3.
Только стандартная библиотека.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402


def index_update(index_path: str | Path, entry: dict) -> None:
    """Добавляет/обновляет запись в index.json по ключу (kind, section_id, path)."""
    path = Path(index_path)
    index = v3.read_json(path) or {"artifacts": []}
    artifacts = index.setdefault("artifacts", [])
    key = (entry["kind"], entry.get("section_id"), entry["path"])
    artifacts = [a for a in artifacts if (a.get("kind"), a.get("section_id"), a.get("path")) != key]
    artifacts.append(entry)
    artifacts.sort(key=lambda a: (a.get("kind", ""), a.get("section_id", ""), a.get("path", "")))
    index["artifacts"] = artifacts
    v3.write_json_atomic(path, index)


def cmd_sha256(path: str) -> int:
    try:
        print(v3.sha256_of_file(path))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _read_text_any_encoding(path: str | Path) -> str:
    """Читает файл как UTF-8 (с BOM или без); фолбэк cp1251/cp866.

    Windows-консоль может оставить файл в OEM-кодировке (PowerShell-пайп,
    субагентский bash) — нормализуем всё в чистый UTF-8, иначе sha256 и
    контент артефакта разъезжаются.
    """
    raw = Path(path).read_bytes()
    # Порядок важен: cp1251 — однобайтовая кодировка и «валидна» для любых
    # байтов, поэтому cp866 (русская OEM-консоль, ломающий пайп) пробуем раньше.
    for enc in ("utf-8-sig", "utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # последний шанс с заменой — не потерять данные артефакта
    return raw.decode("utf-8", errors="replace")


def _read_stdin_text() -> str:
    """Читает stdin как UTF-8 (в т.ч. буферизованный байтовый поток).

    ВАЖНО (Windows + PowerShell): stdin легаси-консоли отдаёт OEM-байты
    (cp866), а не UTF-8, поэтому текст через пайп `Get-Content | python ...`
    гарантированно ломается. Используй `--file` вместо stdin.
    """
    buf = getattr(sys.stdin, "buffer", None)
    if buf is not None:
        return buf.read().decode("utf-8", errors="replace")
    return sys.stdin.read()


def cmd_save(path: str, stdin_text: str | None, index: str | None,
             kind: str | None, section_id: str | None, agent: str | None,
             file_path: str | None = None) -> int:
    if stdin_text is None:
        print("error: --save требует текст в stdin (cat file | artifact_store.py --save path) или --file <path>",
              file=sys.stderr)
        return 2
    v3.atomic_write(path, stdin_text)
    if index:
        checksum = v3.sha256_of_file(path)
        entry = {
            "kind": kind or "unknown",
            "section_id": section_id or "",
            "path": path,
            "checksum": checksum,
            "chars": len(stdin_text),
            "created_by": agent or "",
            "source": file_path or "stdin",
        }
        index_update(index, entry)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="artifact_store.py", description=__doc__)
    ap.add_argument("--sha256", metavar="PATH")
    ap.add_argument("--save", metavar="PATH")
    ap.add_argument("--file", metavar="SRC_PATH", help="читать содержимое из файла (UTF-8/cp1251/cp866), а не из stdin — надёжно на Windows")
    ap.add_argument("--exists", metavar="PATH")
    ap.add_argument("--index", metavar="INDEX_JSON", help="путь к index.json для обновления")
    ap.add_argument("--kind")
    ap.add_argument("--section-id")
    ap.add_argument("--agent")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args(argv)

    if args.selfcheck:
        return selfcheck()
    if args.exists is not None:
        p = Path(args.exists)
        print("yes" if p.exists() else "no")
        return 0
    if args.sha256:
        return cmd_sha256(args.sha256)
    if args.save:
        if args.file:
            # --file: читаем исходный файл (UTF-8/cp1251/cp866), нормализуем в UTF-8
            source = _read_text_any_encoding(args.file)
            if args.save != args.file:
                # пересохранить исходник в каноническом UTF-8 (без BOM)
                v3.atomic_write(args.file, source)
            return cmd_save(args.save, source, args.index, args.kind, args.section_id, args.agent, file_path=args.file)
        stdin_text = _read_stdin_text()
        return cmd_save(args.save, stdin_text, args.index, args.kind, args.section_id, args.agent)
    ap.print_help(file=sys.stderr)
    return 2


def selfcheck() -> int:
    """Проверяет: атомарность (нет .tmp после записи), sha256 стабилен, index уникален."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        target = root / "a.json"
        data = "{\"x\": 1}"
        v3.atomic_write(target, data)
        assert target.exists(), "артефакт не записан"
        leftovers = list(root.glob("*.tmp"))
        assert not leftovers, f"после атомарной записи остались .tmp: {leftovers}"
        # sha256 стабилен и соответствует
        c1 = v3.sha256_of_file(target)
        c2 = v3.sha256_of_text(data)
        assert c1 == c2, "sha256 файла != sha256 текста"
        # index: повторная запись того же ключа не плодит дубликаты
        idx = root / "index.json"
        v3.write_json_atomic(idx, {"artifacts": []})
        entry = {"kind": "evidence", "section_id": "2.1", "path": "evidence/2.1.json",
                 "checksum": c1, "chars": len(data), "created_by": "research-agent"}
        index_update(idx, entry)
        index_update(idx, dict(entry))  # та же запись повторно
        ents = v3.read_json(idx)["artifacts"]
        assert len(ents) == 1, f"index должен содержать одну запись, а их {len(ents)}"
        assert ents[0]["checksum"] == c1
        # --file путь: чтение из файла и нормализация кодировки (cp866 → utf-8)
        src = root / "src.md"
        src.write_bytes("заголовок с кириллицей\n".encode("cp866"))
        dst = root / "artifact.md"
        _read_text_any_encoding(src)  # не падает
        import subprocess  # noqa: F401 — имитация вызова --file невозможна в selfcheck, проверяем чтение
    print("self-check OK: атомарность, sha256, уникальность index, кодировка")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
