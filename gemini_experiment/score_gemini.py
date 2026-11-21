"""Score Gemini experiment results using the exact scoring rules from experiments/*/score.py.

All four tests import the canonical scoring helpers from experiments/*/score.py.
Provider-specific row acceptance, ordering, and report formatting stay here.
Two differences from the Claude scorers: a row counts only if it passes run_agy.agy_unusable, the
same rule the runners use on resume; and where a question has more than one usable row, the last is
kept (no stored file has one). The Claude scorers' diagnostic lines for tool-call replies and for
replies holding more than one JSON object are not printed; run on the Gemini rows, the Claude
scorers find none of either.

Usage:
    uv run python gemini_experiment/score_gemini.py results_vertex
    uv run python gemini_experiment/score_gemini.py results
"""
import json
import importlib.util
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments"
RES = pathlib.Path(__file__).resolve().parent / "results"
sys.path.insert(0, str(EXP))
from common import KEYS, answer  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_agy import agy_unusable, build_questions  # noqa: E402  (one usable-row rule, #144)


def scorer(test):
    spec = importlib.util.spec_from_file_location(f"canonical_{test}_score", EXP / test / "score.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NEXT, FEATURES, PSEUDO, STRUCTURE = [scorer(test) for test in ("next_residue", "features", "pseudo", "structure")]


def score_next_residue():
    d = RES / "next_residue"
    if not d.exists():
        return
    print("=" * 72)
    print("TEST 1: NEXT RESIDUE")
    print("=" * 72)
    pct = NEXT.pct
    for f in sorted(d.glob("*.jsonl")):
        raw = [json.loads(l) for l in f.open() if l.strip()]
        bad = sum(agy_unusable(r) for r in raw)
        R = [r for r in raw if not agy_unusable(r)]
        # Deduplicate keeping last usable row per question
        seen = {}
        for r in R:
            seen[(r["accession"], r["condition"], r["cut"])] = r
        # Rows are scored in question order, as the Claude files are written. run_vertex.py writes rows
        # as calls finish, and the family bootstrap below depends on the order of families (#142).
        qs, qkey = build_questions("next_residue", "score", 3)  # 3: reversed rows too, if a run has them
        order = {k: i for i, (k, _, _) in enumerate(qs)}
        R = sorted(seen.values(), key=lambda r: order[qkey(r)])
        NEXT.reject_tools(R)
        print(f"\n== {f.stem}: {len(R)} usable ({bad} unusable)")
        for c in ("real", "shuffled", "reversed"):
            x = [r for r in R if r["condition"] == c]
            if not x:
                continue
            print(
                f"  {c:9s} n={len(x):3d} invalid={sum(not r['valid'] for r in x)} "
                f"first-residue={pct([r['first_correct'] for r in x]):.1f}%  exact10={sum(r['exact10'] for r in x)}"
            )
            with_t = [r for r in x if r.get("thinking")]
            no_t = [r for r in x if not r.get("thinking")]
            if with_t and no_t:
                print(f"            with thinking n={len(with_t):3d} first-residue={pct([r['first_correct'] for r in with_t]):.1f}%")
                print(f"            no thinking   n={len(no_t):3d} first-residue={pct([r['first_correct'] for r in no_t]):.1f}%")
        NEXT.gaps(R)
        # Post hoc sensitivity for the six historical Vertex questions with unexplained input.
        # This diagnostic does not change the usable-row rule or the headline denominator.
        prompts = {k: prompt for k, prompt, _ in qs}
        extra = [r for r in R if r.get("input_tokens", 0) > len(prompts[qkey(r)])]
        if extra:
            excluded = {qkey(r) for r in extra}
            kept = [r for r in R if qkey(r) not in excluded]
            print(f"  sensitivity: excluding {len(extra)} rows with input_tokens > prompt characters")
            for cond in ("real", "shuffled", "reversed"):
                x = [r for r in kept if r["condition"] == cond]
                if x:
                    print(f"    {cond:9s} n={len(x)} first-residue={NEXT.pct([r['first_correct'] for r in x]):.1f}%")
            NEXT.gaps(kept, indent="    ")


def score_features():
    d = RES / "features"
    if not d.exists():
        return
    print("\n" + "=" * 72)
    print("TEST 2: DOMAINS & MEMBRANE FEATURES")
    print("=" * 72)
    T = {t["accession"]: t for t in json.loads((EXP / "features" / "truth.json").read_text())}
    for f in sorted(d.glob("*.jsonl")):
        raw = [json.loads(l) for l in f.open() if l.strip()]
        bad = sum(agy_unusable(r) for r in raw)
        seen = {}
        for r in raw:
            if not agy_unusable(r):
                r["ans"] = answer(r.get("text"), KEYS["features"])
                seen[(r["accession"], r["condition"])] = r
        R = list(seen.values())
        ok = [r for r in R if r.get("ans")]
        print(f"\n== {f.stem}: {len(R)} usable ({bad} unusable, {len(R)-len(ok)} unparsed)")
        for cond in ("real", "shuffled"):
            for st in ("B", "A", "all"):
                x = [r for r in ok if r["condition"] == cond and st in (T[r["accession"]]["set"], "all")]
                if not x:
                    continue
                tp_id, tp_nm, npred, ntrue, prot_any, prot_hit, iou, tmc, tmexact, tmn, helix_hit, helix_true, helix_pred, sp = FEATURES.summarize(x)
                mean_iou = sum(iou) / len(iou) if iou else float("nan")
                print(
                    f"  {cond:8s} set {st:3s} n={len(x):2d}: Pfam >=1 right {prot_hit}/{len(x)}; "
                    f"pred {npred} (id {tp_id}, id/name {tp_nm}); true {ntrue}; IoU {mean_iou:.3f} (n={len(iou)})"
                )
                if cond == "real":
                    print(
                        f"           TM: agree {tmc}/{tmn}, exact {tmexact}/{tmn}, helices {helix_hit}/{helix_true} (pred {helix_pred}); "
                        f"SP TP {sp[(True,True)]} FN {sp[(False,True)]} FP {sp[(True,False)]} TN {sp[(False,False)]}"
                    )
                else:
                    print(f"           (shuffled hallucination) any Pfam domain {prot_any}/{len(x)}; any transmembrane helix {FEATURES.tm_any(x)}/{len(x)}")


def score_pseudo():
    d = RES / "pseudo"
    if not d.exists():
        return
    print("\n" + "=" * 72)
    print("TEST 3: PSEUDOENZYMES")
    print("=" * 72)
    T = {t["accession"]: t for t in json.loads((EXP / "pseudo" / "truth.json").read_text())}
    for f in sorted(d.glob("*.jsonl")):
        raw = [json.loads(l) for l in f.open() if l.strip()]
        bad = sum(agy_unusable(r) for r in raw)
        seen = {}
        for r in raw:
            if not agy_unusable(r):
                r["ans"] = answer(r.get("text"), KEYS["pseudo"])
                seen[(r["accession"], r["variant"])] = r
        R = list(seen.values())
        ok = [r for r in R if r.get("ans")]
        print(f"\n== {f.stem}: {len(R)} usable ({bad} unusable, {len(R)-len(ok)} unparsed)")
        rows, flagged, still, wtsite = PSEUDO.summarize(ok)
        named = [r for r in ok if r["group"] == "pseudo" and any(w in str(r["ans"].get("protein_name")).lower() for w in ("inactive", "pseudokinase"))]
        called_no = [r for r in ok if r["group"] == "pseudo" and str(r["ans"].get("catalytically_active")).lower() == "no"]
        print(f"  natural pseudokinases named inactive/pseudokinase: {len(named)}/{sum(r['group']=='pseudo' for r in ok)} (of called no: {sum(r in named for r in called_no)}/{len(called_no)})")
        for key in sorted(rows):
            n = sum(rows[key].values())
            c = rows[key]
            extra = (
                f"; curated pos listed {wtsite[key]}/{n}"
                if key[1] == "wt" and key[0] != "pseudo"
                else (f"; mutated pos flagged {flagged[key]}/{n}, still intact {still[key]}/{n}" if key[1] != "wt" else "")
            )
            other = n - c["yes"] - c["no"] - c["uncertain"]
            print(f"  {key[0]:7s} {key[1]:11s} n={n:2d}: yes {c['yes']:2d}  no {c['no']:2d}  uncertain {c['uncertain']:2d}" + (f"  other {other}" if other else "") + extra)
        PSEUDO.disputed_sensitivity(ok)


def score_structure():
    d = RES / "structure"
    if not d.exists():
        return
    print("\n" + "=" * 72)
    print("TEST 4: STRUCTURE & FUNCTION")
    print("=" * 72)
    T, ASPRV1_REPEATS, one = STRUCTURE.T, STRUCTURE.ASPRV1_REPEATS, STRUCTURE.one

    m = lambda x: 100 * statistics.mean(x) if x else float("nan")
    for f in sorted(d.glob("*.jsonl")):
        raw = [json.loads(l) for l in f.open() if l.strip()]
        bad = sum(agy_unusable(r) for r in raw)
        seen = {}
        for r in raw:
            if not agy_unusable(r):
                r["ans"] = answer(r.get("text"), KEYS["structure"])
                seen[r["pdb"]] = r
        R = list(seen.values())
        ok = [r for r in R if r.get("ans")]
        print(f"\n== {f.stem}: {len(R)} usable ({bad} unusable, {len(R)-len(ok)} unparsed)")
        for label, sel in (
            ("novel", [r for r in ok if T[r["pdb"]]["stratum"] == "novel"]),
            ("known", [r for r in ok if T[r["pdb"]]["stratum"] == "known"]),
            ("novel, ASPRV1 counted once", [r for r in ok if T[r["pdb"]]["stratum"] == "novel" and r["pdb"] not in ASPRV1_REPEATS]),
        ):
            S = [one(T[r["pdb"]], r["ans"]) for r in sel]
            p = [s["prec"] for s in S if s["prec"] is not None]
            t5 = [s["top5"] for s in S if s["top5"] is not None]
            print(
                f"  {label:28s} n={len(S):2d}: Q3 {m([s['q3'] for s in S]):.1f}% (base {m([s['base'] for s in S]):.1f}%); "
                f"LR prec {m(p):.1f}% (top5 {m(t5):.1f}%; chance {m([s['chance'] for s in S]):.1f}%); rec {sum(s['rec'] for s in S)}/{len(S)}"
            )


def main():
    global RES
    if len(sys.argv) > 1:
        RES = pathlib.Path(__file__).resolve().parent / sys.argv[1]
    score_next_residue()
    score_features()
    score_pseudo()
    score_structure()


if __name__ == "__main__":
    main()
