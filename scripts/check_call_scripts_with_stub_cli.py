"""Exercise the four model-calling scripts against a stub `claude` executable. No model is called.

Copies experiments/ (without results) to a temp dir, puts a stub named `claude` first on PATH and checks:
  1. every row records effort, attempts and prompt_sha256;
  2. a failed call writes an error row, and the next run moves it to retried_errors/ and asks again (#26);
  3. a reply with two JSON objects is read as the last one (#50);
  4. a reply with a written-out tool call has no answer and, in test 1, is invalid (#49).
Usage: check_call_scripts_with_stub_cli.py     Output: one line per check, exit 1 on failure.   2026-11-18
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parent.parent
STUB = r'''#!/usr/bin/env python3
import json, os, sys
q = sys.stdin.read(); mode = os.environ.get("STUB_MODE", "ok")
if mode == "fail": print("not json"); sys.exit(0)
one = {"pfam_domains": [], "catalytically_active": "yes", "helices": [[1, 5]], "protein_name": "first"}
two = dict(one, protein_name="second")
text = {"ok": json.dumps(one), "multi": json.dumps(one) + "\n\nCorrected version:\n\n" + json.dumps(two),
        "tool": "```bash\ncurl https://example.org\n```\n" + json.dumps(one), "peptide": "ACDEFGHIKL",
        "peptide_tool": "```bash\ncurl -d peps=ACDEFGHIKL https://example.org\n```"}[mode]
print(json.dumps({"result": text, "total_cost_usd": 0.0, "modelUsage": {"stub-model": {}}, "usage": {}, "is_error": False}))
'''
tmp = pathlib.Path(tempfile.mkdtemp()); exp = tmp / "experiments"
shutil.copytree(REPO / "experiments", exp, ignore=shutil.ignore_patterns("results", "retried_errors", "__pycache__"))
for t in ("features", "pseudo", "structure"): (exp / t / "results").mkdir()
(tmp / "bin").mkdir(); stub = tmp / "bin" / "claude"; stub.write_text(STUB); stub.chmod(0o755)
env = dict(os.environ, PATH=f"{tmp / 'bin'}{os.pathsep}{os.environ['PATH']}")
assert shutil.which("claude", path=env["PATH"]) == str(stub), "the stub is not first on PATH; refusing to run"
for t in ("features", "pseudo", "structure"):   # two questions' worth of truth is enough
    f = exp / t / "truth.json"; f.write_text(json.dumps(json.loads(f.read_text())[:2]))
fails = 0
def check(label, cond):
    global fails; fails += not cond; print(("ok   " if cond else "FAIL ") + label)
def run(script, mode, *args):
    p = subprocess.run([sys.executable, str(exp / script), "stub-model", *args], env=dict(env, STUB_MODE=mode), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-2000:]
def rows(path): return [json.loads(l) for l in open(path)] if pathlib.Path(path).exists() else []
for t in ("features", "pseudo", "structure"):
    out = exp / t / "results" / "stub-model.jsonl"; side = exp / t / "retried_errors" / "stub-model.jsonl"
    run(f"{t}/ask.py", "fail", "high"); R = rows(out); n = len(R)
    check(f"{t}: a failed call writes an error row with effort and 3 attempts", n > 0 and all(r.get("error") and r["effort"] == "high" and r["attempts"] == 3 for r in R))
    run(f"{t}/ask.py", "multi", "high"); R = rows(out)
    check(f"{t}: the errored questions are asked again, one row each", len(R) == n and not any("error" in r for r in R))
    check(f"{t}: the error rows are kept in retried_errors/", len(rows(side)) == n)
    check(f"{t}: rows record effort, attempts and a prompt hash", all(r["effort"] == "high" and r["attempts"] == 1 and len(r["prompt_sha256"]) == 64 for r in R))
    check(f"{t}: two JSON objects are read as the last one", all(r["ans"] and r["ans"]["protein_name"] == "second" for r in R))
    run(f"{t}/ask.py", "ok", "high"); check(f"{t}: a finished run asks nothing again", len(rows(out)) == n)
    out.unlink(); run(f"{t}/ask.py", "tool", "high")
    check(f"{t}: a reply with a tool call has no answer", all(r["ans"] is None for r in rows(out)))
out = exp / "next_residue" / "results" / "low" / "stub-model.jsonl"
run("next_residue/run.py", "fail", "low"); n = len(rows(out))
check("next_residue: failed calls write error rows", n > 0 and all("error" in r and r["attempts"] == 3 for r in rows(out)))
run("next_residue/run.py", "peptide", "low"); R = rows(out)
check("next_residue: errored questions are asked again, one row each", len(R) == n and not any("error" in r for r in R))
check("next_residue: rows record effort, attempts and a prompt hash", all(r["effort"] == "low" and r["attempts"] == 1 and len(r["prompt_sha256"]) == 64 and r["valid"] for r in R))
out.unlink(); run("next_residue/run.py", "peptide_tool", "low"); R = rows(out)
check("next_residue: a reply with a tool call is invalid and not correct", all(r["pred"] and not r["valid"] and not r["first_correct"] and not r["exact10"] for r in R))
shutil.rmtree(tmp); sys.exit(1 if fails else 0)
