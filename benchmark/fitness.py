"""Task-fitness eval for the local models. Usage: fitness.py MODELS_DIR OUT_JSON"""
import json, os, re, subprocess, sys, time, glob

M, OUT = sys.argv[1], sys.argv[2]
ML = f"{M}/paraphrase-multilingual-MiniLM-L12-v2_PureRust"
SM = f"{M}/SmolLM2_135MInstruct-PureRust"
WH = f"{M}/Cactus_Whistle-Pure_Rust"
MC = f"{M}/mc"
ND = f"{M}/needle-rs"
EVAL = os.path.dirname(os.path.abspath(__file__))
R = {}


def run(cmd, cwd=None, timeout=300):
    t = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace")
    return p.stdout.strip(), p.stderr.strip(), time.time() - t


# ---------- MiniLM: which file holds X? (real source, hand-labelled)
def minilm():
    roots = {"wh": f"{WH}/src", "ml": f"{ML}/src", "sm": f"{SM}/src", "mc": f"{MC}/rust/src"}
    docs = {}
    for k, root in roots.items():
        for f in glob.glob(f"{root}/**/*.rs", recursive=True):
            name = k + "/" + os.path.relpath(f, root).replace("\\", "/")
            body = open(f, encoding="utf-8", errors="replace").read()
            docs[name] = name + "\n" + body[:800]
    Q = [
        ("reads the WAV file and resamples audio", "wh/audio.rs"),
        ("mel filterbank and STFT", "wh/frontend.rs"),
        ("beam search and silence gate", "wh/model.rs"),
        ("SentencePiece detokenizer", "wh/tokenizer.rs"),
        ("Unicode NFKC normalization", "ml/nfkc.rs"),
        ("compare outputs bit for bit with the reference", "ml/verify.rs"),
        ("minimal JSON parser", "ml/json.rs"),
        ("decode the ONNX protobuf file", "sm/onnx.rs"),
        ("thread pool implementation", "sm/pool.rs"),
        ("greedy token generation with repetition penalty", "sm/generate.rs"),
        ("image center crop and resize to 256", "mc/preprocess.rs"),
        ("matrix multiply micro kernel", "mc/kernels/gemm.rs"),
        ("convolution kernels", "mc/kernels/conv.rs"),
        ("rank image embedding against text labels", "mc/textbank.rs"),
        ("custom error type", "mc/error.rs"),
        # Greek queries against mostly-English source
        ("διάβασμα αρχείου ήχου WAV", "wh/audio.rs"),
        ("κανονικοποίηση Unicode", "ml/nfkc.rs"),
        ("δεξαμενή νημάτων", "sm/pool.rs"),
        ("προεπεξεργασία εικόνας", "mc/preprocess.rs"),
        ("αναζήτηση δέσμης για την αποκωδικοποίηση", "wh/model.rs"),
    ]
    names = list(docs)
    texts = [docs[n] for n in names]
    # embed once: argv would overflow on Windows, so go through --batchless per-chunk calls
    vecs = {}
    t0 = time.time()
    for i in range(0, len(texts), 6):
        out, err, _ = run([f"{ML}/target/release/minilm", "embed", "--model", f"{ML}/model", *texts[i:i + 6]])
        d = json.loads(out)
        dim = d["dims"][-1]
        flat = d["data"] if not isinstance(d["data"][0], list) else [x for v in d["data"] for x in v]
        for j in range(len(texts[i:i + 6])):
            vecs[names[i + j]] = flat[j * dim:(j + 1) * dim]
    index_s = time.time() - t0
    out, _, _ = run([f"{ML}/target/release/minilm", "embed", "--model", f"{ML}/model", *[q for q, _ in Q]])
    d = json.loads(out)
    dim = d["dims"][-1]
    flat = d["data"] if not isinstance(d["data"][0], list) else [x for v in d["data"] for x in v]
    rows = []
    for i, (q, gold) in enumerate(Q):
        qv = flat[i * dim:(i + 1) * dim]
        sc = sorted(((sum(a * b for a, b in zip(qv, vecs[n])), n) for n in names), reverse=True)
        rank = [n for _, n in sc].index(gold) + 1
        rows.append({"q": q, "gold": gold, "rank": rank, "top": sc[0][1], "score": round(sc[0][0], 3)})
    # unanswerable queries: does a score threshold separate them?
    neg = ["kubernetes ingress controller yaml", "postgres connection pooling", "React useEffect cleanup", "τιμολόγηση πελατών"]
    out, _, _ = run([f"{ML}/target/release/minilm", "embed", "--model", f"{ML}/model", *neg])
    d = json.loads(out)
    flat = d["data"] if not isinstance(d["data"][0], list) else [x for v in d["data"] for x in v]
    negs = []
    for i, q in enumerate(neg):
        qv = flat[i * dim:(i + 1) * dim]
        negs.append({"q": q, "best": round(max(sum(a * b for a, b in zip(qv, vecs[n])) for n in names), 3)})
    en, el = rows[:15], rows[15:]
    pct = lambda rs, k: sum(r["rank"] <= k for r in rs) / len(rs)
    R["minilm"] = {"corpus": len(names), "index_s": round(index_s, 1),
                   "en_top1": pct(en, 1), "en_top3": pct(en, 3), "en_top5": pct(en, 5),
                   "el_top1": pct(el, 1), "el_top3": pct(el, 3), "el_top5": pct(el, 5),
                   "rows": rows, "unanswerable": negs}


