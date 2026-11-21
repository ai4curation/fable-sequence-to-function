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
import argparse, ast, collections, json, math, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from common import KEYS, NOTE_CONTINUED, NOTE_FAILED, NOTE_TOOL, answer, continued, efforts, requests_made, sha, tool_calls, unusable as common_unusable
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("probe_dir", nargs="?", type=pathlib.Path, default=HERE.parent)
ap.add_argument("--results", type=pathlib.Path, default=HERE / "results")
ap.add_argument("--pseudo-results", type=pathlib.Path)
args = ap.parse_args()
PROBE, RESULTS = args.probe_dir, args.results
PSEUDO_RESULTS = args.pseudo_results or PROBE / "pseudo/results"
def unusable(row):
    if "codex_row_format" in row or str(row.get("cli_version", "")).startswith("codex-exec"):
        sys.path.insert(0, str(HERE.parent.parent / "gemini_experiment"))
        from run_agy import agy_unusable
        return agy_unusable(row)
    return common_unusable(row)
def failed(rows): return sum(unusable(r) for r in rows)
VARIANTS = [("asp_decoy_to_asn", "asp_to_asn"), ("lys_decoy_to_met", "lys_to_met"), ("site_decoy_to_ala", "site_to_ala")]
D = {(d["accession"], d["variant"]): d for d in json.loads((HERE / "decoys.json").read_text())}
T = {t["accession"]: t for t in json.loads((PROBE / "pseudo/truth.json").read_text())}
def site(acc, variant): t = T[acc]; return {"asp_to_asn": t.get("asp"), "lys_to_met": t.get("lys"), "site_to_ala": t.get("site")}[variant]
def load(path):
    """Rows of one results file with `ans` read from the reply text; the answered rows by (accession, variant)."""
    R = [json.loads(l) for l in path.open() if l.strip()] if path.exists() else []
    for row in R: row["ans"] = None if unusable(row) else answer(row.get("text"), KEYS["pseudo"])
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
AA3 = dict(ALA="A", ARG="R", ASN="N", ASP="D", CYS="C", GLN="Q", GLU="E", GLY="G", HIS="H", ILE="I", LEU="L", LYS="K", MET="M", PHE="F", PRO="P", SER="S", THR="T", TRP="W", TYR="Y", VAL="V")
def one_letter(res): x = str(res).strip().upper(); return AA3.get(x, x)   # "K", "k", "Lys" and "LYS" all read as K
def money(r): c = r.get("cost"); return c if isinstance(c, (int, float)) and not isinstance(c, bool) else 0   # a cost that is not a number counts as 0
def isnum(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def ctx(r):
    """Input tokens of a row: context_tokens when recorded, else the sum of the counts that are numbers."""
    return r["context_tokens"] if isnum(r.get("context_tokens")) else sum(x for x in (r.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) if isnum(x))
def median(xs): xs = sorted(xs); n = len(xs); return None if not n else xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
def window(R):
    """First and last completion time (asked_at is written when the call returns), as HH:MM UTC with the date."""
    t = sorted(r["asked_at"] for r in R if r.get("asked_at")); return f"{t[0][:10]} {t[0][11:16]} to {t[-1][11:16]} UTC" if t else "no times recorded"
def call_of(r): c = str(r["ans"].get("catalytically_active")).lower(); return c if c in ("yes", "no", "uncertain") else "none"
def curated(acc): t = T[acc]; return [t["asp"], t["lys"]] if t["group"] == "kinase" else [t["site"]]
def describe(name, R, ans):
    """Checks on one file that do not depend on the comparison: the question sent, the residue numbering, thinking, missing calls.
    R and ans are restricted to the questions of this control (kinases and enzymes), so every count has the same denominator."""
    ours = lambda k: k in SEQ and T[k[0]]["group"] in ("kinase", "enzyme")
    R = [r for r in R if ours((r["accession"], r["variant"]))]; ans = {k: r for k, r in ans.items() if ours(k)}
    h = [r for r in R if r.get("prompt_sha256")]; good = sum(r["prompt_sha256"] == sha(P + fasta(SEQ[(r["accession"], r["variant"])])) for r in h)
    listed = [(x.get("residue"), x.get("position"), SEQ[k]) for k, r in ans.items() for x in (r["ans"].get("catalytic_residues") or []) if isinstance(x, dict)]
    match = sum(isinstance(p, int) and not isinstance(p, bool) and 0 < p <= len(s) and s[p - 1] == one_letter(res) for res, p, s in listed)
    think = sum((r.get("thinking_tokens") or 0) > 0 for r in ans.values()); none = sorted(f"{a} {v}" for (a, v), r in ans.items() if nocall(r))
    print(f"    {name}: listed catalytic residues that match the given sequence at the stated position {match}/{len(listed)}; answers that used thinking {think}/{len(ans)}; "
          f"rows whose recorded prompt hash is that of the test 3 prompt plus this sequence {good}/{len(h)}; rows without a recorded hash {len(R) - len(h)}"
          + (f"; answers without an activity call, counted as not called active: {', '.join(none)}" if none else ""))
    kind = lambda v: "wild type" if v == "wt" else "decoy" if "decoy" in v else "catalytic-site mutant"
    for g in ("wild type", "catalytic-site mutant", "decoy"):
        rs = [r for (a, v), r in ans.items() if kind(v) == g]
        if not rs: continue
        calls = collections.Counter(map(call_of, rs)); th = [r for r in rs if (r.get("thinking_tokens") or 0) > 0]; nt = [r for r in rs if not (r.get("thinking_tokens") or 0) > 0]
        print(f"      {g}: calls " + ", ".join(f"{c} {calls[c]}" for c in ("yes", "no", "uncertain", "none") if calls[c]) +
              f"; not called active with thinking {sum(not active(r) for r in th)}/{len(th)}, without thinking {sum(not active(r) for r in nt)}/{len(nt)}")
    miss = sorted(a for (a, v), r in ans.items() if v == "wt" and not all(c in positions(r, "catalytic_residues") for c in curated(a)))
    if any(v == "wt" for _, v in ans): print(f"      wild-type answers that do not list every curated catalytic position: {len(miss)}" + (f" ({', '.join(miss)})" if len(miss) <= 8 else ""))
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
            if call_of(r) != "none" and call_of(o) != "none":   # the same counts without answers that have no activity call
                k["called_pairs"] += 1; k["called_orig_active"] += active(o); k["called_yes_no"] += active(r) and not active(o); k["called_no_yes"] += (not active(r)) and active(o)
    wt = [ref[(acc, "wt")] for acc in sorted({acc for acc, _, _ in pairs}) if (acc, "wt") in ref]   # once per protein: a kinase has two decoys
    k["wt_n"] = len(wt); k["wt_active"] = sum(map(active, wt)); return k

dist = sorted(min(abs(d["position"] - c) for c in curated(d["accession"])) for d in D.values())
print(f"Decoy positions: {len(D)} decoys in {len({d['accession'] for d in D.values()})} proteins; distance to the nearest curated catalytic position of the protein: "
      f"median {median(dist):g}, minimum {dist[0]}, within 10 residues {sum(x <= 10 for x in dist)}, within 20 {sum(x <= 20 for x in dist)}")
nodecoy = sorted(t["accession"] for t in T.values() if t["group"] in ("kinase", "enzyme") and t["accession"] not in {d["accession"] for d in D.values()})
print(f"Kinases and enzymes of test 3 with no decoy: {', '.join(nodecoy) or 'none'}")
ORDER = ["claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"]   # as in the manuscript; other files follow by name
for f in sorted((p for p in RESULTS.glob("*.jsonl") if not p.name.startswith(("bridge-", "canary-"))), key=lambda p: (ORDER.index(p.stem) if p.stem in ORDER else len(ORDER), p.stem)):
    m = f.stem; R, dec = load(f); S, stored = load(PSEUDO_RESULTS / f"{m}.jsonl"); B, bridge = load(RESULTS / f"bridge-{m}.jsonl")
    if not R: continue   # an empty file, as a zero-question run could leave
    tokens = sorted(map(ctx, dec.values()))
    print(f"\n== {m}: {len(R)} decoy calls, {len(dec)} answers scored, {len(R) - len(dec) - failed(R)} without an answer, effort {efforts(R)}, "
          f"cost ${sum(money(r) for r in R):.2f}, median input tokens {format(median(tokens), 'g') if tokens else 'n/a'}")
    if failed(R): print(f"  {NOTE_FAILED}: {failed(R)}")
    if continued(R) or continued(B): print(f"  {NOTE_CONTINUED}: decoys {len(continued(R))}, rerun {len(continued(B))}")
    if tool_calls(R): print(f"  {NOTE_TOOL}: " + ", ".join(r["accession"] + " " + r["variant"] for r in tool_calls(R)))
    refs = [("stored run", stored)]
    if B:
        refs.append(("rerun on this route", bridge)); both = sorted(set(bridge) & set(stored)); same = sum(active(bridge[x]) == active(stored[x]) for x in both)
        differ = [f"{acc} {v} (stored {stored[(acc, v)]['ans'].get('catalytically_active')}, rerun {bridge[(acc, v)]['ans'].get('catalytically_active')})" for acc, v in both if active(bridge[(acc, v)]) != active(stored[(acc, v)])]
        print(f"  rerun of the test 3 mutants and wild types on this route: {len(B)} calls, {len(bridge)} answers, effort {efforts(B)}, cost ${sum(money(r) for r in B):.2f}"
              + (f"; {NOTE_FAILED}: {failed(B)}" if failed(B) else "") + (f"; {NOTE_TOOL}: {len(tool_calls(B))}" if tool_calls(B) else ""))
        print(f"    same active/not-active call as the stored run in {same}/{len(both)}" + (": differ " + "; ".join(differ) if differ else ""))
    print("  per file (the stored run and the rerun: all 40 kinases and enzymes of test 3, 60 mutants; the decoys cover 38 of them):"); describe("decoys", R, dec); describe("stored run", S, stored)
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
            if k["called_pairs"] != k["pairs"]:
                print(f"    without answers lacking a call       mutant called active {wilson(k['called_orig_active'], k['called_pairs'])}; paired {k['called_yes_no']} and {k['called_no_yes']}, "
                      f"p = {mcnemar(k['called_yes_no'], k['called_no_yes']):.2g}   ({name})")
            print(f"    catalytic position named as lost     {wilson(k['orig_named_lost'], k['pairs'])}   ({name}, catalytic-site mutant)")
        print(f"    decoy position named as lost         {wilson(sum(p in positions(r, 'substituted_or_missing') for r, p, _ in d), n)};  any residue named as lost {wilson(sum(bool(positions(r, 'substituted_or_missing')) for r, _, _ in d), n)}")
        print(f"    decoy position listed as catalytic   {wilson(sum(p in positions(r, 'catalytic_residues') for r, p, _ in d), n)}")
        print(f"    true catalytic residue still listed  {wilson(sum(s in positions(r, 'catalytic_residues') for r, _, s in d), n)}   (decoy answers)")
        print(f"    decoy position number in the reply   {wilson(sum(mentions(r, p) for r, p, _ in d), n)}   (anywhere in the text; read the replies listed below)")
        own = [min((abs(p - q) for q in positions(r, "catalytic_residues") if isinstance(q, int)), default=None) for r, p, _ in d]; own = sorted(x for x in own if x is not None)
        if own: print(f"    decoy to nearest residue the answer lists as catalytic: median {median(own):g}, "
                      f"within 5 residues {sum(x <= 5 for x in own)}, within 10 {sum(x <= 10 for x in own)}, of {len(own)} answers listing any   (in the model's own numbering)")
    notyes = [(acc, v, D[(acc, v)]["position"], str(r["ans"].get("catalytically_active")), sorted(p for p in positions(r, "substituted_or_missing") if p)) for (acc, v), r in sorted(dec.items()) if not active(r)]
    print(f"  decoys not called active ({len(notyes)}): " + ("; ".join(f"{acc} {v} pos {p} -> {call}, named lost {lost}" for acc, v, p, call, lost in notyes) or "none"))
    seen = [f"{acc} {v} pos {D[(acc, v)]['position']}" for (acc, v), r in sorted(dec.items()) if mentions(r, D[(acc, v)]["position"])]
    print(f"  replies whose text holds the decoy position number ({len(seen)}): " + ("; ".join(seen) or "none"))
    omit = []
    for (acc, v), r in sorted(dec.items()):
        c = site(acc, dict(VARIANTS)[v]); near = sorted((q, one_letter(x.get("residue"))) for x in (r["ans"].get("catalytic_residues") or []) if isinstance(x, dict) for q in [x.get("position")] if isinstance(q, int) and abs(q - c) <= 3)
        if c not in positions(r, "catalytic_residues"): omit.append(f"{acc} {v} (curated {c}; listed within 3: {', '.join(f'{x}{q}' for q, x in near) or 'none'})")
    print(f"  decoy answers that do not list the curated catalytic position ({len(omit)}): " + ("; ".join(omit) if len(omit) <= 8 else "more than 8"))
    lc = [f"{acc} {v} pos {D[(acc, v)]['position']}: listed as {', '.join(one_letter(x.get('residue')) for x in r['ans'].get('catalytic_residues') or [] if isinstance(x, dict) and x.get('position') == D[(acc, v)]['position'])}, "
          f"given sequence has {SEQ[(acc, v)][D[(acc, v)]['position'] - 1]}, call {call_of(r)}" for (acc, v), r in sorted(dec.items()) if D[(acc, v)]["position"] in positions(r, "catalytic_residues")]
    print(f"  decoy positions listed as catalytic ({len(lc)}): " + ("; ".join(lc) or "none"))
    for name, ref in refs:
        flip = [f"{acc} {v} (decoy {call_of(r)}, wild type {call_of(ref[(acc, 'wt')])})" for (acc, v), r in sorted(dec.items()) if (acc, "wt") in ref and active(r) != active(ref[(acc, "wt")])]
        print(f"  decoys whose call differs from the wild type of the same protein ({name}): " + ("; ".join(flip) or "none"))

names = {p.stem for p in RESULTS.glob("*.jsonl") if not p.name.startswith(("bridge-", "canary-")) and p.stat().st_size}
for p in sorted(RESULTS.glob("bridge-*.jsonl")):
    if p.stem[len("bridge-"):] not in names: print(f"\nWARNING: {p.name} has no decoy file {p.stem[len('bridge-'):]}.jsonl and is not read")
for m in sorted(names):
    if not (PSEUDO_RESULTS / f"{m}.jsonl").exists(): print(f"\nWARNING: no stored test 3 file pseudo/results/{m}.jsonl for {m}.jsonl; its stored-run comparisons are empty")
print("\n== records of each file (asked_at is the time a call returned)")
tot = 0.0
for p in sorted(RESULTS.glob("*.jsonl")):
    R = [json.loads(l) for l in p.open() if l.strip()]
    if not R: continue
    rng = {g: (min(ctx(r) for r in R if r.get("group") == g), max(ctx(r) for r in R if r.get("group") == g)) for g in ("kinase", "enzyme") if any(r.get("group") == g for r in R)}
    us = [r for r in R if isinstance(r.get("usage"), dict)]
    one = sum(requests_made(r) == 1 and not any((r["usage"].get("server_tool_use") or {}).get(k) for k in ("web_search_requests", "web_fetch_requests")) for r in us)
    nohash = [f"{r.get('accession')} {r.get('variant')} at {str(r.get('asked_at'))[11:16]}" for r in R if not r.get("prompt_sha256")]
    cost = sum(money(r) for r in R); tot += cost if p.name.startswith("bridge-") else 0
    print(f"  {p.name}: {len(R)} rows, returned {window(R)}, cost ${cost:.4f}; input tokens " + ", ".join(f"{g} {a:,} to {b:,}" for g, (a, b) in rng.items())
          + (f"; total input per row {', '.join(f'{ctx(r):,}' for r in R)}, cost per row {', '.join(f'${money(r):.4f}' for r in R)}" if len(R) <= 3 else "")
          + f"; rows with a prompt hash {len(R) - len(nohash)}" + (f" (without: {'; '.join(nohash)}; those with one returned {window([r for r in R if r.get('prompt_sha256')])})" if 0 < len(nohash) <= 3 and len(nohash) < len(R) else
                                                                    f" (without: {'; '.join(nohash)})" if 0 < len(nohash) <= 3 else "")
          + (f"; rows with a usage record {len(us)}, of them one request and no web search or fetch {one}" if us else ""))
print(f"  rerun files together: cost ${tot:.4f}")
c = RESULTS / "cli_context_check.json"
if c.exists():
    j = json.loads(c.read_text()); runs = j["original_flags"] + j["with_extra_flags"] + [j["description_with_extra_flags"]]
    print(f"  cli_context_check.json: model {j['model']}, run {j['run_at']}, {len(runs)} calls, cost ${sum(money(r) for r in runs):.4f}")
