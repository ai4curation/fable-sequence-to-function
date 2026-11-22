"""FEAT (test 2), Opus 4.6 high effort: the headline counts if the six marked first answers had been kept.

Purpose: NEXT_TASKS T9 (issue #104, "Selection"). Six questions whose first answer was marked as carrying
attached context were asked again, and the new answers are scored. This recomputes the two headline
counts (real proteins with at least one correct family; shuffled proteins given any Pfam domain) with the
scorer's own functions, once as scored and once with each of those six questions answered by its first
(marked) reply instead of its replacement.
Inputs: experiments/features/results/claude-opus-4-6-high.jsonl, experiments/features/truth.json.
Output: stdout. Date: 2026-11-21.
"""
import collections, importlib.util, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
spec = importlib.util.spec_from_file_location("feat_score", ROOT / "experiments" / "features" / "score.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
from common import KEYS, answer, reparse, unusable

R = [json.loads(l) for l in open(ROOT / "experiments" / "features" / "results" / "claude-opus-4-6-high.jsonl")]
reparse(R, KEYS["features"])
key = lambda r: (r["accession"], r["condition"])
dup = {k for k, n in collections.Counter(map(key, R)).items() if n > 1}
scored = [r for r in R if not unusable(r)]
first = [r for r in R if key(r) not in dup and not unusable(r)] + [r for r in R if key(r) in dup and r.get("context_tokens_high")]
print("re-asked questions:", sorted(dup))
for name, rows in (("as scored", scored), ("six first answers instead", first)):
    # reparse() fills `ans` only for usable rows, so a marked first answer is read from its text by the same rule
    real, shuffled = S.headline(rows, lambda r: r.get("ans") or answer(r.get("text") or "", KEYS["features"]))
    print(f"{name}: {len(rows)} rows; real proteins with a correct family {real}; shuffled proteins given any domain {shuffled}")
