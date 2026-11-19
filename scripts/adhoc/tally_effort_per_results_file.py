"""Tally the `effort` field in every results file (main checkout). Inputs: experiments/*/results/**/*.jsonl.
Output: stdout, one line per file. Serves the effort-alignment issue filed 2026-11-18."""
import json, glob, collections
for f in sorted(glob.glob('experiments/*/results/**/*.jsonl', recursive=True)):
    print(f, dict(collections.Counter(json.loads(l).get('effort') for l in open(f))))
