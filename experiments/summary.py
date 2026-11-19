"""Count model calls across all four tests. Usage: summary.py

Prints, per results file and in total: calls, calls recorded as errors (an `error` row, `is_error`, attached context,
or a reply whose text is an API error message; these rows stay in the results files), and calls whose usage record
(the `served` field) lists more than one model. The totals of the files listed in REPORTED are the ones quoted in the
Methods (#31); other files (such as the Opus 4.6 high-effort runs of #51) are counted apart.
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); from common import unusable
HERE = pathlib.Path(__file__).parent
# The results files whose calls the Methods totals describe (#103). Any other results file is counted apart, so a new
# run never enters the quoted totals by its file name alone.
REPORTED = {
    "features/results/claude-fable-5-2.jsonl",
    "features/results/claude-opus-4-6-high.jsonl",
    "features/results/claude-opus-4-6.jsonl",
    "features/results/claude-opus-5-5.jsonl",
    "next_residue/results/high/claude-fable-5-2.jsonl",
    "next_residue/results/high/claude-opus-5-5.jsonl",
    "next_residue/results/low/claude-fable-5-2.jsonl",
    "next_residue/results/low/claude-opus-4-6.jsonl",
    "next_residue/results/low/claude-opus-5-5.jsonl",
    "pseudo/results/claude-fable-5-2.jsonl",
    "pseudo/results/claude-opus-4-6-high.jsonl",
    "pseudo/results/claude-opus-4-6.jsonl",
    "pseudo/results/claude-opus-5-5.jsonl",
    "structure/results/claude-fable-5-2.jsonl",
    "structure/results/claude-opus-4-6-high.jsonl",
    "structure/results/claude-opus-4-6.jsonl",
    "structure/results/claude-opus-5-5.jsonl",
}
tot = {True: [0, 0, 0], False: [0, 0, 0]}
for test in ("next_residue", "features", "pseudo", "structure"):
    for f in sorted((HERE / test / "results").rglob("*.jsonl")):
        R = [json.loads(l) for l in open(f) if l.strip()]
        e = sum(unusable(r) or str(r.get("text") or "").lstrip().startswith("API Error") for r in R)
        s = [r for r in R if len(r.get("served") or []) > 1]
        reported = str(f.relative_to(HERE)) in REPORTED; t = tot[reported]; t[0] += len(R); t[1] += e; t[2] += len(s)
        print(f"{str(f.relative_to(HERE)):48s} calls {len(R):4d}  errors or API-error replies {e}  listing a second model {len(s)}" + ("" if reported else "  (not in the manuscript)"))
print(f"\nruns in the manuscript (the files listed in REPORTED): calls {tot[True][0]}, errors or API-error replies {tot[True][1]}, listing a second model {tot[True][2]}")
print(f"other runs, not in the manuscript: calls {tot[False][0]}, errors or API-error replies {tot[False][1]}, listing a second model {tot[False][2]}")
