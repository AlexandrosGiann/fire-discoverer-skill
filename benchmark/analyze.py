"""Scores runs and sums token use from subagent transcripts. Usage: analyze.py RUNS_DIR OUT_JSON TRANSCRIPT..."""
import json, os, re, subprocess, sys, tempfile
from collections import defaultdict
from statistics import mean, median

RUNS, OUT, FILES = sys.argv[1], sys.argv[2], sys.argv[3:]


def py(args, cwd):
    p = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, encoding="utf-8", errors="replace",
                       timeout=60, env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": cwd})
    return p.returncode, p.stdout, p.stderr


def check_paging(root):
    code = ("from acme.paging import paginate as p\n"
            "def r(*a):\n  try: return p(*a)\n  except ValueError: return 'VE'\n"
            "print([r([1,2,3,4,5],1,2)==[1,2], r([1,2,3,4,5],3,2)==[5], r([1],9,2)==[], r([],1,2)==[],"
            " r([1],1,0)=='VE', r([1],1,-1)=='VE', r([1],0,2)=='VE', r([1],-1,2)=='VE'])")
    rc, out, _ = py(["-c", code], root)
    return eval(out) if rc == 0 else [False] * 8


def check_feature(root):
    d = tempfile.mkdtemp()
    a, empty = os.path.join(d, "a.txt"), os.path.join(d, "e.txt")
    open(a, "w", encoding="utf-8").write("γάτα γάτα dog")
    open(empty, "w").close()
    res = []
    rc, out, _ = py(["-m", "acme.cli", "count", a, "--json"], root)
    try:
        res.append(json.loads(out) == {"γάτα": 2, "dog": 1})
    except ValueError:
        res.append(False)
    rc, out, _ = py(["-m", "acme.cli", "count", empty, "--json"], root)
    try:
        res.append(json.loads(out) == {})
    except ValueError:
        res.append(False)
    rc, out, _ = py(["-m", "acme.cli", "count", a], root)
    res.append("γάτα 2" in out and "{" not in out)
    rc, _, err = py(["-m", "acme.cli", "count", os.path.join(d, "none"), "--json"], root)
    res.append(rc != 0 and "Traceback" not in err)
    return res


def check_newproject(root):
    if not os.path.exists(os.path.join(root, "top_words.py")):
        return [False] * 6
    d = tempfile.mkdtemp()
    a, empty = os.path.join(d, "a.txt"), os.path.join(d, "e.txt")
    open(a, "w", encoding="utf-8").write("γάτα γάτα dog dog dog cat")
    open(empty, "w").close()
    t = "top_words.py"
    res = []
    rc, out, _ = py([t, a, "2"], root)
    res.append(out.split("\n")[0].split() == ["dog", "3"] and "γάτα 2" in out)
    rc, out, _ = py([t, a, "99"], root)
    res.append(rc == 0 and len(out.strip().split("\n")) == 3)
    rc, out, err = py([t, empty, "2"], root)
    res.append(rc == 0 and not out.strip() and "Traceback" not in err)
    rc, _, err = py([t, os.path.join(d, "none"), "2"], root)
    res.append(rc != 0 and "Traceback" not in err)
    rc, out, err = py([t, a, "x"], root)
    res.append(rc != 0 and "Traceback" not in err)
    rc, out, err = py([t, a, "-1"], root)
    res.append("Traceback" not in err and (rc != 0 or not out.strip()))
    return res


def check_download(root, text):
    p = os.path.join(root, "LICENSE")
    return [os.path.exists(p) and "MIT License" in open(p, encoding="utf-8").read(), "MIT" in text]


def check_question(text):
    return [bool(re.search(r"\b30\b", text)), "defaults.py" in text, "ACME_RETRY_MAX_DELAY" in text]


REVIEW = [r"/tmp|cross.?device|filesystem|different (drive|volume)|windows", r"clos|with open|flush|context manager|handle",
          r"KeyError|ValueError|IndexError|invalid|empty|malformed|bad input|negative",
          r"except|swallow|corrupt|silent", r"concurr|race|collision|same temp|shared|fixed (temp|path|name)|hardcoded|hard-coded|predictable|overwrit"]

