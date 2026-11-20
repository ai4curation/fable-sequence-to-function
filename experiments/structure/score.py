"""Score predicted secondary structure and contacts against the deposited PDB structures in truth.json. Usage: score.py

Reports each stratum as drawn, and the novel stratum with human ASPRV1 counted once (it was drawn four times).
A few calls list a second model in their usage record; they are listed, and every line is repeated without them.
Replies that took more than one request (the tool asked again after an output limit, a classifier stop or an empty
reply, or retried a failed request) are scored like any other; every line is also repeated without them, as a
sensitivity check (#83). Rows that record no turn count cannot show this, and their number is printed (#189).
Also prints the counts from the manual function grading in function_grading.yaml.
The answer is read from each reply's text by common.answer: the last JSON object with the requested keys.
figures/make_figures.py imports load() and one() from this file, so the figures use the same scoring code.
"""
import collections, json, math, pathlib, statistics
import yaml
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import KEYS, NOTE_CONTINUED, NOTE_COST, NOTE_FAILED, NOTE_TOOL, efforts, continued, cost_unknown, failed, reparse, tool_calls
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
    pairs = [p for p in (a.get("contacts") or []) if isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) for v in p)
             and abs(p[0] - p[1]) >= 24 and p[0] in ca and p[1] in ca]
    hit = [math.dist(ca[i], ca[j]) < 8 for i, j in pairs]
    lr = [(i, j) for i in obs for j in obs if j - i >= 24]
    return dict(q3=sum(true[i] == pred[i] for i in obs) / len(obs), base=max(sum(true[i] == c for i in obs) for c in "HEC") / len(obs),
                prec=sum(hit) / len(hit) if hit else None, top5=sum(hit[:5]) / len(hit[:5]) if hit else None,
                chance=sum(math.dist(ca[i], ca[j]) < 8 for i, j in lr) / len(lr), rec=bool(a.get("recognised")))
m = lambda x: 100 * statistics.mean(x) if x else float("nan")
def line(label, S):
    p = [s["prec"] for s in S if s["prec"] is not None]
    print(f"  {label:34s} n={len(S):2d}: Q3 {m([s['q3'] for s in S]):.1f}% (best single state {m([s['base'] for s in S]):.1f}%); long-range contact precision {m(p):.1f}% "
          f"(top-5 {m([s['top5'] for s in S if s['top5'] is not None]):.1f}%; chance {m([s['chance'] for s in S]):.1f}%); says it recognises the protein {sum(s['rec'] for s in S)}/{len(S)}")
    return m([s["q3"] for s in S]), m(p)
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
        unrecorded = [r for r in R if r.get("requests") is None and r.get("num_turns") is None]
        if unrecorded: print(f"  rows that record no turn count, so whether the reply was continued is not known: {len(unrecorded)}")   # #189
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
    G = yaml.safe_load((HERE / "function_grading.yaml").read_text())
    print("\n== manual function grading, 12 distinct novel proteins")
    for model in ("claude-fable-5-2", "claude-opus-5-5"):
        c = collections.Counter(g[model]["grade"] for g in G); print(f"  {model}: correct {c['correct']}, abstain {c['abstain']}, wrong {c['wrong']}")
if __name__ == "__main__": main()
