"""Count model calls across all four tests. Usage: summary.py

Prints, per results file and in total: calls, calls with an error row, and calls whose usage record
(the `served` field) lists more than one model. These are the totals quoted in the Methods (#31).
"""
import json, pathlib
HERE = pathlib.Path(__file__).parent
total = errors = second = 0
for test in ("next_residue", "features", "pseudo", "structure"):
    for f in sorted((HERE / test / "results").rglob("*.jsonl")):
        R = [json.loads(l) for l in open(f)]
        e = sum("error" in r or bool(r.get("is_error")) for r in R)
        s = [r for r in R if len(r.get("served") or []) > 1]
        total += len(R); errors += e; second += len(s)
        print(f"{str(f.relative_to(HERE)):48s} calls {len(R):4d}  errors {e}  listing a second model {len(s)}")
print(f"\nall tests: calls {total}, errors {errors}, listing a second model {second}")
