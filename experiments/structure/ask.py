"""Ask a model to predict structure, then function, from sequence alone. Usage: ask.py MODEL EFFORT"""
import json, pathlib, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)); from common import KEYS, answer, resume, sha
HERE = pathlib.Path(__file__).parent; model, eff = sys.argv[1], sys.argv[2]; out = HERE / "results" / f"{model}.jsonl"
T = json.loads((HERE / "truth.json").read_text())
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))
P = ('Below is a protein sequence in one-letter amino acid codes (it may be a recombinant construct). Using only the sequence, predict its '
     'three-dimensional structure and then its function. Reply with a single JSON object and nothing else, with these keys: '
     '"helices": list of [start, end] residue ranges predicted to be helix (1-based positions in this sequence); '
     '"strands": list of [start, end] ranges predicted to be beta strand; '
     '"fold": short name of the predicted fold or structural superfamily; '
     '"contacts": list of exactly 20 [i, j] residue pairs with j - i >= 24 that you predict are in contact in the folded structure '
     '(C-alpha atoms within 8 angstroms), most confident first; '
     '"protein_name": string; "function": one sentence on the molecular function; '
     '"functional_residues": list of {"position": int, "residue": one-letter code, "role": string}; '
     '"recognised": true if you recognise this as a specific known protein, else false.\n\n>sequence\n')
done = resume(out, lambda d: d["pdb"])   # questions whose earlier row is an error are asked again
def ask(t):
    j = None; asked = P + fasta(t["sequence"])
    for attempt in range(1, 4):
        p = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", "", "--tools", "", "--effort", eff, "--output-format", "json"],
                           input=asked, capture_output=True, text=True, cwd="/tmp")
        try: j = json.loads(p.stdout); break
        except Exception: pass
    if j is None: return dict(pdb=t["pdb"], effort=eff, attempts=attempt, error=True)
    text = j.get("result") or ""; ans = answer(text, KEYS["structure"])   # the last JSON object with the requested keys
    return dict(pdb=t["pdb"], effort=eff, attempts=attempt, prompt_sha256=sha(asked), text=text, ans=ans, cost=j.get("total_cost_usd"),
                thinking_tokens=j.get("usage", {}).get("output_tokens_details", {}).get("thinking_tokens"), served=list(j.get("modelUsage", {})))
todo = [t for t in T if t["pdb"] not in done]
with ThreadPoolExecutor(8) as ex, out.open("a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
print(model, "done", len(todo))
