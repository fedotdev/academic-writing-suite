# academic-writing-suite

Оркестратор написания разделов ВКР, статей и учебных материалов по
железнодорожной автоматике и телемеханике (СЦБ). Декомпозирует запрос и
вызывает профильных субагентов в нужный момент: doc-planner (планирование
структуры), research-agent (факты и цитаты), calc-agent (расчёты), draft-agent
(черновик по IMRAD в идиолекте автора), humanizer-agent (очеловечивание,
обязательный гейт), norm-control-agent (ссылки и ГОСТ 7.32-2017),
style-calibrator-agent (обучение на правках автора).

## Usage

Invoke this skill with `/academic-writing-suite` or by describing a task that
matches its routing: «напиши раздел N.M», «напиши главу N», «напиши диплом»,
«дополни раздел», «рассчитай X», «проверь на AI-маркеры», «сравни черновик и
мою правку».

## Component Skills

The suite routes to component skills under `skills/`:

- **doc-planner** — «напиши главу N», «напиши диплом» (принимает план или предлагает свой)
- **research-agent** — «собери материал по разделу», «найди данные»
- **calc-agent** — «рассчитай/пересчитай X», «проверь цифру X»
- **draft-agent** — «напиши раздел N.M» (после research/calc)
- **logic-reviewer-agent** — логическая проверка подраздела (после draft, до humanizer)
- **humanizer-agent** — «очеловечь», «убери AI-маркеры», «проверь на AI-маркеры» (→ audit)
- **norm-control-agent** — «проверь раздел перед сдачей»
- **article-polish-agent** — межразделовая согласованность (после сборки полного документа)
- **style-calibrator-agent** — «сравни черновик и мою правку», «обучи агента на моих правках»

## Key Rules

- Факт-замок: числа/даты/имена/ГОСТы не искажаются; нет данных → маркер пробела.
- Иерархия правил: факт-замок → `assets/user-idiolect.md` (≥3/7) → каталог
  humanizer → общие стилевые правила Projects.
- humanizer-agent — финальная инстанция по стилю; norm-control-agent только
  помечает (ссылки, термины, ГОСТ 7.32-2017), не переписывает.
- Промпт делегирования самодостаточен: дословный заголовок, пути файлов, полный
  вывод предыдущего субагента.
- Полный документ: последовательный конвейер по всем разделам без «продолжай»,
  результат в `outputs/`. После сборки — `article-polish-agent` (read-only)
  проверяет межразделовую согласованность. После подтверждения MD — экспорт в
  DOCX через pandoc с шаблоном `references/Normal_GOST-7-32-2017.dotm` (`--reference-doc`),
  затем `scripts/document_style_validator.py` проверяет контракты (заголовки, подписи,
  формулы, список источников).
- Рисунки: плейсхолдер одной строкой с пустым alt (`![](placeholder.png)`), подпись
  в div `::: {custom-style="caption"}` под рисунком, лог в `assets/figures-todo.md`.

## Gotchas

- Субагенты не видят историю диалога — контекст передаётся только текстом в
  промпте делегирования.
- Проверяй полноту выдачи calc-agent (единицы измерения) перед передачей
  следующему шагу; рассинхронизация форматов ломает конвейер.
- Пилотная проверка на 2–3 реальных разделах ВКР перед полным развёртыванием.

## Details

See [SKILL.md](./SKILL.md) for full implementation details, triggers, routing and
configuration. Component instructions live in `skills/<agent>/SKILL.md`.
