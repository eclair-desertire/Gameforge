# GameForge

Личный плагин Claude Code для полного цикла разработки игр: **идея → концепт → GDD → прототип → продакшн → полировка → релиз → live**.
Движки: **Unity** (Unity CLI + `unity mcp`), **Godot 4**, **Unreal Engine 5**. Треки: **mobile** и **pc/Steam**.
Арт и звук: Blender, **воксели** и **VFX** (свои MCP-серверы плагина), пиксель-арт в Aseprite, HD 2D в GIMP, low-poly в Blockbench, музыка в FL Studio.

GameForge — дирижёр: свои этапы, ворота и состояние проекта + вызов сильных узких скиллов, если они установлены (`unity:*`, `game-trend-skills:*`, `claude-code-game-studios`, `awesome-gamedev-agent-skills`).

## Состав

```
.claude-plugin/
  plugin.json            манифест
  marketplace.json       локальный маркетплейс (для установки через /plugin)
skills/
  studio/                дирижёр: где мы, что дальше, ворота этапов, параллельные потоки
  team/                  команда из 27 агентов: роли, модели, бриф, отчёт, ворота ревью, сценарии
  project-memory/        память проекта: context.md, history.md, версии GDD
  setup/                 подключение проекта: движок, CLI, MCP, .gameforge/, CLAUDE.md
  doctor/                проверка, установка (с согласия) и активация программ и MCP перед работой
  ideas/                 брейншторм по свежим трендам (Steam, мобильные чарты, соцсети, джемы)
  concept/  design/      идея → вердикт; живой GDD
  plan/  build/          backlog по всем потокам; реализация с проверкой в движке
  playtest/              QA: автотесты, playmode/headless, отчёт, keep/kill
  level-design/          метрики, бит-чарт, greybox, проходимость и soft-lock
  blender/               Blender MCP: реалистичные здания (киты), люди (MPFB2), экспорт
  voxel/                 воксели через gameforge-voxel: здания, люди, деревья, рельеф; Blockbench
  pixel-art/             пиксель-арт в Aseprite MCP: палитры, свет, sel-out, анимация, импорт
  art-2d/                HD 2D в GIMP MCP: спрайты, текстуры, UI, капсулы Steam
  vfx/                   эффекты: флипбуки gameforge-fx + частицы движка
  audio/                 SFX и общие требования к звуку: лицензии, ffmpeg, микшер в движке
  music/                 музыка в FL Studio MCP: лейтмотив, адаптивные слои, стемы
  polish/                game feel, UI, производительность
  marketing/             позиционирование, Steam-страница, трейлер, devlog, креативы, ASO
  release/  live/        сборки, Steam/itch/сторы; метрики и апдейты
  engine-unity/          Unity CLI, unity mcp, playmode-проверка, карта unity:*
  engine-godot/          headless, тесты, экспорт, godot-mcp / godot-ai
  engine-unreal/         Build.sh, RunUAT, автотесты, Python, Unreal MCP
agents/                  27 агентов команды (дирекция, лиды, специалисты, помощники) — см. «Команда»
hooks/hooks.json         SessionStart: выводит память проекта (и после сжатия контекста)
                         Stop: напоминает дописать history.md, если файлы менялись
scripts/                 detect-engine.sh, status.sh, history-check.sh, run-mcp.sh,
                         check-tools.py (что установлено/включено для задачи)
mcp-servers/             свои MCP-серверы (Python): voxel/ (gameforge-voxel), fx/ (gameforge-fx)
.claude-plugin/plugin.json  манифест + подключение gameforge-voxel и gameforge-fx (без внешних программ)
mcp-templates/           unity, godot, unreal, blender, aseprite, gimp, blockbench, flstudio —
                         пишутся в .mcp.json проекта по необходимости
templates/               state, context, history, ideas, concept, gdd, backlog, level, sound-list, credits,
                         marketing-plan, playtest, adr
```

## Состояние проекта

Всё, что плагин знает о проекте, лежит в самом проекте — переживает новые сессии и смену машины:

