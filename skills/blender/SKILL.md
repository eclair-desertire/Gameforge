---
name: blender
description: 3D-арт для игры через Blender MCP (mcp-for-blender или официальный Blender Lab MCP) — сложные детализированные модели (реалистичные здания и модульные киты, реалистичные люди через MPFB2, пропсы), материалы PBR, UV, LOD, коллизии, риг, проверка скриншотами вьюпорта и экспорт в Unity, Godot или Unreal. Используй, когда нужно сделать или доработать 3D-модель, персонажа, здание, окружение, ассеты в Blender или настроить Blender MCP.
---

# Blender — сложные игровые ассеты

## Перед началом: инструменты

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" --task blender
```
Итог не «всё готово» → **сначала явно перечисли пользователю, что требуется установить или включить**, и пройди gameforge:doctor (установка только с его согласия). В сессии должны быть инструменты: `mcp__blender__*`; прописан, но инструментов нет — сервер не активен (doctor, шаг 5).

## 0. Подключение — два варианта, ровно один активен

Оба сервера используют порт 9876, но протоколы у них **разные**: сервер работает только со «своим» аддоном. `check-tools.py --task blender` определяет, какой аддон стоит, и проверяет, что прописан подходящий сервер.

| | **Официальный Blender Lab MCP** (предпочтительно, если стоит) | **mcp-for-blender** (community, MIT) |
|--|--|--|
| Blender | 5.1+ | 3.0+ |
| Аддон | расширение `MCP` из репозитория `https://lab.blender.org/` (Preferences → Get Extensions → Repositories) | `uvx mcp-for-blender install-addon` → включить «Interface: MCP for Blender» |
| Сервер MCP | `uvx --from "git+https://projects.blender.org/lab/blender_mcp.git#subdirectory=mcp" blender-mcp` (⚠ пакет `blender-mcp` на PyPI — это другой, community-проект) | `uvx mcp-for-blender` |
| Запуск в Blender | Preferences → Add-ons → MCP → Start (или галка Auto-start) | N-панель → MCP for Blender → Start MCP Server |
| Шаблон | `mcp-templates/blender.json` → `blender` | `mcp-templates/blender.json` → `blender-community` |

**Инструменты по задачам:**

| Задача | Официальный | Community |
|--------|-------------|-----------|
| Выполнить Python в Blender | `execute_blender_code` | `execute_blender_code` |
| Посмотреть результат | `get_screenshot_of_area_as_image` (3D-вид), `render_thumbnail_to_path` / `render_viewport_to_path` + прочитать PNG | `look` (solid/material/rendered/wireframe) |
| Состав сцены | `get_objects_summary`, `get_object_detail_summary`, `get_blendfile_summary_*` | `get_scene_info`, `get_object_info` |
| Документация API и мануал | `search_api_docs`, `get_python_api_docs`, `search_manual_docs` — **используй перед незнакомым API**, это убирает ошибки версий | — |
| Пакетно без GUI | `*_for_cli` (фоновый Blender) | — |
| Готовые ассеты, AI-генерация | скачать CC0 с Poly Haven (api.polyhaven.com) и импортировать через `execute_blender_code` | `search_assets` / `import_asset`, `generate_3d` (ключи — у пользователя) |

Если Blender закрыт или сервер в нём не запущен, MCP подключается, но каждый вызов падает. Тогда скажи пользователю: «открой Blender и запусти MCP-сервер (или включи Auto-start)».

**Безопасность:** `execute_blender_code` выполняет любой Python — **перед серией правок сохраняй .blend** (`bpy.ops.wm.save_as_mainfile` в версионный файл). Сокет без аутентификации — только localhost. Ключи API в файлы проекта не пишем.

**Без MCP (пакетно, headless):** `blender -b scene.blend --python tools/export.py -- <args>` — экспорт, LOD, проверки в CI.

## 1. Главный принцип для сложных моделей

Сложная реалистичная модель **не делается одним скриптом**. Делай как художник — слоями, и после каждого слоя смотри:

```
референс и размеры → блокаут → крупные формы → средние детали → мелкие детали
→ UV → материалы → декали/износ → LOD + коллизии → экспорт → проверка в движке
```

- **Один вызов `execute_blender_code` = один логический шаг** (стена, окно, карниз), а не всё здание. Скрипты складывай в `art/blender/scripts/` проекта — их можно перезапустить и поправить параметры.
- **После каждого шага — скриншот** (`get_screenshot_of_area_as_image` / `look`) минимум с 2 ракурсов (общий + крупный план), в конце — `rendered` с HDRI. Сравни с референсом и честно перечисли расхождения, прежде чем идти дальше.
- **Реальные размеры в метрах** (Unit Scale 1.0). Масштаб — первое, что выдаёт «игрушечность».
- **Неразрушающее моделирование**: модификаторы (Bevel, Array, Mirror, Solidify, Weighted Normal), Geometry Nodes, коллекции-киты. Применяем модификаторы только при экспорте.
- **Комбинируй источники**: процедурное моделирование (точная архитектура) + Poly Haven (CC0 текстуры, HDRI, пропсы) + `generate_3d` в community-варианте (органика и сложные пропсы, требуют чистки) + MPFB2 (люди).

## 2. Типы ассетов

- **Здания и окружение** → [references/buildings.md](references/buildings.md)
- **Люди и персонажи** → [references/humans.md](references/humans.md)
- **Экспорт в движок, LOD, коллизии, текстуры** → [references/export.md](references/export.md)

Читай только нужный файл.

## 3. Бюджеты (сверь с gdd.md, раздел 8)

| Ассет | mobile | pc |
|-------|--------|-----|
| Герой-персонаж | 10–20k tris, 1–2 текстуры 1–2K | 40–100k tris, 4K для лица |
| NPC / толпа | 3–8k + LOD | 15–40k + 2–3 LOD |
| Здание (переднего плана) | 2–10k | 20–80k (модульный кит) |
| Texel density | ~256 px/m | ~512–1024 px/m |

## 4. Учёт и лицензии

Каждый импортированный или сгенерированный ассет — строка в `.gameforge/credits.md` (источник, лицензия, нужно ли указывать автора). AI-генерации — с сервисом и датой; права на коммерческое использование зависят от тарифа пользователя. Не моделируй узнаваемых реальных людей без их согласия и чужих персонажей/бренды.

## 5. Выход

Ассет в `.blend` (исходник, `art/blender/`) + экспорт в папку движка + скрин из движка рядом с референсом. Задача в backlog закрывается только после проверки **в движке** (масштаб, материалы, LOD переключаются, коллизии работают).
