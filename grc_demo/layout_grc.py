"""Adds block positions to the generated .grc files (the generator leaves them unset, so blocks pile up)."""
import sys, yaml, glob, collections
SIMPLE = {"variable","variable_qtgui_range","variable_qtgui_push_button","variable_qtgui_label","variable_qtgui_chooser",
          "variable_qtgui_check_box","import","variable_qtgui_entry"}
for fn in sys.argv[1:]:
    d = yaml.safe_load(open(fn))
    blocks = d["blocks"]; names = [b["name"] for b in blocks]
    byname = {b["name"]: b for b in blocks}
    succ = collections.defaultdict(list); pred = collections.defaultdict(list)
    for c in d.get("connections", []):
        a, b = c[0], c[2]
        succ[a].append(b); pred[b].append(a)
    chain = [n for n in names if byname[n]["id"] not in SIMPLE]
    var = [n for n in names if byname[n]["id"] in SIMPLE]
    depth = {}
    def dep(n, seen=()):
        if n in depth: return depth[n]
        if n in seen: return 0
        p = [x for x in pred[n] if x in chain]
        depth[n] = 0 if not p else 1 + max(dep(x, seen + (n,)) for x in p)
        return depth[n]
    for n in chain: dep(n)
    # variables / sliders: wrapped rows at the top
    x0, y0, W = 20, 70, 260
    per = 5
    for i, n in enumerate(var):
        byname[n].setdefault("states", {})
        byname[n]["states"]["coordinate"] = [x0 + (i % per) * W, y0 + (i // per) * 110]
        byname[n]["states"]["rotation"] = 0
        byname[n]["states"].setdefault("state", "enabled")
    ytop = y0 + ((len(var) + per - 1) // per) * 110 + 60
    cols = collections.defaultdict(list)
    for n in chain: cols[depth[n]].append(n)
    for c, lst in cols.items():
        for r, n in enumerate(lst):
            st = byname[n].setdefault("states", {})
            st["coordinate"] = [x0 + c * 300, ytop + r * 130]
            st["rotation"] = 0
            st.setdefault("state", "enabled")
    yaml.safe_dump(d, open(fn, "w"), sort_keys=False, default_flow_style=False)
    print(fn, len(var), "variables,", len(chain), "blocks in", len(cols), "columns")
