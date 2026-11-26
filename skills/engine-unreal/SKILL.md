---
name: engine-unreal
description: Справочник GameForge по Unreal Engine 5 — пути к движку на macOS, сборка C++ через Build.sh/UBT, генерация проекта, автотесты из командной строки, BuildCookRun через RunUAT, Python в редакторе, Unreal MCP (официальный от Epic в UE 5.8+ или community), правила .uasset/Blueprint/C++. Используй в любом Unreal-проекте (есть *.uproject) перед сборкой, тестами, правкой ассетов, упаковкой или настройкой MCP.
---

# Unreal в GameForge

## Пути (macOS)

- Движок из Epic Launcher: `/Users/Shared/Epic Games/UE_<5.x>/`
- Редактор: `…/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor`
- Командный редактор: `…/Engine/Binaries/Mac/UnrealEditor-Cmd`
- Скрипты: `…/Engine/Build/BatchFiles/Mac/Build.sh`, `…/Engine/Build/BatchFiles/RunUAT.sh`
- Версия проекта: `EngineAssociation` в `<Game>.uproject`

Ниже `UE` = корень движка, `<P>` = абсолютный путь к `.uproject`, `<Game>` = имя проекта. Пути с пробелами — в кавычках.

## Сборка C++

```bash
"$UE/Engine/Build/BatchFiles/Mac/Build.sh" <Game>Editor Mac Development -Project="<P>" -WaitMutex
"$UE/Engine/Build/BatchFiles/Mac/GenerateProjectFiles.sh" -project="<P>" -game   # Xcode-проект
```

Ошибки компиляции — в выводе UBT; Live Coding не заменяет полную сборку для изменений в заголовках (UCLASS/UPROPERTY).

## Тесты

```bash
"$UE/Engine/Binaries/Mac/UnrealEditor-Cmd" "<P>" -ExecCmds="Automation RunTests <Filter>;Quit" \
  -unattended -nullrhi -nosplash -log -ReportExportPath="<P_dir>/Saved/TestReport"
```

Типы: Automation Spec / Simple Automation Tests (C++), Functional Tests (уровни-тесты), Gauntlet для длинных прогонов. Логи — `Saved/Logs/<Game>.log`.

## Упаковка

```bash
"$UE/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun -project="<P>" -platform=Mac \
  -clientconfig=Shipping -build -cook -stage -pak -iostore -archive -archivedirectory="<out>" -unattended -utf8output
```

Платформы: `Mac`, `Win64` (кросс-сборка с Mac невозможна — нужна Windows-машина/CI), `Android`, `IOS`, `Linux`. Ошибки кука — ищи `Error:` и `LogCook` в выводе UAT.

## Python в редакторе

Включить плагин *Python Editor Script Plugin*. Скрипт без UI:
```bash
"$UE/Engine/Binaries/Mac/UnrealEditor-Cmd" "<P>" -run=pythonscript -script="<abs>/tools/do_thing.py" -unattended -nullrhi
```
`unreal.EditorAssetLibrary`, `unreal.EditorLevelLibrary`/`EditorActorSubsystem` — для массовых правок ассетов и уровней вместо ручного кликанья.

## MCP

- **Официальный (Epic, UE 5.8+, экспериментальный):** MCP-сервер внутри процесса редактора, HTTP на `127.0.0.1:<порт>/mcp` (в доках Epic — 8000). Включается плагином в редакторе; Epic генерирует `.mcp.json` для Claude Code. Шаблон — `mcp-templates/unreal.json`. Редактор должен быть запущен.
- **UE < 5.8 — community:** `runreal/unreal-mcp` (через Python Remote Execution, UE 5.4+; включить Python-плагин и Remote Execution в настройках), `ChiR24/Unreal_mcp` (через Remote Control API). Перед установкой проверь актуальность репозитория и поддержку своей версии.

## Правила GameForge для Unreal

- `.uasset`/`.umap` — бинарные: **никогда не правь их текстом**. Только редактор, Python или MCP.
- Логика, которую надо тестировать и ревьюить, — в C++ (`UCLASS`, `UFUNCTION(BlueprintCallable)`); Blueprints — для контента, тюнинга и связки. Данные — DataTable/DataAsset.
- Ввод — Enhanced Input; ИИ — StateTree или Behavior Tree.
- Git: `.gitignore` UE (`Binaries/ Intermediate/ Saved/ DerivedDataCache/`), LFS для `*.uasset *.umap` и сырья; рассмотри Perforce/Git LFS locking для команды.
- Сборки тяжёлые: запускай долгие `Build.sh`/`RunUAT` в фоне и не дёргай их в цикле.

Глубже по подсистемам (Blueprints, C++ gameplay, Enhanced Input, Behavior Trees, Niagara, packaging) — скиллы `unreal-*` из `awesome-gamedev-agent-skills`, если установлен.
