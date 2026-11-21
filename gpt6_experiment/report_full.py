"""Write the comparison report from saved replies; never calls a model.

Refuses to label an incomplete grid complete. --allow-partial produces an explicitly
incomplete diagnostic report, useful when the batch controller has stopped.
"""
import argparse
import statistics
import subprocess
import sys

import run_full as full
import score_gemini as scoring

ROOT, HERE = full.runner.ROOT, full.runner.HERE


def pct(values):
    return f"{100 * statistics.mean(values):.1f}%" if values else "—"


def ratio(rows, predicate):
    return f"{sum(predicate(r) for r in rows)}/{len(rows)}" if rows else "—"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--output", type=full.pathlib.Path, default=HERE / "RESULTS.md")
    args = ap.parse_args()
    data, coverage = {}, []
    complete = True
    for model in full.MODELS:
        for test, effort, ncond in full.GRID:
            rows = full.read_rows(full.runner.OUT_ROOT / test / f"{model}-{effort}.jsonl")
            cov = full.coverage(test, model, effort, ncond, rows)
            coverage.append((model, test, effort, cov))
            complete &= cov["usable"] == cov["expected"]
            _, key = full.runner.build_questions(test, model, ncond)
            chosen = {key(r): dict(r) for r in rows if full.usable(test, r)}
            data[model, test, effort] = list(chosen.values())
            if test != "next_residue":
                for row in chosen.values():
                    row["ans"] = full.runner.answer(row["text"], full.runner.KEYS["pseudo" if test == "decoy_control" else test])
    if not complete and not args.allow_partial:
        ap.error("The full grid is incomplete; use --allow-partial for a diagnostic report")
    details = []
    for title, cmd in (
        ("Canonical scores and sensitivity analyses", ["gemini_experiment/score_gemini.py", "gpt6_experiment/results"]),
        ("Decoy comparison, intervals and paired tests", ["experiments/decoy_control/score_decoys.py", "--results",
            "gpt6_experiment/results/decoy_control", "--pseudo-results", "gpt6_experiment/results/pseudo"]),
        ("Audit and coverage", ["gemini_experiment/audit.py", "gpt6_experiment/results"]),
    ):
        result = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"{title} failed:\n{result.stderr}")
        details.append(f"## {title}\n\n```text\n{result.stdout.rstrip()}\n```\n")
    lines = ["# GPT-6 Astra and Rosalind: full comparison", "",
             "Status: **complete**." if complete else "Status: **INCOMPLETE — diagnostic results only**.", "",
             "The planned grid contains 1,008 questions per model. Retained historical structure canaries are included; "
             "the new batch runs on EC2. Each scored question uses one usable answer. Earlier unusable canary rows "
             "remain in the raw files but are excluded.", "",
             "## Coverage", "", "| Model | Test | Effort | Usable | Attempted | Planned |",
             "|---|---|---|---:|---:|---:|"]
    for model, test, effort, cov in coverage:
        lines.append(f"| {model} | {test} | {effort} | {cov['usable']} | {cov['attempted']} | {cov['expected']} |")
    lines += ["", "## Next residue", "",
              "First-residue accuracy; invalid sequence replies count as incorrect. Family-cluster intervals "
              "and bin-specific differences are in the canonical scores below.", "",
              "| Model | Effort | Real | Shuffled | Reversed | Real − shuffled (points) |", "|---|---|---:|---:|---:|---:|"]
    for model in full.MODELS:
        for effort in ("low", "high"):
            rows = data[model, "next_residue", effort]
            groups = [[r["first_correct"] for r in rows if r["condition"] == cond] for cond in ("real", "shuffled", "reversed")]
            gap = f"{100 * (statistics.mean(groups[0]) - statistics.mean(groups[1])):+.1f}" if all(groups[:2]) else "—"
            lines.append(f"| {model} | {effort} | {' | '.join(pct(g) for g in groups)} | {gap} |")
    lines += ["", "## Domains and membrane features", "",
              "| Model | Real proteins with ≥1 correct Pfam family | Shuffled proteins given any Pfam domain |",
              "|---|---:|---:|"]
    for model in full.MODELS:
        rows = data[model, "features", "high"]
        values = scoring.FEATURES.headline(rows, lambda r: r["ans"])
        lines.append(f"| {model} | {' | '.join(values)} |")
    lines += ["", "The detailed report separates obscure DUFs from sampled proteins and includes boundary overlap, "
              "membrane helices, and signal peptides.", "", "## Catalytic activity and decoys", "",
              "Entries are counts called active, not accuracy. A decoy is unannotated at the substituted position; "
              "it is not experimentally established to retain activity.", "",
              "| Model | Kinase/enzyme wild types active | Catalytic-site mutants active | Natural pseudoenzymes active | Decoys active |",
              "|---|---:|---:|---:|---:|"]
    active = lambda r: str(r["ans"].get("catalytically_active")).lower() == "yes"
    for model in full.MODELS:
        rows = data[model, "pseudo", "high"]
        groups = [[r for r in rows if r["group"] in ("kinase", "enzyme") and r["variant"] == "wt"],
                  [r for r in rows if r["variant"] != "wt"], [r for r in rows if r["group"] == "pseudo"],
                  data[model, "decoy_control", "high"]]
        lines.append(f"| {model} | {' | '.join(ratio(g, active) for g in groups)} |")
    lines += ["", "See the per-substitution paired comparisons and the disputed-site sensitivity analysis below. "
              "The pooled decoy comparison contains two substitutions for each kinase, so those pairs are not independent.",
              "", "## Structure", "",
              "Q3 is secondary-structure accuracy on observed residues. Contact precision averages proteins with at least "
              "one valid predicted long-range contact; it is not full three-dimensional structure accuracy.", "",
              "| Model | Stratum | Proteins | Q3 | Single-state baseline | Contact precision | Chance |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for model in full.MODELS:
        for stratum in ("known", "novel"):
            rows = [r for r in data[model, "structure", "high"] if scoring.STRUCTURE.T[r["pdb"]]["stratum"] == stratum
                    and (stratum != "novel" or r["pdb"] not in scoring.STRUCTURE.ASPRV1_REPEATS)]
            scores = [scoring.STRUCTURE.one(scoring.STRUCTURE.T[r["pdb"]], r["ans"]) for r in rows]
            values = [pct([s[k] for s in scores if s[k] is not None]) for k in ("q3", "base", "prec", "chance")]
            lines.append(f"| {model} | {stratum} | {len(rows)} | {' | '.join(values)} |")
    lines += ["", "The novel summary counts ASPRV1 once. Both the full novel stratum and this sensitivity are in the "
              "canonical output below.", "", "## Interpretation limits", "",
              "This is one stochastic answer per question and setting, not a causal comparison of training or architecture. "
              "Effort labels are not equivalent reasoning budgets across models or providers. Recognition self-reports "
              "do not establish training-set exposure. The audit records the requested model, not the server's actual "
              "served model. Codex does not report monetary costs; zero cost counters in the shared decoy output mean "
              "no recorded cost, not free calls.", "",
              "Reproduce the numeric reports with `just report` and verify them with `just check`. "
              "Regenerate this report with `uv run python gpt6_experiment/report_full.py`.", "", *details]
    args.output.write_text("\n".join(lines) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
