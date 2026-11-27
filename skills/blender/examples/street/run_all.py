"""Rebuild the whole example scene in order (each step clears its own collection)."""
import os
steps = ["10_townhouse_shell.py", "20_townhouse_windows.py", "30_townhouse_details.py", "40_townhouse_roof.py", "50_street_props.py", "55_neighbours.py", "60_light_render.py", "70_human.py"]
d = os.environ.get("GF_SCRIPTS", os.path.expanduser("~/Documents/GameForge-examples/scripts"))
log = {}
for s in steps:
    g = {"__name__": "__gf__"}
    exec(open(os.path.join(d, s)).read(), g)
    log[s] = g.get("result")
result = log
