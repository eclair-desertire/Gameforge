#!/usr/bin/env bash
# SessionStart-хук (startup, resume, clear, compact).
# Если в проекте есть .gameforge/ — выводит Claude память проекта:
# паспорт (context.md), этап (state.md) и последние записи истории (history.md).
# В остальных проектах молчит.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$PWD}"
gf="$root/.gameforge"
[ -d "$gf" ] || exit 0

state="$gf/state.md"
context="$gf/context.md"
history="$gf/history.md"

field() { sed -n "s/^$1: *//p" "$state" 2>/dev/null | head -1; }
# убрать HTML-комментарии (и однострочные, и многострочные)
strip_comments() { perl -0pe 's/<!--.*?-->//gs' "$1"; }

echo "=== GameForge: память проекта (из .gameforge/) ==="

if [ -f "$state" ]; then
  echo "Этап: $(field stage) | движок: $(field engine) $(field engine_version) | трек: $(field track) | обновлено: $(field updated)"
  next="$(sed -n '/^## Следующий шаг/,/^## /p' "$state" | sed '1d;/^## /d' | grep -v '^[[:space:]]*$' | head -3)"
  [ -n "$next" ] && echo "Следующий шаг: $next"
fi

if [ -f "$context" ]; then
  echo
  echo "--- context.md ---"
  # без HTML-комментариев и пустых строк, не больше 150 строк
  strip_comments "$context" | grep -v '^[[:space:]]*$' | head -150
else
  echo "(context.md нет — создай его по шаблону: скилл gameforge:project-memory)"
fi

if [ -f "$history" ]; then
  echo
  echo "--- последние записи history.md ---"
  # две последние записи «## …» (файл дописывается в конец)
  awk '/^## /{n++} {buf[n]=buf[n] $0 "\n"} END{s=(n>1)?n-1:1; for(i=s;i<=n;i++) printf "%s", buf[i]}' \
    <(strip_comments "$history") | grep -v '^[[:space:]]*$' | head -40
fi

echo
echo "GDD: .gameforge/gdd.md (читай нужный раздел). Правила ведения памяти — скилл gameforge:project-memory; навигация по этапам — gameforge:studio."
exit 0
