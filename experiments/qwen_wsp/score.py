"""Score the Qwen sequence tests and weight writes from results/. Usage: score.py

Standard library only. Intervals are 95% bootstrap intervals over Pfam families
(10,000 resamples, fixed seed), as in the next-residue scorer.
"""

import collections
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tasks  # noqa: E402

HERE = pathlib.Path(__file__).parent
RESULTS = HERE / "results"
MODELS = ["Qwen3-1.7B-Base", "Qwen3-8B-Base", "Qwen3-14B-Base"]


def jsonl(path):
    return [json.loads(line) for line in path.open()]


def auroc(positive, negative):
    """Probability that a positive scores above a negative; ties count half.

    >>> auroc([2, 3], [1, 2])
    0.875
    """
    wins = sum((p > n) + 0.5 * (p == n) for p in positive for n in negative)
    return wins / (len(positive) * len(negative))


def interval(values):
    """Mean and 95% bootstrap interval of per-family values.

    >>> interval([0.5, 0.5, 0.5])
    (0.5, 0.5, 0.5)
    """
    rng = random.Random(0)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000))
    return sum(values) / len(values), means[250], means[9750]


def cut_points(scores, condition, keep=None):
    """(family, correct, log-probability) for each scored cut point."""
    return [
        (s["pfam"], p == t, lp)
        for s in scores
        if s["condition"] == condition
        for c, p, t, lp in zip(s["cuts"], s["pred"], s["target"], s["logp"])
        if keep is None or (s["accession"], c) in keep
    ]


def by_family(points):
    family = collections.defaultdict(list)
    for pfam, correct, _ in points:
        family[pfam].append(correct)
    return {f: sum(v) / len(v) for f, v in family.items()}


def family_gap(a, b):
    """Mean over families of accuracy in ``a`` minus accuracy in ``b``, with interval, in points."""
    fa, fb = by_family(a), by_family(b)
    mean, low, high = interval([fa[f] - fb[f] for f in fa])
    return f"{100 * mean:+.1f} pts (95% CI {100 * low:+.1f} to {100 * high:+.1f}), {len(fa)} families"


def line(points):
    return f"n={len(points):4d} top-ranked residue correct {100 * sum(p[1] for p in points) / len(points):5.1f}%  mean log-prob of true residue {sum(p[2] for p in points) / len(points):.3f}"


def next_residue(title, scores):
    print(f"\n== {title}")
    real, shuf = cut_points(scores, "real"), cut_points(scores, "shuffled")
    print(f"  real      {line(real)}")
    print(f"  shuffled  {line(shuf)}")
    print(f"  gap real-shuffled: {family_gap(real, shuf)}")
    mass = [m for s in scores for m in s["aa_mass"]]
    print(f"  share of the next-token distribution on residue tokens at cut points: mean {sum(mass) / len(mass):.3f}, min {min(mass):.3f}")
    asked = jsonl(HERE.parent / "next_residue" / "results" / "high" / "claude-fable-5-2.jsonl")
    keep = {(r["accession"], r["cut"]) for r in asked if r["condition"] == "real"}
    real, shuf = cut_points(scores, "real", keep), cut_points(scores, "shuffled", keep)
    print(f"  the {len(keep)} questions asked of the Claude models: real {100 * sum(p[1] for p in real) / len(real):.1f}%  shuffled {100 * sum(p[1] for p in shuf) / len(shuf):.1f}%")
    if "all_n" in scores[0]:
        for condition in ("real", "shuffled"):
            rows = [s for s in scores if s["condition"] == condition]
            n = sum(s["all_n"] for s in rows)
            print(f"  every position after the first, {condition:8s}: n={n} correct {100 * sum(s['all_correct'] for s in rows) / n:.1f}%  mean log-prob {sum(s['all_logp'] for s in rows) / n:.3f}")
        family = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0.0]))
        for s in scores:
            total = family[s["pfam"]][s["condition"]]
            total[0] += s["all_correct"]
            total[1] += s["all_n"]
            total[2] += s["all_logp"]
        for label, i, scale, unit in (("accuracy", 0, 100, " pts"), ("mean log-prob", 2, 1, "")):
            gap = [d["real"][i] / d["real"][1] - d["shuffled"][i] / d["shuffled"][1] for d in family.values()]
            mean, low, high = interval(gap)
            print(f"  every position, gap real-shuffled in {label}: {scale * mean:+.3f}{unit} (95% CI {scale * low:+.3f} to {scale * high:+.3f}), {len(gap)} families  [not in the protocol]")


