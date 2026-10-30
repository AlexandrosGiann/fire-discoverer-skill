"""Cache-neutral token cost per run. Usage: cost.py GROUP=LIST_FILE... (each list file names transcripts)

The first call's context (system prompt, tools) is excluded: its cache hit or miss depends on run order.
Later calls: new context at 1.25, context already seen at 0.1, output at 5.
"""
import json, re, sys
from collections import defaultdict
from statistics import mean, stdev

sys.stdout.reconfigure(encoding="utf-8")
rows = []
for spec in sys.argv[1:]:
    group, listing = spec.split("=", 1)
    for path in open(listing, encoding="utf-8").read().split():
        name, seen, ctx, out = None, set(), [], 0
        for line in open(path, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "user" and name is None:
                c = d["message"]["content"]
                m = re.search(r"runs\\+(\w+_(caveman|fire)_\d+)", c if isinstance(c, str) else json.dumps(c))
                name = m and m.group(1)
            if d.get("type") == "assistant" and d["message"]["id"] not in seen:
                seen.add(d["message"]["id"])
                u = d["message"].get("usage", {})
                ctx.append(sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")))
                out += u.get("output_tokens", 0) or 0
        if not name:
            continue
        task, arm, _ = name.split("_")
        added = ctx[-1] - ctx[0]
        reread = sum(c - ctx[0] for c in ctx[:-1])
        rows.append({"group": group if arm == "fire" else "caveman", "task": task, "out": out, "added": added, "calls": len(ctx),
                     "cost": 1.25 * added + 0.1 * reread + 5 * out})

by = defaultdict(list)
for r in rows:
    by[r["group"], "ALL"].append(r)
    by[r["group"], r["task"]].append(r)
for (g, t), rs in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    sd = stdev(r["cost"] for r in rs) if len(rs) > 1 else 0
    print(f"{t:11}{g:9}n={len(rs):<3}out={mean(r['out'] for r in rs):<7.0f}added={mean(r['added'] for r in rs):<7.0f}calls={mean(r['calls'] for r in rs):<5.1f}cost={mean(r['cost'] for r in rs):<8.0f}sd={sd:.0f}")
