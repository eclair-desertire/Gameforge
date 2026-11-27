---
name: doctor
description: Проверяет, установлены ли и включены ли программы, CLI и MCP-серверы для задачи (Blender, Aseprite, GIMP, Blockbench, FL Studio, Unity, Godot, Unreal, uv, Node, ffmpeg, встроенные gameforge-voxel и gameforge-fx), явно сообщает, что нужно установить, ставит с согласия пользователя, прописывает MCP в .mcp.json и проверяет, что сервер реально активен. Используй перед работой, которой нужен внешний инструмент, когда MCP не отвечает или его инструментов нет в сессии, или когда просят настроить окружение.
---

# Doctor — инструменты и MCP перед работой

**Правило: никогда не начинай задачу, которой нужен внешний инструмент, не проверив его.** Если что-то не установлено или не включено — скажи об этом пользователю явно, отдельным списком, до начала работы.

## 1. Проверка (дёшево, ~1 с)
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" --task <pixel-art|art-2d|vfx|voxel|lowpoly|blender|humans|music|audio|unity|godot|unreal>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" aseprite gimp      # конкретные инструменты
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" all               # всё сразу
```
Статусы: `[ok]` готово · `[нет]` не установлено · `[выкл]` установлено, но не запущено · `[mcp]` сервер не прописан в проекте · `[?]` необязательное или не удалось проверить. Код выхода 0 — всё готово.

Плюс проверка сессии: инструменты сервера должны быть в твоём списке (`mcp__<сервер>__*`; у встроенных — `mcp__plugin_gameforge_gameforge-voxel__*`, `…gameforge-fx__*`). Прописан, но инструментов нет → сервер не активен в этой сессии (шаг 5).

## 2. Сообщить пользователю — явно
Формат (одним сообщением, до любых установок):

> **Для задачи «…» требуется установка/включение:**
> 1. uv — менеджер Python-пакетов, нужен для GIMP MCP. Команда: `brew install uv`. Бесплатно.
> 2. Плагин GIMP MCP — `uvx gimp-mcp-plugin@latest install-plugin`, затем перезапуск GIMP.
> 3. Обновить GIMP 3.0 → 3.2+ (делаешь ты: скачать с gimp.org).
> 4. Включить сервер в GIMP: MCP → Start Server.
>
> Что могу сделать сам (1, 2, прописать MCP) — сделать?

Разделяй: **что агент может поставить сам** (brew, uvx, git clone, запись `.mcp.json`) и **что делает только пользователь** (покупка Aseprite/FL Studio, вход в аккаунты, клики внутри приложений, обновление приложений с паролем администратора, одобрение MCP-сервера в Claude Code).

## 3. Установка — только после «да»
- Команды из колонки `→` отчёта. Длинные (brew cask, клон) — в фоне, с отчётом по завершении.
- Репозитории MCP клонируй в `~/Tools/<name>` (или куда скажет пользователь), не в проект игры.
- Ничего не покупай, не логинься, не вводи ключи и пароли. Ключи API генераторов пользователь добавляет сам в env.
- Скрипты установки сторонних проектов — сначала прочитай, что они делают.

## 3a. Проверенные рецепты установки

**MPFB2 + ассеты MakeHuman (реалистичные люди, `--task humans`)** — через `execute_blender_code` в живом Blender (нужен Allow Online Access):
1. Каталог: `bpy.ops.extensions.repo_sync(repo_index=<extensions.blender.org>)` → `bpy.ops.extensions.package_install(repo_index=…, pkg_id="mpfb", enable_on_install=True)`. Установка асинхронная; если через ~30 с расширения нет в `extensions/*/mpfb` — сервер медленный (бывает ~5 КБ/с).
2. Запасной путь: `https://codeload.github.com/makehumancommunity/mpfb2/zip/refs/tags/v<версия>` (официальный репозиторий) → запаковать содержимое `src/mpfb/` в zip → `bpy.ops.extensions.package_install_files(filepath=…, repo="user_default", enable_on_install=True)`.
3. Ассеты (кожа, глаза, брови, волосы, одежда, обувь, CC0, 280 МБ): `https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip` (основное зеркало быстрое; `files2` — медленное) → `unzip -t` → распаковать в user data MPFB (`LocationService.get_user_data()`, обычно `~/Library/Application Support/Blender/<v>/extensions/.user/user_default/mpfb/data`).
4. Проверка: `check-tools.py --task humans` → «всё готово».

**Poly Haven (CC0 текстуры, HDRI)**: API отвечает 403 без заголовка User-Agent — ставь нейтральный (`-A "GameForge/1.0"`), без данных пользователя. Качай `curl -C - --retry 5` в фоне; файлы, загруженные в Blender недокачанными, потом `image.reload()`.

**Большие загрузки** всегда в фоне, с докачкой (`curl -C -`) и проверкой архива (`unzip -t`, хеш, если источник его публикует).

## 4. Прописать MCP
1. Шаблон `${CLAUDE_PLUGIN_ROOT}/mcp-templates/<tool>.json` → слить в `.mcp.json` **проекта игры** (не затирая чужие сервера), подставить `{{…}}`, ключ `_comment` не переносить. Инструменты, нужные во всех проектах, можно добавить на уровне пользователя: `claude mcp add --scope user …` — спроси, какой вариант.
2. Встроенные `gameforge-voxel` и `gameforge-fx` прописывать не нужно — они в плагине. Если `[нет]` — `bash "${CLAUDE_PLUGIN_ROOT}/scripts/run-mcp.sh" --install`.

## 5. Активировать и проверить
1. Новый сервер в `.mcp.json` подхватывается при старте сессии, Claude Code спросит одобрение. Скажи пользователю явно: **«перезапусти сессию (или `/mcp` → подключить/reconnect) и одобри сервер <имя>»**.
2. Серверы внутри приложений запускает пользователь: Blender — официальный аддон: Preferences → System → Network → Allow Online Access, затем Add-ons → MCP → Start MCP Bridge Server (community-аддон: N-панель → MCP → Start); GIMP — MCP → Start Server; Blockbench — плагин MCP; FL Studio — открыть проект после `fl-studio-mcp setup`.
3. Повтори `check-tools.py` и вызови самый дешёвый инструмент сервера (Blender `get_scene_info`, GIMP `check_server`, Aseprite — создать холст 8×8 во временной папке, FL Studio — статус/transport, voxel `vox_scene action=list`, fx `fx_palette`).
4. Запиши в `.gameforge/context.md` → «Соглашения и команды»: какие инструменты и MCP настроены, версии, где лежат.

## 6. Если пользователь отказался
Скажи, чем это грозит качеству, и предложи обходной путь: пиксель-арт без Aseprite — gameforge-fx + Python; HD 2D без GIMP — gameforge-fx; музыка без FL Studio — MIDI + gameforge:audio; 3D без Blender — gameforge-voxel или Blockbench. Не делай вид, что инструмент есть.
