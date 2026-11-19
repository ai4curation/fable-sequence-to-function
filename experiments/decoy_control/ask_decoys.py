"""Ask a model whether each decoy sequence is catalytically active. Usage: ask_decoys.py PROBE_DIR MODEL EFFORT [--set decoy|original] [--only ACCESSION:VARIANT ...]

Purpose: run the decoy substitutions from build_decoys.py through the same question and the same working
         directory as the original test 3 (PROBE_DIR/pseudo/ask.py), so the two can be compared.
Route:   the original command line plus four flags (EXTRA below). Measured on 2026-11-18 with CLI 2.1.328: the
         original flags alone do not isolate the question. `--tools ""` removes only the built-in tools; when the
         account's connectors finish connecting in time, 97 connector tools are attached (about 97,000 input
         tokens), and otherwise about 5,900 tokens of user instructions and skill listings still are. With EXTRA
         a one-sentence prompt arrives with about 590 input tokens: an environment block the CLI adds even with an
         empty system prompt. That remainder cannot be removed without `--bare`, which needs an API key.
         Rows whose input exceeds CONTEXT_LIMIT tokens are marked context_tokens_high and must not be scored.
Inputs:  decoys.json beside this file; PROBE_DIR/pseudo/ask.py, from which the prompt is read as text (the file
         is parsed, never run) so the wording cannot drift; PROBE_DIR/pseudo/truth.json for --set original.
         The local `claude` command line tool, which bills each call to the signed-in account.
Outputs: results/MODEL.jsonl (decoys) or results/bridge-MODEL.jsonl (--set original: the original catalytic-site
         mutants and wild types, rerun on this machine to check that this route gives the same answers as the
         stored run). One line per call; appends and resumes, so a rerun only asks what is missing.
Serves:  branch experiment/decoy-substitution-control of ai4curation/fable-sequence-to-function. Date: 2026-11-18.

--only limits the run to the named items; it is how the single canary call is made, on the same path as the batch.
"""
import argparse, ast, datetime, json, pathlib, re, subprocess
from concurrent.futures import ThreadPoolExecutor
EXTRA = ["--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-chrome"]
CONTEXT_LIMIT = 2500   # prompt (about 250 tokens) + longest sequence (650 residues) + CLI environment block (about 590) stays well below this
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("probe_dir", type=pathlib.Path); ap.add_argument("model"); ap.add_argument("effort")
ap.add_argument("--set", choices=("decoy", "original"), default="decoy"); ap.add_argument("--only", nargs="*", default=None)
a = ap.parse_args(); HERE = pathlib.Path(__file__).parent

def original_prompt(path):
    """Return the string assigned to P in the original ask.py without executing that file."""
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "P" for t in node.targets): return ast.literal_eval(node.value)
    raise SystemExit(f"no prompt P found in {path}")
P = original_prompt(a.probe_dir / "pseudo/ask.py")
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))   # same line width as the original

if a.set == "decoy":
    items = [dict(accession=d["accession"], group=d["group"], variant=d["variant"], sequence=d["sequence"]) for d in json.loads((HERE / "decoys.json").read_text())]
    out = HERE / "results" / f"{a.model}.jsonl"
else:
    items = [dict(accession=t["accession"], group=t["group"], variant=v, sequence=s) for t in json.loads((a.probe_dir / "pseudo/truth.json").read_text())
             if t["group"] in ("kinase", "enzyme") for v, s in t["variants"].items()]
    out = HERE / "results" / f"bridge-{a.model}.jsonl"
if a.only is not None: items = [i for i in items if f"{i['accession']}:{i['variant']}" in a.only]
done = {(d["accession"], d["variant"]) for d in map(json.loads, out.open())} if out.exists() else set()
todo = [i for i in items if (i["accession"], i["variant"]) not in done]
VERSION = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()

def ask(i):
    j = None
    for _ in range(3):
        p = subprocess.run(["claude", "-p", "--model", a.model, "--system-prompt", "", "--tools", "", "--effort", a.effort, "--output-format", "json"] + EXTRA,
                           input=P + fasta(i["sequence"]), capture_output=True, text=True, cwd="/tmp")   # directory as in the original
        try: j = json.loads(p.stdout); break
        except Exception: pass
    if j is None: return dict(accession=i["accession"], variant=i["variant"], error=True, stderr=p.stderr[-500:])
    text = j.get("result") or ""; m = re.search(r"\{.*\}", text, re.S); ans = None
    try: ans = json.loads(m.group(0)) if m else None
    except Exception: pass
    u = j.get("usage", {}); context = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return dict(accession=i["accession"], group=i["group"], variant=i["variant"], effort=a.effort, text=text, ans=ans, cost=j.get("total_cost_usd"),
                thinking_tokens=u.get("output_tokens_details", {}).get("thinking_tokens"), served=list(j.get("modelUsage", {})),
                input_tokens=u.get("input_tokens"), cache_creation_input_tokens=u.get("cache_creation_input_tokens"), cache_read_input_tokens=u.get("cache_read_input_tokens"),
                output_tokens=u.get("output_tokens"), context_tokens_high=context > CONTEXT_LIMIT, extra_flags=EXTRA, is_error=j.get("is_error"), cli_version=VERSION, asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))

out.parent.mkdir(exist_ok=True)
with ThreadPoolExecutor(8) as ex, out.open("a") as fh:
    for r in ex.map(ask, todo): fh.write(json.dumps(r) + "\n"); fh.flush()
rows = [json.loads(l) for l in out.open()]
print(f"{a.model} {a.set}: asked {len(todo)}, already present {len(items) - len(todo)}, file {out}; in file: {len(rows)} rows, "
      f"{sum(bool(r.get('error')) for r in rows)} failed, {sum(not r.get('ans') for r in rows)} unparsed, {sum(bool(r.get('context_tokens_high')) for r in rows)} with high context, "
      f"cost ${sum(r.get('cost') or 0 for r in rows):.2f}")
