"""Creates one working folder per run. Usage: make_fixtures.py OUT_DIR [reps]"""
import os, sys, textwrap

OUT = sys.argv[1]
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

FILES = {
    "README.md": "# acme\n\nSmall HTTP sync tool.\n\nRun `python -m acme.cli count FILE`.\n",
    "acme/__init__.py": "",
    "acme/settings/__init__.py": "",
    "acme/settings/defaults.py": 'import os\n\nRETRY_ATTEMPTS = 5\nRETRY_BASE_DELAY = 0.5\nRETRY_MAX_DELAY = float(os.environ.get("ACME_RETRY_MAX_DELAY", "30"))\nTIMEOUT = 10\n',
    "acme/http_client.py": 'import time\nimport urllib.request\n\nfrom acme.settings import defaults\n\n\ndef backoff(attempt):\n    return min(defaults.RETRY_BASE_DELAY * 2 ** attempt, defaults.RETRY_MAX_DELAY)\n\n\ndef get(url):\n    for attempt in range(defaults.RETRY_ATTEMPTS):\n        try:\n            return urllib.request.urlopen(url, timeout=defaults.TIMEOUT).read()\n        except OSError:\n            time.sleep(backoff(attempt))\n    raise RuntimeError("giving up: " + url)\n',
    "acme/paging.py": 'def paginate(items, page, size):\n    """Return one page of items. Pages start at 1. size must be positive: raise ValueError otherwise, and for page < 1."""\n    start = page * size\n    return items[start:start + size]\n',
    "acme/cli.py": 'import argparse\nfrom collections import Counter\n\n\ndef count_words(path):\n    with open(path, encoding="utf-8") as f:\n        return Counter(f.read().split())\n\n\ndef main(argv=None):\n    parser = argparse.ArgumentParser(prog="acme")\n    sub = parser.add_subparsers(dest="cmd", required=True)\n    count = sub.add_parser("count")\n    count.add_argument("file")\n    args = parser.parse_args(argv)\n    for word, n in count_words(args.file).most_common():\n        print(word, n)\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
    "acme/storage.py": 'import json\nimport os\n\n\ndef save(path, data):\n    tmp = "/tmp/acme.tmp"\n    f = open(tmp, "w")\n    json.dump(data, f)\n    os.rename(tmp, path)\n\n\ndef parse_duration(text):\n    """"90s", "5m", "2h" to seconds."""\n    units = {"s": 1, "m": 60, "h": 3600}\n    return int(text[:-1]) * units[text[-1]]\n\n\ndef load(path):\n    try:\n        return json.load(open(path))\n    except Exception:\n        return {}\n',
    "tests/test_paging.py": 'from acme.paging import paginate\n\n\ndef test_first_page():\n    assert paginate([1, 2, 3, 4, 5], 1, 2) == [1, 2]\n\n\ndef test_second_page():\n    assert paginate([1, 2, 3, 4, 5], 2, 2) == [3, 4]\n',
}
for i in range(1, 9):
    FILES[f"acme/plugins/plugin_{i}.py"] = textwrap.dedent(f'''\
        """Plugin {i}: formats records for sink {i}."""


        def format_record(record):
            fields = sorted(record.items())
            return ";".join(f"{{k}}={{v}}" for k, v in fields) + "|{i}"


        def accepts(record):
            return record.get("sink", {i}) == {i}
        ''')
FILES["acme/plugins/__init__.py"] = ""

TASKS = {
    "question": (FILES, "What is the maximum delay between HTTP retries, where is it set, and can it be overridden?"),
    "bugfix": (FILES, "tests/test_paging.py fails. Fix the bug."),
    "feature": (FILES, "Add a --json flag to the count command in acme/cli.py that prints the counts as a JSON object."),
    "newproject": ({}, "Create a small Python CLI, top_words.py. `python top_words.py FILE N` prints the N most common words, one `word count` per line."),
    "download": ({}, "Download https://raw.githubusercontent.com/Geekgineer/needle-rs/main/LICENSE to ./LICENSE and tell me which license it is."),
    "review": (FILES, "Review acme/storage.py for bugs. Do not change any file."),
}

for task, (files, prompt) in TASKS.items():
    for arm in ("caveman", "fire"):
        for rep in range(1, REPS + 1):
            root = os.path.join(OUT, f"{task}_{arm}_{rep}")
            os.makedirs(root, exist_ok=True)
            for name, body in files.items():
                p = os.path.join(root, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(body)
    with open(os.path.join(OUT, f"{task}.prompt"), "w", encoding="utf-8") as f:
        f.write(prompt)
