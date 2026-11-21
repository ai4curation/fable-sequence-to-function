# Recipes for reproducing the analysis. `just` with no arguments lists them.
default:
    @just --list

# Recompute every reported number from the committed model outputs into expected/
report:
    mkdir -p expected
    uv run python experiments/next_residue/score.py > expected/next_residue.txt
    uv run python experiments/next_residue/baselines.py > expected/next_residue_baselines.txt
    uv run python experiments/features/score.py > expected/features.txt
    uv run python experiments/pseudo/score.py > expected/pseudo.txt
    uv run python experiments/pseudo/adjudication/adjudicate.py > expected/adjudication.txt
    uv run python experiments/structure/score.py > expected/structure.txt
    uv run python experiments/summary.py > expected/summary.txt
    uv run python experiments/decoy_control/score_decoys.py > expected/decoy_control.txt
    uv run python gemini_experiment/score_gemini.py results_vertex > expected/gemini_vertex.txt
    uv run python gemini_experiment/score_gemini.py results > expected/gemini_pilots.txt
    uv run python gemini_experiment/audit.py > expected/gemini_audit.txt
    uv run python gemini_experiment/thinking.py > expected/gemini_thinking.txt
    uv run python gemini_experiment/score_gemini.py gpt6_experiment/results > expected/gpt6.txt
    uv run python gemini_experiment/audit.py gpt6_experiment/results > expected/gpt6_audit.txt
    uv run python experiments/decoy_control/score_decoys.py --results gpt6_experiment/results/decoy_control --pseudo-results gpt6_experiment/results/pseudo > expected/gpt6_decoys.txt
    uv run python figures/make_figures.py --values-only > expected/figures.txt

# Recompute the numbers and fail if they differ from the committed expected/ files
check: verify-data
    #!/usr/bin/env bash
    set -euo pipefail
    tmp=$(mktemp -d)
    uv run python experiments/next_residue/score.py > $tmp/next_residue.txt
    uv run python experiments/next_residue/baselines.py > $tmp/next_residue_baselines.txt
    uv run python experiments/features/score.py > $tmp/features.txt
    uv run python experiments/pseudo/score.py > $tmp/pseudo.txt
    uv run python experiments/pseudo/adjudication/adjudicate.py > $tmp/adjudication.txt
    uv run python experiments/structure/score.py > $tmp/structure.txt
    uv run python experiments/summary.py > $tmp/summary.txt
    uv run python experiments/decoy_control/score_decoys.py > $tmp/decoy_control.txt
    uv run python gemini_experiment/score_gemini.py results_vertex > $tmp/gemini_vertex.txt
    uv run python gemini_experiment/score_gemini.py results > $tmp/gemini_pilots.txt
    uv run python gemini_experiment/audit.py > $tmp/gemini_audit.txt
    uv run python gemini_experiment/thinking.py > $tmp/gemini_thinking.txt
    uv run python gemini_experiment/score_gemini.py gpt6_experiment/results > $tmp/gpt6.txt
    uv run python gemini_experiment/audit.py gpt6_experiment/results > $tmp/gpt6_audit.txt
    uv run python experiments/decoy_control/score_decoys.py --results gpt6_experiment/results/decoy_control --pseudo-results gpt6_experiment/results/pseudo > $tmp/gpt6_decoys.txt
    uv run python figures/make_figures.py --values-only > $tmp/figures.txt
    diff -r $tmp expected && echo "All reported numbers reproduce."

# Check that test sets and raw model outputs match the recorded checksums
verify-data:
    shasum -a 256 --check --quiet SHA256SUMS && echo "Data files match SHA256SUMS."

# Rewrite SHA256SUMS (only after deliberately adding new runs)
checksums:
    find experiments gemini_experiment gpt6_experiment -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.tsv' -o -name '*.yaml' -o -name '*.cif' -o -name '*.pdb' \) | sort | xargs shasum -a 256 > SHA256SUMS

# Redraw the figures from the committed model outputs (the plotted values are in expected/figures.txt)
figures:
    uv run python figures/make_figures.py
    for f in fig1_pseudoenzyme fig2_structure; do pdftoppm -png -r 160 -singlefile figures/$f.pdf figures/$f; done

# Build manuscript.pdf (needs pdflatex and bibtex)
pdf:
    pdflatex -interaction=nonstopmode manuscript.tex > /dev/null
    bibtex manuscript > /dev/null
    pdflatex -interaction=nonstopmode manuscript.tex > /dev/null
    pdflatex -interaction=nonstopmode manuscript.tex | grep -E "Warning|^!|Output written" || true

# Run the model-calling scripts and the reply-reading rules against a stub CLI, and the Gemini API runners against a stub endpoint. Calls no model.
check-calls:
    uv run python scripts/check_call_scripts_with_stub_cli.py
    uv run python scripts/check_gemini_runners_with_stub_endpoint.py
    uv run python scripts/check_codex_runner_with_stub_provider.py
    uv run python scripts/check_codex_full_analysis.py
    scripts/adhoc/mutation_check_gemini_audit.sh

# Ask one model the questions of one test again (costs money; appends to results and resumes).
# Example: just ask pseudo claude-opus-5-5 high        (add --limit 1 for a single canary call, --tag NAME for a separate file)
ask test model effort *args:
    python3 experiments/{{test}}/{{ if test == "next_residue" { "run.py" } else { "ask.py" } }} {{model}} {{effort}} {{args}}
