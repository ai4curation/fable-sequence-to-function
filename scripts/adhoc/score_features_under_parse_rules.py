"""Rescore test 2 for Opus 4.6 under three rules for replies with more than one JSON object: unparsed (as
committed), first object, last object. Copies the scorer, truth and results to a temp dir per rule; the
repository files are not changed. Inputs: experiments/features/. Output: stdout. Serves issue #50. 2026-11-18."""
import json, pathlib, shutil, subprocess, sys, tempfile
SRC = pathlib.Path("experiments/features"); dec = json.JSONDecoder()
def blocks(text):
    out, i = [], 0
    while (i := text.find("{", i)) >= 0:
        try: obj, n = dec.raw_decode(text[i:]); out.append(obj); i += n
        except Exception: i += 1
    return [b for b in out if isinstance(b, dict)]
for rule in ("unparsed", "first", "last"):
    d = pathlib.Path(tempfile.mkdtemp()); (d / "results").mkdir()
    shutil.copy(SRC / "score.py", d); shutil.copy(SRC / "truth.json", d)
    with open(d / "results" / "claude-opus-4-6.jsonl", "w") as fh:
        for l in open(SRC / "results" / "claude-opus-4-6.jsonl"):
            r = json.loads(l)
            if not r.get("ans") and rule != "unparsed":
                b = blocks(r["text"]); r["ans"] = b[0] if rule == "first" else b[-1]
            fh.write(json.dumps(r) + "\n")
    out = subprocess.run([sys.executable, str(d / "score.py")], capture_output=True, text=True).stdout
    print(f"##### rule: {rule}"); print("\n".join(l for l in out.splitlines() if "set all" in l or "any Pfam" in l or "TM:" in l or l.startswith("==")))
    shutil.rmtree(d)
