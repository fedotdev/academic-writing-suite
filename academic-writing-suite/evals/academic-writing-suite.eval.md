# Eval spec: academic-writing-suite

Бинарные проверки того, что субагенты suite соблюдают контракты. Детерминированные
проверки гоняются кодом (`command`), качественные — через LLM-judge (`llm-judge`,
см. блок `judge`; известная-плохая канарейка обязана проваливать каждый judge-критерий).

Команды command-чеков используют абсолютный путь к `shared/eval_checks.py`
(runner `_run_one` запускает команды из текущей директории процесса, без `cwd`;
универсальный путь ниже верен и для Windows, и для POSIX). При переезде suite
в другую папку замените этот путь.

## Критерии

| id | Текст (что проверяем) | Тип | Команда |
|---|---|---|---|
| no-ai-markers | Текст не содержит типовых AI-маркеров (стоит отметить, важно понимать, данным образом, является, представляет собой) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check no-ai-markers {output}` |
| no-backticks | В тексте нет бэктиков-обрамления идентификаторов (правило идиолекта №1) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check no-backticks {output}` |
| no-rhetorical-question | Зачин раздела — утверждение, не риторический вопрос (правило/кандидат К1) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check no-rhetorical-question {output}` |
| italic-identifiers | Англо-идентификаторы в курсиве, без бэктиков (правило идиолекта №1) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check italic-identifiers {output}` |
| quotes-station | Название станции в кавычках-ёлочках (правило идиолекта №2) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check quotes-station {output}` |
| no-bold-blocks | Внутренние блоки не выделены **жирным** в начале абзаца (правило №3) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check no-bold-blocks {output}` |
| no-heading-literal-number | Заголовки не содержат литеральных номеров в начале (нумерация из стиля .dotm) | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check no-heading-literal-number {output}` |
| figure-placeholder-format | Плейсхолдер рисунка — пустой alt `![](placeholder.png)` + div caption | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check figure-placeholder-format {output}` |
| figure-caption-below | Подпись ПОД рисунком в div `::: {custom-style="caption"}` | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check figure-caption-below {output}` |
| figure-numbering-section | Нумерация рисунков N.M (в пределах раздела): Рисунок 2.1, Рисунок 3.2 | command | `python3 "E:\akadem-text_agent\academic-writing-suite\shared\eval_checks.py" --check figure-numbering-section {output}` |
| cohesion-ok | Текст связный: тезис в начале абзаца, коннекторы на переходах (качество) | llm-judge | — |
| tone-academic | Тон академический, деловой, без обращения к читателю (качество) | llm-judge | — |
| logic-coherence | Логическая связность: тезис→доказательство→вывод замкнуты, нет разрывов рассуждения и голых утверждений (качество) | llm-judge | — |

## Golden cases

| id | split | input | expected | expected_status |
|---|---|---|---|---|
| case-1 | val | golden/case-1/input.txt | golden/case-1/expected.txt | — |
| case-2 | val | golden/case-2/input.txt | golden/case-2/expected.txt | — |
| case-3 | test (holdout) | golden/case-3/input.txt | golden/case-3/expected.txt | — |
| case-4 | val | golden/case-4/input.txt | golden/case-4/expected.txt | — |
| case-5 | val | golden/case-5/input.txt | null | pending-first-green (канарейка не применима; прогон захватит baseline) |
| case-6 | val | golden/case-6/input.txt | golden/case-6/expected.txt | — |
| case-7 | val | golden/case-7/input.txt | null | pending-first-green (logic-reviewer: подраздел с разрывом логики) |
| case-8 | val | golden/case-8/input.txt | null | pending-first-green (logic-reviewer: чистый подраздел без дефектов) |
| case-9 | val | golden/case-9/input.txt | golden/case-9/expected.txt | — (DOCX-контракты: заголовки, рисунки, формулы, список источников) |
| case-9 | val | golden/case-9/input.txt | golden/case-9/expected_bad.txt | fail (литеральный номер в заголовке + alt-текст в рисунке + unicode subscript) |

Judge-критерии (cohesion-ok, tone-academic) с канарейкой: `golden/case-5/canary.txt` —
заведомо плохой текст, должен проваливать оба.

## JSON-блок (машинно-читаемая спецификация для run_evals.py)

```json
{
  "skill": "academic-writing-suite",
  "criteria": [
    {"id": "no-ai-markers", "text": "Текст не содержит типовых AI-маркеров (стоит отметить, важно понимать, данным образом, является, представляет собой)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check no-ai-markers {output}"},
    {"id": "no-backticks", "text": "В тексте нет бэктиков-обрамления идентификаторов (правило идиолекта №1)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check no-backticks {output}"},
    {"id": "no-rhetorical-question", "text": "Зачин раздела — утверждение, не риторический вопрос (правило/кандидат К1)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check no-rhetorical-question {output}"},
    {"id": "italic-identifiers", "text": "Англо-идентификаторы в курсиве, без бэктиков (правило идиолекта №1)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check italic-identifiers {output}"},
    {"id": "quotes-station", "text": "Название станции в кавычках-ёлочках (правило идиолекта №2)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check quotes-station {output}"},
    {"id": "no-bold-blocks", "text": "Внутренние блоки не выделены **жирным** в начале абзаца (правило №3)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check no-bold-blocks {output}"},
    {"id": "no-heading-literal-number", "text": "Заголовки не содержат литеральных номеров (нумерация из многоуровневого списка .dotm)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check no-heading-literal-number {output}"},
    {"id": "figure-placeholder-format", "text": "Плейсхолдер рисунка — изображение с пустым alt: ![](E:/.../placeholder.png)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check figure-placeholder-format {output}"},
    {"id": "figure-caption-below", "text": "Подпись ПОД рисунком в div ::: {custom-style=\"caption\"} с текстом \"Рисунок N.M — Название\"", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check figure-caption-below {output}"},
    {"id": "figure-numbering-section", "text": "Нумерация рисунков N.M (в пределах раздела)", "type": "command", "cmd": "python3 \"E:\\akadem-text_agent\\academic-writing-suite\\shared\\eval_checks.py\" --check figure-numbering-section {output}"},
    {"id": "cohesion-ok", "text": "Текст связный: тезис в начале абзаца, коннекторы на переходах", "type": "llm-judge"},
    {"id": "tone-academic", "text": "Тон академический, деловой, без обращения к читателю", "type": "llm-judge"},
    {"id": "logic-coherence", "text": "Логическая связность: каждый тезис доказан, каждый вывод следует из доказательства, нет разрывов рассуждения, нет голых утверждений без обоснования", "type": "llm-judge"}
  ],
  "judge": {
    "model": "claude-haiku-4-5-20251001",
    "temperature": 0,
    "canary": "golden/case-5/canary.txt"
  },
  "golden": [
    {"id": "case-1", "input": "golden/case-1/input.txt", "expected": "golden/case-1/expected.txt", "split": "val"},
    {"id": "case-2", "input": "golden/case-2/input.txt", "expected": "golden/case-2/expected.txt", "split": "val"},
    {"id": "case-3", "input": "golden/case-3/input.txt", "expected": "golden/case-3/expected.txt", "split": "test"},
    {"id": "case-4", "input": "golden/case-4/input.txt", "expected": "golden/case-4/expected.txt", "split": "val"},
    {"id": "case-5", "input": "golden/case-5/input.txt", "expected": null, "split": "val", "expected_status": "pending-first-green"},
    {"id": "case-6", "input": "golden/case-6/input.txt", "expected": "golden/case-6/expected.txt", "split": "val"},
    {"id": "case-7", "input": "golden/case-7/input.txt", "expected": null, "split": "val", "expected_status": "pending-first-green"},
    {"id": "case-8", "input": "golden/case-8/input.txt", "expected": null, "split": "val", "expected_status": "pending-first-green"},
    {"id": "case-9", "input": "golden/case-9/input.txt", "expected": "golden/case-9/expected.txt", "split": "val"}
  ]
}
```

Примечание: у suite нет детерминированного `run`-конвейера (конвейер написания —
агентный, LLM-шаги; скрипты `shared/` — инструменты субагентов). Поэтому
`run`-поле отсутствует: `run_evals.py --validate` проходит, `--rollout` печатает
"rollout unavailable" и выходит 0. Бейзлайн-чеки по `expected` (варианты автора)
прогоняются обычным `run_evals.py` без `--rollout`.
