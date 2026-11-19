"""Ask a model whether each decoy sequence is catalytically active. Usage: ask_decoys.py MODEL EFFORT [--set decoy|original] [--only ACCESSION:VARIANT ...] [--limit N] [--tag TAG] [--probe-dir DIR]

Purpose: run the decoy substitutions from build_decoys.py through the same question and the same working
         directory as test 3 (pseudo/ask.py), so the two can be compared.
Route:   call() in experiments/common.py: the original command line plus four flags (common.EXTRA). Measured on
         2026-11-18 with CLI 2.1.328: the original flags alone do not isolate the question. `--tools ""` removes
         only the built-in tools; when the account's connectors finish connecting in time, 97 connector tools are
         attached (about 97,000 input tokens), and otherwise about 5,900 tokens of user instructions and skill
         listings still are. With the four flags a one-sentence prompt arrives with about 590 input tokens: an
         environment block the CLI adds even with an empty system prompt. That remainder cannot be removed
         without `--bare`, which needs an API key. A row whose input is larger than common.context_limit allows
         is marked context_tokens_high, is not scored, and the question is asked again on the next run.
Inputs:  decoys.json beside this file; DIR/pseudo/ask.py (DIR defaults to experiments/), from which the prompt is
         read as text (the file is parsed, never run) so the wording cannot drift; DIR/pseudo/truth.json for
         --set original. The local `claude` command line tool, which bills each call to the signed-in account.
Outputs: results/MODEL[-TAG].jsonl (decoys) or results/bridge-MODEL[-TAG].jsonl (--set original: the catalytic-site
         mutants and wild types of test 3, asked again on this route, so that decoys and mutants can be compared
         within one route). One line per call. Files are append-only and a run resumes: a failed or marked row
         stays, and its question is asked again. A run at another effort needs its own file (--tag).
Serves:  pull request 10 and issue 11 of ai4curation/fable-sequence-to-function. Date: 2026-11-18, revised 2026-11-19.

--only limits the run to the named items and --limit to the first N missing ones; --limit 1 is the single canary
call, on the same path as the batch.
"""
import argparse, ast, json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); from common import KEYS, answer, call, failed, resume
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("model"); ap.add_argument("effort")
ap.add_argument("--set", choices=("decoy", "original"), default="decoy"); ap.add_argument("--only", nargs="*", default=None)
ap.add_argument("--limit", type=int, default=None); ap.add_argument("--tag", default=None); ap.add_argument("--probe-dir", type=pathlib.Path, default=HERE.parent)
a = ap.parse_args()

def original_prompt(path):
    """Return the string assigned to P in the original ask.py without executing that file."""
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "P" for t in node.targets): return ast.literal_eval(node.value)
    raise SystemExit(f"no prompt P found in {path}")
P = original_prompt(a.probe_dir / "pseudo/ask.py")
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))   # same line width as the original

if a.set == "decoy":
    items = [dict(accession=d["accession"], group=d["group"], variant=d["variant"], sequence=d["sequence"]) for d in json.loads((HERE / "decoys.json").read_text())]
else:
    items = [dict(accession=t["accession"], group=t["group"], variant=v, sequence=s) for t in json.loads((a.probe_dir / "pseudo/truth.json").read_text())
             if t["group"] in ("kinase", "enzyme") for v, s in t["variants"].items()]
out = HERE / "results" / f"{'bridge-' if a.set == 'original' else ''}{a.model}{'-' + a.tag if a.tag else ''}.jsonl"; out.parent.mkdir(exist_ok=True)
if a.only is not None: items = [i for i in items if f"{i['accession']}:{i['variant']}" in a.only]
done = resume(out, lambda d: (d["accession"], d["variant"]), a.effort)   # a question whose only rows are unusable is asked again
todo = [i for i in items if (i["accession"], i["variant"]) not in done][:a.limit]

def ask(i):
    text, rec = call(a.model, a.effort, P + fasta(i["sequence"])); row = dict(accession=i["accession"], group=i["group"], variant=i["variant"])
    if text is None: return dict(row, **rec)
    return dict(row, text=text, ans=answer(text, KEYS["pseudo"]), **rec)

with ThreadPoolExecutor(8) as ex, out.open("a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
rows = [json.loads(l) for l in out.open()]
print(f"{a.model} {a.set}: asked {len(todo)}, already answered {sum((i['accession'], i['variant']) in done for i in items)} of {len(items)}, file {out}; in file: {len(rows)} rows, "
      f"{failed(rows)} not usable (failed, API error or attached context), {sum(not r.get('ans') for r in rows) - failed(rows)} without an answer, cost ${sum(r.get('cost') or 0 for r in rows):.2f}")
