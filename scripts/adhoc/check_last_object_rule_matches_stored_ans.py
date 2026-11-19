"""Check that a 'last top-level JSON object in the reply' rule reproduces the stored `ans` for every row of
tests 2 to 4 that already has one. Inputs: experiments/{features,pseudo,structure}/results/*.jsonl.
Output: stdout counts. Serves issue #50. 2026-11-18."""
import json, glob
dec = json.JSONDecoder()
def last(text):
    out, i = [], 0
    while (i := text.find("{", i)) >= 0:
        try: obj, n = dec.raw_decode(text[i:]); out.append(obj); i += n
        except Exception: i += 1
    out = [b for b in out if isinstance(b, dict)]
    return out[-1] if out else None
for f in sorted(glob.glob("experiments/*/results/claude-*.jsonl")):
    R = [json.loads(l) for l in open(f)]; same = diff = null_now_parsed = still_null = 0
    for r in R:
        b = last(r.get("text") or "")
        if r.get("ans"): same += b == r["ans"]; diff += b != r["ans"]
        else: null_now_parsed += b is not None; still_null += b is None
    print(f"{f}: same={same} differ={diff} newly_parsed={null_now_parsed} still_unparsed={still_null}")
