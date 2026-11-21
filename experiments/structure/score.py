"""Score predicted secondary structure and contacts against the deposited PDB structures in truth.json. Usage: score.py

Reports each stratum as drawn, and the novel stratum with human ASPRV1 counted once (it was drawn four times).
A few calls list a second model in their usage record; they are listed, and every line is repeated without them.
Replies that took more than one request (the tool asked again after an output limit, a classifier stop or an empty
reply, or retried a failed request) are scored like any other; every line is also repeated without them, as a
sensitivity check (#83). Usable rows that record no turn count cannot show this; every scorer prints their number (#189, #192).
Also prints the counts from the manual function grading in function_grading.yaml.
The answer is read from each reply's text by common.answer: the last JSON object with the requested keys.
figures/make_figures.py imports load() and one() from this file, so the figures use the same scoring code.
"""
import collections, runpy, json, math, pathlib, statistics
import yaml
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import KEYS, NOTE_CONTINUED, NOTE_NO_TURNS, no_turn_count, NOTE_COST, NOTE_FAILED, NOTE_TOOL, efforts, continued, cost_unknown, failed, reparse, tool_calls
HERE = pathlib.Path(__file__).parent
T = {t["pdb"]: t for t in json.loads((HERE / "truth.json").read_text())}
ASPRV1_REPEATS = {"27JP", "27JO", "27IQ"}   # 27IK is kept as the single ASPRV1 entry
def ss(n, helices, strands):
    s = ["C"] * (n + 1)
    for code, segs in (("H", helices), ("E", strands)):
        for seg in segs or []:
            if isinstance(seg, list) and len(seg) == 2 and all(isinstance(v, int) for v in seg):
                for i in range(max(1, seg[0]), min(n, seg[1]) + 1): s[i] = code
    return s
def one(t, a):
    L = len(t["sequence"]); ca = {int(k): v for k, v in t["ca"].items()}; obs = sorted(ca)   # residues resolved in the crystal structure
    true, pred = ss(L, t["helices"], t["strands"]), ss(L, a.get("helices"), a.get("strands"))
    submitted = [p for p in (a.get("contacts") or []) if isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) for v in p)]
    # Reported precision is over qualifying pairs only: at least 24 apart in sequence, both residues resolved.
    pairs = [p for p in submitted if abs(p[0] - p[1]) >= 24 and p[0] in ca and p[1] in ca]
    hit = [math.dist(ca[i], ca[j]) < 8 for i, j in pairs]
    lr = [(i, j) for i in obs for j in obs if j - i >= 24]
    return dict(q3=sum(true[i] == pred[i] for i in obs) / len(obs), base=max(sum(true[i] == c for i in obs) for c in "HEC") / len(obs),
                prec=sum(hit) / len(hit) if hit else None, prec_all=sum(hit) / len(submitted) if submitted else None,
                n_submitted=len(submitted), n_qualifying=len(pairs), top5=sum(hit[:5]) / len(hit[:5]) if hit else None,
                chance=sum(math.dist(ca[i], ca[j]) < 8 for i, j in lr) / len(lr), rec=bool(a.get("recognised")))
m = lambda x: 100 * statistics.mean(x) if x else float("nan")
def line(label, S):
    p = [s["prec"] for s in S if s["prec"] is not None]
    print(f"  {label:34s} n={len(S):2d}: Q3 {m([s['q3'] for s in S]):.1f}% (best single state {m([s['base'] for s in S]):.1f}%); long-range contact precision {m(p):.1f}% "
          f"(top-5 {m([s['top5'] for s in S if s['top5'] is not None]):.1f}%; chance {m([s['chance'] for s in S]):.1f}%; over all submitted pairs {m([s['prec_all'] for s in S if s['prec_all'] is not None]):.1f}%, {sum(s['n_qualifying'] for s in S)} of {sum(s['n_submitted'] for s in S)} pairs qualifying); says it recognises the protein {sum(s['rec'] for s in S)}/{len(S)}")
    return m([s["q3"] for s in S]), m(p)
