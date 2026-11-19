"""Check that common.answer (the rule the scorers use) reproduces the `ans` stored at run time for every row of
tests 2 to 4, and that common.has_tool_call hits no reply but the known one. Rows written before the rule existed
are the point of the check; later rows were stored with the rule itself.
Inputs: experiments/{features,pseudo,structure,next_residue}/results/**/*.jsonl. Output: stdout counts.
Serves issues #50, #49 and #59. 2026-11-18."""
import glob, json, pathlib, sys
sys.path.insert(0, "experiments"); from common import KEYS, answer, has_tool_call
tot = same = 0
for f in sorted(glob.glob("experiments/*/results/**/*.jsonl", recursive=True)):
    test = pathlib.Path(f).parts[1]; R = [json.loads(l) for l in open(f)]
    tool = [r for r in R if has_tool_call(r.get("text"))]
    line = f"{f}: rows={len(R)} tool-call replies={len(tool)}" + "".join(f" [{r.get('accession') or r.get('pdb')} {r.get('condition', '')} {r.get('cut', '')}]" for r in tool)
    if test != "next_residue":
        eq = sum(answer(r.get("text"), KEYS[test]) == r.get("ans") for r in R); tot += len(R); same += eq
        line += f" derived answer equals stored ans={eq} differs={len(R) - eq}"
    print(line)
print(f"\ntests 2 to 4: {same} of {tot} rows have a derived answer equal to the stored one")
