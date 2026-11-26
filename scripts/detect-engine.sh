#!/usr/bin/env bash
# Определяет движок проекта по файлам-отпечаткам.
# Использование: detect-engine.sh [путь_к_проекту]
# Вывод (одна строка JSON): {"engine":"unity|godot|unreal|web|unknown","version":"...","root":"..."}
set -euo pipefail

dir="${1:-$PWD}"
dir="$(cd "$dir" && pwd)"

json() { printf '{"engine":"%s","version":"%s","root":"%s"}\n' "$1" "$2" "$3"; }

# Ищем вверх по дереву, но не выше $HOME.
d="$dir"
while [ "$d" != "/" ]; do
  if [ -f "$d/ProjectSettings/ProjectVersion.txt" ]; then
    v="$(sed -n 's/^m_EditorVersion: *//p' "$d/ProjectSettings/ProjectVersion.txt" | head -1)"
    json unity "${v:-?}" "$d"; exit 0
  fi
  if [ -f "$d/project.godot" ]; then
    v="$(grep -o 'config/features=PackedStringArray("[0-9.]*' "$d/project.godot" | grep -o '[0-9.]*$' | head -1 || true)"
    json godot "${v:-?}" "$d"; exit 0
  fi
  up="$(ls "$d"/*.uproject 2>/dev/null | head -1 || true)"
  if [ -n "$up" ]; then
    v="$(grep -o '"EngineAssociation"[^,}]*' "$up" | sed 's/.*: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | head -1 || true)"
    json unreal "${v:-?}" "$d"; exit 0
  fi
  if [ -f "$d/package.json" ] && grep -qE '"(phaser|three|pixi\.js|@react-three/fiber)"' "$d/package.json"; then
    json web "-" "$d"; exit 0
  fi
  [ "$d" = "$HOME" ] && break
  d="$(dirname "$d")"
done

json unknown "-" "$dir"
