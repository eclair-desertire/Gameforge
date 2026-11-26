---
name: engine-godot
description: Справочник GameForge по Godot 4 — бинарь и headless-режим, импорт и проверка скриптов, тесты GUT/gdUnit4, экспорт через CLI, Godot MCP (Coding-Solo/godot-mcp или godot-ai для живого редактора), правила uid/res:// и GDScript. Используй в любом Godot-проекте (есть project.godot) перед запуском, тестами, правкой сцен, экспортом или настройкой MCP.
---

# Godot в GameForge

## Бинарь

macOS: `/Applications/Godot.app/Contents/MacOS/Godot` (или `Godot_mono.app` для C#). Проверь `which godot`; если нет — используй полный путь, запиши его в CLAUDE.md проекта. Версия: `godot --version`.

Ниже `godot` = путь к бинарю, `<p>` = папка с `project.godot`.

## Ключевые команды

```bash
godot --headless --path <p> --import                          # импорт ассетов (после добавления файлов, в CI)
godot --headless --path <p> --check-only -s res://path/x.gd   # синтаксис/типы одного скрипта
godot --path <p>                                              # запустить игру
godot --path <p> res://scenes/level_1.tscn                    # запустить конкретную сцену
godot --headless --path <p> -s res://tests/run_tests.gd       # скрипт-раннер (exit code = результат)
godot --headless --path <p> --export-release "<preset>" build/<file>
godot --headless --path <p> --export-debug "<preset>" build/<file>
```

Экспорт требует установленных export templates той же версии и пресета в `export_presets.cfg` (создаётся в редакторе: Project → Export).

## Тесты

- **GUT** (`addons/gut`): `godot --headless --path <p> -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit`
- **gdUnit4** (`addons/gdUnit4`): `addons/gdUnit4/runtest.sh -a res://tests` (headless, отчёт в `reports/`)
- Без фреймворка: свой `SceneTree`-скрипт, который вызывает `quit(1)` при провале.

Ненулевой exit code при падении — обязательно, иначе CI «зелёный» на сломанной игре.

## MCP

- **Вариант A (по умолчанию):** `@coding-solo/godot-mcp` — шаблон `mcp-templates/godot.json`, `GODOT_PATH` = путь к бинарю. Инструменты: `launch_editor`, `run_project`, `get_debug_output`, `stop_project`, `create_scene`, `add_node`, `load_sprite`, `save_scene`, `get_uid`, `update_project_uids` и др. Быстрая установка: `claude mcp add godot -e GODOT_PATH=<path> -- npx @coding-solo/godot-mcp`.
- **Вариант B (живой редактор, Godot 4.7+):** `hi-godot/godot-ai` — аддон в `addons/godot_ai/` + Python-сервер через `uv`. Команду подключения генерирует кнопка Configure в доке Godot AI — руками конфиг не пишем. Порт 8000 (HTTP) и 9500 (WebSocket). Телеметрию можно выключить: `GODOT_AI_DISABLE_TELEMETRY=true`.

Цикл проверки через MCP: `run_project` → подождать → `get_debug_output` (ошибки/принты) → `stop_project`.

## Правила GameForge для Godot

- Статическая типизация GDScript везде (`var hp: int`, `func f() -> void`), `@export` для тюнинга.
- Связи между системами — сигналы и autoload-шина событий, не `get_node("../../..")`.
- Данные баланса — свои `Resource` (`class_name EnemyStats extends Resource`) в `.tres`.
- `.tscn`/`.tres` — текст, их можно править, но аккуратно: сохраняй `uid://` и `ExtResource` id; после переноса файлов — `update_project_uids` или открыть проект в редакторе. `.godot/` — в `.gitignore`.
- C#: нужен Godot .NET; godot-ai поддерживает C# только как текст.
- Web-экспорт Godot 4: нужны заголовки COOP/COEP (или single-threaded экспорт) — учесть для itch/порталов.

Глубже по подсистемам (физика, TileMapLayer, UI, шейдеры, мультиплеер) — если установлен набор `awesome-gamedev-agent-skills`, его скиллы `godot-*`.
