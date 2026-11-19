# Raw outputs as reviewed on 18 November 2026

A copy of the test sets, raw model outputs and function grading from `projects/LLM_SEQUENCE_PROBE` in
`ai4curation/ai-gene-review` at commit `119ac18676`, the state the skeptical review in this folder's parent
examined. Files are unchanged. Scripts and the manuscript folder of that commit are not copied.

`review/scripts/recompute_from_pr6527.py` reads this folder by default.

The current data are in `experiments/`. Seventeen of the eighteen files here are byte-identical to their
counterparts there. The one that differs is `next_residue/results/high/claude-opus-5-5.jsonl`: it has 264 rows
here, and the current file has the same 264 rows followed by 8 added on 19 November.
