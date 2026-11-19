"""Exercise the five model-calling scripts and the reply-reading rules against a stub `claude` executable.
No model is called.

Copies experiments/ (without results) to a temp dir, puts a stub named `claude` first on PATH and checks:
  1. the command line, working directory and question each script sends, against what its row records;
  2. every row records effort, attempts, a prompt hash, the flags and the token counts;
  3. a failed call, an API-error reply and a call with attached context are kept in the file, are not answers,
     and are asked again; rows already in the file are never rewritten (#26, #54, #56);
  4. a finished run asks nothing; a run at another effort on the same file stops (#60);
  5. --limit asks only that many questions and --tag writes to its own file;
  6. the reply-reading rules of common.py on the cases of #49, #50 and #61.
Usage: check_call_scripts_with_stub_cli.py     Output: one line per check, exit 1 on failure.   2026-11-18
"""
import contextlib, hashlib, io, json, os, pathlib, shutil, subprocess, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parent.parent
STUB = r'''#!/usr/bin/env python3
import hashlib, json, os, sys
if sys.argv[1:] == ["--version"]: print("0.0.0 (stub)"); sys.exit(0)
q = sys.stdin.read(); mode = os.environ.get("STUB_MODE", "ok")
with open(os.environ["STUB_LOG"], "a") as fh: fh.write(json.dumps(dict(argv=sys.argv[1:], cwd=os.getcwd(), stdin_sha256=hashlib.sha256(q.encode()).hexdigest())) + "\n")
if mode == "fail": print("not json"); sys.exit(0)
if mode == "apierror": print(json.dumps({"result": "API Error: overloaded", "is_error": True, "usage": {}, "modelUsage": {}})); sys.exit(0)
one = {"pfam_domains": [], "catalytically_active": "yes", "helices": [[1, 5]], "protein_name": "first"}
two = dict(one, protein_name="second")
text = {"ok": json.dumps(one), "bigctx": json.dumps(one), "multi": json.dumps(one) + "\n\nCorrected version:\n\n" + json.dumps(two),
        "tool": "```bash\ncurl https://example.org\n```\n" + json.dumps(one), "peptide": "ACDEFGHIKL",
        "peptide_tool": "```bash\ncurl -d peps=ACDEFGHIKL https://example.org\n```"}[mode]
usage = {"input_tokens": 90000 if mode == "bigctx" else 3, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0, "output_tokens": 50, "output_tokens_details": {"thinking_tokens": 7}}
print(json.dumps({"result": text, "total_cost_usd": 0.0, "modelUsage": {"stub-model": {}}, "usage": usage, "is_error": False}))
'''
tmp = pathlib.Path(tempfile.mkdtemp()); exp = tmp / "experiments"
shutil.copytree(REPO / "experiments", exp, ignore=shutil.ignore_patterns("results", "__pycache__"))
(tmp / "bin").mkdir(); stub = tmp / "bin" / "claude"; stub.write_text(STUB); stub.chmod(0o755)
LOG = tmp / "stub_calls.jsonl"; env = dict(os.environ, PATH=f"{tmp / 'bin'}{os.pathsep}{os.environ['PATH']}", STUB_LOG=str(LOG))
assert shutil.which("claude", path=env["PATH"]) == str(stub), "the stub is not first on PATH; refusing to run"
for t in ("features", "pseudo", "structure"):   # two questions' worth of truth is enough
    f = exp / t / "truth.json"; f.write_text(json.dumps(json.loads(f.read_text())[:2]))
f = exp / "decoy_control/decoys.json"; f.write_text(json.dumps(json.loads(f.read_text())[:2]))
sys.path.insert(0, str(exp)); import common
fails = 0
def check(label, cond):
    global fails; fails += not cond; print(("ok   " if cond else "FAIL ") + label)
def run(script, mode, *args, ok=True):
    if LOG.exists(): LOG.unlink()
    p = subprocess.run([sys.executable, str(exp / script), "stub-model", *args], env=dict(env, STUB_MODE=mode), capture_output=True, text=True)
    assert (p.returncode == 0) == ok, p.stderr[-2000:]
    return p
def rows(path): return [json.loads(l) for l in open(path)] if pathlib.Path(path).exists() else []
def lines(path): return open(path).read().splitlines(True)
def argv(effort): return ["-p", "--model", "stub-model", "--system-prompt", "", "--tools", "", "--effort", effort, "--output-format", "json"] + common.EXTRA
def sent_ok(effort, calls, per_question):   # the command line, the directory, and how many times each question was sent
    L = rows(LOG); return len(L) == calls and all(c["argv"] == argv(effort) and os.path.realpath(c["cwd"]) == os.path.realpath("/tmp") for c in L) \
        and all(sum(c["stdin_sha256"] == h for c in L) == per_question for h in {c["stdin_sha256"] for c in L})
