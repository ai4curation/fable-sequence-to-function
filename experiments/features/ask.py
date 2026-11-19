"""Ask a model to annotate domains, membrane helices and signal peptides from sequence alone. Usage: ask.py MODEL EFFORT [--tag TAG] [--limit N]

Appends to results/MODEL.jsonl (results/MODEL-TAG.jsonl with --tag) and resumes; see common.call for the route.
"""
import json, pathlib, random, sys, zlib
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)); from common import KEYS, answer, call, options, out_path, resume
HERE = pathlib.Path(__file__).parent; (model, eff), TAG, LIMIT = options(sys.argv); out = out_path(HERE, model, eff, TAG)
T = json.load(open(HERE / "truth.json"))
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))
def shuffled(seq, acc):
    r = list(seq); random.Random(zlib.crc32(acc.encode())).shuffle(r); return "".join(r)
P = ('Below is a protein sequence in one-letter amino acid codes. Annotate it using only the sequence. '
     'Reply with a single JSON object and nothing else, with these keys: '
     '"pfam_domains": list of {"accession": "PFxxxxx", "name": Pfam short name, "start": int, "end": int} (1-based residue positions; empty list if none recognised); '
     '"transmembrane_helices": list of [start, end]; "signal_peptide": true or false; '
     '"protein_name": string; "ec_number": string or null; "function": one sentence. '
     'Do not guess identifiers you are not confident of: leave a field empty or null instead.\n\n>sequence\n')
qs = [(t, c) for t in T for c in ("real", "shuffled")]
done = resume(out, lambda d: (d["accession"], d["condition"]), eff)   # a question whose only rows are unusable is asked again
def ask(tc):
    t, c = tc; seq = t["sequence"] if c == "real" else shuffled(t["sequence"], t["accession"])
    text, rec = call(model, eff, P + fasta(seq)); row = dict(accession=t["accession"], condition=c)
    if text is None: return dict(row, **rec)
    rec["thinking"] = rec.pop("thinking_tokens")   # the name this test's rows have always used
    return dict(row, text=text, ans=answer(text, KEYS["features"]), **rec)
todo = [q for q in qs if (q[0]["accession"], q[1]) not in done][:LIMIT]
with ThreadPoolExecutor(8) as ex, open(out, "a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
print(model, "done", len(todo))
