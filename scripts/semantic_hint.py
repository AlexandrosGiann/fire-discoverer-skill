#!/usr/bin/env python3
"""Rank doc sections against a query with local MiniLM. Prints the top 5 as score path:line."""
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~/.fire-discoverer")
MAX_CHUNKS, CHUNK_CHARS, BATCH = 60, 400, 20


def chunks(path):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    start, out = 0, []
    for i, line in enumerate(lines + ["# end"]):
        if re.match(r"#{1,3} ", line) and i > start:
            text = " ".join(lines[start:i]).strip()
            if text:
                out.append((f"{path}:{start + 1}", text[:CHUNK_CHARS]))
            start = i
    return out


def embed(texts):
    exe = os.path.join(HOME, "bin", "minilm")
    run = subprocess.run([exe, "embed", "--model", os.path.join(HOME, "minilm-model"), *texts],
                         capture_output=True, encoding="utf-8", check=True)
    data = json.loads(run.stdout)
    dim = data["dims"][-1]
    flat = data["data"] if not isinstance(data["data"][0], list) else [x for v in data["data"] for x in v]
    return [flat[i * dim:(i + 1) * dim] for i in range(len(texts))]


def main():
    if len(sys.argv) < 3:
        sys.exit('usage: semantic_hint.py "query" file...')
    query, items = sys.argv[1], []
    for path in sys.argv[2:]:
        items += chunks(path)
    skipped = max(0, len(items) - MAX_CHUNKS)
    items = items[:MAX_CHUNKS]
    if not items:
        sys.exit("no text found")
    vectors = []
    for i in range(0, len(items), BATCH):
        vectors += embed([text for _, text in items[i:i + BATCH]])
    q = embed([query])[0]
    scored = sorted(((sum(a * b for a, b in zip(q, v)), items[i][0]) for i, v in enumerate(vectors)), reverse=True)
    sys.stdout.reconfigure(encoding="utf-8")
    for score, where in scored[:5]:
        print(f"{score:.2f} {where}")
    if skipped:
        print(f"skipped {skipped} sections: pass fewer files")


if __name__ == "__main__":
    main()
