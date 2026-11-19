"""Screen the stored calls for signs that connector tools were attached (issues #13, #49). PR #10 saw one call
with the original flags carry 97,811 input tokens ($1.69) where its neighbour carried 6,411 ($0.21). The stored
rows have no input-token count, so this uses cost: per results file it prints the cost distribution, and lists
rows costing more than 4 times the file median together with their thinking tokens and reply length.
Inputs: experiments/*/results/**/*.jsonl. Output: stdout. 2026-11-18."""
import glob, json, statistics
tot = flagged = 0
for f in sorted(glob.glob("experiments/*/results/**/*.jsonl", recursive=True)):
    R = [r for r in map(json.loads, open(f)) if r.get("cost") is not None]; c = sorted(r["cost"] for r in R); med = statistics.median(c)
    hi = [r for r in R if r["cost"] > 4 * med]; tot += len(R); flagged += len(hi)
    print(f"{f}: n={len(R)} cost min {c[0]:.4f} median {med:.4f} p95 {c[int(.95*len(c))]:.4f} max {c[-1]:.4f}; above 4x median: {len(hi)}")
    for r in sorted(hi, key=lambda r: -r["cost"])[:8]:
        th = r.get("thinking", r.get("thinking_tokens")); k = r.get("accession") or r.get("pdb")
        print(f"     {k} {r.get('condition', r.get('variant', ''))} {r.get('cut', '')}: cost {r['cost']:.4f}, thinking tokens {th}, reply chars {len(r.get('text') or '')}, served {r.get('served')}")
print(f"\nrows with a cost: {tot}; above 4x their file median: {flagged}")
