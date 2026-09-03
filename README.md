<div align="center">

# academic-writing-suite

**Мультиагентный конвейер для подготовки ВКР, статей и учебных материалов по железнодорожной автоматике и телемеханике (СЦБ)**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Pandoc](https://img.shields.io/badge/Pandoc-DOCX-339933?style=flat-square)](https://pandoc.org/)

[Обзор](#обзор) · [Быстрый старт](#быстрый-старт) · [Использование](#использование) · [Архитектура](#архитектура) · [Проверки](#проверки)

</div>

`academic-writing-suite` — это skill для AI-инструментов, который разбивает академическую задачу на последовательность специализированных этапов. Он помогает собирать факты, выполнять проверяемые расчёты, писать и проверять текст, сохраняя числа, даты, термины и ссылки.

## Возможности

- маршрутизация запроса к нужному субагенту;
- сбор фактов и цитат с привязкой к источникам;
- расчёты только по переданным нормативным методикам;
- черновик раздела по IMRAD в стиле автора;
- логическая проверка до стилистической правки;
- обязательный humanizer-gate для снятия шаблонных AI-конструкций;
- контроль ссылок, терминов и требований ГОСТ 7.32-2017;
- сохранение промежуточных артефактов, контрольных сумм и состояния запуска;
- экспорт подтверждённого Markdown в DOCX через Pandoc и шаблон оформления.

## Быстрый старт

### Требования

- Python 3.11 или новее — скрипты используют стандартную библиотеку;
- AI-инструмент с поддержкой skills/agents: OpenCode, Claude Code, Cursor, Codex или совместимый инструмент;
- Pandoc — только для экспорта в DOCX;
- шаблон `references/Normal_GOST-7-32-2017.dotm` — для оформления DOCX.

### Установка

Из корня репозитория:

```bash
# Автоматически определить доступные платформы
./academic-writing-suite/install.sh

# Установить skill на уровень проекта
./academic-writing-suite/install.sh --project

# Установить во все обнаруженные поддерживаемые инструменты
./academic-writing-suite/install.sh --all
```

Если установщик не подходит, скопируйте каталог `academic-writing-suite/` в каталог skills выбранного инструмента. Например:

| Инструмент | Каталог |
|---|---|
| OpenCode | `~/.config/opencode/skills/academic-writing-suite/` |
| Claude Code | `~/.claude/skills/academic-writing-suite/` |
| Codex / Agents | `~/.agents/skills/academic-writing-suite/` |
| model service | `~/.config/model service/skills/academic-writing-suite/` |

> [!IMPORTANT]
> После установки перезапустите AI-инструмент. Проектные копии в `.opencode/`, `.model service/` и глобальные копии могут существовать одновременно; при расхождениях проверяйте, какая копия используется текущей рабочей директорией.

## Использование

Активируйте skill командой `/academic-writing-suite` или сформулируйте задачу естественным языком:

```text
/academic-writing-suite напиши раздел 2.1.1 «Постановка задачи формализации»
/academic-writing-suite напиши главу 2
/academic-writing-suite проверь текст на AI-маркеры
/academic-writing-suite сравни черновик и мою правку
```

Для отдельного раздела стандартный маршрут выглядит так:

```text
research-agent ──┐
                 ├─> draft-agent -> logic-reviewer-agent
calc-agent   ────┘                         |
                                           v
                              humanizer-agent -> norm-control-agent
```

Расчётный агент запускается параллельно с исследовательским, если в разделе есть формулы или числовые данные. Для полного документа сначала вызывается `doc-planner`, затем каждый подраздел проходит полный маршрут; после сборки выполняется `article-polish-agent`.

## Архитектура

| Субагент | Ответственность |
|---|---|
| `doc-planner` | План главы, статьи или полного документа |
| `research-agent` | Факты, цифры, цитаты и источники |
| `calc-agent` | Проверяемые расчёты по ГОСТ, инструкциям и ПТР |
| `draft-agent` | Черновик раздела и плейсхолдеры рисунков |
| `logic-reviewer-agent` | Проверка связки «тезис → доказательство → вывод» |
| `humanizer-agent` | Стилистическая правка и сохранение фактов |
| `norm-control-agent` | Ссылки, термины и оформление; только помечает проблемы |
| `article-polish-agent` | Согласованность готовых подразделов |
| `style-calibrator-agent` | Извлечение правил из ручных правок автора |

### Основные правила конвейера

1. **Факт-замок.** Числа, даты, имена, проценты и номера нормативных документов не изменяются. Если данных нет, агент возвращает явный пробел вместо догадки.
2. **Иерархия стиля.** Сначала факт-замок, затем подтверждённый `assets/user-idiolect.md`, правила humanizer и общие стилевые правила.
3. **Артефакты прежде ответа.** Промежуточный результат сохраняется в `outputs/<document_id>/`; агент возвращает путь, контрольную сумму и статус.
4. **Узкий контекст.** Следующему агенту передаются релевантные артефакты, а не весь документ целиком.
5. **Финальная проверка.** `humanizer-agent` отвечает за стиль, `norm-control-agent` — за замечания по нормам и ссылкам; они не выполняют одну и ту же работу повторно.

## Структура репозитория

```text
academic-writing-suite/
├── SKILL.md                 # Оркестратор, триггеры и маршрутизация
├── AGENTS.md                # Краткая инструкция для AI-агентов
├── install.sh               # Установщик для поддерживаемых платформ
├── skills/                  # Инструкции девяти субагентов
├── assets/                  # Идиолект, шаблоны рисунков и списки задач
├── references/              # ГОСТ, DOCX-шаблон и служебные скрипты
├── shared/                  # Общие Python-модули без внешних зависимостей
├── scripts/                 # Запуски, артефакты, валидация и evals
├── evals/                   # Спецификация и golden cases
└── outputs/                 # Результаты запусков и отчёты
```

## Артефакты и экспорт

Полный запуск создаёт каталог `outputs/<document_id>/` с манифестом, состоянием, журналом событий, расчётами, черновиками, проверками и итоговым Markdown. Точный состав зависит от маршрута.

После проверки Markdown экспортируйте документ:

```bash
pandoc outputs/<document_id>/final/<document_type>.md \
  -o outputs/<document_id>/final/<document_type>.docx \
  --reference-doc="references/Normal_GOST-7-32-2017.dotm"

python references/fix_table.py outputs/<document_id>/final/<document_type>.docx
python scripts/fix_docx_numbering.py outputs/<document_id>/final/<document_type>.docx
python scripts/document_style_validator.py \
  outputs/<document_id>/final/<document_type>.docx
```

В Markdown используются специальные стили шаблона для структурных элементов, подписей рисунков и таблиц. Нумерация заголовков выполняется шаблоном DOCX, поэтому в начале Markdown-заголовков не следует вручную указывать номера.

## Проверки

```bash
# Проверить спецификацию и контракты
python3 academic-writing-suite/scripts/run_evals.py --validate

# Запустить детерминированные проверки golden cases
python3 academic-writing-suite/scripts/run_evals.py

# Проверить artifact-first, idempotency и форматы артефактов
python3 academic-writing-suite/scripts/test_v3.py

# Проверить актуальность и выполнить основной набор проверок
python3 academic-writing-suite/scripts/evolve.py
```

> [!TIP]
> Перед запуском полного документа протестируйте конвейер на двух-трёх реальных разделах. Это позволяет обнаружить неправильные пути к источникам, ограничения выбранной модели и несоответствия форматов без большого расхода времени.

## Калибровка стиля автора

Калибровка нужна только при обучении suite на новых ручных правках:

```text
draft-agent пишет черновик
        ↓
автор правит текст
        ↓
/academic-writing-suite сравни черновик и мою правку
        ↓
style-calibrator-agent обновляет user-idiolect.md
```

Повторяющиеся правила с подтверждённой частотой попадают в `assets/user-idiolect.md`; единичные кандидаты сохраняются отдельно до подтверждения. Обычному пользователю достаточно уже подготовленных правил идиолекта.

## Полезные файлы

- [`academic-writing-suite/SKILL.md`](academic-writing-suite/SKILL.md) — полная логика оркестратора;
- [`academic-writing-suite/AGENTS.md`](academic-writing-suite/AGENTS.md) — краткая версия правил;
- [`academic-writing-suite/references/GOST_7-32-2017.md`](academic-writing-suite/references/GOST_7-32-2017.md) — требования к оформлению;
- [`academic-writing-suite/references/placeholder.png`](academic-writing-suite/references/placeholder.png) — плейсхолдер рисунка;
- [`academic-writing-suite/scripts/document_style_validator.py`](academic-writing-suite/scripts/document_style_validator.py) — проверка DOCX;
- [`academic-writing-suite/scripts/test_v3.py`](academic-writing-suite/scripts/test_v3.py) — самопроверка artifact-first-конвейера.