#!/usr/bin/env bash
# Stop-хук: мягкое напоминание дописать .gameforge/history.md.
# Срабатывает, только если:
#   - в проекте есть .gameforge/history.md,
#   - файлы проекта менялись после последней записи в history.md,
#   - history.md не обновлялся дольше GAMEFORGE_HISTORY_MINUTES (по умолчанию 20) минут,
#   - напоминания не было последние GAMEFORGE_NAG_MINUTES (по умолчанию 45) минут.
# Не зацикливается: при stop_hook_active=true сразу выходит.
set -uo pipefail

input="$(cat || true)"
echo "$input" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true' && exit 0

root="${CLAUDE_PROJECT_DIR:-$PWD}"
history="$root/.gameforge/history.md"
[ -f "$history" ] || exit 0

mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
now="$(date +%s)"
hist_age=$(( (now - $(mtime "$history")) / 60 ))
[ "$hist_age" -lt "${GAMEFORGE_HISTORY_MINUTES:-20}" ] && exit 0

key="$(printf '%s' "$root" | cksum | cut -d' ' -f1)"
nag="${TMPDIR:-/tmp}/gameforge-nag-$key"
if [ -f "$nag" ] && [ $(( (now - $(mtime "$nag")) / 60 )) -lt "${GAMEFORGE_NAG_MINUTES:-45}" ]; then
  exit 0
fi

changed="$(find "$root" \
  \( -name .git -o -name Library -o -name Temp -o -name Logs -o -name obj -o -name Build -o -name Builds \
     -o -name .godot -o -name Intermediate -o -name Saved -o -name DerivedDataCache -o -name Binaries \
     -o -name node_modules -o -name archive \) -prune -o \
  -type f -newer "$history" ! -name '*.meta' ! -name '.DS_Store' -print 2>/dev/null | head -1)"
[ -z "$changed" ] && exit 0

touch "$nag"
cat <<'EOF'
{"decision":"block","reason":"GameForge: файлы проекта изменились, а .gameforge/history.md давно не обновлялся. Если в этой сессии сделана или решена значимая работа — допиши запись в конец history.md (Сделано / Решено / Проверено / Дальше), при новых решениях или терминах обнови context.md, при изменении механик — gdd.md и его «Историю изменений». Если изменения мелкие и записывать нечего — просто заверши ответ."}
EOF
exit 0
