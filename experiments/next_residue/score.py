"""Score the next-residue probe from results/EFFORT/MODEL.jsonl. Usage: score.py

Prints, per effort and model: first-residue accuracy by condition, the real-minus-shuffled and real-minus-reversed
gaps with a 95% bootstrap interval over families (10,000 resamples, fixed seed), accuracy split by whether the model
used thinking tokens, and the authors' stored accuracy on the identical questions (upstream/authors_outputs_subset.jsonl).
Runs with calls whose usage record lists a second model are also scored without those calls.
A reply that contains a tool invocation instead of an answer is invalid and counts as wrong (common.has_tool_call).
"""
import collections, json, pathlib, random
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import NOTE_CONTINUED, NOTE_FAILED, continued, failed, has_tool_call, unusable
HERE = pathlib.Path(__file__).parent
AUTH = {}
for l in open(HERE / "upstream" / "authors_outputs_subset.jsonl"):
    d = json.loads(l); AUTH[(d["model"], d["accession"], d["condition"], d["cut"])] = d
pct = lambda x: 100 * sum(x) / len(x)
def gaps(R, indent="  "):
    fam = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in R: fam[r["pfam"]][r["condition"]].append(r["first_correct"])
    for other in ("shuffled", "reversed"):
        g = [sum(d["real"]) / len(d["real"]) - sum(d[other]) / len(d[other]) for d in fam.values() if d["real"] and d[other]]
        if not g: continue
        rng = random.Random(0); bs = sorted(sum(rng.choices(g, k=len(g))) / len(g) for _ in range(10000))
        print(f"{indent}gap real-{other}: {100*sum(g)/len(g):+.1f} pts (95% CI {100*bs[250]:+.1f} to {100*bs[9750]:+.1f}), {len(g)} families")
for effort in ("low", "high"):
    for f in sorted((HERE / "results" / effort).glob("claude-*.jsonl")):
        model = f.stem
        R = [json.loads(l) for l in open(f)]
        bad = failed(R); R = [r for r in R if not unusable(r)]
        tool = [r for r in R if has_tool_call(r["text"])]
        for r in tool: r.update(valid=False, first_correct=False, exact10=False)
        print(f"\n== {model}, effort {effort}: {len(R)} answered; models in usage records {sorted({m for r in R for m in r['served']})}; cost ${sum(r['cost'] or 0 for r in R):.2f}; "
              f"calls whose usage record lists a second model: {sum(len(r['served']) > 1 for r in R)}")
        if bad: print(f"  {NOTE_FAILED}: {bad}")
        if continued(R): print(f"  {NOTE_CONTINUED}: {len(continued(R))}")
        for c in ("real", "shuffled", "reversed"):
            x = [r for r in R if r["condition"] == c]
            if not x: continue
            print(f"  {c:9s} n={len(x)} invalid={sum(not r['valid'] for r in x)} first-residue={pct([r['first_correct'] for r in x]):.1f}%  exact10={sum(r['exact10'] for r in x)}")
            for label, y in (("with thinking", [r for r in x if r["thinking"]]), ("no thinking", [r for r in x if not r["thinking"]])):
                if y and len(y) != len(x): print(f"            {label:13s} n={len(y):3d} first-residue={pct([r['first_correct'] for r in y]):.1f}%")
        if tool: print("  replies with a tool invocation instead of an answer (invalid, counted as wrong): " + ", ".join(f"{r['accession']} {r['condition']} cut {r['cut']}" for r in tool))
        gaps(R)
        for c in ("real", "shuffled"):
            x = [(r, AUTH[(model, r["accession"], c, r["cut"])]) for r in R if r["condition"] == c and (model, r["accession"], c, r["cut"]) in AUTH]
            if x: print(f"  authors' stored run, same {len(x)} {c} questions: {pct([b['first_correct'] for a, b in x]):.1f}%")
        two = [r for r in R if len(r["served"]) > 1]
        if two:
            print("  calls listing a second model: " + ", ".join(f"{r['accession']} {r['condition']} cut {r['cut']}" for r in two))
            K = [r for r in R if len(r["served"]) == 1]
            for c in ("real", "shuffled", "reversed"):
                x = [r for r in K if r["condition"] == c]
                if x: print(f"  without them: {c:9s} n={len(x)} first-residue={pct([r['first_correct'] for r in x]):.1f}%")
            gaps(K, indent="  without them: ")