```
<игра>/.gameforge/
  context.md    паспорт проекта: что за игра, где мы, решения, глоссарий, соглашения
  history.md    журнал работы — только дописывается
  gdd.md        дизайн-документ с версией и историей изменений
  state.md      этап, ворота, следующий шаг
  concept.md    backlog.md    credits.md    marketing.md
  ideas/  levels/  audio/  playtests/  decisions/ (ADR)  releases/
  archive/      снимки GDD по версиям, старая история
```

Чтобы Claude не забывал, что это за проект:
1. **SessionStart-хук** выводит context.md, этап и последние записи истории на старте, при resume, после `/clear` и **после сжатия контекста**.
2. **CLAUDE.md проекта** импортирует `@.gameforge/context.md`.
3. **Stop-хук** напоминает дописать history.md, если файлы проекта менялись, а журнал не обновлялся 20+ минут (не чаще раза в 45 минут; пороги — `GAMEFORGE_HISTORY_MINUTES`, `GAMEFORGE_NAG_MINUTES`).
4. Если проект под git — `.gameforge/` коммитится вместе с кодом.

## Команда

Основная сессия — руководитель студии; работу выполняют агенты со своей специализацией, моделью и зоной файлов. Директора и лиды принимают работу специалистов на воротах ревью (строгость — `review: full | lean | solo` в `state.md`). Подробно — `skills/team`.

| Уровень | Агенты (модель) |
|---------|-----------------|
| Дирекция | creative-director (opus), technical-director (opus), producer (sonnet) |
| Лиды | game-designer (opus), lead-programmer (opus), art-director (opus), audio-director (sonnet), qa-lead (sonnet), marketing-lead (sonnet) |
| Дизайн | economy-designer, level-designer, ux-designer, writer (sonnet) |
| Код | gameplay-programmer, ui-programmer, unity-specialist, godot-specialist, unreal-specialist (sonnet) |
| Арт | 2d-artist (opus), 3d-artist (opus), tech-artist (sonnet) |
| Звук | audio-designer (sonnet), composer (opus) |
| QA и сборки | qa-playtester, build-engineer (sonnet) |
| Помощники | scout, runner (haiku) — поиск, чтение логов, прогон готовых команд |

Каждый агент заканчивает ответ отчётом СТАТУС / ФАЙЛЫ / ПРОВЕРЕНО / НЕ ПРОВЕРЕНО / РЕШИТЬ ПОЛЬЗОВАТЕЛЮ / ДАЛЬШЕ; вопросы пользователю задаёт только основная сессия.

## Проверка инструментов

- **При старте каждой сессии** в игровом проекте хук проверяет инструменты из поля `tools:` в `.gameforge/state.md` и выводит, что нужно установить, а что просто не запущено.
- **Перед работой** с внешней программой скиллы запускают `python3 scripts/check-tools.py --task <задача>` (или `all`) и **явно перечисляют, что нужно установить или включить**; установка и подключение MCP — через `gameforge:doctor`, только с согласия пользователя.
- **Агенты** проверяют инструменты сами и при нехватке возвращают BLOCKED, ничего не устанавливая.

## MCP-серверы

**Свои, встроены в плагин** (стартуют сами, нужен python3 3.10+ или uv; окружение создаётся один раз в `~/.cache/gameforge/venv`, заранее — `bash scripts/run-mcp.sh --install`, проверка — `--selftest`):

| Сервер | Инструменты | Что умеет |
|--------|-------------|-----------|
| `gameforge-voxel` | 12 | сцены и модели до 256³, рампы с hue shift, формы (box/ellipsoid/cylinder/cone/capsule, шероховатость), шум/эрозия/scatter, запечённое AO и световые рёбра, генераторы зданий, людей, деревьев, скал и рельефа, kit-штампы, превью (iso/turnaround/sheet), MagicaVoxel `.vox` (+ материалы), экспорт `.glb`/`.obj` с палитрой и emissive |
| `gameforge-fx` | 6 | HDR-флипбуки (explosion, fire, smoke, magic, slash, hit, lightning, portal, heal, sparkle) с bloom, гладкие или пиксельные (общая палитра, жёсткая альфа, sel-out); пост-обработка (outline, тень, glow, rim light, грейдинг, quantize+dither, pixelate); normal maps; палитры `.gpl`; спрайтшиты и GIF; просмотр с pixel-art lint |

