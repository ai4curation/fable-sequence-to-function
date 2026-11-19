"""Apply the request-count and marking rule of call() to stored rows that carry the tool's usage record.

Purpose: issues 105 and 109 changed how call() counts requests (the turn count plus at most one retry inferred from
         the summed input divided by the listed response). This recomputes, for every stored row with a usage
         record, the turn count, the count from tokens, and whether the row would be marked under the new rule and
         under the turn count alone, and lists rows where they differ. Nothing is written; stored marks are not
         changed.
Inputs:  results .jsonl files of tests 2 to 4 given as arguments. The limit needs the question's length, which is
         rebuilt from the test's prompt and the row's sequence (real sequences only); rows whose question cannot
         be rebuilt (shuffled test 2 sequences) are counted and skipped.
Outputs: text on standard output.     Serves: issue 105 (pull request 53).     2026-11-19
Usage:   simulate_request_count_on_real_rows.py RESULTS.jsonl ...
"""
import ast, json, pathlib, sys
EXP = pathlib.Path(__file__).resolve().parents[2] / "experiments"; sys.path.insert(0, str(EXP)); import common
def prompt_of(test):
    t = (EXP / test / "ask.py").read_text(); return next(ast.literal_eval(n.value) for n in ast.parse(t).body if isinstance(n, ast.Assign) and any(getattr(x, "id", "") == "P" for x in n.targets))
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))
SEQ = {}
for test in ("features", "pseudo", "structure"):
    P = prompt_of(test)
    for t in json.loads((EXP / test / "truth.json").read_text()):
        if test == "pseudo":
            for v, s in t["variants"].items(): SEQ[common.sha(P + fasta(s))] = len(P + fasta(s))
        elif test == "features":
            for s in (t["sequence"],): SEQ[common.sha(P + fasta(s))] = len(P + fasta(s))
        else:
            s = t.get("sequence") or t.get("seq")
            if s: SEQ[common.sha(P + fasta(s))] = len(P + fasta(s))
for f in map(pathlib.Path, sys.argv[1:]):
    R = [json.loads(l) for l in f.open() if l.strip()]; seen = disagree = unknown = 0
    for r in R:
        u = r.get("usage")
        if not isinstance(u, dict) or not isinstance(u.get("iterations"), list) or not u["iterations"]: continue
        seen += 1; ctx = r["context_tokens"]; listed = max(sum(i.get(k) or 0 for k in common.INPUT_KEYS) for i in u["iterations"] if isinstance(i, dict))
        turns = common._int(r.get("num_turns")) or 1; by_tokens = round(ctx / listed) if listed else 1; n = turns + min(max(by_tokens - turns, 0), common.MAX_UNCOUNTED_RETRIES)
        L = SEQ.get(r.get("prompt_sha256")); lim = 700 + L if L else None
        if lim is None: unknown += 1; continue
        old = listed > lim or ctx > turns * lim; new = listed > lim or ctx > n * lim
        if by_tokens != turns or old != new:
            disagree += 1; print(f"  {f.name}: {r.get('accession') or r.get('pdb')} {r.get('variant') or r.get('condition') or ''}: turns {turns}, by tokens {by_tokens} (sum {ctx}, listed {listed}), limit {lim}, marked by turns {old}, by new rule {new}, stored mark {r.get('context_tokens_high')}")
    print(f"{f.name}: {seen} rows with a usage record, {disagree} where the counts or the mark differ, {unknown} whose prompt could not be rebuilt")
