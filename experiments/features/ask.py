import json, pathlib, random, subprocess, sys, zlib, re
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)); from common import KEYS, answer, resume, sha
HERE = pathlib.Path(__file__).parent; model, eff = sys.argv[1], sys.argv[2]; out = str(HERE / "results" / f"{model}.jsonl")
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
done = resume(out, lambda d: (d["accession"], d["condition"]))   # questions whose earlier row is an error are asked again
def ask(tc):
    t, c = tc; seq = t["sequence"] if c == "real" else shuffled(t["sequence"], t["accession"])
    j = None; asked = P + fasta(seq)
    for attempt in range(1, 4):
        p = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", "", "--tools", "", "--effort", eff, "--output-format", "json"],
                           input=asked, capture_output=True, text=True, cwd="/tmp")
        try: j = json.loads(p.stdout); break
        except Exception: pass
    if j is None: return dict(accession=t["accession"], condition=c, effort=eff, attempts=attempt, error=True)
    text = j.get("result") or ""; ans = answer(text, KEYS["features"])   # the last JSON object with the requested keys
    return dict(accession=t["accession"], condition=c, effort=eff, attempts=attempt, prompt_sha256=sha(asked), text=text, ans=ans, cost=j.get("total_cost_usd"),
                thinking=j.get("usage", {}).get("output_tokens_details", {}).get("thinking_tokens"), served=list(j.get("modelUsage", {})))
todo = [q for q in qs if (q[0]["accession"], q[1]) not in done]
with ThreadPoolExecutor(8) as ex, open(out, "a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
print(model, "done", len(todo))
