"""MiniLM on prose docs vs a keyword baseline. Usage: prose.py MODELS_DIR"""
import json, re, subprocess, sys, unicodedata
M = sys.argv[1]; sys.stdout.reconfigure(encoding="utf-8")
ML = f"{M}/paraphrase-multilingual-MiniLM-L12-v2_PureRust"
DOCS = {"wh": f"{M}/Cactus_Whistle-Pure_Rust/README.md", "ml": f"{ML}/README.md", "sm": f"{M}/SmolLM2_135MInstruct-PureRust/README.md",
        "mc": f"{M}/mc/rust/README.md", "nd": f"{M}/needle-rs/ARCHITECTURE.md", "nb": f"{M}/needle-rs/BENCHMARKS.md", "nc": f"{M}/needle-rs/CONTRIBUTING.md", "cj": f"{M}/mc/README.md"}
sec = {}
for k, f in DOCS.items():
    for part in re.split(r"(?m)^## ", open(f, encoding="utf-8").read())[1:]:
        h = part.split("\n", 1)[0].strip(); sec[f"{k}:{h}"] = h + "\n" + part[:1500]
Q = [("how long does it take to process one picture", "mc:Speed"), ("is the output exactly the same as the official engine", "wh:Verification"),
     ("call it from my own program", "wh:Use it from code"), ("where do the weights come from", "mc:Model files"),
     ("how is the picture prepared before inference", "mc:Preprocessing"), ("which parts of the code do what", "wh:Files"),
     ("how to compile the binary and try a clip", "wh:Build and run"), ("how was correctness tested for the image model", "mc:Validation"),
     ("πόσο γρήγορα τρέχει το μοντέλο εικόνας", "mc:Speed"), ("πώς το καλώ από τον δικό μου κώδικα", "wh:Use it from code"),
     ("πώς προετοιμάζεται η εικόνα", "mc:Preprocessing"), ("τι διαφέρει από την έκδοση JavaScript", "wh:Differences"),
     ("πού βρίσκω τα αρχεία του μοντέλου", "mc:Model files"), ("how do I build and run the sentence embedding tool", "ml:Εκτέλεση"),
     ("was the embedding port tested against WebAssembly", "ml:Επαλήθευση"), ("how do I download the chat model", "sm:Εκτέλεση")]
names = list(sec); print("sections", len(names))
for _, g in Q:
    assert any(n.startswith(g) for n in names), g
def embed(ts):
    out = []
    for i in range(0, len(ts), 6):
        d = json.loads(subprocess.run([f"{ML}/target/release/minilm", "embed", "--model", f"{ML}/model", *ts[i:i+6]], capture_output=True, encoding="utf-8").stdout)
        dim = d["dims"][-1]; fl = d["data"] if not isinstance(d["data"][0], list) else [x for v in d["data"] for x in v]
        out += [fl[j*dim:(j+1)*dim] for j in range(len(ts[i:i+6]))]
    return out
V = embed([sec[n] for n in names]); QV = embed([q for q, _ in Q])
norm = lambda s: re.findall(r"\w+", unicodedata.normalize("NFD", s.lower()))
def rank(order, g): return next(i+1 for i, n in enumerate(order) if n.startswith(g))
sem, kw = [], []
for (q, g), qv in zip(Q, QV):
    s = sorted(names, key=lambda n: -sum(a*b for a, b in zip(qv, V[names.index(n)])))
    ws = set(norm(q)); k = sorted(names, key=lambda n: -len(ws & set(norm(sec[n]))))
    sem.append(rank(s, g)); kw.append(rank(k, g)); print(sem[-1], kw[-1], q, "->", s[0])
p = lambda r, k: sum(x <= k for x in r) / len(r)
print("minilm top1/top3", p(sem, 1), p(sem, 3), "| keyword top1/top3", p(kw, 1), p(kw, 3))
