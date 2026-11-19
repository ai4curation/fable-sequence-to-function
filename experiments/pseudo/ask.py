"""Ask a model, from sequence alone, whether each protein is catalytically active. Usage: ask.py MODEL EFFORT [--tag TAG] [--limit N]

Calls the local `claude` CLI with no tools and an empty system prompt; the same prompt is used for wild-type
and mutant sequences. Appends to results/MODEL.jsonl (results/MODEL-TAG.jsonl with --tag) and resumes if interrupted;
see common.call for the route.
"""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)); from common import KEYS, answer, call, options, out_path, resume
HERE = pathlib.Path(__file__).parent; (model, eff), TAG, LIMIT = options(sys.argv); out = out_path(HERE, model, eff, TAG)
T = json.loads((HERE / "truth.json").read_text())
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))
P = ('Below is a protein sequence in one-letter amino acid codes. Using only the sequence, decide whether the protein is '
     'likely to be catalytically active. Reply with a single JSON object and nothing else, with these keys: '
     '"protein_name": string; "enzyme_family": string; '
     '"catalytic_residues": list of {"role": string, "residue": one-letter code actually present in this sequence, "position": int (1-based)}; '
     '"substituted_or_missing": list of {"role": string, "expected": string, "found": string, "position": int or null} for any canonical catalytic or '
     'cofactor-binding residue that this sequence lacks (empty list if none); '
     '"catalytically_active": "yes", "no" or "uncertain"; "ec_number": string or null; "reason": one or two sentences.\n\n>sequence\n')
qs = [(t, v) for t in T for v in t["variants"]]
done = resume(out, lambda d: (d["accession"], d["variant"]), eff)   # a question whose only rows are unusable is asked again
def ask(tv):
    t, v = tv; text, rec = call(model, eff, P + fasta(t["variants"][v])); row = dict(accession=t["accession"], group=t["group"], variant=v)
    if text is None: return dict(row, **rec)
    return dict(row, text=text, ans=answer(text, KEYS["pseudo"]), **rec)
todo = [q for q in qs if (q[0]["accession"], q[1]) not in done][:LIMIT]
with ThreadPoolExecutor(8) as ex, out.open("a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
print(model, "done", len(todo))
