#!/usr/bin/env python3
"""Кросс-платформенные command-чеки для eval spec academic-writing-suite.

Заменяет Unix-пайпы (grep/head) в критериях — работает в cmd.exe/PowerShell и
в POSIX-шеллах. Каждая проверка возвращает 0 (прошла) или 1 (провалена).

Запуск:
    python3 shared/eval_checks.py --check <id> <text-file>
    python3 shared/eval_checks.py --selfcheck
"""
import json
import sys
from pathlib import Path

AI_MARKERS = [
    "стоит отметить",
    "следует отметить",
    "важно понимать",
    "важно отметить",
    "необходимо отметить",
    "таким образом",
    "в заключение",
    "следует подчеркнуть",
    "нельзя не отметить",
    "представляет собой",
]

# "данный" (и формы) — слишком частотны в русском; в критерий их не включаем,
# иначе чеки будут ложно падать на любом приличном тексте.


def check_no_ai_markers(text: str) -> bool:
    """Текст не содержит типовых AI-маркеров."""
    lowered = text.lower()
    return not any(m in lowered for m in AI_MARKERS)


def check_no_backticks(text: str) -> bool:
    """Нет бэктиков-обрамления идентификаторов (правило идиолекта №1)."""
    return "`" not in text


def check_no_rhetorical_question(text: str) -> bool:
    """Зачин раздела — утверждение, не риторический вопрос (К1).

    # ponytail: ищет точную фразу «необходим и достаточен?». Другие
    # риторические вопросы не ловятся. Upgrade path: regex `^[^.!?\\n]*\\?\\s*$`
    # на первом непустом предложении файла (пропуск заголовков) — добавить,
    # когда появятся реальные правки зачинов, отличные от этой конкретной
    # фразы.
    """
    return "необходим и достаточен?" not in text


def check_italic_identifiers(text: str) -> bool:
    """Англо-идентификаторы в курсиве (правило идиолекта №1).

    # ponytail: жёстко зашит под `simpy.Resource` и `route_setup_time_s`.
    # Новые идентификаторы не ловятся. Upgrade path: регулярка
    # `(?<!\\*)\\b[a-zA-Z_]\\w*(?:\\.\\w+)+\\b(?!\\*)` — ищет англо-имена без
    # обрамления звёздочками — когда список идентификаторов расширится.
    """
    return ("*simpy.Resource*" in text) or ("*route_setup_time_s*" in text)


def check_quotes_station(text: str) -> bool:
    """Название станции в кавычках-ёлочках (правило идиолекта №2).

    # ponytail: ищет ««Миитовская»». Другие станции/полигоны не ловятся.
    # Upgrade path: regex `«[А-Яа-яЁё\\s-]{2,}»` + набор известных собственных
    # имён из user-idiolect — добавить, когда идиолект расширится.
    """
    return "«Миитовская»" in text


def check_no_bold_blocks(text: str) -> bool:
    """Внутренние блоки не выделены **жирным** в начале абзаца (правило №3)."""
    for line in text.splitlines():
        if line.lstrip().startswith("**"):
            return False
    return True


CHECKS = {
    "no-ai-markers": check_no_ai_markers,
    "no-backticks": check_no_backticks,
    "no-rhetorical-question": check_no_rhetorical_question,
    "italic-identifiers": check_italic_identifiers,
    "quotes-station": check_quotes_station,
    "no-bold-blocks": check_no_bold_blocks,
}


def demo() -> None:
    """Self-check: эталонные правки автора проходят все чеки; заведомо плохой
    текст (канарейка) проваливает маркерные чеки."""
    good = """# Постановка задачи формализации
Прежде чем строить имитационную модель, нужно ответить на вопрос, который часто остаётся без ответа: какой именно объём информации о реальной станции необходим и достаточен для того, чтобы воспроизвести её пропускную способность.

*Выбор объекта моделирования.* Станция «Миитовская» относится к промежуточным однопутным станциям.

*Терминология модели.* В работе приняты определения: *simpy.Resource* — ресурс симуляции, *route_setup_time_s* — время приготовления маршрута."""
    for cid, fn in CHECKS.items():
        assert fn(good), f"self-check: {cid} обязан проходить на эталоне"
    bad = "**Данный** текст — плохой — и ещё — и `simpy`.\nСтоит отметить, что далее всё плохо."
    assert not check_no_ai_markers(bad), "self-check: AI-маркер обязан ловиться"
    assert not check_no_backticks(bad), "self-check: бэктик обязан ловиться"
    assert not check_no_bold_blocks(bad), "self-check: жирный блок обязан ловиться"
    print(f"self-check OK: {len(CHECKS)} чеков, все эталонные проходят")


def main(argv: list[str]) -> int:
    if "--selfcheck" in argv or "-t" in argv:
        demo()
        return 0
    if len(argv) < 3 or "--check" not in argv:
        print(
            "usage: python3 shared/eval_checks.py --check <id> <text-file> "
            "| --selfcheck",
            file=sys.stderr,
        )
        print(f"checks: {', '.join(sorted(CHECKS))}", file=sys.stderr)
        return 2
    idx = argv.index("--check")
    cid = argv[idx + 1]
    text_path = Path(argv[idx + 2])
    if cid not in CHECKS:
        print(f"error: неизвестная проверка '{cid}'", file=sys.stderr)
        return 2
    try:
        text = text_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: не удалось прочитать файл: {exc}", file=sys.stderr)
        return 1
    ok = CHECKS[cid](text)
    if "--json" in argv:
        print(json.dumps({"check": cid, "pass": ok}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
