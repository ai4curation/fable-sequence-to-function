"""Score Pfam, transmembrane and signal-peptide calls in results/*.jsonl against truth.json. Usage: score.py

Set B is the 45 sampled UniProt proteins, set A the 15 obscure DUF proteins, "all" both together.
The answer is read from each reply's text by common.answer: the last JSON object with the requested keys. Where a
reply holds more than one, the headline counts are also printed for the first object and with those replies left out.
"""
import json, glob, pathlib, re, collections
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import KEYS, NOTE_FAILED, NOTE_TOOL, efforts, failed, json_objects, reparse, tool_calls
HERE = pathlib.Path(__file__).parent
T = {t["accession"]: t for t in json.load(open(HERE / "truth.json"))}
norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
def ov(a, b): return max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)
def fam(t, a):
    """(given any Pfam domain, given at least one correct family) for one answer, by the rule used in the main loop."""
    pd = [d for d in (a.get("pfam_domains") or []) if isinstance(d, dict)]
    acc = {p["accession"] for p in t["pfam"]}; nm = {norm(p["short"]) for p in t["pfam"]} | {norm(p["name"]) for p in t["pfam"]}
    return bool(pd), any(str(d.get("accession") or "").split(".")[0] in acc or norm(d.get("name")) in nm for d in pd)
def headline(R, pick):
    """Set all: real proteins with a correct family, and shuffled proteins given any domain, when `pick` chooses each row's answer."""
    out = []
    for cond, k in (("real", 1), ("shuffled", 0)):
        x = [(r, a) for r in R if r["condition"] == cond and (a := pick(r))]
        out.append(f"{sum(fam(T[r['accession']], a)[k] for r, a in x)}/{len(x)}")
    return out
for f in sorted(glob.glob(str(HERE / "results" / "claude-*.jsonl"))):
    R = [json.loads(l) for l in open(f)]; multi = reparse(R, KEYS["features"])
    ok = [r for r in R if r.get("ans")]
    bad = failed(R); tool = tool_calls(R)
    print(f"\n== {pathlib.Path(f).stem}: {len(R)} calls, {len(R)-len(ok)-bad} unparsed, effort {efforts(R)}, cost ${sum(r.get('cost') or 0 for r in R):.2f}")
    if bad: print(f"  {NOTE_FAILED}: {bad}")
    if tool: print(f"  {NOTE_TOOL}: " + ", ".join(r["accession"] + " " + r["condition"] for r in tool))
    if multi:
        ids = {id(r) for r in multi}; last = headline(R, lambda r: r["ans"])
        first = headline(R, lambda r: (json_objects(r.get("text"), KEYS["features"]) or [None])[0]); out = headline(R, lambda r: None if id(r) in ids else r["ans"])
        print(f"  replies with more than one JSON object, scored on the last: {len(multi)} ({', '.join(r['accession'] + ' ' + r['condition'] for r in multi)})")
        print(f"    set all, real proteins with >=1 correct family and shuffled proteins given any Pfam domain: last object {last[0]} and {last[1]}; "
              f"first object {first[0]} and {first[1]}; those replies left out {out[0]} and {out[1]}")
    for cond in ("real", "shuffled"):
        for st in ("B", "A", "all"):
            x = [r for r in ok if r["condition"] == cond and st in (T[r["accession"]]["set"], "all")]
            if not x: continue
            tp_id = tp_nm = npred = ntrue = prot_any = prot_hit = 0; iou = []; tmc = tmt = tmexact = tmn = 0; sp = collections.Counter(); helix_hit = helix_true = helix_pred = 0
            for r in x:
                t = T[r["accession"]]; a = r["ans"]
                pd = [d for d in (a.get("pfam_domains") or []) if isinstance(d, dict)]
                true_acc = {p["accession"] for p in t["pfam"]}; true_nm = {norm(p["short"]) for p in t["pfam"]} | {norm(p["name"]) for p in t["pfam"]}
                npred += len(pd); ntrue += len(true_acc); given, right = fam(t, a); prot_any += given; prot_hit += right
                for d in pd:
                    ia = str(d.get("accession") or "").split(".")[0] in true_acc; im = norm(d.get("name")) in true_nm
                    tp_id += ia; tp_nm += (ia or im)
                    if (ia or im) and isinstance(d.get("start"), int) and isinstance(d.get("end"), int):
                        best = max(((ov((d["start"], d["end"]), (p["start"], p["end"])) / (max(d["end"], p["end"]) - min(d["start"], p["start"]) + 1)) for p in t["pfam"]
                                    if p["accession"] == str(d.get("accession")).split(".")[0] or norm(d.get("name")) in (norm(p["short"]), norm(p["name"]))), default=None)
                        if best is not None: iou.append(best)
                ph = [h for h in (a.get("transmembrane_helices") or []) if isinstance(h, list) and len(h) == 2 and all(isinstance(v, int) for v in h)]
                tmn += 1; tmexact += len(ph) == len(t["tm"]); tmc += (bool(ph) == bool(t["tm"]))
                helix_true += len(t["tm"]); helix_pred += len(ph); helix_hit += sum(any(ov(h, u) >= 10 for h in ph) for u in t["tm"])
                sp[(bool(a.get("signal_peptide")), t["signal"])] += 1
            print(f"  {cond:8s} set {st} n={len(x)}: Pfam proteins with >=1 correct family {prot_hit}/{len(x)}; predicted domains {npred} (correct by id {tp_id}, by id-or-name {tp_nm}); true families {ntrue}; "
                  f"boundary IoU mean {sum(iou)/len(iou) if iou else float('nan'):.3f} (n={len(iou)})")
            if cond == "real":
                print(f"           TM: membrane yes/no agrees {tmc}/{tmn}, helix count exact {tmexact}/{tmn}, helices recovered {helix_hit}/{helix_true}, predicted {helix_pred}; "
                      f"signal peptide TP {sp[(True,True)]} FN {sp[(False,True)]} FP {sp[(True,False)]} TN {sp[(False,False)]}")
            else:
                print(f"           (shuffled = hallucination check) proteins given any Pfam domain {prot_any}/{len(x)}")
