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
    uv run python experiments/structure/score.py > expected/structure.txt

# Recompute the numbers and fail if they differ from the committed expected/ files
check: verify-data
    #!/usr/bin/env bash
    set -euo pipefail
    tmp=$(mktemp -d)
    uv run python experiments/next_residue/score.py > $tmp/next_residue.txt
    uv run python experiments/next_residue/baselines.py > $tmp/next_residue_baselines.txt
    uv run python experiments/features/score.py > $tmp/features.txt
    uv run python experiments/pseudo/score.py > $tmp/pseudo.txt
    uv run python experiments/structure/score.py > $tmp/structure.txt
    diff -r $tmp expected && echo "All reported numbers reproduce."

# Check that test sets and raw model outputs match the recorded checksums
verify-data:
    sha256sum --check --quiet SHA256SUMS && echo "Data files match SHA256SUMS."

# Rewrite SHA256SUMS (only after deliberately adding new runs)
checksums:
    find experiments -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.tsv' -o -name '*.yaml' \) | sort | xargs sha256sum > SHA256SUMS

# Redraw the figures from the committed model outputs
figures:
    uv run python figures/make_figures.py
    for f in fig1_pseudoenzyme fig2_structure; do pdftoppm -png -r 160 -singlefile figures/$f.pdf figures/$f; done

# Build manuscript.pdf (needs pdflatex and bibtex)
pdf:
    pdflatex -interaction=nonstopmode manuscript.tex > /dev/null
    bibtex manuscript > /dev/null
    pdflatex -interaction=nonstopmode manuscript.tex > /dev/null
    pdflatex -interaction=nonstopmode manuscript.tex | grep -E "Warning|^!|Output written" || true

# Ask one model the questions of one test again (costs money; appends to results and resumes).
# Example: just ask pseudo claude-opus-5-5 high
ask test model effort:
    python3 experiments/{{test}}/{{ if test == "next_residue" { "run.py" } else { "ask.py" } }} {{model}} {{effort}}
