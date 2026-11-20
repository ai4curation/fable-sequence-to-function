"""Offline audit of stored Gemini runs; no credentials or model calls required.

Checks that the Gemini and Claude questions are the same set (prompt hashes where Claude rows record
them; test-1 targets and families), that row labels match file names and usable API rows report the
requested model version, that each row's prompt hash matches the rebuilt question, that usable replies
parse, and that stored next-residue targets, families, predictions and scores recompute. A reversed
test-1 Gemini row fails as an unexpected question: no Gemini run asked reversed sequences.
Rows from #155 on must agree with the response metadata stored beside them (metadata_problem).
scripts/adhoc/mutation_check_gemini_audit.sh, run by `just check-calls`, plants defects for these checks. Reports coverage,
failures, retries, and response metadata independently of the performance summaries. Imported runners have no import-time API calls.
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


def metadata_problem(row, usable=True):
    """None if a row's fields agree with the endpoint metadata stored beside them (#155, #160).

    Every row: response id and model version. Usable rows also: finish reason and reply length.
    Rows of row_format 2 that got a response must carry the metadata, or the error that stopped it.
    """
    if row.get("row_format", 1) >= 2 and (usable or str(row.get("error", "")).startswith("no candidates")):
        if "response_id" not in row:
            return "row of format 2 with a response has no response id"
        if "response_metadata" not in row and "response_metadata_error" not in row:
            return "row of format 2 with a response has no metadata"
    if "response_metadata" not in row:
        return None
    m = row["response_metadata"]
    if row.get("response_id") != m.get("responseId"):
        return "response id differs from the stored metadata"
    if row.get("model_version") != m.get("modelVersion"):
        return "model version differs from the stored metadata"
    if not usable:
        return None
    cands = m.get("candidates") or []
    if not cands:
        return "stored metadata has no candidate"
    cand = cands[0]
    if row.get("finish_reason") != cand.get("finishReason"):
        return "finish reason differs from the stored metadata"
    shown = sum(q.get("text_chars", 0) for q in (cand.get("content") or {}).get("parts") or [] if not q.get("thought"))
    if shown != len(row.get("text") or ""):
        return "reply length differs from the stored metadata"
    return None


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

    # Compare the rebuilt questions with the stored Claude rows (#145): prompt hashes where the Claude
    # rows record one, and for test 1 every question's identity, target and family.
    for test in ("next_residue", "features", "pseudo", "structure"):
        questions, key = build_questions(test, "audit", 2)
        expected = {k: (sha(prompt), meta) for k, prompt, meta in questions}
        claude = [json.loads(line) for path in sorted((HERE.parent / "experiments" / test / "results").rglob("*.jsonl"))
                  for line in path.read_text().splitlines() if line.strip()]
        hashed = covered = 0
        found = set()
        for row in claude:
            identity = key(row)
            if test == "next_residue" and row.get("condition") == "reversed":
                continue  # Gemini was not asked reversed sequences
            require(identity in expected, f"{test}: Claude row {identity} is not one of the rebuilt questions")
            found.add(identity)
            if row.get("prompt_sha256"):
                hashed += 1
                require(row["prompt_sha256"] == expected[identity][0], f"{test}: prompt differs from Claude row {identity}")
            if test == "next_residue":
                meta = expected[identity][1]
                require((row["target"], row["pfam"]) == (meta["target"], meta["pfam"]), f"{test}: target or family differs from Claude row {identity}")
        covered = len(found)
        require(covered == len(expected), f"{test}: {len(expected) - covered} Gemini questions absent from the Claude rows")
        print(f"{test}: all {covered} questions found in the Claude rows; {hashed} Claude rows with a prompt hash, all equal")

    # The Gemini folders, then any results folder named on the command line (e.g. gpt6_experiment/results, #52).
    folders = [HERE / "results_vertex", HERE / "results"] + [(HERE.parent / a).resolve() for a in sys.argv[1:]]
    for folder in folders:
        for path in sorted(folder.glob("*/*.jsonl")):
            test = path.parent.name
            questions, key = build_questions(test, "audit", 2)
            expected = {k: (prompt, meta) for k, prompt, meta in questions}
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            seen, usable = set(), {}
            for row in rows:
                label = row["model"] if row.get("effort") is None else f"{row['model']}-{row['effort']}"
                require(label == path.stem, f"{path.name}: row labelled {label}")
                identity = key(row)
                require(identity in expected, f"{path.name}: unexpected question {identity}")
                prompt, meta = expected[identity]
                require(row["prompt_sha256"] == sha(prompt), f"{path.name}: prompt hash mismatch")
                seen.add(identity)
                problem = metadata_problem(row, usable=not agy_unusable(row))  # every row, blocked ones too
                require(problem is None, f"{path.name}: {problem}")
                if agy_unusable(row):
                    continue
                route = str(row.get("cli_version", ""))
                if route.startswith("codex-exec"):  # GPT-6 through Codex: no endpoint model version is logged (#52)
                    require(row.get("context_ok") is True and row.get("request_problem") is None
                            and row.get("requests_logged", 0) >= 1 and row.get("requested_model_logged") == [row["model"]]
                            and not row.get("context_tokens_high") and (row.get("input_tokens") or 0) <= row.get("context_limit", 0),
                            f"{path.name}: Codex row without a passing context check")
                elif not route.startswith("agy"):
                    require(row.get("model_version") == row["model"], f"{path.name}: endpoint model version {row.get('model_version')} for {row['model']}")
                if test == "next_residue":
                    require(row["target"] == meta["target"], f"{path.name}: target mismatch")
                    require(row["pfam"] == meta["pfam"], f"{path.name}: family mismatch")
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
            print(path.relative_to(HERE) if path.is_relative_to(HERE) else path.relative_to(HERE.parent) if path.is_relative_to(HERE.parent) else path)
            print(f"  expected {len(expected)}; rows {len(rows)}; unique attempted {len(seen)}; usable {len(usable)}; unusable rows {errors}; duplicate rows {len(rows)-len(seen)}")
            print(f"  safety-block rows {safety}; rows with retries {retries}; missing usable questions {len(expected)-len(usable)}")
            print(f"  route {counts('cli_version')}; model version {counts('model_version')}; finish {counts('finish_reason')}")
            if usable:
                thinking = [r.get("thinking_tokens") or 0 for r in usable.values()]
                print(f"  median thinking tokens {statistics.median(thinking):g}")
    print("Verified: the Gemini and Claude questions are the same set, with equal prompt hashes wherever a")
    print("Claude row records one; each row's model and effort match its file name, and each usable API row's")
    print("model version equals its model; each row's prompt hash matches the rebuilt question; every usable")
    print("reply in tests 2-4 yields a JSON answer; and the stored next-residue target, family, prediction")
    print("and scores match a recomputation. Rows that store the endpoint's response metadata (from #155 on)")
    print("agree with it: response id and model version on every row, finish reason and reply length on usable ones.")
    print("CLI pilot hashes describe the base prompt; run_agy.py prepended a no-tool instruction.")
    print("Retries record attempt counts, not all failed responses or their token usage.")


if __name__ == "__main__":
    main()
