"""Survey every stored reply for (a) more than one top-level JSON object, (b) text that looks like a tool call
or code, (c) for test 1, more than one candidate peptide and whether first and last candidates score differently.
Inputs: experiments/*/results/**/*.jsonl. Output: stdout. Serves issues #49 and #50. 2026-11-18."""
import json, glob, re, collections
dec = json.JSONDecoder()
def blocks(text):
    out, i = [], 0
    while True:
        i = text.find("{", i)
        if i < 0: return out
        try: obj, n = dec.raw_decode(text[i:]); out.append(obj); i += n
        except Exception: i += 1
TOOL = re.compile(r"curl |https?://|<function_calls|<invoke|antml|tool_use|```(?:bash|sh|python)|\bHTTP/\d|import requests|web_search|I'll (?:try|search|look|use)|Let me (?:search|look up|fetch|query)", re.I)
for f in sorted(glob.glob("experiments/*/results/**/*.jsonl", recursive=True)):
    R = [json.loads(l) for l in open(f)]; test = f.split("/")[1]
    tool = [r for r in R if TOOL.search(r.get("text") or "")]
    line = f"{f}: n={len(R)} toolish={len(tool)}"
    if test == "next_residue":
        multi = diff = 0
        for r in R:
            c = re.findall(r"[ACDEFGHIKLMNPQRSTVWY]{5,}", (r.get("text") or "").replace(" ", ""))
            if len(c) > 1:
                multi += 1; t = r["target"]
                if (c[0][0] == t[0]) != (c[-1][0] == t[0]): diff += 1
        line += f" multi_candidate={multi} first_vs_last_differs={diff}"
    else:
        nb = collections.Counter(len([b for b in blocks(r.get("text") or "") if isinstance(b, dict) and len(b) > 2]) for r in R)
        unp = sum(1 for r in R if not r.get("ans"))
        line += f" unparsed={unp} top-level-blocks={dict(sorted(nb.items()))}"
    print(line)
    for r in tool:
        k = r.get("accession") or r.get("pdb"); m = TOOL.search(r["text"])
        print("   toolish:", k, r.get("variant", r.get("cond", "")), r.get("cut", ""), "|", repr(r["text"][max(0, m.start()-60):m.end()+100]))
