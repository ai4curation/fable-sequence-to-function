"""How much the next-residue gap's 95% bootstrap interval moves with the random seed.

Purpose: NEXT_TASKS T9 (issue #104, "Seed"). experiments/next_residue/score.py bootstraps the
family gaps with random.Random(0) and 10,000 resamples. This rebuilds the same family gaps (same
row filtering: unusable rows dropped, tool-call replies made invalid) and repeats the bootstrap
with seeds 0-99, printing the range of the lower and upper bounds for each run.
Inputs: experiments/next_residue/results/{low,high}/claude-*.jsonl. Output: stdout.
Date: 2026-11-21.
"""
import collections, importlib.util, json, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
spec = importlib.util.spec_from_file_location("nr_score", ROOT / "experiments" / "next_residue" / "score.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
from common import unusable

for effort in ("low", "high"):
    for f in sorted((ROOT / "experiments" / "next_residue" / "results" / effort).glob("claude-*.jsonl")):
        R = [json.loads(l) for l in open(f)]
        R = [r for r in R if not unusable(r)]
        S.reject_tools(R)
        fam = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in R:
            fam[r["pfam"]][r["condition"]].append(r["first_correct"])
        g = [sum(d["real"]) / len(d["real"]) - sum(d["shuffled"]) / len(d["shuffled"]) for d in fam.values() if d["real"] and d["shuffled"]]
        lo, hi = [], []
        for seed in range(100):
            rng = random.Random(seed)
            bs = sorted(sum(rng.choices(g, k=len(g))) / len(g) for _ in range(10000))
            lo.append(100 * bs[250]); hi.append(100 * bs[9750])
        print(f"{f.stem} {effort}: gap {100 * sum(g) / len(g):+.1f}; seed 0 interval {lo[0]:+.1f} to {hi[0]:+.1f}; "
              f"over seeds 0-99 lower {min(lo):+.1f} to {max(lo):+.1f}, upper {min(hi):+.1f} to {max(hi):+.1f}")
