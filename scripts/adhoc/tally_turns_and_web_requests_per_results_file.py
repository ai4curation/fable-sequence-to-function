"""Tally, per results file and call route, how many rows can show the number of turns and web requests of a call.

Purpose: check what the stored rows support for the Methods statement on web search and fetch requests (issues 116,
         127 and 136, pull request 125). No model is called.
Inputs:  every experiments/*/results/**/*.jsonl file (read only).
Outputs: one line per file and route on standard output. Route is "revised" when the row records `extra_flags`
         (written by common.call), else "original". Per line: rows; rows with a usage record; rows with more than one
         turn or request; rows whose usage (server_tool_use) or model_usage (webSearchRequests) shows any web
         search or fetch request; rows with a non-numeric web count.
Usage:   python3 scripts/adhoc/tally_turns_and_web_requests_per_results_file.py
Date:    2026-11-19
"""
import json, math, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2] / "experiments"
def n(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None
def web(r):
    """True if any web request is recorded, False if none, None if a count is not a number."""
    counts = []
    stu = (r.get("usage") or {}).get("server_tool_use")
    if isinstance(stu, dict): counts += [stu.get(k) for k in ("web_search_requests", "web_fetch_requests")]   # a missing key is unknown
    mu = r.get("model_usage")
    if isinstance(mu, dict): counts += [v.get("webSearchRequests", 0) for v in mu.values() if isinstance(v, dict)]
    if any(n(c) is None for c in counts): return None
    return any(c > 0 for c in counts)
for f in sorted(ROOT.glob("*/results/**/*.jsonl")):
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    for route in ("original", "revised"):
        R = [r for r in rows if bool(r.get("extra_flags")) == (route == "revised")]
        if not R: continue
        withu = [r for r in R if isinstance(r.get("usage"), dict)]
        multi = sum(1 for r in R if max(n(r.get("num_turns")) or 1, n(r.get("requests")) or 1) > 1)
        w = [web(r) for r in withu]
        print(f"{f.relative_to(ROOT)} [{route}]: rows {len(R)}, with usage {len(withu)}, more than one turn or request "
              f"{multi}, web requests > 0 {sum(1 for x in w if x)}, non-numeric web count {sum(1 for x in w if x is None)}")
