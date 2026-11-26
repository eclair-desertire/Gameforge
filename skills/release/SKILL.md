---
name: release
description: Готовит и выпускает сборки игры — релизные билды Unity/Godot/Unreal под платформы, CI, тестовые сборки, Steam (SteamPipe, страница, демо, вишлисты), itch.io (butler), Google Play и App Store, веб-порталы — с чеклистом в .gameforge/releases/. Используй, когда просят собрать билд, настроить CI, выпустить игру, залить в Steam/itch/стор, подготовить страницу магазина.
---

# Release — сборки и публикация

**Всё, что уходит наружу (загрузка в Steam/стор, публикация страницы, отправка на ревью), делай только после явного «да» пользователя.** Ключи, пароли, keystore-пароли агент не вводит — пользователь вводит сам или через переменные окружения/секреты CI.

## 1. Сборка по движку

| Движок | Локальная сборка | CI |
|--------|------------------|----|
| Unity | `unity build <p> --list-profiles`, затем `unity build <p> --profile "<name>" --output-path ./Build/<...>` или `--target <Target>` | `unity ci init` (генерирует пайплайн) — см. `unity:unity-cli` |
| Godot | `godot --headless --path <p> --export-release "<preset>" <out>`; пресеты в `export_presets.cfg`, шаблоны экспорта должны быть установлены | GitHub Actions с образом godot-ci / barichello |
| Unreal | `<UE>/Engine/Build/BatchFiles/RunUAT.sh BuildCookRun -project=<p>.uproject -platform=<Mac|Win64|Android|IOS> -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory=<out>` | self-hosted раннер (UE тяжёлый) |

После сборки: запусти билд (`unity build run`, исполняемый файл Godot/UE) и проверь, что стартует и доходит до геймплея. Shipping/Release-конфигурация, а не Development.

## 2. Чеклист релиза — `.gameforge/releases/<version>.md`

- [ ] Версия и build number подняты (PlayerSettings / project.godot `config/version` / DefaultGame.ini)
- [ ] Нет debug-меню, читов, логов в релизе; ассерты не роняют билд
- [ ] Иконки, сплэш, имя приложения, bundle id
- [ ] Сохранения совместимы с прошлой версией
- [ ] Размер билда в бюджете; первый запуск < N секунд
- [ ] Прогон gameforge:playtest на релизной сборке, S1/S2 багов — 0
- [ ] Changelog для игроков
- [ ] `.gameforge/credits.md` сверен с титрами игры (все CC-BY и прочие атрибуции указаны)

## 3. Платформы

### Steam (pc)
Ассеты страницы, трейлер, Next Fest, стримеры — gameforge:marketing; здесь только техническая часть.
- Страница стора **задолго до релиза** (с этапа production): капсулы всех размеров, 5+ скриншотов, трейлер, короткое описание, теги. Вишлисты — главная метрика до релиза.
- SteamPipe: `app_build_<appid>.vdf` + `depot_build_<depotid>.vdf`, загрузка `steamcmd +login <user> +run_app_build <vdf> +quit` — логин пользователь делает сам (Steam Guard).
- Ветки: `beta` для тестеров, `default` — после проверки. Демо — отдельный app id. Steam Next Fest — подать заранее.
- Steam Deck: проверка контроллера, текста ≥ 9 px при 1280×800, Proton.

### itch.io
- `butler push <dir> <user>/<game>:<channel>` (каналы `windows`, `mac`, `linux`, `html5`). Для HTML5 — SharedArrayBuffer/COOP-COEP, если нужно (Godot 4 web).

### Mobile
- Android: AAB, подпись upload key (keystore хранит пользователь), target API актуальный, Play Console → internal testing → closed → production.
- iOS: Xcode-проект из Unity/Godot/UE, signing в Xcode, TestFlight → ревью.
- Монетизация: Unity — `unity:levelplay-unity-integration`, `unity:implement-in-app-purchases`. Политика конфиденциальности и согласие (GDPR/ATT) — обязательно.
- Бесплатное продвижение и порталы (CrazyGames, Poki, Яндекс Игры) — `game-trend-skills:launching-on-zero-budget`.

## 4. После релиза

`state.md`: ворота release, `stage: live`, «Следующий шаг: gameforge:live (собрать метрики за D1/D7)».
