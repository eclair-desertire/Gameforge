---
name: engine-unity
description: Справочник GameForge по Unity — Unity CLI (status, command, recompile, test, build, projects create, pipeline install), Unity MCP (unity mcp), управление запущенным редактором, playmode-проверка, правила .meta/сцен/префабов и карта официальных unity:* скиллов. Используй в любом Unity-проекте (есть ProjectSettings/ProjectVersion.txt) перед компиляцией, тестами, правкой сцен, сборкой или настройкой MCP.
---

# Unity в GameForge

## Перед началом: инструменты

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" --task unity
```
Итог не «всё готово» → **сначала явно перечисли пользователю, что требуется установить или включить**, и пройди gameforge:doctor (установка только с его согласия). В сессии должны быть инструменты: Unity CLI в PATH; `mcp__unity__*` — если нужен захват Game/Scene View; прописан, но инструментов нет — сервер не активен (doctor, шаг 5).

**Первоисточник по CLI — официальный скилл `unity:unity-cli`.** Если он установлен — загрузи его для любой нетривиальной команды; ниже — короткая шпаргалка и правила GameForge поверх.

## Установка и проверка

```bash
which unity && unity --version          # CLI есть?
unity self-update --check --format json # держим последнюю версию
unity doctor --format json              # здоровье окружения
```

Установка (только с согласия пользователя): `curl -fsSL https://unity.com/install.sh | bash`.

Новый проект: `unity projects create <Name> --path <dir> --editor-version <ver> --template com.unity.template.urp-blank` (или `unity:new-unity-project` — он проведёт через выбор платформ и пакетов).

## Управление редактором (пакет com.unity.pipeline, Unity 6.0+)

```bash
unity pipeline install --project-path <p>                 # один раз на проект
unity status --until-ready --project-path <p>             # дождаться редактора
unity command --query <слово> --project-path <p>          # найти команду (не grep по help!)
unity command <name> --caller plugin --skill gameforge-build --project-path <p>
unity command script eval --caller plugin --skill gameforge-build --project-path <p> '<C#>'
unity recompile --project-path <p>                        # компиляция + ошибки
```

- **Всегда `--project-path`** — может быть открыто несколько редакторов (воркtree, другие проекты).
- **Всегда `--format json`**, если разбираешь вывод.
- `--caller plugin --skill <имя-скилла>` на каждом `unity command` — метка вызова.
- Не подключается → сначала `unity status`: **Safe Mode** из-за ошибок компиляции — чини ошибки, а не правь сцены руками.
- Таймауты, падение редактора → скажи пользователю, не обходи молча. `unity bug` не запускай без его согласия (отправляет логи в Unity).

## Тесты и сборки

```bash
unity test <p> --mode EditMode --output ./TestResults/edit.xml
unity test <p> --mode PlayMode --output ./TestResults/play.xml
unity test <p> --mode EditMode --rerun-failed --output ./TestResults/edit.xml
unity build <p> --list-profiles --format json
unity build <p> --profile "<Profile>" --output-path ./Build/<...>
unity build run <p>                                       # запустить собранный билд
unity ci init --project-path <p>                          # сгенерировать CI
```

## Проверка в Play mode

Вход в Play mode — это ещё не доказательство. Порядок (полный рецепт — `unity:unity-cli` → `references/playmode-verification-loop.md`):
1. редактор `ready` → 2. редактор тикает в фоне (не заморожен) → 3. `editor.playmode start` и дождаться Pipeline → 4. **убедиться, что время/кадры растут** → 5. захват Game View → 6. **консоль без исключений** → 7. тюнинг через `script eval` без перекомпиляции → 8. выйти из Play mode.

## MCP

`unity mcp` — встроенный в CLI stdio-сервер; шаблон — `mcp-templates/unity.json`, настройка — gameforge:setup или `unity mcp configure claude-code`. **В Claude Code с шеллом CLI приоритетнее MCP**; MCP ценен для `capture_game_view`/`capture_scene_view` и `job_*`. Сузить набор инструментов: `--tools`/`--exclude-tools`.

## Правила GameForge для Unity

- `.meta` не создаём и не удаляем руками; перенос ассетов — через редактор (`AssetDatabase.MoveAsset` в `script eval`), иначе ломаются GUID-ссылки.
- Сцены/префабы при открытом редакторе — только через редактор.
- Баланс — ScriptableObject; события между системами — SO-каналы или C# events, не `FindObjectOfType` в Update.
- Новый ввод — Input System; UI — сначала спроси `unity:ui`, какой фреймворк.
- Git: `.gitignore` Unity, LFS для `*.psd *.png *.fbx *.wav *.mp3 *.ogg`, Force Text serialization, Visible Meta Files.

## Карта официальных скиллов `unity:*`

| Тема | Скилл |
|------|-------|
| Новый проект | `unity:new-unity-project` |
| Пакеты | `unity:unity-package-management` |
| UI | `unity:ui` → `ui-uitk` / `ui-ugui` / `ui-imgui` |
| 2D | `unity:create-2d-physics`, `unity:create-tile-palette-or-rule-tiles`, `unity:2d-pixel-perfect`, `unity:sprite-editor`, `unity:manage-sprite-atlas` |
| 3D/AI | `unity:physics-3d-collision`, `unity:initialize-ai-navigation` |
| Рендер | `unity:urp-postprocessing`, `unity:migrate-birp-to-urp`, `unity:shader-graph-create-custom-node` |
| Звук | `unity:audio-setup-mixers`, `unity:optimize-audio` |
| Текст/язык | `unity:optimize-text-mesh-pro`, `unity:localization` |
| Полировка | `unity:craft-game-floors` |
| Монетизация | `unity:implement-in-app-purchases`, `unity:levelplay-unity-integration` |
| Онлайн | `unity:build-live-game`, `unity:setup-multiplayer-services`, `unity:setup-vivox-voice-chat` |
| Web | `unity:optimize-web` |
| Поиск в редакторе | `unity:generate-editor-search-query` |
