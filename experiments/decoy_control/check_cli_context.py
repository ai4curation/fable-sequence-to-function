"""Measure what the `claude` command line attaches to a prompt under the original flags and under the flags used here. Usage: check_cli_context.py [MODEL]

Purpose: the README states that `--system-prompt "" --tools ""` does not isolate a prompt. This script produces
         the evidence: for a fixed one-sentence prompt it records the number of attached tools, the state of the
         account's connectors, and the input tokens, several times per flag set, because the outcome varies.
Inputs:  the local `claude` command line tool and the signed-in account. MODEL defaults to the cheapest model;
         the whole check costs a few cents.
Outputs: results/cli_context_check.json beside this file. Connector names are not saved, only how many there
         are and their states. The model's own description of its context is saved as text; read it before
         committing, since it describes the account's environment.
Serves:  pull request 10 of ai4curation/fable-sequence-to-function (review finding: route claims not saved). Date: 2026-11-18.
"""
import collections, datetime, json, pathlib, subprocess, sys
HERE = pathlib.Path(__file__).parent; MODEL = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-5-5"
BASE = ["claude", "-p", "--model", MODEL, "--system-prompt", "", "--tools", ""]
EXTRA = ["--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-chrome"]   # must equal EXTRA in ask_decoys.py
PROMPT = "Reply with the single word OK."
DESCRIBE = ("Describe in general terms, without quoting, what kinds of information you were given before this sentence in this conversation. "
            "Do not include any names, addresses, paths or identifiers. If you were given nothing, reply NONE.")

def call(flags, prompt):
    p = subprocess.run(BASE + flags + ["--output-format", "stream-json", "--verbose"], input=prompt, capture_output=True, text=True, cwd="/tmp")
    rec = {}
    for line in p.stdout.splitlines():
        try: j = json.loads(line)
        except Exception: continue
        if j.get("type") == "system" and j.get("subtype") == "init":
            rec.update(tools_attached=len(j.get("tools", [])), connectors=dict(collections.Counter(m.get("status") for m in j.get("mcp_servers", []))),
                       skills_listed=len(j.get("skills", [])), cli_version=j.get("claude_code_version"))
        if j.get("type") == "result":
            u = j.get("usage", {})
            rec.update(result=j.get("result"), input_tokens=u.get("input_tokens"), cache_creation_input_tokens=u.get("cache_creation_input_tokens"),
                       cache_read_input_tokens=u.get("cache_read_input_tokens"), cost=j.get("total_cost_usd"))
    return rec

out = dict(model=MODEL, prompt=PROMPT, describe_prompt=DESCRIBE, extra_flags=EXTRA, run_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           original_flags=[call([], PROMPT) for _ in range(4)], with_extra_flags=[call(EXTRA, PROMPT) for _ in range(2)], description_with_extra_flags=call(EXTRA, DESCRIBE))
(HERE / "results" / "cli_context_check.json").write_text(json.dumps(out, indent=1))
ctx = lambda r: sum(r.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
for name in ("original_flags", "with_extra_flags"):
    for r in out[name]: print(f"{name:17s} tools {r.get('tools_attached')}  connectors {r.get('connectors')}  context tokens {ctx(r)}  cost ${r.get('cost') or 0:.4f}")
print("description:", out["description_with_extra_flags"].get("result"))