def hashes_ok(R): return {r["prompt_sha256"] for r in R} <= {c["stdin_sha256"] for c in rows(LOG)}   # the hash in each row is of a text that was sent

for t, script, eff, extra, out in (("features", "features/ask.py", "high", [], exp / "features/results/stub-model.jsonl"),
                                   ("pseudo", "pseudo/ask.py", "medium", [], exp / "pseudo/results/stub-model.jsonl"),
                                   ("structure", "structure/ask.py", "low", [], exp / "structure/results/stub-model.jsonl"),
                                   ("decoy_control", "decoy_control/ask_decoys.py", "high", [], exp / "decoy_control/results/stub-model.jsonl"),
                                   ("next_residue", "next_residue/run.py", "xhigh", ["2"], exp / "next_residue/results/xhigh/stub-model.jsonl")):
    good = "peptide" if t == "next_residue" else "multi"
    run(script, "fail", eff, *extra); R = rows(out); n = len(R)
    check(f"{t}: a failed call writes an error row with effort, 3 attempts and a prompt hash", n > 0 and all(r.get("error") and r["effort"] == eff and r["attempts"] == 3 for r in R) and hashes_ok(R))
    check(f"{t}: each question is sent 3 times with the original command line plus common.EXTRA, from /tmp", sent_ok(eff, 3 * n, 3))
    before = lines(out); run(script, good, eff, *extra); R = rows(out); new = R[n:]
    check(f"{t}: the failed questions are asked again, once each", len(new) == n and sent_ok(eff, n, 1) and not any(common.unusable(r) for r in new))
    check(f"{t}: the error rows stay in the file, byte for byte", lines(out)[:n] == before)
    check(f"{t}: rows record effort, attempts, a prompt hash, the flags and the tokens", len(new) == n and hashes_ok(new) and all(r["effort"] == eff and r["attempts"] == 1
          and r["extra_flags"] == common.EXTRA and r["context_tokens"] == 603 and r["context_tokens_high"] is False and r["cli_version"] == "0.0.0 (stub)" and r["asked_at"]
          and r["served"] == ["stub-model"] and r["is_error"] is False for r in new))
    if t == "next_residue": check(f"{t}: the thinking tokens keep this test's field name, and the peptide is read", all(r["thinking"] == 7 and "thinking_tokens" not in r and r["pred"] == "ACDEFGHIKL" and r["valid"] for r in new))
    else: check(f"{t}: two JSON objects are read as the last one", all(r["ans"] and r["ans"]["protein_name"] == "second" for r in new))
    before = lines(out); run(script, "ok", eff, *extra)
    check(f"{t}: a finished run (a file mixing failed and answered rows) asks nothing and changes nothing", lines(out) == before and len(rows(LOG)) == 0)
    p = run(script, "ok", "max", *(extra if t != "next_residue" else []), ok=(t == "next_residue"))   # test 1 keeps efforts in separate folders
    if t != "next_residue": check(f"{t}: a run at another effort on the same file stops without calling", lines(out) == before and len(rows(LOG)) == 0 and "--tag" in p.stderr)
    out.unlink(); run(script, "bigctx", eff, *extra); R = rows(out)
    check(f"{t}: a call with attached context is marked", len(R) == n and all(r["context_tokens_high"] for r in R))
    run(script, "apierror", eff, *extra); R = rows(out)
    check(f"{t}: marked calls are asked again; an API error is tried 3 times and recorded", len(R) == 2 * n and all(r["is_error"] and r["attempts"] == 3 for r in R[n:]) and sent_ok(eff, 3 * n, 3))
    run(script, good, eff, *extra); R = rows(out)
    check(f"{t}: API-error rows are asked again; the file then has one usable row per question", len(R) == 3 * n and sum(not common.unusable(r) for r in R) == n and sent_ok(eff, n, 1))
    out.unlink(); run(script, "peptide_tool" if t == "next_residue" else "tool", eff, *extra); R = rows(out)
    if t == "next_residue": check(f"{t}: a reply with a tool call is invalid and not correct", len(R) == n and all(r["pred"] and not r["valid"] and not r["first_correct"] and not r["exact10"] for r in R))
    else: check(f"{t}: a reply with a tool call has no answer", len(R) == n and all(r["ans"] is None for r in R))
    out.unlink(); run(script, good, eff, *extra, "--limit", "1", "--tag", "canary")
    check(f"{t}: --limit 1 --tag canary asks one question into its own file", len(rows(out.with_name("stub-model-canary.jsonl"))) == 1 and not out.exists() and len(rows(LOG)) == 1)