# ---------- SmolLM: small agent chores with deterministic scoring
LOG = "Compiling foo v0.1.0\nerror[E0308]: mismatched types\n --> src/main.rs:42:9\nerror: could not compile `foo` due to 1 previous error"
TESTS = "test a ... ok\ntest b ... ok\ntest c ... FAILED\ntest d ... ok\n\ntest result: FAILED. 3 passed; 1 failed; 0 ignored"
SMOL = [
    ("extract-line", f"{LOG}\n\nWhich line number has the error? Reply with the number only.", r"\b42\b", None),
    ("extract-file", f"{LOG}\n\nWhich file has the error? Reply with the path only.", r"src/main\.rs", None),
    ("extract-code", f"{LOG}\n\nWhat is the error code? Reply with the code only.", r"E0308", None),
    ("count-failed", f"{TESTS}\n\nHow many tests failed? Reply with the number only.", r"\b1\b", r"\b3\b"),
    ("which-failed", f"{TESTS}\n\nWhich test failed? Reply with its name only.", r"\bc\b", None),
    ("yesno-pass", f"{TESTS}\n\nDid all tests pass? Reply yes or no.", r"(?i)\bno\b", r"(?i)\byes\b"),
    ("yesno-pass2", "test a ... ok\ntest result: ok. 1 passed; 0 failed\n\nDid all tests pass? Reply yes or no.", r"(?i)\byes\b", r"(?i)\bno\b"),
    ("classify-err", "Traceback: ModuleNotFoundError: No module named 'x'\n\nIs this a missing dependency or a syntax error? Reply with one of: dependency, syntax.", r"(?i)dependency", r"(?i)syntax"),
    ("classify-err2", "  File \"a.py\", line 3\n    def f(:\nSyntaxError: invalid syntax\n\nIs this a missing dependency or a syntax error? Reply with one of: dependency, syntax.", r"(?i)syntax", r"(?i)dependency"),
    ("code-return", "def add(a, b):\n    return a * b\n\nDoes this function correctly add two numbers? Reply yes or no.", r"(?i)\bno\b", r"(?i)\byes\b"),
    ("negation", "The migration does not drop the users table.\n\nDoes the migration drop the users table? Reply yes or no.", r"(?i)\bno\b", r"(?i)\byes\b"),
    ("summary-keep-number", "Build finished in 42 seconds with 3 warnings and 0 errors. Summarize in one short sentence.", r"(?=.*\b42\b)(?=.*\b3\b)", None),
    ("commit-msg", "Diff: renamed getUser to fetchUser in api.py.\n\nWrite a one-line commit message.", r"(?i)fetchUser", None),
    ("greek-extract", "Το build απέτυχε στη γραμμή 17 του αρχείου app.py.\n\nΣε ποια γραμμή απέτυχε; Απάντησε μόνο με τον αριθμό.", r"\b17\b", None),
    ("greek-yesno", "Όλα τα τεστ πέρασαν.\n\nΠέρασαν τα τεστ; Απάντησε ναι ή όχι.", r"(?i)ναι|yes", r"(?i)όχι|no\b"),
    ("no-answer", "Build finished in 42 seconds.\n\nWhat is the author's email? If unknown, reply unknown.", r"(?i)unknown", r"@"),
]


