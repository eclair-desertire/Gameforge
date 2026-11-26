title: {{TITLE}}
engine: {{ENGINE}}
engine_version: {{ENGINE_VERSION}}
track: {{TRACK}}
stage: setup
platforms: {{PLATFORMS}}
tools: {{TOOLS}}
review: lean
updated: {{DATE}}

<!--
Этапы: setup → concept → design → prototype → production → polish → release → live
track: mobile | pc | both
tools: инструменты проекта для автопроверки при старте сессии, через пробел: unity godot unreal blender aseprite gimp blockbench flstudio voxel fx ffmpeg
review: lean | full — строгость ворот ревью команды (gameforge:team); по умолчанию lean
Поля выше читает хук SessionStart (scripts/status.sh) — сохраняй формат `ключ: значение`.
-->

## Ворота этапов

- [ ] setup — движок определён, CLI/MCP проверены, .gameforge/ создан
- [ ] concept — concept.md заполнен, вердикт «делаем» записан
- [ ] design — gdd.md: core loop, 3 столпа, scope и cut list
- [ ] prototype — играбельный core loop, плейтест, решение keep / kill / retune
- [ ] production — вертикальный срез готов, контент по backlog.md
- [ ] polish — juice, аудио, UI, производительность в бюджете
- [ ] release — сборки прошли чеклист, страница стора / сабмит
- [ ] live — метрики собираются, план апдейтов

## Следующий шаг

Запустить gameforge:concept.

## Журнал решений

<!-- YYYY-MM-DD — решение — почему. Крупные технические решения → .gameforge/decisions/ADR-NNNN.md -->