# The decoy control asks the test 3 question: the text sent for a decoy is the test 3 prompt plus the decoy sequence (PR 10), and
# --set original asks the test 3 mutants and wild types of the kinases and enzymes into bridge-MODEL.jsonl (#11).
sys.path.insert(0, str(exp / "pseudo")); _argv = sys.argv; sys.argv = ["ask.py", "stub-model", "high", "--limit", "0", "--tag", "import-only"]
with contextlib.redirect_stdout(io.StringIO()): import ask as pseudo_ask   # --limit 0: the import asks nothing
sys.argv = _argv; (exp / "pseudo/results/stub-model-import-only.jsonl").unlink()
decoys = json.loads((exp / "decoy_control/decoys.json").read_text()); out = exp / "decoy_control/results/stub-model.jsonl"
run("decoy_control/ask_decoys.py", "ok", "high"); R = rows(out)
check("decoy_control: each decoy is sent as the test 3 prompt followed by the decoy sequence", len(R) == len(decoys) and
      {r["prompt_sha256"] for r in R} == {common.sha(pseudo_ask.P + pseudo_ask.fasta(d["sequence"])) for d in decoys} == {c["stdin_sha256"] for c in rows(LOG)})
truth = [t for t in json.loads((exp / "pseudo/truth.json").read_text()) if t["group"] in ("kinase", "enzyme")]; want = {(t["accession"], v) for t in truth for v in t["variants"]}
run("decoy_control/ask_decoys.py", "ok", "high", "--set", "original"); B = rows(exp / "decoy_control/results/bridge-stub-model.jsonl")
check("decoy_control: --set original asks every test 3 variant of the kinases and enzymes, into bridge-MODEL.jsonl, and leaves the decoy file alone",
      len(want) > 0 and {(r["accession"], r["variant"]) for r in B} == want and len(B) == len(want) and rows(out) == R
      and {r["prompt_sha256"] for r in B} == {common.sha(pseudo_ask.P + pseudo_ask.fasta(s)) for t in truth for s in t["variants"].values()})
run("decoy_control/ask_decoys.py", "ok", "high", "--set", "original", "--only", "NOPE:wt")
check("decoy_control: --only with no matching item asks nothing", len(rows(LOG)) == 0)

# The reply-reading rules, case by case (#49, #50, #61). K is the key list of test 2.
K = common.KEYS["features"]; A = {"pfam_domains": [], "transmembrane_helices": [], "signal_peptide": False, "protein_name": "x", "ec_number": None, "function": "y"}
J = json.dumps(A); B = json.dumps(dict(A, protein_name="z"))
for label, text, want in (
    ("a plain answer", J, A), ("an answer in a json fence", "```json\n" + J + "\n```", A), ("two answers: the last", J + "\nCorrected version:\n" + B, dict(A, protein_name="z")),
    ("braces inside a string", json.dumps(dict(A, function="a {curly} note")), dict(A, function="a {curly} note")),
    ("no JSON at all", "I cannot annotate this.", None), ("an answer wrapped in an outer object: not found", json.dumps({"annotation": A}), None),
    ("a truncated answer: a nested item with one requested key is not taken", '{"pfam_domains": [{"accession": "PF00001", "name": "7tm_1", "function": "x"}], "transmembrane', None),
    ("a function-call object is not an answer", '{"type": "function", "function": {"name": "web_search", "arguments": "{}"}}', None),
    ("very deep nesting does not crash", '{"pfam_domains": ' + "[" * 100000, None),
    ("a shell fence with a command: no answer, even with a JSON answer after it", "```bash\ncurl https://rest.uniprot.org\n```\n" + J, None),
    ("an answer followed by a suggested shell command: no answer (the scorer lists the reply)", J + "\nYou can check this with:\n```bash\nhmmscan Pfam-A.hmm seq.fa\n```", None),
    ("an untagged fence with curl", "```\ncurl -s https://rest.uniprot.org\n```\n" + J, None), ("a Python web request", "```python\nrequests.get('https://rest.uniprot.org')\n```\n" + J, None),
    ("tool_call markup", "<tool_call>{}</tool_call>" + J, None),
    ("an example object after the answer is taken as the answer (known limit)", J + "\nFor comparison: " + B, dict(A, protein_name="z"))):
    try: got = common.answer(text, K)
    except Exception as e: got = repr(e)
    check("rule: " + label, got == want)
check("rule: the stored tool-call reply is detected", common.has_tool_call('I\'ll try UniProt.\n\n```bash\ncurl -sS -X POST "https://peptidesearch.uniprot.org/asyncrest"\n```'))
check("rule: an amino-acid answer is not a tool call", not common.has_tool_call("MKTAYIAKQR") and not common.has_tool_call(J))
shutil.rmtree(tmp); sys.exit(1 if fails else 0)