ANNOUNCE_READ = re.compile(r"(?i)\b(read|reading|look|looking|check|checking|search|grep|inspect|διαβάζ|κοιτ|ψάχν)")
rows = []
for path in FILES:
    usage, seen, texts, tools = defaultdict(int), set(), [], []
    prefix, skills = 0, []
    name = None
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "user" and name is None:
            c = d["message"]["content"]
            s = c if isinstance(c, str) else json.dumps(c)
            m = re.search(r"runs\\+(\w+_(?:caveman|fire)_\d+)", s)
            if m:
                name = m.group(1)
        if d.get("type") != "assistant":
            continue
        msg = d["message"]
        if msg["id"] not in seen:
            if not seen:
                prefix = msg.get("usage", {}).get("cache_creation_input_tokens", 0) or 0
            seen.add(msg["id"])
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                usage[k] += msg.get("usage", {}).get(k, 0) or 0
        for b in msg["content"]:
            if b["type"] == "text" and b["text"].strip():
                texts.append(b["text"].strip())
            elif b["type"] == "tool_use" and b["name"] == "SubagentHandback":
                texts.append(b["input"].get("message", "").strip())
            elif b["type"] == "tool_use":
                tools.append(b["name"])
                if b["name"] == "Skill":
                    skills.append(b["input"].get("skill"))
    if not name:
        continue
    task, arm, rep = name.split("_")
    root = os.path.join(RUNS, name)
    final = texts[-1] if texts else ""
    if task == "bugfix":
        s = check_paging(root)
    elif task == "feature":
        s = check_feature(root)
    elif task == "newproject":
        s = check_newproject(root)
    elif task == "download":
        s = check_download(root, final)
    elif task == "question":
        s = check_question(final)
    else:
        s = [bool(re.search(r, final, re.I)) for r in REVIEW]
    interim = texts[:-1]
    # Price ratios for one model: input 1, cache write 1.25, cache read 0.1, output 5.
    weighted = (usage["input_tokens"] + 1.25 * usage["cache_creation_input_tokens"] + 0.1 * usage["cache_read_input_tokens"]
                + 5 * usage["output_tokens"])
    # Harness system prompt (same in both arms) removed: its first write plus its cache reads on later turns.
    marginal = weighted - 1.25 * prefix - 0.1 * prefix * (len(seen) - 1)
    rows.append({"run": name, "marginal": round(marginal), "skills": skills, "task": task, "arm": arm, **usage, "weighted": round(weighted), "turns": len(seen),
                 "tools": len(tools), "score": sum(s), "max": len(s), "checks": s, "final_chars": len(final),
                 "interim": len(interim), "interim_chars": sum(map(len, interim)),
                 "read_notices": sum(bool(ANNOUNCE_READ.search(t)) for t in interim), "interim_text": interim, "final": final})

json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
sys.stdout.reconfigure(encoding="utf-8")
print(f"{'task':11}{'arm':8}{'n':>2}{'output':>8}{'weighted':>10}{'marginal':>10}{'turns':>6}{'finalch':>8}{'interim':>8}{'score':>7}")
groups = defaultdict(list)
for r in rows:
    groups[r["task"], r["arm"]].append(r)
    groups["ALL", r["arm"]].append(r)
for (t, a), rs in sorted(groups.items()):
    print(f"{t:11}{a:8}{len(rs):>2}{mean(r['output_tokens'] for r in rs):>8.0f}{mean(r['weighted'] for r in rs):>10.0f}{mean(r['marginal'] for r in rs):>10.0f}"
          f"{mean(r['turns'] for r in rs):>6.1f}{mean(r['final_chars'] for r in rs):>8.0f}{mean(r['interim'] for r in rs):>8.1f}"
          f"{sum(r['score'] for r in rs)}/{sum(r['max'] for r in rs):<4}")
