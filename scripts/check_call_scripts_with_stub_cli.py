"""Exercise the five model-calling scripts and the reply-reading rules against a stub `claude` executable.
No model is called.

Copies experiments/ (without results) to a temp dir, puts a stub named `claude` first on PATH and checks:
  1. the command line, working directory and question each script sends, against what its row records;
  2. every row records effort, attempts, a prompt hash, the flags and the token counts;
  3. a failed call, an API-error reply and a call with attached context are kept in the file, are not answers,
     and are asked again; rows already in the file are never rewritten (#26, #54, #56); the input is checked
     per request, so a reply that took two requests is an answer;
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
q = sys.stdin.read(); mode, _, mod = os.environ.get("STUB_MODE", "ok").partition("+")   # "+two": the reply took two requests; "+hidden": one request, summed input too large; "+bigiter": one large request
with open(os.environ["STUB_LOG"], "a") as fh: fh.write(json.dumps(dict(argv=sys.argv[1:], cwd=os.getcwd(), stdin_sha256=hashlib.sha256(q.encode()).hexdigest(), stdin_len=len(q))) + "\n")
if mode == "fail": print("not json"); sys.exit(0)
if mode == "apierror": print(json.dumps({"result": "API Error: overloaded\n\nRequest ID: req_stub", "is_error": True, "total_cost_usd": 0.25, "usage": {}, "modelUsage": {}})); sys.exit(0)
one = {"pfam_domains": [], "catalytically_active": "yes", "helices": [[1, 5]], "protein_name": "first"}
two = dict(one, protein_name="second")
text = {"ok": json.dumps(one), "bigctx": json.dumps(one), "multi": json.dumps(one) + "\n\nCorrected version:\n\n" + json.dumps(two),
        "tool": "```bash\ncurl https://example.org\n```\n" + json.dumps(one), "peptide": "ACDEFGHIKL",
        "peptide_tool": "```bash\ncurl -d peps=ACDEFGHIKL https://example.org\n```"}[mode]
usage = {"input_tokens": 90000 if mode == "bigctx" else 3, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0, "output_tokens": 50, "output_tokens_details": {"thinking_tokens": 7}}
per = 600 + len(q) // 2   # one request, below the limit of 700 + len(q); two of them sum to more than the limit
turns = 2 if mod in ("two", "twobig") else 1
if mod in ("two", "hidden"): usage.update(input_tokens=2 * per, cache_creation_input_tokens=0, iterations=[{"input_tokens": per, "type": "message"}])   # as the tool reports two requests: summed input, last request listed
elif mod == "twobig": usage.update(input_tokens=180000, cache_creation_input_tokens=0, iterations=[{"input_tokens": 90000, "type": "message"}])   # two requests, each with attached context
elif mod == "bigiter": usage["iterations"] = [{"input_tokens": 3}, "noise", {"cache_read_input_tokens": 90000}, {"input_tokens": 3}]   # only the listed response shows the large cached input
elif mod == "odd": usage.update(input_tokens="12", iterations=5, output_tokens_details="none", new_key="x")   # a malformed record must not stop a paid call from being written
elif mode != "bigctx": usage["iterations"] = [{"input_tokens": 3, "cache_creation_input_tokens": 600, "type": "message"}]
print(json.dumps({"result": text, "total_cost_usd": 0.0, "modelUsage": {"stub-model": {"inputTokens": 3, "new_key": "x"}}, "usage": usage, "is_error": False, "session_id": "stub-session", "num_turns": turns, "stop_reason": "end_turn", "duration_ms": 1234}))
'''
tmp = pathlib.Path(tempfile.mkdtemp()); exp = tmp / "experiments"
shutil.copytree(REPO / "experiments", exp, ignore=shutil.ignore_patterns("results", "__pycache__"))
(tmp / "bin").mkdir(); stub = tmp / "bin" / "claude"; stub.write_text(STUB); stub.chmod(0o755)
LOG = tmp / "stub_calls.jsonl"; env = dict(os.environ, PATH=f"{tmp / 'bin'}{os.pathsep}{os.environ['PATH']}", STUB_LOG=str(LOG))
assert shutil.which("claude", path=env["PATH"]) == str(stub), "the stub is not first on PATH; refusing to run"
for t in ("features", "structure"):   # two questions' worth of truth is enough
    f = exp / t / "truth.json"; f.write_text(json.dumps(json.loads(f.read_text())[:2]))
# Test 3 and its decoy control keep one protein of each group, so a script that drops or adds a group is caught (#68).
f = exp / "decoy_control/decoys.json"; allD = json.loads(f.read_text()); g = exp / "pseudo/truth.json"; allT = json.loads(g.read_text())
keep = [next(d["accession"] for d in allD if d["group"] == grp) for grp in ("kinase", "enzyme")] + [next(t["accession"] for t in allT if t["group"] == "pseudo")]
f.write_text(json.dumps([d for d in allD if d["accession"] in keep])); g.write_text(json.dumps([t for t in allT if t["accession"] in keep]))
assert [len([d for d in allD if d["accession"] == k]) for k in keep] == [2, 1, 0], "fixture: a kinase with two decoys, an enzyme with one, a pseudokinase with none"
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
def limit(r): return 700 + next(c["stdin_len"] for c in rows(LOG) if c["stdin_sha256"] == r["prompt_sha256"])   # common.context_limit for the question this row asked
def hashes_ok(R): return {r["prompt_sha256"] for r in R} <= {c["stdin_sha256"] for c in rows(LOG)}   # the hash in each row is of a text that was sent

for t, script, eff, extra, out in (("features", "features/ask.py", "high", [], exp / "features/results/stub-model.jsonl"),
                                   ("pseudo", "pseudo/ask.py", "medium", [], exp / "pseudo/results/stub-model.jsonl"),
                                   ("structure", "structure/ask.py", "low", [], exp / "structure/results/stub-model.jsonl"),
                                   ("decoy_control", "decoy_control/ask_decoys.py", "medium", [], exp / "decoy_control/results/stub-model.jsonl"),
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
          and r["served"] == ["stub-model"] and r["is_error"] is False and r["requests"] == 1 and r["context_tokens_max"] == 603
          and r["session_id"] == "stub-session" and r["num_turns"] == 1 and r["stop_reason"] == "end_turn" and r["duration_ms"] == 1234
          and r["usage"] == {"input_tokens": 3, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0, "output_tokens": 50, "output_tokens_details": {"thinking_tokens": 7},
                             "iterations": [{"input_tokens": 3, "cache_creation_input_tokens": 600, "type": "message"}]} and r["model_usage"] == {"stub-model": {"inputTokens": 3}} for r in new))
    if t == "next_residue": check(f"{t}: the thinking tokens keep this test's field name, and the peptide is read", all(r["thinking"] == 7 and "thinking_tokens" not in r and r["pred"] == "ACDEFGHIKL" and r["valid"] for r in new))
    else: check(f"{t}: two JSON objects are read as the last one", all(r["ans"] and r["ans"]["protein_name"] == "second" for r in new))
    before = lines(out); run(script, "ok", eff, *extra)
    check(f"{t}: a finished run (a file mixing failed and answered rows) asks nothing and changes nothing", lines(out) == before and len(rows(LOG)) == 0)
    p = run(script, "ok", "max", *(extra if t != "next_residue" else []), ok=(t == "next_residue"))   # test 1 keeps efforts in separate folders
    if t != "next_residue": check(f"{t}: a run at another effort on the same file stops without calling", lines(out) == before and len(rows(LOG)) == 0 and "--tag" in p.stderr)
    out.unlink(); run(script, "bigctx", eff, *extra); R = rows(out)
    check(f"{t}: a call with attached context is marked", len(R) == n and all(r["context_tokens_high"] for r in R))
    run(script, "apierror", eff, *extra); R = rows(out)
    check(f"{t}: marked calls are asked again; an API error is tried 3 times and recorded", len(R) == 2 * n and all(r["is_error"] and r["attempts"] == 3
          and r["attempt_errors"] == ["API Error: overloaded"] * 3 and r["cost_all_attempts"] == 0.75 for r in R[n:]) and sent_ok(eff, 3 * n, 3))
    run(script, good, eff, *extra); R = rows(out)
    check(f"{t}: API-error rows are asked again; the file then has one usable row per question", len(R) == 3 * n and sum(not common.unusable(r) for r in R) == n and sent_ok(eff, n, 1))
    out.unlink(); run(script, "peptide_tool" if t == "next_residue" else "tool", eff, *extra); R = rows(out)
    if t == "next_residue": check(f"{t}: a reply with a tool call is invalid and not correct", len(R) == n and all(r["pred"] and not r["valid"] and not r["first_correct"] and not r["exact10"] for r in R))
    else: check(f"{t}: a reply with a tool call has no answer", len(R) == n and all(r["ans"] is None for r in R))
    out.unlink(); run(script, good, eff, *extra, "--limit", "1", "--tag", "canary")
    check(f"{t}: --limit 1 --tag canary asks one question into its own file", len(rows(out.with_name("stub-model-canary.jsonl"))) == 1 and not out.exists() and len(rows(LOG)) == 1)
    two = out.with_name("stub-model-two.jsonl"); run(script, good + "+two", eff, *extra, "--tag", "two"); R = rows(two)
    check(f"{t}: a reply that took two requests is usable and counted, though its summed input passes the limit", len(R) == n and all(r["requests"] == 2 and not r["context_tokens_high"]
          and r["context_tokens"] == 2 * r["context_tokens_max"] and r["context_tokens_max"] <= limit(r) < r["context_tokens"] and not common.unusable(r) for r in R) and len(common.continued(R)) == n)
    if t != "next_residue":   # the scorer of this test prints the count (test 1 needs the upstream answers for the stub's questions, so it is left out)
        named = two.with_name("claude-stub.jsonl"); shutil.copy(two, named)   # the test 2 scorer reads claude-*.jsonl
        p_ = subprocess.run([sys.executable, str(exp / t / ("score_decoys.py" if t == "decoy_control" else "score.py"))], capture_output=True, text=True)
        named.unlink()
        check(f"{t}: the scorer prints the replies that took more than one request", p_.returncode == 0 and common.NOTE_CONTINUED in p_.stdout)
    two.unlink(); run(script, good + "+twobig", eff, *extra, "--tag", "two"); R = rows(two)
    check(f"{t}: two requests that each carry attached context are marked and not counted as continued", len(R) == n and all(r["context_tokens_high"] and r["requests"] == 2 for r in R) and not common.continued(R))
    two.unlink(); run(script, good + "+hidden", eff, *extra, "--tag", "two"); R = rows(two)
    check(f"{t}: one request whose summed input passes the limit is marked, though the listed request is small", len(R) == n and all(r["context_tokens_high"] and r["requests"] == 1
          and r["context_tokens_max"] <= limit(r) < r["context_tokens"] for r in R))
    two.unlink(); run(script, good + "+bigiter", eff, *extra, "--tag", "two"); R = rows(two)
    check(f"{t}: a listed response above the limit is marked, though the summed input is small", len(R) == n and all(r["context_tokens_high"] and r["requests"] == 1
          and r["context_tokens"] <= limit(r) < r["context_tokens_max"] == 90000 for r in R))
    two.unlink(); run(script, good + "+odd", eff, *extra, "--tag", "two"); R = rows(two)
    check(f"{t}: a malformed usage record still gives a usable row, without the unknown key", len(R) == n and all(not common.unusable(r) and r["context_tokens"] == 600 and r["requests"] == 1
          and "new_key" not in r["usage"] and r["usage"]["iterations"] == 5 for r in R))

# The decoy control asks the test 3 question: the text sent for a decoy is the test 3 prompt plus the decoy sequence (PR 10), and
# --set original asks the test 3 mutants and wild types of the kinases and enzymes into bridge-MODEL.jsonl (#11).
sys.path.insert(0, str(exp / "pseudo")); _argv = sys.argv; sys.argv = ["ask.py", "stub-model", "high", "--limit", "0", "--tag", "import-only"]
with contextlib.redirect_stdout(io.StringIO()): import ask as pseudo_ask   # --limit 0: the import asks nothing
sys.argv = _argv; (exp / "pseudo/results/stub-model-import-only.jsonl").unlink()
decoys = json.loads((exp / "decoy_control/decoys.json").read_text()); out = exp / "decoy_control/results/stub-model.jsonl"
def by_item(R): return {(r["accession"], r["variant"]): r["prompt_sha256"] for r in R}
run("decoy_control/ask_decoys.py", "ok", "xhigh"); R = rows(out)
check("decoy_control: each decoy row records the test 3 prompt followed by that decoy's sequence, at the effort asked for", len(R) == len(decoys) == 3 and all(r["effort"] == "xhigh" for r in R) and sent_ok("xhigh", 3, 1)
      and by_item(R) == {(d["accession"], d["variant"]): common.sha(pseudo_ask.P + pseudo_ask.fasta(d["sequence"])) for d in decoys} and {c["stdin_sha256"] for c in rows(LOG)} == set(by_item(R).values()))
truth = json.loads((exp / "pseudo/truth.json").read_text()); want = {(t["accession"], v): common.sha(pseudo_ask.P + pseudo_ask.fasta(s)) for t in truth if t["group"] in ("kinase", "enzyme") for v, s in t["variants"].items()}
run("decoy_control/ask_decoys.py", "ok", "xhigh", "--set", "original"); B = rows(exp / "decoy_control/results/bridge-stub-model.jsonl")
check("decoy_control: --set original asks every test 3 variant of the kinase and the enzyme and none of the pseudokinase, into bridge-MODEL.jsonl, and leaves the decoy file alone",
      len(want) == 5 and by_item(B) == want and len(B) == 5 and rows(out) == R and {t["group"] for t in truth} == {"kinase", "enzyme", "pseudo"})
run("decoy_control/ask_decoys.py", "ok", "xhigh", "--set", "original", "--only", "NOPE:wt")
check("decoy_control: --only with no matching item asks nothing", len(rows(LOG)) == 0)
one = decoys[0]; only = exp / "decoy_control/results/stub-model-only.jsonl"; run("decoy_control/ask_decoys.py", "ok", "xhigh", "--only", f"{one['accession']}:{one['variant']}", "--tag", "only"); R1 = rows(only)
check("decoy_control: --only ACCESSION:VARIANT asks that one item, not the protein's other decoy", [(r["accession"], r["variant"]) for r in R1] == [(one["accession"], one["variant"])] and len(rows(LOG)) == 1
      and sum(d["accession"] == one["accession"] for d in decoys) == 2)
run("decoy_control/ask_decoys.py", "ok", "xhigh", "--limit", "0", "--tag", "none")
check("decoy_control: a run that asks nothing creates no file", not (exp / "decoy_control/results/stub-model-none.jsonl").exists() and len(rows(LOG)) == 0)
p_ = subprocess.run([sys.executable, str(exp / "decoy_control/ask_decoys.py"), "stub-model", "xhigh", "--limit", "-1"], env=dict(env, STUB_MODE="ok"), capture_output=True, text=True)
check("decoy_control: a negative --limit is refused", p_.returncode != 0 and len(rows(out)) == 3)
# The decoy scorer on the stub rows: it runs, skips nothing silently, and stops on a second usable row for a question (#71).
def score(): return subprocess.run([sys.executable, str(exp / "decoy_control/score_decoys.py")], capture_output=True, text=True)
shutil.copy(out, exp / "decoy_control/results/stub-model-b.jsonl"); p_ = score()
check("decoy_control: the scorer scores each results file as its own block and checks every recorded prompt hash", p_.returncode == 0 and "\n== stub-model-b:" in p_.stdout
      and p_.stdout.count("\n== ") == sum(1 for f in (exp / "decoy_control/results").glob("*.jsonl") if not f.name.startswith("bridge-") and rows(f)) >= 2 and "hash is that of the test 3 prompt plus this sequence 3/3" in p_.stdout and "5/5" in p_.stdout)
with out.open("a") as fh: fh.write(lines(out)[0])
p_ = score(); check("decoy_control: the scorer stops on a second usable row for one question", p_.returncode != 0 and "more than one usable row" in p_.stderr)

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
