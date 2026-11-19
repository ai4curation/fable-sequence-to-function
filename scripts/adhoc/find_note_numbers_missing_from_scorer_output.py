"""List the numbers in a results note that do not appear in the frozen scorer output.

Purpose: RESULTS.md of the decoy control says every number in it is printed by score_decoys.py (#90). This lists each
         number token of the note (commas removed) that does not occur as a number in expected/decoy_control.txt,
         with its line, so each can be checked by eye. Section numbers, list numbers and identifiers (accessions,
         variant names, issue numbers, file names) are reported too; they are not errors.
Inputs:  NOTE (default experiments/decoy_control/RESULTS.md), OUTPUT (default expected/decoy_control.txt).
Outputs: text on standard output.     Serves: pull request 10, issue 90.     2026-11-19
"""
import pathlib, re, sys
root = pathlib.Path(__file__).resolve().parents[2]
note = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / "experiments/decoy_control/RESULTS.md"
out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / "expected/decoy_control.txt"
NUM = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?(?:e-?\d+)?(?![\w])")
have = {m.group(0).lstrip("$").replace(",", "") for m in NUM.finditer(out.read_text())}
for i, line in enumerate(note.read_text().splitlines(), 1):
    miss = [m.group(0) for m in NUM.finditer(line) if m.group(0).lstrip("$").replace(",", "") not in have]
    if miss: print(f"{i}: {', '.join(miss)}   | {line.strip()[:110]}")