**Внешние** — плагин их не включает глобально: `gameforge:setup` пишет нужные в `.mcp.json` проекта.

| Шаблон | Проект | Зачем |
|--------|--------|-------|
| `aseprite.json` | [diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp) (MIT) | пиксель-арт и анимация в Aseprite |
| `gimp.json` | [gimp-mcp/gimp-mcp](https://github.com/gimp-mcp/gimp-mcp) (GPL-3.0) | HD 2D, текстуры, UI, маркетинговые картинки |
| `blockbench.json` | [jasonjgardner/blockbench-mcp-plugin](https://github.com/jasonjgardner/blockbench-mcp-plugin) (GPL-3.0) | low-poly и блочные модели, UV, анимация |
| `flstudio.json` | [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp) (MIT) | музыка: piano roll, паттерны, микшер, плагины |
| `blender.json` | официальный [Blender Lab MCP](https://projects.blender.org/lab/blender_mcp) (GPL-3.0) или [mcp-for-blender](https://github.com/ahujasid/mcp-for-blender) (MIT) — под установленный аддон | 3D в Blender |
| `unity.json`, `godot.json`, `unreal.json` | см. ниже | движки |

## Установка

Проверка без установки (одна сессия):

```bash
claude --plugin-dir ~/Documents/GitHub/Gameforge
```

Постоянно — как маркетплейс из GitHub (на любой машине):

```bash
claude plugin marketplace add eclair-desertire/Gameforge
```

или из локальной копии репозитория (правки видны после `update`):

```bash
claude plugin marketplace add ~/Documents/GitHub/Gameforge
```

```bash
claude plugin install gameforge@gameforge-local
```

После правок в плагине: `claude plugin update gameforge@gameforge-local` и перезапуск сессии.

## Как пользоваться

В папке игры: «давай начнём новую игру» или `/gameforge:studio` — дальше плагин сам ведёт по этапам. Точечно: `/gameforge:build P-03`, `/gameforge:playtest`, `/gameforge:release`.

## Источники и благодарности

- Unity CLI и `unity mcp` — официальный плагин Unity (`unity:unity-cli`).
- Godot MCP — [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) (MIT), [hi-godot/godot-ai](https://github.com/hi-godot/godot-ai) (MIT).
- Unreal MCP — официальный от Epic (UE 5.8+, experimental), community: [runreal/unreal-mcp](https://github.com/runreal/unreal-mcp), [ChiR24/Unreal_mcp](https://github.com/ChiR24/Unreal_mcp).
- Blender MCP — официальный [lab/blender_mcp](https://projects.blender.org/lab/blender_mcp) (Blender 5.1+, GPL-3.0) и [ahujasid/mcp-for-blender](https://github.com/ahujasid/mcp-for-blender) (MIT; пакет `blender-mcp` на PyPI — это он).
- Идея команды со специализациями и воротами ревью — [Claude Code Game Studios](https://github.com/Donchitos/Claude-Code-Game-Studios); состав, роли, ворота и тексты GameForge — свои.
- Люди — [MPFB2](https://static.makehumancommunity.org/mpfb.html) (core-ассеты CC0, код GPL).
- Идеи структуры — [awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) (Apache-2.0: один engine-скилл + дисциплины поверх, headless-проверки) и [OhMyGame](https://github.com/WhiteTowerAI/ohmygame) (Apache-2.0: цикл «дизайн → код → запуск → игра агентом → фикс», состояние проекта в файле).

## Дорожная карта

- [ ] Скиллы-дисциплины: game-feel, save-system, procedural-gen, narrative/dialogue
- [ ] Blender: скульпт/бейк high→low, анимация
- [ ] gameforge-voxel: риг частей персонажа и покадровая анимация; gameforge-fx: больше эффектов (вода, пыль, щит, снаряды), лучше огонь
- [ ] Жанровые надстройки: platformer, roguelike, idle/tycoon, hybrid-casual
- [ ] PostToolUse-хук: после правок .cs/.gd/.cpp напоминать о компиляции
- [ ] Evals (`claude plugin eval`) на маршрутизацию скиллов
