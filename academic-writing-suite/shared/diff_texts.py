#!/usr/bin/env python3
"""Дифф двух текстов на уровне предложений. Возвращает JSON-список операций.

Используется style-calibrator-agent'ом (шаг 2) для детерминированного сравнения
пары «AI-черновик / ручная правка автора» вместо «сравнения на глаз».

Запуск:
    python3 shared/diff_texts.py <draft.txt> <corrected.txt>

Выход: JSON-массив операций [{"op": "replace|delete|insert",
"before": [предложения...], "after": [предложения...]}].
"""
import difflib
import json
import re
import sys
from pathlib import Path


def split_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения (точка/восклицание/вопросительный знак/
    многоточие + пробел). Сохраняет порядок, отбрасывает пустые фрагменты.

    # ponytail: regex-сплиттер ломается на сокращениях «п. 5, пп. «ж»»,
    # «т.е.», «см. выше», номерах разделов «2.1». Для нормативных текстов с
    # такими конструкциями сплиттер даёт ложные разбиения. Upgrade path:
    # заменить на nltk.sent_tokenize("russian") или regex с исключениями
    # сокращений — когда на таких текстах начнёт накапливаться edit-log.
    """
    text = text.replace("\n", " ")
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def diff_texts(draft: str, corrected: str) -> list[dict]:
    """Возвращает операции difflib между последовательностями предложений.

    ``equal``-операции отбрасываются. Имена полей соответствуют контракту
    style-calibrator-agent: ``op``, ``before``, ``after``.
    """
    a = split_sentences(draft)
    b = split_sentences(corrected)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops.append({"op": tag, "before": a[i1:i2], "after": b[j1:j2]})
    return ops


def demo() -> None:
    """Self-check: небольшой пример, где дифф обязан найти известные правки."""
    draft = "Стоит отметить, что интервал сокращается до 4,5 мин. Это важный результат."
    corrected = "Интервал сокращается до 4,5 мин. Это важный результат."
    ops = diff_texts(draft, corrected)
    assert ops, "self-check: дифф не нашёл ни одной операции"
    replace_ops = [o for o in ops if o["op"] == "replace"]
    assert replace_ops, "self-check: ожидалась replace-операция для удалённого зачина"
    # Первая операция обязана снять хеджирующий зачин «Стоит отметить, что».
    assert "Стоит отметить, что" in replace_ops[0]["before"][0]
    assert replace_ops[0]["after"] == ["Интервал сокращается до 4,5 мин."]
    print(f"self-check OK: {len(ops)} операций, первая — replace зачина")
    print(json.dumps(ops, ensure_ascii=False, indent=2))


def main(argv: list[str]) -> int:
    if "--selfcheck" in argv or "-t" in argv:
        demo()
        return 0
    if len(argv) < 2:
        print(
            "usage: python3 shared/diff_texts.py <draft.txt> <corrected.txt> "
            "| --selfcheck",
            file=sys.stderr,
        )
        return 2
    draft_path, corrected_path = Path(argv[0]), Path(argv[1])
    try:
        draft = draft_path.read_text(encoding="utf-8")
        corrected = corrected_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: не удалось прочитать файлы: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(diff_texts(draft, corrected), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
