#!/usr/bin/env python3
"""GameForge preflight: are the apps, CLIs and MCP servers a task needs installed, configured
and running? Stdlib only. Russian report for the user, exit 0 = all ready, 1 = action needed.

  python3 check-tools.py aseprite gimp          # specific tools
  python3 check-tools.py --task pixel-art        # tools a skill needs
  python3 check-tools.py all                     # everything
  python3 check-tools.py --json voxel fx         # machine-readable

Statuses: ok | missing (install) | off (installed but not running/enabled) | config (MCP not in
.mcp.json) | warn (optional / cannot verify).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)

TASKS = {
    "pixel-art": ["aseprite", "fx"],
    "art-2d": ["gimp", "fx"],
    "vfx": ["fx"],
    "voxel": ["voxel"],
    "lowpoly": ["blockbench"],
    "blender": ["blender"],
    "humans": ["blender", "mpfb"],
    "music": ["flstudio", "ffmpeg"],
    "audio": ["ffmpeg"],
    "unity": ["unity"],
    "godot": ["godot"],
    "unreal": ["unreal"],
}
ALL = ["git", "uv", "node", "ffmpeg", "voxel", "fx", "blender", "mpfb", "aseprite", "gimp", "blockbench", "flstudio", "unity", "godot", "unreal"]


def which(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def first(*patterns):
    for pat in patterns:
        hits = sorted(glob.glob(os.path.expanduser(pat)))
        if hits:
            return hits[-1]
    return None


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except OSError:
        return False


def app_version(app: str) -> str:
    plist = Path(app) / "Contents" / "Info.plist"
    if not plist.exists():
        return ""
    try:
        out = subprocess.run(["defaults", "read", str(plist.with_suffix("")), "CFBundleShortVersionString"], capture_output=True, text=True, timeout=3)
        return out.stdout.strip()
    except Exception:
        return ""


CMDS: dict[str, str] = {}  # server name -> "command args..." (to check which implementation)
ENVS: dict[str, dict] = {}  # server name -> env


def mcp_servers() -> dict[str, str]:
    """name -> where it is configured (project .mcp.json, user/local scope in ~/.claude.json)."""
    found: dict[str, str] = {}

    def take(servers: dict, where: str):
        for k, v in (servers or {}).items():
            if k not in found:
                found[k] = where
                if isinstance(v, dict):
                    CMDS[k] = " ".join([str(v.get("command", "")), *map(str, v.get("args", [])), str(v.get("url", ""))])
                    ENVS[k] = v.get("env") or {}

    pj = PROJECT / ".mcp.json"
    if pj.exists():
        try:
            take(json.loads(pj.read_text()).get("mcpServers", {}), "проект (.mcp.json)")
        except ValueError:
            found["__broken__"] = f"{pj} — битый JSON"
    cj = HOME / ".claude.json"
    if cj.exists():
        try:
            d = json.loads(cj.read_text())
            take(((d.get("projects") or {}).get(str(PROJECT), {})).get("mcpServers", {}), "локально для проекта (~/.claude.json)")
            take(d.get("mcpServers", {}), "пользователь (~/.claude.json)")
        except ValueError:
            pass
    return found


def configured(servers: dict[str, str], *keys: str):
    for name, where in sorted(servers.items(), key=lambda kv: "community" in kv[0]):
        low = name.lower()
        if any(k in low for k in keys):
            return name, where
    return None


R: list[dict] = []


def add(tool, status, msg, fix=""):
    R.append({"tool": tool, "status": status, "msg": msg, "fix": fix})


# ------------------------------------------------------------------ checks


def c_git():
    p = which("git")
    add("git", "ok" if p else "missing", p or "git не найден", "" if p else "xcode-select --install")


def c_uv():
    p = which("uvx")
    add("uv", "ok" if p else "missing", p or "uv/uvx не найден (нужен для Blender/GIMP/FL Studio MCP)", "" if p else "brew install uv")


def c_node():
    p = which("npx")
    add("node", "ok" if p else "missing", p or "Node.js/npx не найден (нужен для Blockbench bbmodel, Godot MCP)", "" if p else "brew install node")


def c_ffmpeg():
    p = which("ffmpeg")
    add("ffmpeg", "ok" if p else "missing", p or "ffmpeg не найден", "" if p else "brew install ffmpeg")


def c_builtin(name):
    venv = Path(os.environ.get("GAMEFORGE_VENV", HOME / ".cache/gameforge/venv"))
    if which("uv"):
        add(name, "ok", f"gameforge-{name}: встроен в плагин, запуск через uv")
        return
    py = venv / "bin" / "python"
    if py.exists():
        r = subprocess.run([str(py), "-c", "import mcp, numpy, PIL"], capture_output=True)
        if r.returncode == 0:
            add(name, "ok", f"gameforge-{name}: встроен в плагин, окружение {venv}")
            return
    if not which("python3"):
        add(name, "missing", f"gameforge-{name}: нужен python3 3.10+ или uv", "brew install uv")
        return
    add(name, "missing", f"gameforge-{name}: Python-окружение ещё не создано (создастся при первом запуске, ~1 мин)", f'bash "{PLUGIN_ROOT}/scripts/run-mcp.sh" --install')


def blender_addon():
    """('official'|'community'|None, path). Official = Blender Lab extension with manifest maintainer Blender Lab."""
    for man in sorted(glob.glob(os.path.expanduser("~/Library/Application Support/Blender/*/extensions/*/*/blender_manifest.toml")), reverse=True):
        txt = Path(man).read_text(errors="ignore")
        if "Blender Lab" in txt and 'id = "mcp"' in txt:
            return "official", str(Path(man).parent)
    hit = first("~/Library/Application Support/Blender/*/scripts/addons/*blender*mcp*", "~/Library/Application Support/Blender/*/scripts/addons/addon.py", "~/Library/Application Support/Blender/*/extensions/*/*blender*mcp*")
    return ("community", hit) if hit else (None, None)


def c_blender(servers):
    app = first("/Applications/Blender.app") or which("blender")
    if not app:
        add("blender", "missing", "Blender не установлен", "brew install --cask blender  (или blender.org)")
        return
    add("blender", "ok", f"Blender {app_version(app) or ''} — {app}".strip())
    kind, path = blender_addon()
    if kind == "official":
        add("blender", "ok", f"аддон: официальный Blender Lab MCP — {path}")
    elif kind == "community":
        add("blender", "ok", f"аддон: mcp-for-blender (community) — {path}")
    else:
        add("blender", "missing", "MCP-аддон в Blender не найден", "Blender 5.1+: Preferences → Get Extensions → репозиторий https://lab.blender.org/ → MCP (официальный); или uvx mcp-for-blender install-addon")
    hit = configured(servers, "blender")
    if not hit:
        tpl = "blender" if kind != "community" else "blender-community"
        add("blender", "config", "MCP для blender не прописан", f"gameforge:doctor — сервер «{tpl}» из mcp-templates/blender.json")
    else:
        cmd = CMDS.get(hit[0], "")
        impl = "official" if "projects.blender.org/lab" in cmd else ("community" if ("mcp-for-blender" in cmd or "blender-mcp" in cmd) else None)
        if kind and impl and impl != kind:
            add("blender", "config", f"MCP «{hit[0]}» ({impl}) не подходит к аддону ({kind}) — протоколы разные", "gameforge:doctor — заменить на сервер под установленный аддон (mcp-templates/blender.json)")
        else:
            add("blender", "ok", f"MCP «{hit[0]}» прописан: {hit[1]}")
            if impl == "official" and "BLENDER_PATH" not in ENVS.get(hit[0], {}):
                add("blender", "config", f"у MCP «{hit[0]}» не задан BLENDER_PATH — фоновые *_for_cli-инструменты не работают",
                    f"gameforge:doctor — добавить env BLENDER_PATH={app}/Contents/MacOS/Blender" if app.endswith(".app") else "gameforge:doctor — добавить env BLENDER_PATH=<бинарник Blender>")
    on = port_open(9876)
    start = ("Blender → Preferences → System → Network → включить Allow Online Access (без неё расширения не открывают даже локальный порт), "
             "затем Preferences → Add-ons → MCP → Start MCP Bridge Server (или галка Auto-start)") if kind == "official" else "Blender → N-панель → MCP → Start MCP Server"
    add("blender", "ok" if on else "off", "сервер в Blender на :9876 " + ("отвечает" if on else "не отвечает (Blender закрыт или сервер не запущен)"), "" if on else start)


def c_mpfb(servers):
    """MPFB2 (MakeHuman for Blender) + CC0 system assets — needed for realistic humans."""
    ext = first("~/Library/Application Support/Blender/*/extensions/*/mpfb/blender_manifest.toml")
    if ext:
        v = re_version(Path(ext).read_text(errors="ignore"))
        add("mpfb", "ok", f"MPFB {v} — {Path(ext).parent}")
    else:
        add("mpfb", "missing", "MPFB2 (генератор людей для Blender) не установлен",
            "gameforge:doctor → MPFB: Get Extensions «MPFB» или (если extensions.blender.org медленный) архив тега с github.com/makehumancommunity/mpfb2 → src/mpfb → package_install_files")
    data = first("~/Library/Application Support/Blender/*/extensions/.user/*/mpfb/data")
    skins = data and os.path.isdir(os.path.join(data, "skins")) and os.listdir(os.path.join(data, "skins"))
    if skins:
        add("mpfb", "ok", f"ассеты MakeHuman (CC0): {len(skins)} скинов, одежда/волосы/глаза — {data}")
    else:
        add("mpfb", "missing", "системные ассеты MakeHuman (кожа, глаза, волосы, одежда) не установлены",
            "gameforge:doctor → MPFB: makehuman_system_assets_cc0.zip (280 МБ, зеркало files.makehumancommunity.org) → распаковать в user data MPFB")


def re_version(txt):
    for line in txt.splitlines():
        if line.startswith("version"):
            return line.split("=")[1].strip().strip('"')
    return ""


def c_aseprite(servers):
    app = first("/Applications/Aseprite.app", "~/Library/Application Support/Steam/steamapps/common/Aseprite/Aseprite.app") or which("aseprite")
    if app:
        add("aseprite", "ok", f"Aseprite {app_version(app)} — {app}".strip())
    else:
        add("aseprite", "missing", "Aseprite не установлен (платный: Steam / itch / aseprite.org — покупает пользователь)", "купить и установить Aseprite; без него — пиксель-арт через gameforge-fx")
    srv = os.environ.get("ASEPRITE_MCP_DIR") or first("~/Tools/aseprite-mcp", "~/Documents/GitHub/aseprite-mcp", "~/aseprite-mcp")
    if srv and Path(srv, "pyproject.toml").exists():
        add("aseprite", "ok", f"aseprite-mcp: {srv}")
    else:
        add("aseprite", "missing", "aseprite-mcp (diivi) не склонирован", "git clone https://github.com/diivi/aseprite-mcp ~/Tools/aseprite-mcp  (нужны uv и Python 3.13+)")
    c_mcp(servers, "aseprite", ("aseprite", "pixel"), "aseprite.json")


def c_gimp(servers):
    app = first("/Applications/GIMP.app", "/Applications/GIMP-3*.app", "/Applications/GIMP*.app")
    if not app:
        add("gimp", "missing", "GIMP не установлен (нужен 3.2+)", "brew install --cask gimp")
        return
    v = app_version(app)
    old = v and tuple(int(x) for x in v.split(".")[:2] if x.isdigit()) < (3, 2)
    add("gimp", "missing" if old else "ok", f"GIMP {v} — {app}" + (" — для MCP нужен 3.2+" if old else ""), "обновить GIMP до 3.2+ (gimp.org или brew upgrade --cask gimp) — делает пользователь" if old else "")
    plug = first("~/Library/Application Support/GIMP/3.*/plug-ins/*mcp*")
    add("gimp", "ok" if plug else "missing", f"плагин GIMP MCP: {plug}" if plug else "плагин GIMP MCP не установлен", "" if plug else "uvx gimp-mcp-plugin@latest install-plugin → перезапустить GIMP")
    c_mcp(servers, "gimp", ("gimp",), "gimp.json")
    ok = port_open(int(os.environ.get("GIMP_MCP_PORT", 9877)))
    add("gimp", "ok" if ok else "off", "сервер GIMP на :9877 " + ("отвечает" if ok else "не отвечает"), "" if ok else "GIMP → MCP → Start Server (или включить автозапуск в том же диалоге)")


def c_blockbench(servers):
    app = first("/Applications/Blockbench.app")
    add("blockbench", "ok" if app else "missing", f"Blockbench — {app}" if app else "Blockbench не установлен", "" if app else "brew install --cask blockbench")
    c_mcp(servers, "blockbench", ("blockbench", "bbmodel"), "blockbench.json")
    ok = port_open(3000)
    add("blockbench", "ok" if ok else "off", "плагин MCP на :3000 " + ("отвечает" if ok else "не отвечает"), "" if ok else "Blockbench → File → Plugins → Load from URL: https://jasonjgardner.github.io/blockbench-mcp-plugin/mcp.js")


def c_flstudio(servers):
    app = first("/Applications/FL Studio*.app")
    add("flstudio", "ok" if app else "missing", f"FL Studio {app_version(app) if app else ''} — {app}" if app else "FL Studio не установлен (платный — решение пользователя)", "" if app else "установить FL Studio 2025+ (image-line.com)")
    script = first("~/Documents/Image-Line/FL Studio/Settings/Hardware/*MCP*", "~/Documents/Image-Line/FL Studio/Settings/Hardware/*mcp*")
    add("flstudio", "ok" if script else "missing", f"controller script: {script}" if script else "controller script FL Studio MCP не установлен", "" if script else "uvx --from git+https://github.com/rosasynthesiz/flstudio-mcp fl-studio-mcp setup → открыть FL Studio")
    c_mcp(servers, "flstudio", ("flstudio", "fl-studio", "fl_studio", "fruity"), "flstudio.json")


def c_unity(servers):
    p = which("unity")
    add("unity", "ok" if p else "missing", f"Unity CLI — {p}" if p else "Unity CLI не найден", "" if p else "см. gameforge:engine-unity (установка Unity CLI — с согласия)")
    c_mcp(servers, "unity", ("unity",), "unity.json", optional=True)


def c_godot(servers):
    p = which("godot") or first("/Applications/Godot*.app")
    add("godot", "ok" if p else "missing", f"Godot — {p}" if p else "Godot не найден", "" if p else "brew install --cask godot")
    c_mcp(servers, "godot", ("godot",), "godot.json", optional=True)


def c_unreal(servers):
    p = first("/Users/Shared/Epic Games/UE_*")
    add("unreal", "ok" if p else "missing", f"Unreal Engine — {p}" if p else "Unreal Engine не найден", "" if p else "Epic Games Launcher → Unreal Engine")
    c_mcp(servers, "unreal", ("unreal",), "unreal.json", optional=True)


def c_mcp(servers, tool, keys, template, optional=False):
    hit = configured(servers, *keys)
    if hit:
        add(tool, "ok", f"MCP «{hit[0]}» прописан: {hit[1]}")
    else:
        add(tool, "warn" if optional else "config", f"MCP для {tool} не прописан в проекте", f"gameforge:doctor — добавить из mcp-templates/{template} в .mcp.json, затем перезапустить сессию / /mcp")


CHECKS = {
    "git": lambda s: c_git(),
    "uv": lambda s: c_uv(),
    "node": lambda s: c_node(),
    "ffmpeg": lambda s: c_ffmpeg(),
    "voxel": lambda s: c_builtin("voxel"),
    "fx": lambda s: c_builtin("fx"),
    "blender": c_blender,
    "mpfb": lambda s: c_mpfb(s),
    "aseprite": c_aseprite,
    "gimp": c_gimp,
    "blockbench": c_blockbench,
    "flstudio": c_flstudio,
    "unity": c_unity,
    "godot": c_godot,
    "unreal": c_unreal,
}
NEEDS_UV = {"blender", "gimp", "flstudio", "aseprite"}
NEEDS_NODE = {"blockbench"}

ICON = {"ok": "[ok]   ", "missing": "[нет]  ", "off": "[выкл] ", "config": "[mcp]  ", "warn": "[?]    "}


def main(argv):
    as_json = "--json" in argv
    brief = "--brief" in argv  # for the SessionStart hook: only problems, nothing if all ready
    args = [a for a in argv if a not in ("--json", "--brief")]
    tools: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--task":
            tools += TASKS.get(args[i + 1], [])
            i += 2
            continue
        tools += ALL if args[i] == "all" else [args[i]]
        i += 1
    if not tools:
        print(__doc__)  # also: --brief (problems only, for hooks)
        return 2
    unknown = [t for t in tools if t not in CHECKS]
    if unknown:
        print(f"неизвестно: {unknown}. Доступно: {list(CHECKS)}, задачи: {list(TASKS)}")
        return 2
    if NEEDS_UV & set(tools) and "uv" not in tools:
        tools.insert(0, "uv")
    if NEEDS_NODE & set(tools) and "node" not in tools:
        tools.insert(0, "node")
    servers = mcp_servers()
    seen = set()
    for t in tools:
        if t not in seen:
            seen.add(t)
            CHECKS[t](servers)
    blocking = [r for r in R if r["status"] in ("missing", "off", "config")]
    if brief:
        line = lambda r: f"  - {r['tool']}: {r['msg']}" + (f" → {r['fix']}" if r["fix"] else "")
        need = [r for r in R if r["status"] in ("missing", "config")]
        off = [r for r in R if r["status"] == "off"]
        if need:
            print("--- ИНСТРУМЕНТЫ: требуется установка/настройка (скажи пользователю явно, затем gameforge:doctor) ---")
            print("\n".join(map(line, need)))
        if off:
            print("--- Не запущено сейчас (понадобится в работе — попроси пользователя запустить) ---")
            print("\n".join(map(line, off)))
        return 1 if blocking else 0
    if as_json:
        print(json.dumps({"project": str(PROJECT), "ready": not blocking, "results": R}, ensure_ascii=False, indent=1))
    else:
        print(f"GameForge: проверка инструментов для {PROJECT}")
        for r in R:
            line = f"{ICON[r['status']]}{r['tool']}: {r['msg']}"
            if r["fix"] and r["status"] != "ok":
                line += f"\n         → {r['fix']}"
            print(line)
        if blocking:
            print("\nИТОГ: ТРЕБУЕТСЯ УСТАНОВКА/ВКЛЮЧЕНИЕ — " + ", ".join(sorted({r['tool'] for r in blocking})) + ". См. gameforge:doctor.")
        else:
            print("\nИТОГ: всё готово.")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
