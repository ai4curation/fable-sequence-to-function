"""Tally, per results file, how many rows can show the number of turns and web requests of a call.

Purpose: check what the stored rows support for the Methods claim that calls were single-turn with no web search or
         fetch (review of the issues proposed for closing, 2026-11-19; follows up issue 49).
Inputs:  every experiments/*/results/**/*.jsonl file (read only).
Outputs: one line per file on standard output: rows, rows recording num_turns, rows with num_turns > 1, rows recording
         usage.server_tool_use, rows with any web_search_requests or web_fetch_requests > 0.
Usage:   tally_turns_and_web_requests_per_results_file.py      No model is called.      2026-11-19
"""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2] / "experiments"
for f in sorted(ROOT.glob("*/results/**/*.jsonl")):
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    turns = [r.get("num_turns") for r in rows if r.get("num_turns") is not None]
    stu = [(r.get("usage") or {}).get("server_tool_use") for r in rows]
    stu = [s for s in stu if isinstance(s, dict)]
    web = sum(1 for s in stu if any((s.get(k) or 0) > 0 for k in ("web_search_requests", "web_fetch_requests")))
    multi = sum(1 for t in turns if isinstance(t, int) and t > 1)
    print(f"{f.relative_to(ROOT)}: rows {len(rows)}, with num_turns {len(turns)}, num_turns>1 {multi}, "
          f"with server_tool_use {len(stu)}, web requests>0 {web}")
