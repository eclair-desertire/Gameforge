---
name: studio
description: Дирижёр полного цикла разработки игры (идея → концепт → GDD → прототип → продакшн → полировка → релиз → live) для Unity, Godot и Unreal. Используй, когда пользователь начинает новую игру, спрашивает «что дальше», «на каком мы этапе», хочет вести проект по этапам или не указал конкретный этап.
---

# GameForge Studio — дирижёр цикла

Ты ведёшь игровой проект по этапам. Состояние живёт в файлах проекта, а не в памяти разговора: `.gameforge/state.md` — источник правды.

## 1. Определи, где мы

1. Есть `.gameforge/state.md`? Прочитай его (поля `engine`, `track`, `stage`, раздел «Следующий шаг»).
2. Нет — это новый проект или проект без GameForge → запусти скилл **gameforge:setup**.
3. Движок не очевиден → `bash "${CLAUDE_PLUGIN_ROOT}/scripts/detect-engine.sh" <путь>`.

## 2. Карта этапов и ворот

| Этап | Скилл | Выход из этапа (ворота) |
|------|-------|--------------------------|
| setup | gameforge:setup | движок и версия определены, CLI/MCP проверены, `.gameforge/` создан |
| concept | gameforge:ideas → gameforge:concept | `concept.md` заполнен, вердикт «делаем» с датой |
| design | gameforge:design | `gdd.md`: 3 столпа, core loop, MVP scope, cut list |
| prototype | gameforge:plan → gameforge:build → gameforge:playtest | core loop играбелен, плейтест записан, решение keep/kill/retune |
| production | gameforge:plan → gameforge:build (циклом) | вертикальный срез, затем контент по `backlog.md` |
| polish | gameforge:polish | juice/аудио/UI, производительность в бюджете платформы |
| release | gameforge:release | сборки прошли чеклист, стор/сабмит готов |
| live | gameforge:live | метрики собираются, план апдейтов, решение iterate/scale/sunset |

### Параллельные потоки (идут через этапы, а не после них)

| Поток | Скилл | Агент | Стартует на |
|-------|-------|-------|-------------|
| Код | gameforge:build | `gameplay-programmer` | prototype |
| QA | gameforge:playtest | `qa-playtester` | prototype (после каждого milestone) |
| Левел-дизайн | gameforge:level-design | `level-designer` | prototype (greybox) → production |
| 3D-арт (Blender, воксели, low-poly) | gameforge:blender, gameforge:voxel | `3d-artist` | vertical slice (в прототипе — только greybox) |
| 2D-арт (пиксель-арт, HD 2D, UI) | gameforge:pixel-art, gameforge:art-2d | `2d-artist` | prototype (палитра и стиль-тест) → vertical slice |
| Эффекты (VFX) | gameforge:vfx | `2d-artist` | prototype (хит/взрыв для feel) → polish |
| Звук | gameforge:audio | `audio-designer` | prototype (2–3 заглушки для feel) → vertical slice |
| Музыка (FL Studio) | gameforge:music | `composer` | vertical slice (лейтмотив) → production |
| Маркетинг | gameforge:marketing | `marketing-lead` | **concept** (хук, гифки), Steam-страница — vertical slice |
| Сборки | gameforge:release | `build-engineer` | prototype (тестовые сборки) |

Задачи всех потоков живут в одном `backlog.md` с префиксом потока (`[code]`, `[qa]`, `[level]`, `[art]`, `[audio]`, `[mkt]`, `[build]`).

**Не перепрыгивай ворота молча.** Если пользователь хочет сразу кодить без концепта — можно (это его проект), но запиши в журнал решений state.md «ворота concept пропущены сознательно» и предупреди об одном главном риске.

**Kill — нормальный исход.** На ворот prototype и live «закрываем» — это успех процесса, а не провал. Предлагай его честно, если данные говорят «нет».

## 3. Треки

- `mobile` — короткий цикл: прототип за дни, ранний тест рынка (CPI/D1), ads+IAP. Опирайся на скиллы `game-trend-skills:*`, если они установлены.
- `pc` — длинный цикл: вертикальный срез, Steam-страница и вишлисты **уже на этапе production** (не в релизе!), демо, фестивали.
- `both` — общее ядро, ветки в release/live.

## 4. Подключаемые чужие скиллы (если установлены)

GameForge — дирижёр: свои этапы + вызов сильных узких скиллов. Проверь список доступных скиллов, вызывай только те, что реально есть; если нет — работай по своим инструкциям.

| Задача | Скилл |
|--------|-------|
| Свой брейншторм с трендами (все треки) | gameforge:ideas |
| Тренды, идеи, оценка идеи (mobile) | `game-trend-skills:scanning-game-trends`, `:brainstorming-game-ideas`, `:evaluating-game-ideas` |
| Бриф для агентов-кодеров | `game-trend-skills:writing-game-agent-briefs` |
| Запуск без бюджета, метрики | `game-trend-skills:launching-on-zero-budget`, `:tracking-game-metrics` |
| Unity: CLI, пакеты, подсистемы | `unity:unity-cli`, `unity:unity-package-management`, `unity:new-unity-project`, `unity:ui`, `unity:create-2d-physics`, `unity:localization`, `unity:optimize-*`, `unity:craft-game-floors` и др. |
| ADR | `claude-code-game-studios:architecture-decision` или шаблон `templates/adr.md` |

Движковые детали — в **gameforge:engine-unity**, **gameforge:engine-godot**, **gameforge:engine-unreal**.

## 5. Роли (субагенты плагина)

Для тяжёлых кусков отдавай работу агентам плагина: `game-designer` (концепт/GDD/баланс), `gameplay-programmer`, `qa-playtester`, `level-designer`, `3d-artist`, `2d-artist`, `audio-designer`, `composer`, `marketing-lead`, `build-engineer` (см. таблицу потоков). Агент получает: путь к проекту, движок, ID задачи из backlog и критерий готовности. Независимые задачи разных потоков (например, `[art]` и `[audio]`) можно отдавать агентам параллельно, если они не трогают одни и те же файлы.

## 6. Память проекта (обязательно)

Правила — скилл **gameforge:project-memory**. Коротко:
- в начале работы опирайся на `context.md` + хвост `history.md` (хук выводит их автоматически, в том числе после сжатия контекста);
- после каждого законченного куска работы — запись в конец `history.md`;
- решения, новые термины, предпочтения пользователя — в `context.md`;
- изменения дизайна — в `gdd.md` + «История изменений» + версия; снимок GDD в `archive/` при смене этапа/milestone.

## 7. После каждого шага

Обнови `.gameforge/state.md`: `stage`, `updated`, отметь ворота, перепиши «Следующий шаг» одной-двумя строками (их показывает хук в начале каждой сессии), добавь строку в «Журнал решений», если что-то решили. При смене этапа — также «Где мы сейчас» в `context.md` и снимок GDD.
