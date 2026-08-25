#!/usr/bin/env python3
"""dedupe_sources.py — дедупликация источников по canonical URL и exact-text checksum.

Реализует §5.4 плана v3: на v3 достаточно canonical URL + exact-text sha256
(embedding-семантика НЕ используется — она опасна для нормативных текстов).

canonical_url: нормализация — удалить фрагмент, параметры отслеживания,
выровнять регистр хоста и схему, убрать trailing slash.

Вход: evidence-артефакт (JSON) со списком sources[]. Выход: дедуплицированный
список с сохранением порядка. Только стандартная библиотека.
"""
import argparse
import hashlib
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import v3  # noqa: E402

# Параметры, не влияющие на содержание (отслеживание/служебные).
_DROP_QUERY_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                      "utm_content", "ref", "referrer", "fbclid", "gclid"}


def canonical_url(url: str) -> str:
    """Каноническая форма URL для сравнения источников."""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip().rstrip("/").lower()
    scheme = parsed.scheme.lower() or "http"
    host = (parsed.hostname or "").lower()
    port = ""
    if parsed.port and not (
        (scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)
    ):
        port = f":{parsed.port}"
    path = parsed.path or "/"
    path = path.rstrip("/") or "/"
    query = urllib.parse.urlencode(
        [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
         if k.lower() not in _DROP_QUERY_PARAMS],
        doseq=True,
    )
    qs = f"?{query}" if query else ""
    return f"{scheme}://{host}{port}{path}{qs}"


def dedupe_sources(sources: list[dict]) -> tuple[list[dict], dict]:
    """Дедупликация источников (§5.3 шаг 5).

    Только stdlib, без embeddings. Правило: источник считается дубликатом, если
    его canonical URL уже встречался (одинаковый URL = один источник, независимо
    от заголовка) ЛИБО его текст уже встречался (одинаковый текст на разных
    адресах — тоже дубль). Сохраняется первый по порядку.

    Returns:
        (уникальные источники в порядке появления, статистика)
    """
    seen_url: set = set()
    seen_text: set = set()
    deduped: list[dict] = []
    stats = {"before": len(sources), "after": 0, "removed": 0}
    for src in sources:
        path = (src.get("path") or src.get("url") or "").strip()
        if not path:
            continue
        key_url = canonical_url(path) if path.startswith(("http://", "https://")) else path
        text = (src.get("title") or src.get("excerpt") or src.get("text") or "").strip()
        key_text = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key_url in seen_url or (text and key_text in seen_text):
            stats["removed"] += 1
            continue
        seen_url.add(key_url)
        if text:
            seen_text.add(key_text)
        deduped.append(src)
    stats["after"] = len(deduped)
    return deduped, stats


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="dedupe_sources.py", description=__doc__)
    ap.add_argument("--file", help="путь к evidence-артефакту (JSON) с полем sources")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args(argv)
    if args.selfcheck:
        return selfcheck()
    if not args.file:
        ap.print_help(file=sys.stderr)
        return 2
    data = v3.read_json(args.file)
    if data is None:
        print(f"error: не удалось прочитать {args.file}", file=sys.stderr)
        return 1
    deduped, stats = dedupe_sources(data.get("sources", []))
    v3.write_json_atomic(args.file, {**data, "sources": deduped})
    print(f"dedupe: {stats['before']} -> {stats['after']} (removed {stats['removed']})")
    return 0


def selfcheck() -> int:
    urls = [
        {"path": "https://Example.com/page/", "title": "a"},
        {"path": "https://example.com/page?utm_source=x", "title": "a"},  # тот же canonical
        {"path": "https://example.com/page?utm_campaign=y", "title": "b"},  # тот же URL, др. заголовок
        {"path": "http://example.org/other", "title": "c"},
        {"path": "E:/data/doc.md", "title": "d"},
    ]
    deduped, stats = dedupe_sources(urls)
    after_paths = {s["path"] for s in deduped}
    # Второй и третий URL канонически совпадают с первым -> оба удаляются
    # (одинаковый URL = один источник, независимо от заголовка).
    assert stats["removed"] == 2, f"ожидалось 2 удаления, а было {stats['removed']}"
    assert stats["after"] == 3, f"ожидалось 3 уникальных, а было {stats['after']}"
    assert urls[0]["path"] in after_paths, "первый URL должен остаться"
    assert "utm_source=x" not in " ".join(after_paths), "query-мусор не должен оставаться"

    # одинаковый текст на разных адресах — тоже дубль
    dup_text = [
        {"path": "https://x.org/1", "excerpt": "один и тот же текст"},
        {"path": "https://x.org/2", "excerpt": "один и тот же текст"},
    ]
    _, st2 = dedupe_sources(dup_text)
    assert st2["removed"] == 1, f"text-дедуп: ожидалось 1 удаление, а было {st2['removed']}"
    print(f"self-check OK: de-duplication {stats['before']} -> {stats['after']}, text-дедуп работает")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