def composition_reference(rows):
    counts = collections.Counter("".join(r["sequence"] for r in rows))
    top = counts.most_common(1)[0][0]
    for condition in ("real", "shuffled"):
        hits = n = 0
        for r in rows:
            seq = r["sequence"] if condition == "real" else tasks.shuffled(r["sequence"], r["accession"])
            hits += sum(seq[c] == top for c in r["cuts"])
            n += len(r["cuts"])
        print(f"  reference, always answering the most common residue ({top}), {condition}: {100 * hits / n:.1f}%")
    total = sum(counts.values())
    entropy = -sum(c / total * __import__("math").log(c / total) for c in counts.values())
    print(f"  reference, log-prob per residue from overall residue frequencies: {-entropy:.3f}; uniform over 20: {-__import__('math').log(20):.3f}")


def substitutions(rows, indent="  "):
    for kind in ("catalytic", "decoy"):
        x = [r for r in rows if r["kind"] == kind]
        print(
            f"{indent}{kind:9s} n={len(x)}  wild type preferred at the site {sum(r['site_margin'] > 0 for r in x)}/{len(x)}, mean margin {sum(r['site_margin'] for r in x) / len(x):+.3f}"
            f";  whole sequence {sum(r['sequence_margin'] > 0 for r in x)}/{len(x)}, mean margin {sum(r['sequence_margin'] for r in x) / len(x):+.3f}"
        )
    catalytic = {(r["accession"], r["variant"]): r for r in rows if r["kind"] == "catalytic"}
    pairs = [(catalytic[(r["accession"], r["variant"])], r) for r in rows if r["kind"] == "decoy"]
    for key in ("site_margin", "sequence_margin"):
        diff = [c[key] - d[key] for c, d in pairs]
        print(f"{indent}paired catalytic minus decoy, {key}: mean {sum(diff) / len(diff):+.3f}, catalytic larger in {sum(x > 0 for x in diff)}/{len(diff)} pairs")


def features(folder):
    data = json.loads((folder / "baseline_features.json").read_text())
    items, names = tasks.feature_items()
    truth = {i["accession"]: i for i in items}
    print("\n== Features (test 2 proteins, restricted choice, sequence written without spaces)")
    for condition in ("real", "shuffled"):
        rows = [r for r in data["items"] if r["condition"] == condition]
        for label, normalise in (("summed log-prob", False), ("per-token log-prob", True)):
            ranks = []
            for r in rows:
                if not truth[r["accession"]]["pfam"]:
                    continue  # proteins of test 2 with no Pfam domain
                score = [lp / n if normalise else lp for lp, n in zip(r["pfam_logp"], r["pfam_tokens"])]
                best = max(score[names.index(n)] for n in truth[r["accession"]]["pfam"])
                ranks.append(sum(s > best for s in score) + 1)
            print(f"  {condition:8s} Pfam name of {len(names)}, {label:18s}: top-ranked {sum(r == 1 for r in ranks)}/{len(ranks)}, in top five {sum(r <= 5 for r in ranks)}/{len(ranks)}, median rank {sorted(ranks)[len(ranks) // 2]}")
        for key, label in (("signal", "signal peptide"), ("tm", "transmembrane helix")):
            pos = [r[f"{key}_margin"] for r in rows if truth[r["accession"]][key]]
            neg = [r[f"{key}_margin"] for r in rows if not truth[r["accession"]][key]]
            print(f"  {condition:8s} {label}: AUROC of the yes-minus-no margin {auroc(pos, neg):.3f} ({len(pos)} with, {len(neg)} without); 'yes' preferred for {sum(m > 0 for m in pos + neg)}/{len(pos + neg)}")
    print("  (truth labels belong to the real sequences; a shuffled copy keeps its protein's label, so a score that survives shuffling reflects composition)")


def seen_context(rows, splits):
    """Cut points of seen-family test proteins whose ten preceding residues and target occur in a fitting member."""
    fit = collections.defaultdict(list)
    for r in rows:
        if splits[r["accession"]] == "fit":
            fit[r["pfam"]].append(r["sequence"])
    return {
        (r["accession"], c)
        for r in rows
        if splits[r["accession"]] == "test_seen"
        for c in r["cuts"]
        if any(r["sequence"][c - 10 : c + 1] in s for s in fit[r["pfam"]])
    }


