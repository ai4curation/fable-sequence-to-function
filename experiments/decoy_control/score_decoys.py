"""Score the decoy-substitution control against the catalytic-site mutants of test 3. Usage: score_decoys.py [PROBE_DIR]

Purpose: report, per model, how often a sequence with a substitution at a non-catalytic position is still called
         active, how often the model names that position as a lost catalytic residue, and the paired contrast
         with the catalytic-site mutant of the same protein.
Inputs:  decoys.json and results/MODEL.jsonl beside this file (from build_decoys.py and ask_decoys.py);
         PROBE_DIR/pseudo/{truth.json,results/MODEL.jsonl}, the stored answers of test 3 (asked with the original
         flags on another machine; see README.md); results/bridge-MODEL.jsonl if present, the same mutants and
         wild types asked again on the route of the decoys. PROBE_DIR defaults to experiments/.
Outputs: a plain-text table on standard output (frozen in expected/decoy_control.txt). Nothing is written.
Serves:  pull request 10 and issues 11, 12 and 17 of ai4curation/fable-sequence-to-function. Date: 2026-11-18, revised 2026-11-19.

Every answer is read from the reply text by common.answer (the last JSON object with the requested keys; a reply
with a tool invocation has none), and rows that common.unusable marks are left out, as in the four tests.
Each comparison is printed twice when the rerun exists: against the stored run, and against the rerun on the
decoys' route. Only the second compares answers collected the same way.
Intervals are 95% Wilson score intervals. The paired test is an exact two-sided McNemar (binomial) test on the
pairs where the decoy and the catalytic-site mutant got different calls. In the "all three types" block each
kinase contributes two pairs, so those pairs are not independent; the per-type blocks have one pair per protein.
"Active" means the answer "yes"; "no", "uncertain" and an answer without the field all count as not called active,
as in Figure 1; answers without the field are listed.
Files: results/NAME.jsonl is one block, compared with PROBE_DIR/pseudo/results/NAME.jsonl and results/bridge-NAME.jsonl,
where NAME is MODEL or MODEL-TAG. Empty files are skipped. A question may have one usable row per file; a second one stops the script.
"""
import ast, collections, json, math, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from common import KEYS, NOTE_CONTINUED, NOTE_FAILED, NOTE_TOOL, continued, efforts, failed, reparse, sha, tool_calls, unusable
if len(sys.argv) > 2: sys.exit(__doc__)
PROBE = pathlib.Path(sys.argv[1]) if len(sys.argv) == 2 else HERE.parent
VARIANTS = [("asp_decoy_to_asn", "asp_to_asn"), ("lys_decoy_to_met", "lys_to_met"), ("site_decoy_to_ala", "site_to_ala")]
D = {(d["accession"], d["variant"]): d for d in json.loads((HERE / "decoys.json").read_text())}
T = {t["accession"]: t for t in json.loads((PROBE / "pseudo/truth.json").read_text())}
def site(acc, variant): t = T[acc]; return {"asp_to_asn": t.get("asp"), "lys_to_met": t.get("lys"), "site_to_ala": t.get("site")}[variant]
def load(path):
    """Rows of one results file with `ans` read from the reply text; the answered rows by (accession, variant)."""
    R = [json.loads(l) for l in path.open() if l.strip()] if path.exists() else []; reparse(R, KEYS["pseudo"])
    twice = sorted(k for k, n in collections.Counter((r["accession"], r["variant"]) for r in R if not unusable(r)).items() if n > 1)
    if twice: sys.exit(f"{path}: more than one usable row for {twice}; a question is scored on one answer")
    return R, {(r["accession"], r["variant"]): r for r in R if r.get("ans")}
def active(r): return str(r["ans"].get("catalytically_active")).lower() == "yes"
def positions(r, key): return {x.get("position") for x in (r["ans"].get(key) or []) if isinstance(x, dict)}
def original_prompt(path):
    """The string assigned to P in pseudo/ask.py, read without running that file (as ask_decoys.py does)."""
    return next(ast.literal_eval(n.value) for n in ast.parse(path.read_text()).body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "P" for t in n.targets))