def per_protein(files, strata=("novel",)):
    """One line per protein and results file: Q3, its single-state baseline, and contact precision over qualifying pairs."""
    print("\n== per protein (ASPRV1 once): Q3 %, best single state %, long-range contact precision % (qualifying pairs correct/qualifying, of submitted)")
    for f in files:
        R, _ = load(f)
        for r in R:
            t = T[r["pdb"]]
            if not r.get("ans") or t["stratum"] not in strata or r["pdb"] in ASPRV1_REPEATS: continue
            v = one(t, r["ans"]); k = round(v["prec"] * v["n_qualifying"]) if v["prec"] is not None else 0
            print(f"  {pathlib.Path(f).stem:24s} {r['pdb']:5s} Q3 {100*v['q3']:5.1f} (base {100*v['base']:5.1f})  contacts {100*v['prec'] if v['prec'] is not None else float('nan'):5.1f} ({k}/{v['n_qualifying']}, of {v['n_submitted']})")
def load(f):
    """Rows of one results file with `ans` read from the reply text, and the rows holding more than one answer object."""
    R = [json.loads(l) for l in open(f)]; return R, reparse(R, KEYS["structure"])
def main():
    for f in sorted((HERE / "results").glob("*.jsonl")):
        R, multi = load(f); ok = [r for r in R if r.get("ans")]
        mixed = {r["pdb"]: r["served"] for r in R if len(r.get("served") or []) > 1}
        isapi = lambda r: bool(r.get("is_error")) or (r.get("text") or "").lstrip().startswith("API Error")
        api = sum(isapi(r) for r in R); bad = failed([r for r in R if not isapi(r)]); tool = tool_calls(R)   # bad: failed calls and attached context
        print(f"\n== {f.stem}: {len(R)} calls, {len(R)-len(ok)-api-bad} unparsed, {api} API-error replies (no answer; excluded), effort {efforts(R)}, cost ${sum(r.get('cost') or 0 for r in R):.2f}; calls listing a second model: {mixed or 'none'}")
        if multi: print(f"  replies with more than one JSON object, scored on the last: {len(multi)}")
        if bad: print(f"  {NOTE_FAILED}: {bad}")
        if cost_unknown(R): print(f"  {NOTE_COST}: {len(cost_unknown(R))}")
        if continued(R): print(f"  {NOTE_CONTINUED}: {len(continued(R))}")
        if no_turn_count(R): print(f"  {NOTE_NO_TURNS}: {len(no_turn_count(R))}")   # #189, #192
        if tool: print(f"  {NOTE_TOOL}: " + ", ".join(r["pdb"] for r in tool))
        cont = {r["pdb"] for r in continued(R)}
        for tag, keep, skip in (("", lambda r: True, False), (" [without those calls]", lambda r: r["pdb"] not in mixed, not mixed),
                                (" [without continued replies]", lambda r: r["pdb"] not in cont, not cont)):   # #83
            if skip: continue
            sel = [r for r in ok if keep(r)]
            known = None
            for stratum in ("novel", "known"):
                v = line(stratum + tag, [one(T[r["pdb"]], r["ans"]) for r in sel if T[r["pdb"]]["stratum"] == stratum])
                if stratum == "known": known = v
            novel1 = line("novel, ASPRV1 counted once" + tag, [one(T[r["pdb"]], r["ans"]) for r in sel if T[r["pdb"]]["stratum"] == "novel" and r["pdb"] not in ASPRV1_REPEATS])
            print(f"  {'known minus novel (ASPRV1 once)' + tag}: Q3 {known[0] - novel1[0]:+.1f} points; long-range contact precision {known[1] - novel1[1]:+.1f} points")   # #42
    per_protein(sorted((HERE / "results").glob("*.jsonl")))
    G = yaml.safe_load((HERE / "function_grading.yaml").read_text())
    print("\n== first function grading (one grader, unblinded, three grades; superseded by the regrading below), 12 distinct novel proteins")
    for model in ("claude-fable-5-2", "claude-opus-5-5"):
        c = collections.Counter(g[model]["grade"] for g in G); print(f"  {model}: correct {c['correct']}, abstain {c['abstain']}, wrong {c['wrong']}")
    print()
    runpy.run_path(str(HERE / "function_regrade" / "summarise.py"), run_name="__main__")
if __name__ == "__main__": main()
