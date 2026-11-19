"""Count model calls across all four tests. Usage: summary.py

Prints, per results file and in total: calls, calls recorded as errors (an `error` row, `is_error`, attached context,
or a reply whose text is an API error message; these rows stay in the results files), and calls whose usage record
(the `served` field) lists more than one model. These are the totals quoted in the Methods (#31).
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); from common import unusable
HERE = pathlib.Path(__file__).parent
total = errors = second = 0
for test in ("next_residue", "features", "pseudo", "structure"):
    for f in sorted((HERE / test / "results").rglob("*.jsonl")):
        R = [json.loads(l) for l in open(f)]
        e = sum(unusable(r) or (r.get("text") or "").lstrip().startswith("API Error") for r in R)
        s = [r for r in R if len(r.get("served") or []) > 1]
        total += len(R); errors += e; second += len(s)
        print(f"{str(f.relative_to(HERE)):48s} calls {len(R):4d}  errors or API-error replies {e}  listing a second model {len(s)}")
print(f"\nall tests: calls {total}, errors or API-error replies {errors}, listing a second model {second}")
