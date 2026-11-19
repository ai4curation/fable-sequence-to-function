"""Offline audit of stored Gemini runs; no credentials or model calls required.

Checks question identities, reconstructed prompt hashes, parsing, and next-residue
scores. Reports coverage, failures, retries, and response metadata independently
of the performance summaries. Imported runners have no import-time API calls.
"""
import ast
import collections
import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "experiments"))
from common import KEYS, answer, has_tool_call, sha
from run_agy import PROMPTS, build_questions
from score_gemini import agy_unusable


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    # Read the existing prompt literals without importing model-calling scripts.
    for test, prompt in PROMPTS.items():
        tree = ast.parse((HERE.parent / "experiments" / test / "ask.py").read_text())
        literals = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                try:
                    literals.append(ast.literal_eval(node.value))
                except (ValueError, TypeError):
                    pass
        require(prompt in literals, f"{test}: Gemini prompt differs from canonical prompt")

    for directory in ("results_vertex", "results"):
        for path in sorted((HERE / directory).glob("*/*.jsonl")):
            test = path.parent.name
            questions, key = build_questions(test, "audit", 2)
            expected = {k: (prompt, meta) for k, prompt, meta in questions}
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            seen, usable = set(), {}
            for row in rows:
                identity = key(row)
                require(identity in expected, f"{path.name}: unexpected question {identity}")
                prompt, meta = expected[identity]
                require(row["prompt_sha256"] == sha(prompt), f"{path.name}: prompt hash mismatch")
                seen.add(identity)
                if agy_unusable(row):
                    continue
                if test == "next_residue":
                    require(row["target"] == meta["target"], f"{path.name}: target mismatch")
                    candidates = re.findall(r"[ACDEFGHIKLMNPQRSTVWY]{5,}", row["text"].replace(" ", ""))
                    pred = candidates[-1] if candidates else ""
                    valid = bool(pred) and not has_tool_call(row["text"])
                    require(row["pred"] == pred and row["valid"] == valid, f"{path.name}: prediction mismatch")
                    require(row["first_correct"] == (valid and pred[0] == meta["target"][0]), f"{path.name}: first-residue score mismatch")
                    require(row["exact10"] == (valid and pred[:10] == meta["target"]), f"{path.name}: exact-ten score mismatch")
                else:
                    require(answer(row.get("text"), KEYS[test]) is not None, f"{path.name}: unparsed successful reply")
                usable[identity] = row
            errors = sum(agy_unusable(r) for r in rows)
            safety = sum("safety" in str(r.get("error", "")).lower() for r in rows)
            retries = sum((r.get("attempts") or 1) > 1 for r in rows)
            counts = lambda field: dict(sorted(collections.Counter(str(r.get(field)) for r in rows).items()))
            print(path.relative_to(HERE))
            print(f"  expected {len(expected)}; rows {len(rows)}; unique attempted {len(seen)}; usable {len(usable)}; unusable rows {errors}; duplicate rows {len(rows)-len(seen)}")
            print(f"  safety-block rows {safety}; rows with retries {retries}; missing usable questions {len(expected)-len(usable)}")
            print(f"  route {counts('cli_version')}; model version {counts('model_version')}; finish {counts('finish_reason')}")
            if usable:
                thinking = [r.get("thinking_tokens") or 0 for r in usable.values()]
                print(f"  median thinking tokens {statistics.median(thinking):g}")
    print("All question identities, prompt hashes, parsed answers, and next-residue scores verified.")
    print("CLI pilot hashes describe the base prompt; run_agy.py prepended a no-tool instruction.")
    print("Retries record attempt counts, not all failed responses or their token usage.")


if __name__ == "__main__":
    main()
