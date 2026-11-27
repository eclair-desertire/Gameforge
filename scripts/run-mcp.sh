#!/usr/bin/env bash
# Launch a GameForge MCP server over stdio: voxel | fx | music.
#   bash run-mcp.sh voxel          — run the server (Claude Code does this from .mcp.json)
#   bash run-mcp.sh --install      — prepare the Python environment once (recommended after install)
#   bash run-mcp.sh --selftest     — import both servers and render a tiny test
# Uses `uv` if available (cached, no global installs); otherwise a private venv in
# ${GAMEFORGE_VENV:-~/.cache/gameforge/venv}. stdout is the MCP channel: all logs go to stderr.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
srv_dir="$root/mcp-servers"
deps=("mcp>=1.10" "numpy>=1.26" "pillow>=10")
venv="${GAMEFORGE_VENV:-$HOME/.cache/gameforge/venv}"

python_cmd() {
  if command -v uv >/dev/null 2>&1; then
    local w=(); for d in "${deps[@]}"; do w+=(--with "$d"); done
    echo "uv run --quiet --no-project ${w[*]} python"
    return
  fi
  if [ ! -x "$venv/bin/python" ] || ! "$venv/bin/python" -c 'import mcp, numpy, PIL' 2>/dev/null; then
    command -v python3 >/dev/null 2>&1 || { echo "gameforge: need python3 (3.10+) or uv" >&2; exit 1; }
    echo "gameforge: creating Python env in $venv (one time)…" >&2
    python3 -m venv "$venv" >&2
    "$venv/bin/pip" install --quiet --disable-pip-version-check "${deps[@]}" >&2
  fi
  echo "$venv/bin/python"
}

case "${1:-}" in
  voxel|fx|music)
    py="$(python_cmd)"
    # shellcheck disable=SC2086
    exec $py "$srv_dir/$1/server.py" ;;
  --install)
    py="$(python_cmd)"; $py -c 'import mcp, numpy, PIL; print("gameforge MCP env ok")' ;;
  --selftest)
    py="$(python_cmd)"
    $py - "$srv_dir" <<'PY'
import sys, tempfile, pathlib
root = pathlib.Path(sys.argv[1]); sys.path[:0] = [str(root), str(root / "voxel"), str(root / "fx")]
import voxcore as V, fxcore as F
sc = V.Scene("t"); m = sc.add_model("c", (24, 16, 36)); V.gen_character(sc, m, height=32); V.shade(sc, m)
d = pathlib.Path(tempfile.mkdtemp())
V.save_vox(sc, d / "c.vox"); V.export_mesh(sc, d / "c.glb")
fr, meta = F.render_effect("hit", size=64); F.write_effect(fr, meta, d, "hit")
sys.path.insert(0, str(root / "music")); import musiccore as MU, audio as AU
song = MU.compose({"genre": "chiptune", "bars": 4, "seed": 1}); x, _ = AU.render(song, "chip"); AU.write_wav(d / "music.wav", x)
song = MU.compose({"genre": "synthwave", "bars": 4, "seed": 1}); x, _ = AU.render(song, "synth"); AU.write_wav(d / "synth.wav", x)
print("selftest ok:", sorted(p.name for p in d.iterdir()))
PY
    ;;
  *) echo "usage: run-mcp.sh voxel|fx|music|--install|--selftest" >&2; exit 2 ;;
esac
