"""Score the decoy-substitution control against the original catalytic-site mutants. Usage: score_decoys.py PROBE_DIR

Purpose: report, per model, how often a sequence with a substitution at a non-catalytic position is still called
         active, how often the model names that position as a lost catalytic residue, and the paired contrast
         with the catalytic-site mutant of the same protein.
Inputs:  decoys.json and results/MODEL.jsonl beside this file (from build_decoys.py and ask_decoys.py);
         PROBE_DIR/pseudo/results/MODEL.jsonl, the stored answers for the original mutants (a different machine
         and date; see README.md); results/bridge-MODEL.jsonl if present, the original mutants rerun on this route.
Outputs: a plain-text table on standard output. Nothing is written.
Serves:  branch experiment/decoy-substitution-control of ai4curation/fable-sequence-to-function. Date: 2026-11-18.

Intervals are 95% Wilson score intervals. The paired test is an exact two-sided McNemar (binomial) test on the
proteins where the decoy and the catalytic-site mutant got different calls. "Active" means the answer "yes";
"no" and "uncertain" both count as not called active, as in the original figure.
"""
import collections, json, math, pathlib, sys
if len(sys.argv) != 2: sys.exit(__doc__)
HERE = pathlib.Path(__file__).parent; PROBE = pathlib.Path(sys.argv[1])
MODELS = ["claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"]
VARIANTS = [("asp_decoy_to_asn", "asp_to_asn"), ("lys_decoy_to_met", "lys_to_met"), ("site_decoy_to_ala", "site_to_ala")]
D = {(d["accession"], d["variant"]): d for d in json.loads((HERE / "decoys.json").read_text())}
T = {t["accession"]: t for t in json.loads((PROBE / "pseudo/truth.json").read_text())}
def site(acc, variant): t = T[acc]; return {"asp_to_asn": t.get("asp"), "lys_to_met": t.get("lys"), "site_to_ala": t.get("site")}[variant]
def rows(path): return [json.loads(l) for l in path.open()] if path.exists() else []
def active(r): return str((r.get("ans") or {}).get("catalytically_active")).lower() == "yes"
def positions(r, key): return {x.get("position") for x in ((r.get("ans") or {}).get(key) or []) if isinstance(x, dict)}
def wilson(k, n, z=1.959964):
    if not n: return "n/a"
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{k}/{n} ({100 * p:.0f}%, {100 * max(0, c - h):.0f}-{100 * min(1, c + h):.0f})"
def mcnemar(b, c):
    n = b + c
    return 1.0 if not n else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)

for m in MODELS:
    dec = [r for r in rows(HERE / "results" / f"{m}.jsonl")]
    if not dec: print(f"\n== {m}: no decoy results"); continue
    bad = [r for r in dec if r.get("error") or not r.get("ans") or r.get("context_tokens_high")]
    dec = {(r["accession"], r["variant"]): r for r in dec if r not in bad}
    stored = {(r["accession"], r["variant"]): r for r in rows(PROBE / "pseudo/results" / f"{m}.jsonl") if r.get("ans")}
    bridge = {(r["accession"], r["variant"]): r for r in rows(HERE / "results" / f"bridge-{m}.jsonl") if r.get("ans") and not r.get("context_tokens_high")}
    efforts = sorted({r["effort"] for r in dec.values()}); cost = sum(r.get("cost") or 0 for r in dec.values())
    print(f"\n== {m}: {len(dec)} decoy answers scored, {len(bad)} excluded (failed, unparsed or high context), effort {efforts}, cost ${cost:.2f}, "
          f"median input tokens {sorted((r.get('cache_creation_input_tokens') or 0) + (r.get('input_tokens') or 0) + (r.get('cache_read_input_tokens') or 0) for r in dec.values())[len(dec) // 2]}")
    tot = collections.Counter()
    for dv, ov in VARIANTS + [("all", "all")]:
        if dv == "all": k = tot; label = "all three types"
        else:
            k = collections.Counter(); label = f"{dv} vs {ov}"
            for (acc, v), r in dec.items():
                if v != dv: continue
                pos = D[(acc, v)]["position"]; o = stored.get((acc, ov)); w = stored.get((acc, "wt"))
                k["n"] += 1; k["decoy_active"] += active(r)
                k["decoy_named_lost"] += pos in positions(r, "substituted_or_missing")          # false localisation: the harmless change is reported as a lost catalytic residue
                k["decoy_any_lost"] += bool(positions(r, "substituted_or_missing"))
                k["true_site_kept"] += site(acc, ov) in positions(r, "catalytic_residues")      # the real catalytic residue is still listed as present
                if o:
                    k["pairs"] += 1; k["orig_active"] += active(o); k["orig_named_lost"] += site(acc, ov) in positions(o, "substituted_or_missing")
                    k["decoy_yes_orig_no"] += active(r) and not active(o); k["decoy_no_orig_yes"] += (not active(r)) and active(o)
                if w: k["wt_n"] += 1; k["wt_active"] += active(w)
                b = bridge.get((acc, ov))
                if b and o: k["bridge_n"] += 1; k["bridge_same_call"] += active(b) == active(o); k["bridge_active"] += active(b)
            tot.update(k)
        if not k["n"]: continue
        print(f"  {label}")
        print(f"    decoy still called active            {wilson(k['decoy_active'], k['n'])}")
        print(f"    catalytic-site mutant called active  {wilson(k['orig_active'], k['pairs'])}   (stored run, same proteins)")
        print(f"    wild type called active              {wilson(k['wt_active'], k['wt_n'])}   (stored run, same proteins)")
        print(f"    paired: decoy active and mutant not  {k['decoy_yes_orig_no']}; mutant active and decoy not {k['decoy_no_orig_yes']}; exact McNemar p = {mcnemar(k['decoy_yes_orig_no'], k['decoy_no_orig_yes']):.2g}")
        print(f"    decoy position named as lost         {wilson(k['decoy_named_lost'], k['n'])};  any residue named as lost {wilson(k['decoy_any_lost'], k['n'])}")
        print(f"    catalytic position named as lost     {wilson(k['orig_named_lost'], k['pairs'])}   (stored run, catalytic-site mutant)")
        print(f"    true catalytic residue still listed  {wilson(k['true_site_kept'], k['n'])}   (decoy answers)")
        if k["bridge_n"]: print(f"    bridge: mutants rerun on this route  {k['bridge_n']} rerun, same call as stored run in {k['bridge_same_call']}, called active {k['bridge_active']}")
    notyes = [(acc, v, D[(acc, v)]["position"], str(r["ans"].get("catalytically_active")), sorted(p for p in positions(r, "substituted_or_missing") if p)) for (acc, v), r in sorted(dec.items()) if not active(r)]
    print(f"  decoys not called active ({len(notyes)}): " + ("; ".join(f"{acc} {v} pos {p} -> {call}, named lost {lost}" for acc, v, p, call, lost in notyes) or "none"))
