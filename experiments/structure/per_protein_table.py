"""Per-protein STRFN results for the 12 unmatched proteins and the three frontier models.

Prints, for each protein and model: Q3 (%), correct/qualifying contacts, and the blinded overall function
grade (both graders where they differ). The manuscript's per-protein table is this output.
"""
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


S = module("structure_score", HERE / "score.py")
G = module("score_gemini", ROOT / "gemini_experiment" / "score_gemini.py")
MODELS = ["claude-fable-5-2", "claude-opus-5-5", "gemini-4-neon"]
SHORT = {"correct": "correct", "partly_correct": "partly", "wrong": "wrong", "abstained": "abstained"}


def answers():
    out = {}
    for m in MODELS[:2]:
        R, _ = S.load(HERE / "results" / f"{m}.jsonl")
        out[m] = {r["pdb"]: r["ans"] for r in R if r.get("ans")}
    out[MODELS[2]] = {}
    for line in (ROOT / "gemini_experiment" / "results_vertex" / "structure" / "gemini-4-neon-medium.jsonl").open():
        r = json.loads(line)
        if line.strip() and not G.agy_unusable(r):
            a = G.answer(r.get("text"), G.KEYS["structure"])
            if a: out[MODELS[2]][r["pdb"]] = a
    return out


def main():
    D = HERE / "function_regrade"
    key = json.loads((D / "key.json").read_text())
    truth = {x["item"].split("-")[0]: x["truth"] for x in json.loads((D / "items.json").read_text())}
    grades = {g: {x["item"]: x["overall"] for x in json.loads((D / f"grader_{g}.json").read_text())} for g in "AB"}
    A = answers()
    print("== per protein, 12 unmatched proteins: Q3 % / contacts correct of qualifying / function grade")
    print(f"  best single state Q3 is given after the PDB id")
    for pdb in sorted(truth, key=lambda p: -S.one(S.T[p], A[MODELS[0]][p])["q3"]):
        cells = []
        for m in MODELS:
            v = S.one(S.T[pdb], A[m][pdb]); k = round(v["prec"] * v["n_qualifying"]) if v["prec"] is not None else 0
            i = next(i for i in key if i.startswith(pdb + "-") and key[i] == m)
            a, b = SHORT[grades["A"][i]], SHORT[grades["B"][i]]
            cells.append(f"{100 * v['q3']:.0f} {k}/{v['n_qualifying']} {a if a == b else a + '|' + b}")
        print(f"  {pdb:5s} base {100 * S.one(S.T[pdb], A[MODELS[0]][pdb])['base']:.0f}  " + "  ;  ".join(cells))
    print("  deposited titles:")
    for pdb in sorted(truth): print(f"    {pdb}: {json.dumps(truth[pdb])[:150]}")


if __name__ == "__main__":
    main()
