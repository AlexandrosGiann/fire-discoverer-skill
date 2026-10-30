# Local models

Installed in `~/.fire-discoverer` by `scripts/setup-models.sh`. Missing and needed: ask once, then announce the download. Output is a hint or draft, not proof.

| Task | Command | Limits |
|---|---|---|
| Audio to text | `~/.fire-discoverer/bin/whistle --model ~/.fire-discoverer/whistle.cact clip.wav` | en, de, fr, es, it, nl, pl only. Not Greek. WAV only. Check names and numbers. |
| Find docs when Grep found nothing, or query and docs differ in language | `python <skill-dir>/scripts/semantic_hint.py "query" file...` | Candidates only: read before claiming. Never conclude "not found" from it. Not for code. |
| Sort 20+ photos by rough subject | `~/.fire-discoverer/bin/mobileclip-s0 --root ~/.fire-discoverer/mobileclip --top 3 a.jpg b.jpg` | Fixed labels. Cannot read text or screenshots. No landmarks. Read the image when the answer matters. |

Never use SmolLM2 or Needle: they failed the reliability tests in `benchmark/RESULTS.md`.
