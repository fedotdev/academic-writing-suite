#!/usr/bin/env python3
"""Метрики ритма и AI-маркеров для текста раздела.

Используется humanizer-agent'ом: замер доли эм-дешей (порог 3–5%), длин
предложений (ритм: на 6–8 предложений минимум одно короткое ≤10 слов и одно
длинное ≥25 слов) и частот типовых AI-маркеров.

Запуск:
    python3 shared/rhythm_metrics.py <text.txt>
    python3 shared/rhythm_metrics.py --selfcheck

Выход: JSON-объект с метриками.
"""
import json
import re
import sys
from pathlib import Path

AI_MARKERS = [
    "стоит отметить",
    "следует отметить",
    "важно понимать",
    "важно отметить",
    "необходимо отметить",
    "данный",
    "данная",
    "данные",
    "таким образом",
    "в заключение",
    "следует подчеркнуть",
    "нельзя не отметить",
    "является",
    "представляет собой",
]
# ponytail: поиск подстрок без границ слов. «Данный» ложно ловит «данного»,
# «данным», «данными». «Является» ловит «является ли». Это осознанно: в
# академическом тексте любая форма — канцелярит/калька. Если на реальных
# прогонах ложные срабатывания станут частыми, upgrade path: regex с границами
# слов \b + whitelist исключений (например, «является ли» в вопросах).


def split_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения (точка/восклицание/вопросительный знак/
    многоточие + пробел).

    # ponytail: regex-сплиттер ломается на сокращениях «п. 5, пп. «ж»»,
    # «т.е.», «см. выше», номерах разделов «2.1». Для нормативных текстов с
    # такими конструкциями сплиттер даёт ложные разбиения. Upgrade path:
    # заменить на nltk.sent_tokenize("russian") или regex с исключениями
    # сокращений — когда на таких текстах начнёт накапливаться edit-log.
    """
    text = re.sub(r"\n+", " ", text)
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def metrics(text: str) -> dict:
    """Считает метрики ритма и AI-маркеров для текста."""
    sentences = split_sentences(text)
    n = len(sentences)
    em_dash_sents = sum(1 for s in sentences if "—" in s)
    short_sents = sum(1 for s in sentences if len(s.split()) <= 10)
    long_sents = sum(1 for s in sentences if len(s.split()) >= 25)
    lowered = text.lower()
    marker_counts = {m: lowered.count(m) for m in AI_MARKERS}
    return {
        "sentences": n,
        "em_dash_sentences": em_dash_sents,
        "em_dash_share": round(em_dash_sents / n, 4) if n else 0.0,
        "em_dash_threshold_3_5pct_ok": n == 0 or em_dash_sents / n <= 0.05,
        "short_sentences_le10": short_sents,
        "long_sentences_ge25": long_sents,
        "rhythm_ok": n < 6 or (short_sents >= 1 and long_sents >= 1),
        "ai_markers": {k: v for k, v in marker_counts.items() if v},
    }


def demo() -> None:
    """Self-check: ритмичный текст проходит пороги, ровная цепочка — нет."""
    good = ("Интервал сокращается до 4,5 мин. Это важный результат. "
            "При длинной цепочке событий модель демонстрирует устойчивое "
            "поведение при высокой интенсивности движения поездов, что "
            "подтверждает корректность принятых допущений и упрощений. "
            "Данный вывод согласуется с расчётами. Пик смещается вправо.")
    bad = ("Первое предложение этой цепочки имеет среднюю длину. "
           "Второе предложение этой цепочки тоже среднее. "
           "Третье предложение этой цепочки сохраняет ритм. "
           "Четвёртое предложение этой цепочки не нарушает его. "
           "Пятое предложение этой цепочки продолжает ряд. "
           "Шестое предложение этой цепочки завершает абзац.")
    g, b = metrics(good), metrics(bad)
    assert g["rhythm_ok"] and g["em_dash_threshold_3_5pct_ok"], \
        "self-check: качественный текст обязан проходить пороги"
    assert not b["rhythm_ok"], "self-check: ровная цепочка обязана быть помечена"
    assert g["ai_markers"], "self-check: 'данный'/'важно' должны находиться"
    print(f"self-check OK: good rhythm_ok={g['rhythm_ok']}, bad rhythm_ok={b['rhythm_ok']}")


def main(argv: list[str]) -> int:
    if "--selfcheck" in argv or "-t" in argv:
        demo()
        return 0
    if len(argv) < 1:
        print("usage: python3 shared/rhythm_metrics.py <text.txt> | --selfcheck",
              file=sys.stderr)
        return 2
    try:
        text = Path(argv[0]).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: не удалось прочитать файл: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(metrics(text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
