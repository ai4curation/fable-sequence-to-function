"""Check, against the committed files, the factual claims in the external review filed as issues #201 to #207.

Purpose: before the manuscript text is narrowed (branch text/issues-201-208), confirm what the review says the
         stored answers contain. Reads only; calls no model and writes no file.
Inputs:  experiments/{pseudo,features,structure}/results/*.jsonl, experiments/decoy_control/results/*.jsonl,
         gemini_experiment/results_vertex/*/*.jsonl, the truth.json files.
Output:  a printed report with one section per claim.
Serves:  issues #201 (calls on RLK902, RKL1, kin-32), #203/#207 (which rows were written by which route),
         #204 (transmembrane helices predicted for shuffled sequences), #205 (the 9YP0 function answers),
         #206 (contact precision when short-range and unresolved submissions count as misses).
Date:    2026-11-20.
Usage:   uv run python scripts/adhoc/check_review_claims_issues_201_to_207.py
"""
import json, math, pathlib, statistics, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
from common import KEYS, answer   # the rule every scorer uses to read a reply

def rows(path): return [json.loads(l) for l in open(path)]
def ans(r, test): return answer(r.get("text") or "", KEYS[test])
CLAUDE = ["claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6-high", "claude-opus-4-6"]
NEON = {"pseudo": "gemini-4-neon-low", "features": "gemini-4-neon-low", "structure": "gemini-4-neon-medium"}
def files(test):
    out = [(m, ROOT / "experiments" / test / "results" / f"{m}.jsonl") for m in CLAUDE]
    return out + [(NEON[test], ROOT / "gemini_experiment" / "results_vertex" / test / f"{NEON[test]}.jsonl")]

print("== #201: calls on three proteins Swiss-Prot names inactive (wild type)")
for acc, label in (("Q9LVI6", "RLK902"), ("Q9LP77", "RKL1 / At1g48480"), ("Q95YD4", "kin-32")):
    print(f"  {acc} {label}")
    for m, f in files("pseudo"):
        for r in rows(f):
            if r.get("accession") == acc and r.get("variant", "wt") == "wt":
                a = ans(r, "pseudo") or {}
                print(f"    {m:22s} active={a.get('catalytically_active')!r:12} name={str(a.get('protein_name'))[:90]!r}")

PS = [d for d in json.loads((ROOT / "experiments/pseudo/truth.json").read_text()) if d["group"] == "pseudo"]
pred = [d["accession"] for d in PS if any("predicted to be catalytically inactive" in c for c in d.get("caution") or [])]
print(f"  stored UniProt comments (truth.json `caution`): {len(pred)} of {len(PS)} say the kinase domain is 'predicted to be catalytically inactive'")
for d in PS:
    for c in d.get("caution") or []:
        if "utophosphorylation" in c: print(f"    {d['accession']}: {c}")

print("\n== #203/#207: rows per results file, by route (a row with extra_flags or prompt_sha256 was written by call(), the revised route)")
for d in ("next_residue", "features", "pseudo", "structure", "decoy_control"):
    for f in sorted((ROOT / "experiments" / d / "results").rglob("*.jsonl")):
        R = rows(f); rev = [r for r in R if r.get("extra_flags") or r.get("prompt_sha256")]
        web = sum(1 for r in rev if any((r.get("usage") or {}).get("server_tool_use", {}).get(k) for k in ("web_search_requests", "web_fetch_requests")))
        hasweb = sum(1 for r in rev if isinstance((r.get("usage") or {}).get("server_tool_use"), dict))
        ver = sorted({str(r.get("cli_version")) for r in rev}); tok = sum(1 for r in rev if r.get("input_tokens") is not None)
        print(f"  {str(f.relative_to(ROOT)):62s} rows {len(R):4d}  original route {len(R)-len(rev):4d}  revised route {len(rev):4d}"
              f"  (of those: record input tokens {tok}, record web-request counts {hasweb}, show a web request {web}; tool version {ver if rev else '-'})")

print("\n== #204: shuffled sequences given at least one transmembrane helix (FEAT test, 60 shuffled per model)")
for m, f in files("features"):
    R = [r for r in rows(f) if r.get("condition") == "shuffled"]
    seen = {}
    for r in R:                       # the scorers take the last usable row per question; here: last row with an answer
        a = ans(r, "features")
        if a: seen[r["accession"]] = a
    tm = sum(1 for a in seen.values() if a.get("transmembrane_helices"))
    pf = sum(1 for a in seen.values() if a.get("pfam_domains"))
    sp = sum(1 for a in seen.values() if a.get("signal_peptide") is True)
    print(f"  {m:22s} answered {len(seen):2d}: any TM helix {tm:2d}, any Pfam domain {pf:2d}, signal peptide called {sp:2d}")

print("\n== #205: function answers for the designed cysteine protease HC34 (9YP0)")
for m, f in files("structure"):
    for r in rows(f):
        if r.get("pdb") == "9YP0":
            a = ans(r, "structure") or {}
            print(f"  {m}\n    protein_name: {a.get('protein_name')!r}\n    function:     {a.get('function')!r}\n    recognised:   {a.get('recognised')!r}")

print("\n== #206: novel stratum (ASPRV1 once), contact precision by two definitions")
T = {t["pdb"]: t for t in json.loads((ROOT / "experiments/structure/truth.json").read_text())}
REPEATS = {"27JP", "27JO", "27IQ"}
def pair_ok(p): return isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) for v in p)
for m, f in files("structure"):
    reported, strict, nsub, nqual = [], [], [], []
    for r in rows(f):
        t = T.get(r.get("pdb"))
        if not t or t["stratum"] != "novel" or r["pdb"] in REPEATS: continue
        a = ans(r, "structure")
        if not a: continue
        ca = {int(k): v for k, v in t["ca"].items()}
        sub = [p for p in (a.get("contacts") or []) if pair_ok(p)]
        qual = [p for p in sub if abs(p[0] - p[1]) >= 24 and p[0] in ca and p[1] in ca]
        hits = sum(math.dist(ca[i], ca[j]) < 8 for i, j in qual)
        nsub.append(len(sub)); nqual.append(len(qual))
        if qual: reported.append(hits / len(qual))
        if sub: strict.append(hits / len(sub))
    print(f"  {m:22s} n={len(nsub):2d}: as reported (qualifying pairs only) {100*statistics.mean(reported):.1f}%;"
          f" over all submitted pairs {100*statistics.mean(strict):.1f}%; pairs submitted {sum(nsub)}, qualifying {sum(nqual)}")
