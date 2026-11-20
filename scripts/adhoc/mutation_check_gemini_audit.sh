#!/usr/bin/env bash
# Purpose: check that gemini_experiment/audit.py fails on the defects it now claims to catch (#145):
#   one planted defect of each kind it checks (#145, #150).
# The unmutated control must print MISSED, so that a crash is not mistaken for a catch.
# Inputs: this checkout. Outputs: one line per mutation (CAUGHT / MISSED) on stdout; scratch copies
#   under .temp/audit_mutations/ (gitignored), removed at the end.
# PR #148, 2026-11-19.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd); work="$root/.temp/audit_mutations"
mutate() {  # $1 name, $2 python snippet run inside the copy
  rm -rf "$work"; mkdir -p "$work"; cp -R "$root/experiments" "$root/gemini_experiment" "$work/"
  (cd "$work" && python3 -c "$2")
  if out=$(cd "$work" && uv run --project "$root" python gemini_experiment/audit.py 2>&1); then echo "MISSED $1"
  else echo "CAUGHT $1 -- $(printf '%s\n' "$out" | tail -1)"; fi
}
mutate "nothing (control: must print MISSED)" 'pass'
mutate "row relabelled" '
import json, pathlib
p = pathlib.Path("gemini_experiment/results_vertex/features/gemini-4-neon-low.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; rows[5]["effort"] = "high"
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Claude prompt hash differs" '
import json, pathlib
p = pathlib.Path("experiments/pseudo/results/claude-opus-4-6-high.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; rows[3]["prompt_sha256"] = "0" * 64
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Claude test-1 target differs" '
import json, pathlib
p = sorted(pathlib.Path("experiments/next_residue/results").rglob("*.jsonl"))[0]
rows = [json.loads(l) for l in p.read_text().splitlines()]; rows[0]["target"] = "W" * 10
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Gemini test-1 family differs" '
import json, pathlib
p = pathlib.Path("gemini_experiment/results_vertex/next_residue/gemini-4-neon-low.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; r = next(r for r in rows if "error" not in r); r["pfam"] = "PF00000"
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Gemini model version differs" '
import json, pathlib
p = pathlib.Path("gemini_experiment/results_vertex/structure/gemini-4-neon-medium.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; rows[2]["model_version"] = "gemini-other"
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Gemini test-1 score differs" '
import json, pathlib
p = pathlib.Path("gemini_experiment/results_vertex/next_residue/gemini-4-neon-low.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; r = next(r for r in rows if "error" not in r); r["first_correct"] = not r["first_correct"]
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Gemini test-2 reply does not parse" '
import json, pathlib
p = pathlib.Path("gemini_experiment/results_vertex/features/gemini-4-neon-low.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; rows[0]["text"] = "no answer"
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "Claude row without hash has another accession" '
import json, pathlib
p = pathlib.Path("experiments/features/results/claude-fable-5-2.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines()]; rows[0]["accession"] = "X00000"
p.write_text("".join(json.dumps(r) + "\n" for r in rows))'
mutate "a Gemini question absent from the Claude rows" '
import json, pathlib
files = sorted(pathlib.Path("experiments/structure/results").rglob("*.jsonl"))
pdb = json.loads(files[0].read_text().splitlines()[0])["pdb"]
for p in files:
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows if r.get("pdb") != pdb))'
rm -rf "$work"
