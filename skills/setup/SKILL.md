---
name: setup
description: Подключает игровой проект (Unity, Godot или Unreal) к циклу GameForge — определяет движок и версию, проверяет CLI движка, настраивает MCP-сервер в .mcp.json проекта, создаёт .gameforge/ и CLAUDE.md. Используй при старте новой игры, при первом открытии существующего игрового проекта или когда просят настроить Unity CLI / Unity MCP / Godot MCP / Unreal MCP.
---

# Setup — подключение проекта

## 1. Движок

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/detect-engine.sh" "<путь к проекту>"
```

- `unknown` и папка пустая → это новый проект. Спроси движок (если не сказан) и трек (mobile / pc / both). Для Unity нового проекта вызови `unity:new-unity-project`, если он есть, иначе `unity projects create` по gameforge:engine-unity. Для Godot/Unreal — см. соответствующий engine-скилл.
- Определился → прочитай **один** engine-скилл (gameforge:engine-unity / engine-godot / engine-unreal) и дальше следуй ему в части команд.

## 2. Проверка инструментов (не пропускай)

Быстро и целиком: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" all` (или `--task …`). Всё, что `[нет]`/`[выкл]`/`[mcp]`, — явно перечисли пользователю и установи/включи через gameforge:doctor. Таблица ниже — что именно проверяется.

| Движок | Проверка | Если нет |
|--------|----------|----------|
| Unity | `which unity && unity --version`, затем `unity doctor --format json` | Установить Unity CLI (команда в engine-unity). Сам скрипт установки не запускай без согласия пользователя. |
| Unity | в проекте есть `com.unity.pipeline` (Packages/manifest.json) | `unity pipeline install --project-path <p>` — с согласия |
| Godot | путь к бинарю: `which godot`, `/Applications/Godot.app/Contents/MacOS/Godot`, `godot --version` | попросить путь |
| Unreal | `EngineAssociation` из .uproject → найти установку движка (`/Users/Shared/Epic Games/UE_<ver>`); наличие `RunUAT.sh` | попросить путь к движку |
| Blender (если будет 3D) | `/Applications/Blender.app/Contents/MacOS/Blender --version`, `which uvx` | предложить установку Blender и uv; MCP — шаблон `blender.json` (см. gameforge:blender) |
| Арт-инструменты (по арт-стилю из GDD) | Aseprite: `/Applications/Aseprite.app` или Steam; GIMP 3.2+: `/Applications/GIMP.app`; Blockbench; `which uv node` | спросить, что из этого пользователь использует; покупки (Aseprite, FL Studio) — решение пользователя |
| Музыка | FL Studio установлен? (`/Applications/FL Studio*.app`) | музыка через gameforge:audio без DAW-MCP |
| Встроенные MCP плагина | `bash "${CLAUDE_PLUGIN_ROOT}/scripts/run-mcp.sh" --selftest` (один раз: готовит Python-окружение для gameforge-voxel и gameforge-fx) | нужен python3 3.10+ или uv |
| Аудио/видео | `which ffmpeg` | `brew install ffmpeg` — с согласия |
| Все | `git status` — проект под git? Есть `.gitignore` под движок? Для Unity/Unreal — Git LFS для бинарных ассетов | предложить `git init` + gitignore + LFS |

## 3. MCP

Шаблоны лежат в `${CLAUDE_PLUGIN_ROOT}/mcp-templates/<engine>.json`. Плагин **не** включает MCP глобально — сервер пишется в `.mcp.json` конкретного проекта.