def smol():
    rows = []
    for name, prompt, good, bad in SMOL:
        out, _, dt = run([f"{SM}/target/release/smollm2", "generate", "--model", f"{SM}/model", prompt], cwd=SM)
        ok = bool(re.search(good, out, re.S)) and not (bad and re.search(bad, out))
        rows.append({"t": name, "ok": ok, "s": round(dt, 1), "out": out[:160]})
    R["smollm"] = {"pass": sum(r["ok"] for r in rows), "n": len(rows), "rows": rows}


# ---------- Needle: route a request to a tool
TOOLS = [
    {"name": "read_file", "description": "Read a file from disk", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "search_code", "description": "Search source code for a text pattern", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
    {"name": "run_tests", "description": "Run the project's test suite", "parameters": {"type": "object", "properties": {"filter": {"type": "string"}}, "required": []}},
    {"name": "git_commit", "description": "Create a git commit", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
    {"name": "fetch_url", "description": "Download a web page", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "delete_file", "description": "Delete a file from disk", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]
NEEDLE = [
    ("Open config.toml", "read_file", "config.toml"),
    ("Show me what is in src/main.rs", "read_file", "src/main.rs"),
    ("Find where parse_header is used", "search_code", "parse_header"),
    ("grep for TODO in the code", "search_code", "TODO"),
    ("Run the tests", "run_tests", None),
    ("Run only the auth tests", "run_tests", "auth"),
    ("Commit with the message fix login bug", "git_commit", "fix login bug"),
    ("Get https://example.com/docs", "fetch_url", "https://example.com/docs"),
    ("Remove old.log", "delete_file", "old.log"),
    ("Delete the temp file build.tmp", "delete_file", "build.tmp"),
    ("Άνοιξε το αρχείο config.toml", "read_file", "config.toml"),
    ("Τρέξε τα τεστ", "run_tests", None),
    ("Βρες πού χρησιμοποιείται το parse_header", "search_code", "parse_header"),
    ("Σβήσε το old.log", "delete_file", "old.log"),
    # must not call a dangerous tool / no tool fits
    ("What's the capital of France?", None, None),
    ("Do not delete old.log, just read it", "read_file", "old.log"),
]


def needle():
    out = {}
    for w, flags in (("needle3", ["--json", "--constrain"]), ("needle2", ["--json"])):
        rows = []
        for q, tool, arg in NEEDLE:
            o, e, dt = run([f"{ND}/target/release/needle-rs", *flags, f"{ND}/weights/{w}.cact", q, json.dumps(TOOLS)])
            try:
                calls = json.loads(o[o.index("["):o.rindex("]") + 1])
            except Exception:
                calls = []
            name = calls[0]["name"] if calls else None
            args = json.dumps(calls[0].get("arguments", {}), ensure_ascii=False) if calls else ""
            ok = name == tool and (arg is None or arg in args)
            rows.append({"q": q, "ok": ok, "got": name, "args": args[:80], "s": round(dt, 1)})
        out[w] = {"pass": sum(r["ok"] for r in rows), "n": len(rows), "rows": rows}
    R["needle"] = out


# ---------- Whistle: synthetic English speech with technical words, noise, silence
PHRASES = [
    "Please fix the bug in the login function and run the tests again.",
    "The server returned an error because the database connection timed out.",
    "Deploy the new version to staging after the review is finished.",
    "Rename the variable and update the documentation.",
    "Open the config file and change the port to eight thousand.",
    "Add a retry to the download step in the build script.",
]


def wer(ref, hyp):
    a, b = re.findall(r"[a-z']+", ref.lower()), re.findall(r"[a-z']+", hyp.lower())
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (x != y))
    return d[-1] / max(1, len(a))


def whistle():
    wd = f"{EVAL}/wav"
    os.makedirs(wd, exist_ok=True)
    rows = []
    for i, ph in enumerate(PHRASES):
        f = f"{wd}/{i}.wav".replace("/", "\\")
        ps = f"Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.SetOutputToWaveFile('{f}');$s.Speak('{ph}');$s.Dispose()"
        subprocess.run(["powershell", "-NoProfile", "-c", ps], check=True)
        o, e, dt = run([f"{WH}/target/release/whistle", "--model", f"{WH}/whistle.cact", f])
        rows.append({"ref": ph, "hyp": o, "wer": round(wer(ph, o), 2), "s": round(dt, 1)})
    # silence must produce nothing; a 1 kHz tone must not invent speech
    import struct, wave
    sil = f"{wd}/silence.wav"
    with wave.open(sil, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(struct.pack("<h", 0) * 16000 * 3)
    o_sil, _, _ = run([f"{WH}/target/release/whistle", "--model", f"{WH}/whistle.cact", sil])
    o_tone, _, _ = run([f"{WH}/target/release/whistle", "--model", f"{WH}/whistle.cact", f"{WH}/tests/data/whistle_demo_1khz.wav"])
    R["whistle"] = {"mean_wer": round(sum(r["wer"] for r in rows) / len(rows), 3), "rows": rows, "silence": o_sil[:120], "tone": o_tone[:120]}


# ---------- MobileCLIP: does the fixed text bank tell image kinds apart?
def mobileclip():
    from PIL import Image, ImageDraw
    labels = json.load(open(f"{MC}/text-bank/labels.json", encoding="utf-8"))["labels"]
    wd = f"{EVAL}/img"
    os.makedirs(wd, exist_ok=True)
    kinds = {}
    im = Image.new("RGB", (800, 500), "#1e1e1e"); d = ImageDraw.Draw(im)
    for i in range(24):
        d.text((20, 10 + i * 20), f"fn main() {{ let x = {i}; println!(\"{{}}\", x); }}", fill="#9cdcfe")
    im.save(f"{wd}/code.png"); kinds["code.png"] = r"(?i)code|screen|text|computer|program|terminal|document"
    im = Image.new("RGB", (800, 500), "white"); d = ImageDraw.Draw(im)
    for i, h in enumerate([120, 300, 200, 380, 90, 260]):
        d.rectangle([60 + i * 115, 460 - h, 140 + i * 115, 460], fill="#3366cc")
    d.line([40, 460, 780, 460], fill="black", width=2); d.line([40, 20, 40, 460], fill="black", width=2)
    im.save(f"{wd}/chart.png"); kinds["chart.png"] = r"(?i)chart|graph|diagram|plot"
    im = Image.new("RGB", (800, 500), "#f3f3f3"); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 800, 50], fill="#2b579a"); d.rectangle([250, 150, 550, 190], outline="gray", fill="white")
    d.rectangle([250, 210, 550, 250], outline="gray", fill="white"); d.rectangle([250, 280, 550, 325], fill="#2b579a")
    im.save(f"{wd}/form.png"); kinds["form.png"] = r"(?i)screen|interface|website|web|form|app|computer"
    for f in glob.glob("C:/Windows/Web/Wallpaper/Theme*/img2*.jpg")[:4]:
        kinds[f] = None
    rows = []
    for f, want in kinds.items():
        p = f if os.path.isabs(f) else f"{wd}/{f}"
        o, e, dt = run([f"{MC}/rust/target/release/mobileclip-s0", "--root", MC, "--top", "3", p])
        rows.append({"img": os.path.basename(f), "out": o[:200], "ok": bool(want and re.search(want, o)) if want else "manual", "s": round(dt, 1)})
    ui = [l for l in labels if re.search(r"(?i)screen|code|chart|graph|diagram|website|text|document", l)]
    R["mobileclip"] = {"n_labels": len(labels), "ui_labels": ui[:40], "rows": rows}


only = sys.argv[3:] 
for fn in [f for f in (minilm, smol, needle, whistle, mobileclip) if not only or f.__name__ in only]:
    try:
        fn()
    except Exception as e:
        R[fn.__name__ + "_ERROR"] = repr(e)
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done")
