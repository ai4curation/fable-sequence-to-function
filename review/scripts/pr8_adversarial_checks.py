"""Adversarial checks of PR #8 (move experiments here, make analysis reproducible). 2026-11-18.

Inputs: experiments/ in this repository. Output: findings printed to stdout; feeds the issues filed from the PR #8 review.
Run from the repository root: uv run python review/scripts/pr8_adversarial_checks.py
"""
import collections, json, pathlib, runpy, sys, yaml
E = pathlib.Path("experiments")
load = lambda p: [json.loads(l) for l in open(p)]

print("1. Result rows that are errors, unparsed, or carry is_error")
for f in sorted(E.glob("*/results/**/*.jsonl")):
    R = load(f)
    err = sum("error" in r for r in R); iserr = sum(bool(r.get("is_error")) for r in R)
    unp = sum(("ans" in r or "error" in r) and not r.get("ans") for r in R) if "next_residue" not in str(f) else 0
    print(f"   {f}: rows {len(R)}, error {err}, is_error {iserr}, unparsed {unp}")

print("2. Test 3 answers whose catalytically_active is not yes/no/uncertain")
for f in sorted((E / "pseudo/results").glob("*.jsonl")):
    for r in load(f):
        v = str((r.get("ans") or {}).get("catalytically_active")).lower()
        if r.get("ans") and v not in ("yes", "no", "uncertain"): print(f"   {f.stem} {r['accession']} {r['variant']} group={r['group']}: {v!r}")

print("3. Test 4 duplicate contact pairs within one answer (counted twice by the scorer)")
T = {t["pdb"]: t for t in json.load(open(E / "structure/truth.json"))}
for f in sorted((E / "structure/results").glob("*.jsonl")):
    d = 0
    for r in load(f):
        c = [tuple(sorted(p)) for p in ((r.get("ans") or {}).get("contacts") or []) if isinstance(p, list) and len(p) == 2]
        d += len(c) - len(set(c))
    print(f"   {f.stem}: duplicate pairs {d}")

print("4. ASPRV1 repeats and function grading")
for pid in ("27IK", "27JP", "27JO", "27IQ"):
    t = T[pid]; print(f"   {pid} {t['stratum']} {t['description']} uniprot={t['uniprot']}")
seqs = collections.Counter((t["sequence"], t["stratum"]) for t in T.values())
print("   identical sequences drawn more than once:", [(s[1], n) for s, n in seqs.items() if n > 1])
uni = collections.Counter(u for t in T.values() if t["stratum"] == "novel" for u in (t["uniprot"] or []))
print("   novel-stratum UniProt ids seen more than once:", {u: n for u, n in uni.items() if n > 1})
G = yaml.safe_load(open(E / "structure/function_grading.yaml"))
print(f"   function_grading entries: {len(G)}; keys of first: {list(G[0])}")

print("5. Does run.py regenerate exactly the question keys stored in each test-1 results file?")
import csv, random, zlib
HERE = E / "next_residue"
rows = list(csv.DictReader(open(HERE / "upstream/confirm_sequences.tsv"), delimiter="\t"))
byfam = collections.defaultdict(list)
for r in rows: byfam[(r["size_bin"], r["pfam"])].append(r)
rng = random.Random(20261118); bins = collections.defaultdict(list)
for (b, f) in sorted(byfam): bins[b].append(f)
qs = set()
for b in sorted(bins):
    for f in rng.sample(bins[b], 17):
        r = rng.choice(byfam[(b, f)])
        for cut in rng.sample([int(c) for c in r["cuts"].split(",")], 2):
            for cond in ("real", "shuffled", "reversed"): qs.add((r["accession"], cond, cut))
for f in sorted(HERE.glob("results/*/*.jsonl")):
    got = {(r["accession"], r["condition"], r["cut"]) for r in load(f)}
    print(f"   {f}: stored {len(got)}, not regenerated {len(got - qs)}, regenerated-but-missing {len({q for q in qs if q[1] in {g[1] for g in got}} - got)}")
