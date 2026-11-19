"""Ask a model to predict structure, then function, from sequence alone. Usage: ask.py MODEL EFFORT [--tag TAG] [--limit N]

Appends to results/MODEL.jsonl (results/MODEL-TAG.jsonl with --tag) and resumes; see common.call for the route.
"""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)); from common import KEYS, answer, call, options, out_path, resume
HERE = pathlib.Path(__file__).parent; (model, eff), TAG, LIMIT = options(sys.argv); out = out_path(HERE, model, eff, TAG)
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
done = resume(out, lambda d: d["pdb"], eff)   # a question whose only rows are unusable is asked again
def ask(t):
    text, rec = call(model, eff, P + fasta(t["sequence"])); row = dict(pdb=t["pdb"])
    if text is None: return dict(row, **rec)
    return dict(row, text=text, ans=answer(text, KEYS["structure"]), **rec)
todo = [t for t in T if t["pdb"] not in done][:LIMIT]
with ThreadPoolExecutor(8) as ex, out.open("a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
print(model, "done", len(todo))