P = original_prompt(PROBE / "pseudo/ask.py")
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))
SEQ = {k: d["sequence"] for k, d in D.items()}; SEQ.update({(t["accession"], v): s for t in T.values() for v, s in t["variants"].items()})
def nocall(r): return str(r["ans"].get("catalytically_active")).lower() not in ("yes", "no", "uncertain")
def describe(name, R, ans):
    """Checks on one file that do not depend on the comparison: the question sent, the residue numbering, thinking, missing calls."""
    h = [r for r in R if r.get("prompt_sha256")]; good = sum(r["prompt_sha256"] == sha(P + fasta(SEQ[(r["accession"], r["variant"])])) for r in h)
    listed = [(x.get("residue"), x.get("position"), SEQ[k]) for k, r in ans.items() for x in (r["ans"].get("catalytic_residues") or []) if isinstance(x, dict)]
    match = sum(isinstance(p, int) and 0 < p <= len(s) and s[p - 1] == str(res).strip().upper() for res, p, s in listed)
    think = sum((r.get("thinking_tokens") or 0) > 0 for r in ans.values()); none = sorted(f"{a} {v}" for (a, v), r in ans.items() if nocall(r))
    print(f"    {name}: listed catalytic residues that match the given sequence at the stated position {match}/{len(listed)}; answers that used thinking {think}/{len(ans)}; "
          f"rows whose recorded prompt hash is that of the test 3 prompt plus this sequence {good}/{len(h)}; rows without a recorded hash {len(R) - len(h)}"
          + (f"; answers without an activity call, counted as not called active: {', '.join(none)}" if none else ""))
def mentions(r, pos): return bool(re.search(rf"(?<!\d){pos}(?!\d)", r.get("text") or ""))   # the position number anywhere in the reply
def wilson(k, n, z=1.959964):
    if not n: return "n/a"
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{k}/{n} ({100 * p:.0f}%, {100 * max(0, c - h):.0f}-{100 * min(1, c + h):.0f})"
def mcnemar(b, c):
    n = b + c
    return 1.0 if not n else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)
def versus(dec, pairs, ref):
    """Counts for the decoys of `pairs` (accession, decoy variant, mutant variant) against one run of the mutants and wild types."""
    k = collections.Counter()
    for acc, dv, ov in pairs:
        r = dec[(acc, dv)]; o = ref.get((acc, ov))
        if o:
            k["pairs"] += 1; k["orig_active"] += active(o); k["orig_named_lost"] += site(acc, ov) in positions(o, "substituted_or_missing")
            k["decoy_yes_orig_no"] += active(r) and not active(o); k["decoy_no_orig_yes"] += (not active(r)) and active(o)
    wt = [ref[(acc, "wt")] for acc in sorted({acc for acc, _, _ in pairs}) if (acc, "wt") in ref]   # once per protein: a kinase has two decoys
    k["wt_n"] = len(wt); k["wt_active"] = sum(map(active, wt)); return k

