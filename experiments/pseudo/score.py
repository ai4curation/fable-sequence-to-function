"""Score the catalytic-activity calls in results/*.jsonl against truth.json. Usage: score.py

The answer is read from each reply's text by common.answer: the last JSON object with the requested keys.
figures/make_figures.py imports load() from this file, so Figure 1 reads the answers the same way.
"""
import collections, glob, json, pathlib
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import KEYS, NOTE_CONTINUED, NOTE_COST, NOTE_FAILED, NOTE_TOOL, efforts, continued, cost_unknown, failed, reparse, tool_calls
HERE = pathlib.Path(__file__).parent
T = {t["accession"]: t for t in json.loads((HERE / "truth.json").read_text())}
# Enzymes whose curated active-site position is disputed by adjudication/; mutant activity is unresolved.
# They stay in the main counts; one extra line per file gives a post hoc sensitivity analysis without them.
DISPUTED = ("P64636", "Q08651")
def positions(ans, key):
    return {d.get("position") for d in (ans.get(key) or []) if isinstance(d, dict)}
def load(f):
    """Rows of one results file with `ans` read from the reply text, and the rows holding more than one answer object."""
    R = [json.loads(l) for l in open(f)]; return R, reparse(R, KEYS["pseudo"])
def summarize(ok):
    """Activity calls and curated-position counts for parsed rows, shared across providers."""
    rows = collections.defaultdict(collections.Counter); flagged = collections.Counter(); still = collections.Counter(); wtsite = collections.Counter()
    for r in ok:
        t = T[r["accession"]]; a = r["ans"]; key = (t["group"], r["variant"])
        rows[key][str(a.get("catalytically_active")).lower()] += 1
        site = {"asp_to_asn": t.get("asp"), "lys_to_met": t.get("lys"), "site_to_ala": t.get("site")}.get(r["variant"])
        if site:   # mutant: was the mutated position reported as substituted, or still listed as an intact catalytic residue?
            flagged[key] += site in positions(a, "substituted_or_missing")
            still[key] += site in positions(a, "catalytic_residues") and site not in positions(a, "substituted_or_missing")
        elif t["group"] in ("kinase", "enzyme"):   # wild type: is the curated catalytic position among those listed?
            want = [t["asp"], t["lys"]] if t["group"] == "kinase" else [t["site"]]
            wtsite[key] += all(w in positions(a, "catalytic_residues") for w in want)
    return rows, flagged, still, wtsite

def disputed_sensitivity(ok):
    """Print the post hoc sensitivity excluding the adjudicated, disputed reference sites."""
    kept = [r for r in ok if r["group"] == "enzyme" and r["variant"] == "site_to_ala" and r["accession"] not in DISPUTED]
    c = collections.Counter(str(r["ans"].get("catalytically_active")).lower() for r in kept)
    print(f"  enzyme  site_to_ala without {' and '.join(DISPUTED)} (curated site disputed, see adjudication/) n={len(kept)}: active yes {c['yes']}  no {c['no']}  uncertain {c['uncertain']}; "
          f"mutated position flagged as substituted {sum(T[r['accession']]['site'] in positions(r['ans'], 'substituted_or_missing') for r in kept)}/{len(kept)}")

def main():
    for f in sorted(glob.glob(str(HERE / "results" / "*.jsonl"))):
        R, multi = load(f); ok = [r for r in R if r.get("ans")]
        bad = failed(R); tool = tool_calls(R)
        print(f"\n== {pathlib.Path(f).stem}: {len(R)} calls, {len(R)-len(ok)-bad} unparsed, effort {efforts(R)}, cost ${sum(r.get('cost') or 0 for r in R):.2f}")
        if bad: print(f"  {NOTE_FAILED}: {bad}")
        if cost_unknown(R): print(f"  {NOTE_COST}: {len(cost_unknown(R))}")
        if continued(R): print(f"  {NOTE_CONTINUED}: {len(continued(R))}")
        if tool: print(f"  {NOTE_TOOL}: " + ", ".join(r["accession"] + " " + r["variant"] for r in tool))
        if multi: print(f"  replies with more than one JSON object, scored on the last: {len(multi)}")
        rows, flagged, still, wtsite = summarize(ok)
        named = [r for r in ok if r["group"] == "pseudo" and any(w in str(r["ans"].get("protein_name")).lower() for w in ("inactive", "pseudokinase"))]
        print(f"  natural pseudokinases whose returned protein_name says inactive or pseudokinase: {len(named)}/{sum(r['group'] == 'pseudo' for r in ok)}")
        called_no = [r for r in ok if r["group"] == "pseudo" and str(r["ans"].get("catalytically_active")).lower() == "no"]
        print(f"    of those called inactive: {sum(r in named for r in called_no)}/{len(called_no)}")
        mixed = [r for r in R if len(r.get("served") or []) > 1]
        print(f"  calls whose usage record lists a second model: {len(mixed)}")
        for key in sorted(rows):
            n = sum(rows[key].values()); c = rows[key]
            extra = f"; curated catalytic position(s) listed {wtsite[key]}/{n}" if key[1] == "wt" and key[0] != "pseudo" else (
                    f"; mutated position flagged as substituted {flagged[key]}/{n}, still listed as intact {still[key]}/{n}" if key[1] != "wt" else "")
            other = n - c["yes"] - c["no"] - c["uncertain"]   # e.g. a null catalytically_active
            print(f"  {key[0]:7s} {key[1]:11s} n={n}: active yes {c['yes']}  no {c['no']}  uncertain {c['uncertain']}" + (f"  other {other}" if other else "") + extra)
        disputed_sensitivity(ok)
if __name__ == "__main__": main()