def edits(folder):
    selection = json.loads((folder / "edit_selection.json").read_text())
    print("\n== Weight writes: selection on validation proteins (real sequences) and calibration controls")
    print(f"  unedited: validation accuracy {100 * selection['baseline_validation_accuracy']:.1f}%, mean log-prob {selection['baseline_validation_logp']:.3f}; {selection['fit_keys']} fitting positions")
    for c in selection["calibration"]:
        where = f"MLP layer {c['layer']}" if c["kind"] == "mlp" else "output rows "
        print(
            f"  {where} strength {c['strength']:<4}: validation {100 * c['validation_accuracy']:5.1f}%  log-prob {c['validation_logp']:.3f}"
            f"  control answer changes {c['control']['prediction_flips']}/{c['control']['n']}  drift {c['control']['mean_abs_target_logp_drift']:.3f}"
            f"  eligible {'yes' if c['eligible'] else 'no '}  change/original norm {c['relative_frobenius']:.3f}"
        )
    for s in selection["selected"]:
        chosen = f"layer {s['layer']} " if s.get("layer") is not None else ""
        print(f"  selected {s['kind']}: " + (f"{chosen}strength {s['strength']}" if s["strength"] else s["reason"]))

    rows = tasks.load_sequences()
    splits = json.loads((HERE / "splits.json").read_text())["splits"]
    conditions = jsonl(folder / "edit_results.jsonl")
    base = conditions[0]
    subsets = {
        "seen families": {(r["accession"], c) for r in rows if splits[r["accession"]] == "test_seen" for c in r["cuts"]},
        "unseen families": {(r["accession"], c) for r in rows if splits[r["accession"]] == "test_unseen" for c in r["cuts"]},
    }
    copied = seen_context(rows, splits)
    subsets["seen, context shared with a fitting member"] = copied
    subsets["seen, context not shared"] = subsets["seen families"] - copied
    for name, keep in subsets.items():
        scored = len(cut_points(base["next_residue"], "real", keep))
        if not scored:
            continue
        print(f"\n== Test proteins, {name} ({scored} cut points)")
        for cond in conditions:
            real, shuf = cut_points(cond["next_residue"], "real", keep), cut_points(cond["next_residue"], "shuffled", keep)
            text = f"  {cond['name']:19s} real {100 * sum(p[1] for p in real) / len(real):5.1f}% ({sum(p[2] for p in real) / len(real):.3f})  shuffled {100 * sum(p[1] for p in shuf) / len(shuf):5.1f}% ({sum(p[2] for p in shuf) / len(shuf):.3f})"
            if cond is not base:
                text += f"  real vs unedited {family_gap(real, cut_points(base['next_residue'], 'real', keep))}"
            print(text)
    print("  (accuracy, with the mean log-probability of the true residue in brackets)")

    print("\n== Substitution items under each condition")
    for cond in conditions:
        if cond["substitutions"]:
            print(f"  {cond['name']}")
            substitutions(cond["substitutions"], indent="    ")

    print("\n== Held-out controls (qwen2obo's questions) and size of each write")
    for cond in conditions:
        c, e = cond["controls"], cond["edit"]
        size = f"  {e['changed_scalar_n']} scalars changed, change/original norm {e['relative_frobenius']:.3f}" if e else ""
        print(f"  {cond['name']:19s} correct {c['correct_n']}/{c['n']}  answer changes {c['prediction_flips']}  drift {c['mean_abs_target_logp_drift']:.3f}{size}")
    print("\n== Greedy completions of the held-out control questions")
    for cond in conditions:
        for g in cond["generations"]:
            print(f"  [{cond['name']}] {g['prompt'].splitlines()[0]} -> expected {g['expected']!r}; completion {(g['completion'].strip().splitlines() or [''])[0][:90]!r}")


def main():
    rows = tasks.load_sequences()
    print("Qwen base models on protein sequences. Protocol: experiments/qwen_wsp/protocol.json")
    for model in MODELS:
        folder = RESULTS / model
        if not (folder / "baseline_manifest.json").exists():
            continue
        print(f"\n######## {model}")
        next_residue("Next residue, one token per residue (primary)", jsonl(folder / "baseline_next_residue.jsonl"))
        composition_reference(rows)
        next_residue("Next residue, sequence written without spaces (secondary)", jsonl(folder / "baseline_raw.jsonl"))
        print("\n== Substitutions: wild-type residue against the substituted residue (log-probability margins)")
        substitutions(jsonl(folder / "baseline_substitutions.jsonl"))
        features(folder)
        if (folder / "edit_results.jsonl").exists():
            edits(folder)


if __name__ == "__main__":
    main()
