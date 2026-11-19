"""Check that the stub test catches deliberate defects in experiments/common.py (mutation testing). No model is called.

Purpose: for each mutant (a literal text replacement in common.py), copy the committed tree to a scratch directory,
         apply the replacement there, run scripts/check_call_scripts_with_stub_cli.py and report its exit code and
         number of FAIL lines. A mutant is caught when the exit code is not 0 (a crash counts as caught).
Inputs:  the working tree of this repository (copied with `git ls-files`; the live tree is never modified).
Outputs: one line per mutant on standard output.     Serves: issues 78, 84, 86, 105 and 108 (pull request 53).     2026-11-19
Usage:   mutate_common_and_run_stub_test.py

A mutant that only removes the explicit check for a usage record that is not a dictionary is equivalent to the
unmutated code (an empty record is marked by the next rule), so it is not listed.
"""
import pathlib, shutil, subprocess, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]
MUTANTS = [   # name, text in common.py, replacement
    ("requests from the turn count only (#105)", "n = turns_n + min(max(by_tokens - turns_n, 0), MAX_UNCOUNTED_RETRIES)", "n = turns_n"),
    ("retry bound removed (#109)", "n = turns_n + min(max(by_tokens - turns_n, 0), MAX_UNCOUNTED_RETRIES)", "n = max(turns_n, by_tokens)"),
    ("empty usage record accepted (#110)", "    bad = bad or all(c is None for c in top)", "    pass"),
    ("negative cost stored (#110)", "and c is not None and c >= 0", "and c is not None"),
    ("sum rule dropped", " or context > n * context_limit(prompt)", ""),
    ("listed-response rule dropped", "context_tokens_high=largest > context_limit(prompt) or context", "context_tokens_high=context"),
    ("continued() reads only requests", "return max(_int(r.get(\"requests\")) or 1, _int(r.get(\"num_turns\")) or 1)", "return _int(r.get(\"requests\")) or 1"),
    ("continued() reads only num_turns", "return max(_int(r.get(\"requests\")) or 1, _int(r.get(\"num_turns\")) or 1)", "return _int(r.get(\"num_turns\")) or 1"),
    ("successful attempt's cost left out", "        spent += _num(j.get(\"total_cost_usd\"))\n        if not j.get(\"is_error\"): break\n",
     "        if not j.get(\"is_error\"): break\n        spent += _num(j.get(\"total_cost_usd\"))\n"),
    ("n = turns for any int", "turns_n = max(_int(turns) or 1, 1)", "turns_n = _int(turns) if _int(turns) is not None else 1"),
    ("negative counts accepted", "and _finite(x) and x >= 0 else False", "and _finite(x) else False"),
    ("listed counts not checked", "bad = bad or any(c is False for c in top + sum(each, []))", "bad = bad or any(c is False for c in top)"),
    ("output_tokens_details not filtered", "out[\"output_tokens_details\"] = _keep(out[\"output_tokens_details\"], DETAIL_KEYS, dropped, \"output_tokens_details.\")", "pass"),
    ("top-level cache_creation not filtered", "out[\"cache_creation\"] = _keep(out[\"cache_creation\"], CACHE_KEYS, dropped, \"cache_creation.\")", "pass"),
    ("error text not coerced", "errs.append((str(j.get(\"result\") or \"\")", "errs.append(((j.get(\"result\") or \"\")"),
    ("non-numeric cost stored", "rec.update(cost=c if ok_cost else None,", "rec.update(cost=c,"),
    ("attempt_errors keeps the last only", "        errs.append(", "        errs[:] = []; errs.append("),
    ("raw cost added", "spent += _num(j.get(\"total_cost_usd\"))", "spent += j.get(\"total_cost_usd\") or 0"),
    ("unreadable counts read as 0", "    if bad: rec[\"usage_unreadable\"] = True", "    pass"),
    ("unusable ignores usage_unreadable", " or bool(r.get(\"usage_unreadable\"))", ""),
    ("_int rejects strings", "    if isinstance(x, str) and x.strip().isascii() and x.strip().isdecimal() and len(x.strip()) < 10: return int(x.strip())", "    pass"),
    ("nested filter removed", "out[\"server_tool_use\"] = _keep(out[\"server_tool_use\"], SERVER_TOOL_KEYS, dropped, \"server_tool_use.\")", "pass"),
    ("dropped key names not recorded", "    if dropped: rec[\"usage_keys_dropped\"] = sorted(set(dropped))", "    pass"),
    ("listed size without iterations recorded as 0", "largest = listed or _ratio(context, n)", "largest = listed or 0"),
    ("top-level key filter removed", "usage=_usage(u, dropped)", "usage=u"),
]
def tree():
    d = pathlib.Path(tempfile.mkdtemp()) / "repo"
    for f in subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines():
        (d / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(REPO / f, d / f)
    return d
def run(d):
    p = subprocess.run([sys.executable, "scripts/check_call_scripts_with_stub_cli.py"], cwd=d, capture_output=True, text=True)
    return p.returncode, p.stdout.count("\nFAIL ") + p.stdout.startswith("FAIL "), (p.stderr.strip().splitlines() or [""])[-1][:100]
base = tree(); code, fails, _ = run(base); print(f"unmutated: exit {code}, FAIL {fails}"); missed = 0
for name, old, new in MUTANTS:
    d = tree(); f = d / "experiments/common.py"; s = f.read_text()
    if old not in s: print(f"{name}: TEXT NOT FOUND"); missed += 1; continue
    f.write_text(s.replace(old, new, 1)); code, fails, err = run(d); missed += code == 0
    print(f"{name}: exit {code}, FAIL {fails}" + (f", crash: {err}" if code and not fails else "") + ("   <- NOT CAUGHT" if code == 0 else ""))
    shutil.rmtree(d.parent)
shutil.rmtree(base.parent); print(f"\n{len(MUTANTS) - missed} of {len(MUTANTS)} mutants caught"); sys.exit(1 if missed else 0)
