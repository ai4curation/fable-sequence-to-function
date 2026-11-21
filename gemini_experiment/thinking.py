"""Recorded thinking-token medians for the completed comparison runs; no model calls.

Count usable rows, including zeros, and report missing values rather than imputing
them. Test 1 uses real and shuffled questions only, matching Neon's conditions.
These are provider-reported counts, not comparable units of compute or budgets.
"""
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent / "experiments"
sys.path.insert(0, str(EXP))
from common import KEYS, answer, unusable
from run_agy import agy_unusable


def main():
    for test in ("next_residue", "features", "pseudo", "structure"):
        print(test)
        effort = "medium" if test == "structure" else "low"
        paths = [(HERE / "results_vertex" / test / f"gemini-4-neon-{effort}.jsonl", effort, agy_unusable)]
        for model in ("claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"):
            eff = "low" if test == "next_residue" and model == "claude-opus-4-6" else "high"
            path = EXP / test / "results"
            if test == "next_residue":
                path = path / eff / f"{model}.jsonl"
            else:
                path = path / f"{model}{'-high' if model == 'claude-opus-4-6' else ''}.jsonl"
            paths.append((path, eff, unusable))
        for path, eff, reject in paths:
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            rows = [r for r in rows if not reject(r) and r.get("condition") != "reversed"]
            if test != "next_residue":
                rows = [r for r in rows if answer(r.get("text"), KEYS[test]) is not None]
            values = [r.get("thinking_tokens", r.get("thinking")) for r in rows]
            present = [v for v in values if v is not None]
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 for v in present):
                raise ValueError(f"Invalid thinking count in {path}")
            median = f"{statistics.median(present):g}" if present else "unavailable"
            print(f"  {path.stem}, effort {eff}: n={len(rows)}, recorded={len(present)}, missing={len(rows)-len(present)}, median={median}")
    print("Medians include zero-thinking replies; missing counts are not treated as zero.")
    print("Test 1: real and shuffled only. Test 2: both real and shuffled included.")
    print("Claude test-2 Fable/Opus 5.5 effort is reported in the methods, absent from those stored rows.")
    print("Counts use each route's stored thinking field; retries/continuations may be accounted for differently.")
    print("These are recorded token counts, not equal compute budgets across providers or tokenizers.")


if __name__ == "__main__":
    main()