1. Прочитай существующий `.mcp.json` проекта (если есть) — сливай, не затирай чужие сервера.
2. Сервер движка + серверы под арт-стиль и музыку игры — только нужные:
   | Стиль/задача | Шаблон | Скилл |
   |--------------|--------|-------|
   | 3D реализм / сложные модели | `blender.json` | gameforge:blender |
   | Пиксель-арт | `aseprite.json` (+ встроенный gameforge-fx) | gameforge:pixel-art |
   | HD 2D, текстуры, маркетинговые картинки | `gimp.json` | gameforge:art-2d |
   | Воксели | — встроенный **gameforge-voxel** (уже подключён плагином) | gameforge:voxel |
   | Low-poly / блочные модели | `blockbench.json` | gameforge:voxel |
   | Эффекты (VFX) | — встроенный **gameforge-fx** | gameforge:vfx |
   | Музыка в FL Studio | `flstudio.json` | gameforge:music |

   Подставь плейсхолдеры: `{{PROJECT_PATH}}` (абсолютный путь), `{{GODOT_PATH}}`, `{{UNREAL_MCP_PORT}}` (спроси/посмотри в настройках плагина редактора; по умолчанию 8000), `{{ASEPRITE_MCP_DIR}}` (куда пользователь согласился клонировать diivi/aseprite-mcp, например `~/Tools/aseprite-mcp`), `{{ASEPRITE_PATH}}`. Клонирование репозиториев и установка плагинов в GIMP/FL Studio/Blockbench — только с согласия пользователя, по шагам из `_comment` шаблона.
3. Ключ `_comment` в `.mcp.json` не переноси.
4. Скажи пользователю: после изменения `.mcp.json` Claude Code спросит одобрение сервера при следующем запуске в проекте.

Правило Unity: **когда есть шелл — CLI (`unity command …`) приоритетнее MCP**, MCP нужен для захвата Game/Scene View и long-running job’ов. Альтернатива ручному шаблону — `unity mcp configure claude-code` (пишет конфиг сам).

## 4. Структура .gameforge/

Создай из `${CLAUDE_PLUGIN_ROOT}/templates/`:

```
.gameforge/
  state.md        ← templates/state.md (заполни title/engine/engine_version/track/platforms/date)
  context.md      ← templates/context.md — паспорт проекта (заполни всё, что уже известно)
  history.md      ← templates/history.md — журнал, первая запись «Проект подключён»
  archive/        ← снимки GDD и старые части истории
  concept.md      ← templates/concept.md
  gdd.md          ← templates/gdd.md
  backlog.md      ← templates/backlog.md
  credits.md      ← templates/credits.md (лицензии всех сторонних ассетов)
  marketing.md    ← templates/marketing-plan.md
  ideas/          ← сессии брейншторма (templates/ideas.md)
  levels/         ← документы уровней (templates/level.md)
  audio/          ← sound-list.md (templates/sound-list.md)
  playtests/      ← сюда templates/playtest.md как NNN.md
  decisions/      ← ADR по templates/adr.md
  releases/
```

Если проект под git — `.gameforge/` коммитится вместе с кодом (в `.gitignore` не добавлять): так у GDD, контекста и истории есть полная история версий.

Существующий проект без .gameforge: перед заполнением `context.md` изучи код, сцены и README и заполни паспорт по факту (что за игра, где что лежит, как запускать), а неизвестное вынеси в «Открытые вопросы» и спроси пользователя.

Исходники арта — `art/blender/` (.blend и скрипты) в корне проекта, не внутри `Assets/`/`Content/`.

## 5. CLAUDE.md проекта

Добавь (или дополни) короткий раздел — не больше 20 строк. Строка `@.gameforge/context.md` — импорт: Claude Code подгружает паспорт проекта в каждую сессию вместе с CLAUDE.md.

```markdown
## GameForge
@.gameforge/context.md

- Движок: <engine> <version>, трек: <track>, платформы: <...>
- Память проекта: .gameforge/context.md (паспорт), .gameforge/history.md (журнал — дописывать после каждого куска работы), .gameforge/gdd.md (дизайн, с версиями)
- Состояние цикла: .gameforge/state.md, backlog: .gameforge/backlog.md
- Проверка изменений: <команда компиляции/тестов из engine-скилла>
- Не редактировать руками: <Unity: .meta, сцены/префабы при открытом редакторе — через unity command; Godot: uid; Unreal: .uasset>
```

## 6. Готово

Отметь ворота `setup` в state.md, «Следующий шаг: gameforge:concept» (или design, если концепт уже есть). Кратко отчитайся: что найдено, что настроено, что требует действий пользователя (одобрить MCP, установить CLI и т.п.).