ORDER = ["claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"]   # as in the manuscript; other files follow by name
for f in sorted((p for p in (HERE / "results").glob("*.jsonl") if not p.name.startswith(("bridge-", "canary-"))), key=lambda p: (ORDER.index(p.stem) if p.stem in ORDER else len(ORDER), p.stem)):
    m = f.stem; R, dec = load(f); S, stored = load(PROBE / "pseudo/results" / f"{m}.jsonl"); B, bridge = load(HERE / "results" / f"bridge-{m}.jsonl")
    if not R: continue   # an empty file, as a zero-question run could leave
    ctx = sorted(r["context_tokens"] if "context_tokens" in r else sum(r.get(x) or 0 for x in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) for r in dec.values())
    print(f"\n== {m}: {len(R)} decoy calls, {len(dec)} answers scored, {len(R) - len(dec) - failed(R)} without an answer, effort {efforts(R)}, "
          f"cost ${sum(r.get('cost') or 0 for r in R):.2f}, median input tokens {ctx[len(ctx) // 2] if ctx else 'n/a'}")
    if failed(R): print(f"  {NOTE_FAILED}: {failed(R)}")
    if continued(R) or continued(B): print(f"  {NOTE_CONTINUED}: decoys {len(continued(R))}, rerun {len(continued(B))}")
    if tool_calls(R): print(f"  {NOTE_TOOL}: " + ", ".join(r["accession"] + " " + r["variant"] for r in tool_calls(R)))
    refs = [("stored run", stored)]
    if B:
        refs.append(("rerun on this route", bridge)); both = sorted(set(bridge) & set(stored)); same = sum(active(bridge[x]) == active(stored[x]) for x in both)
        differ = [f"{acc} {v} (stored {stored[(acc, v)]['ans'].get('catalytically_active')}, rerun {bridge[(acc, v)]['ans'].get('catalytically_active')})" for acc, v in both if active(bridge[(acc, v)]) != active(stored[(acc, v)])]
        print(f"  rerun of the test 3 mutants and wild types on this route: {len(B)} calls, {len(bridge)} answers, effort {efforts(B)}, cost ${sum(r.get('cost') or 0 for r in B):.2f}"
              + (f"; {NOTE_FAILED}: {failed(B)}" if failed(B) else "") + (f"; {NOTE_TOOL}: {len(tool_calls(B))}" if tool_calls(B) else ""))
        print(f"    same active/not-active call as the stored run in {same}/{len(both)}" + (": differ " + "; ".join(differ) if differ else ""))
    print("  per file:"); describe("decoys", R, dec); describe("stored run", S, {k: r for k, r in stored.items() if k in SEQ and T[k[0]]["group"] != "pseudo"})
    if B: describe("rerun on this route", B, bridge)
    if not dec: continue
    for dv, ov in VARIANTS + [("all", "all")]:
        pairs = sorted((acc, v, dict(VARIANTS)[v]) for acc, v in dec if dv in (v, "all"))
        if not pairs: continue
        d = [(dec[(acc, v)], D[(acc, v)]["position"], site(acc, o)) for acc, v, o in pairs]; n = len(d)
        print(f"  {'all three types' if dv == 'all' else dv + ' vs ' + ov}")
        print(f"    decoy still called active            {wilson(sum(active(r) for r, _, _ in d), n)}")
        for name, ref in refs:
            k = versus(dec, pairs, ref)
            print(f"    catalytic-site mutant called active  {wilson(k['orig_active'], k['pairs'])}   ({name}, same proteins)")
            print(f"    wild type called active              {wilson(k['wt_active'], k['wt_n'])}   ({name}, same proteins)")
            print(f"    paired: decoy active and mutant not  {k['decoy_yes_orig_no']}; mutant active and decoy not {k['decoy_no_orig_yes']}; exact McNemar p = {mcnemar(k['decoy_yes_orig_no'], k['decoy_no_orig_yes']):.2g}   ({name})")
            print(f"    catalytic position named as lost     {wilson(k['orig_named_lost'], k['pairs'])}   ({name}, catalytic-site mutant)")
        print(f"    decoy position named as lost         {wilson(sum(p in positions(r, 'substituted_or_missing') for r, p, _ in d), n)};  any residue named as lost {wilson(sum(bool(positions(r, 'substituted_or_missing')) for r, _, _ in d), n)}")
        print(f"    decoy position listed as catalytic   {wilson(sum(p in positions(r, 'catalytic_residues') for r, p, _ in d), n)}")
        print(f"    true catalytic residue still listed  {wilson(sum(s in positions(r, 'catalytic_residues') for r, _, s in d), n)}   (decoy answers)")
        print(f"    decoy position number in the reply   {wilson(sum(mentions(r, p) for r, p, _ in d), n)}   (anywhere in the text; read the replies listed below)")
    notyes = [(acc, v, D[(acc, v)]["position"], str(r["ans"].get("catalytically_active")), sorted(p for p in positions(r, "substituted_or_missing") if p)) for (acc, v), r in sorted(dec.items()) if not active(r)]
    print(f"  decoys not called active ({len(notyes)}): " + ("; ".join(f"{acc} {v} pos {p} -> {call}, named lost {lost}" for acc, v, p, call, lost in notyes) or "none"))
    seen = [f"{acc} {v} pos {D[(acc, v)]['position']}" for (acc, v), r in sorted(dec.items()) if mentions(r, D[(acc, v)]["position"])]
    print(f"  replies whose text holds the decoy position number ({len(seen)}): " + ("; ".join(seen) or "none"))
