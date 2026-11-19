"""Print the counts quoted in experiments/decoy_control/RESULTS.md that score_decoys.py does not print.

Purpose: for each model, among the 58 catalytic-site mutants that have a decoy: how many answers are "uncertain"
         in the stored run and in the rerun; which decoy answers omit the curated catalytic position; which
         wild-type answers of the rerun omit it; the cost of each file.
Inputs:  experiments/decoy_control/{decoys.json,results/*.jsonl}, experiments/pseudo/{truth.json,results/*.jsonl}.
Outputs: text on standard output. Nothing is written.     Serves: pull request 10, issue 11.     2026-11-19
"""
import collections, json, pathlib, sys
EXP = pathlib.Path(__file__).resolve().parents[2] / "experiments"; sys.path.insert(0, str(EXP)); from common import KEYS, reparse
D = json.loads((EXP / "decoy_control/decoys.json").read_text()); T = {t["accession"]: t for t in json.loads((EXP / "pseudo/truth.json").read_text())}
PAIR = {"asp_decoy_to_asn": "asp_to_asn", "lys_decoy_to_met": "lys_to_met", "site_decoy_to_ala": "site_to_ala"}; SITE = {"asp_to_asn": "asp", "lys_to_met": "lys", "site_to_ala": "site"}
def load(p):
    R = [json.loads(l) for l in p.open()]; reparse(R, KEYS["pseudo"]); return R, {(r["accession"], r["variant"]): r for r in R if r.get("ans")}
def call(r): return str(r["ans"].get("catalytically_active")).lower()
def pos(r, k): return {x.get("position") for x in (r["ans"].get(k) or []) if isinstance(x, dict)}
muts = [(d["accession"], PAIR[d["variant"]]) for d in D]; prots = sorted({d["accession"] for d in D})
for m in ("claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"):
    Rd, dec = load(EXP / "decoy_control/results" / f"{m}.jsonl"); Rs, st = load(EXP / "pseudo/results" / f"{m}.jsonl"); Rb, br = load(EXP / "decoy_control/results" / f"bridge-{m}.jsonl")
    print(f"\n{m}: cost decoys ${sum(r.get('cost') or 0 for r in Rd):.2f}, rerun ${sum(r.get('cost') or 0 for r in Rb):.2f}")
    for name, ref in (("stored", st), ("rerun", br)):
        print(f"  {name}: the 58 mutants: {dict(collections.Counter(call(ref[k]) for k in muts))}; the 38 wild types: {dict(collections.Counter(call(ref[(a, 'wt')]) for a in prots))}")
        miss = [a for a in prots if not all(T[a][s] in pos(ref[(a, "wt")], "catalytic_residues") for s in (("asp", "lys") if T[a]["group"] == "kinase" else ("site",)))]
        print(f"  {name}: wild-type answers that do not list every curated catalytic position: {len(miss)} {miss if len(miss) < 8 else ''}")
    print("  decoy answers:", dict(collections.Counter(call(r) for r in dec.values())), "; omit the curated position of the paired mutant:",
          sorted(f"{d['accession']} {d['variant']}" for d in D if T[d["accession"]][SITE[PAIR[d["variant"]]]] not in pos(dec[(d["accession"], d["variant"])], "catalytic_residues")) if m != "claude-opus-4-6" else "(many)")
    print("  decoy position listed as catalytic:", [f"{d['accession']} {d['position']}" for d in D if d["position"] in pos(dec[(d["accession"], d["variant"])], "catalytic_residues")])
