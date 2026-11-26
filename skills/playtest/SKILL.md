---
name: playtest
description: Проводит QA и плейтест игры — автотесты движка, прогон в playmode/headless с проверкой консоли и FPS, скриншоты, наблюдения, баги в backlog и вывод keep/kill/retune в .gameforge/playtests/NNN.md. Используй после закрытия milestone, перед релизом, или когда просят протестировать игру, найти баги, проверить что всё работает.
---

# Playtest — QA и решение по итерации

## 1. Автоматика (агент делает сам)

Прогон автотестов и сборки — агенту `runner` (haiku) с точными командами из engine-скилла; разбор логов — `scout`. Себе — оценку ощущений, keep/kill/retune.

По engine-скиллу проекта:

| Проверка | Unity | Godot | Unreal |
|----------|-------|-------|--------|
| Компиляция | `unity recompile` (редактор открыт) / `unity status` | `godot --headless --check-only -s <script>` или `--import` | `Build.sh <Target>Editor Mac Development` |
| Unit/логика | `unity test <p> --mode EditMode --output …` | GUT/gdUnit4 в `--headless` | `UnrealEditor-Cmd … -ExecCmds="Automation RunTests <filter>;Quit"` |
| Интеграция | `unity test <p> --mode PlayMode` | headless-сцена-тест с ненулевым exit code при фейле | Functional Tests |
| Живой прогон | playmode-verification loop из `unity:unity-cli` (см. engine-unity) | MCP `run_project` → `get_debug_output` → `stop_project` | PIE через MCP/Python, лог `Saved/Logs` |

Для живого прогона обязательно убедись, что **игра реально идёт** (кадры/время растут), а не застыла на первом кадре; прочитай консоль на исключения; сделай 1–3 скриншота ключевых моментов.

## 2. Сценарии

Пройди сценарии из критериев задач milestone + «злые» кейсы: пауза/сворачивание (mobile), смена разрешения, геймпад отключён на ходу, двойной тап/клик, ресурс уходит в минус, сохранение посреди действия.

## 3. Человеческий плейтест

Агент не заменяет живого игрока для «весело ли». Подготовь пользователю:
- что проверить руками (3–5 вопросов: понятно ли, что делать; где скучно; где нечестно);
- для внешних тестеров — короткую анкету и билд (gameforge:release, раздел «тестовые сборки»).

## 4. Отчёт

Создай `.gameforge/playtests/NNN.md` по `templates/playtest.md`. Баги — в `backlog.md` → «Баги» с серьёзностью S1 (крэш/блокер) … S4 (косметика).

## 5. Решение (ворота prototype / production)

Предложи пользователю **keep / retune / kill** с аргументами из отчёта. Для mobile после тест-публикации — метрики через gameforge:live. Запиши решение в журнал `state.md`.

Большой прогон отдай агенту `qa-playtester`.
