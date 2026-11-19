"""Find the command line tool's own session record for each flagged call and show the messages it holds.

Purpose: five Opus 4.6 high-effort test 2 rows are marked context_tokens_high with about twice (once three times)
         the input of a single request (#65). The tool keeps a session file per call under
         <config dir>/projects/-private-tmp/. This script finds the session whose first user message hashes to the
         row's prompt_sha256 and prints, per record, its type, role, stop reason, usage and the start of any text that
         is not the question, so that what the second request carried can be read.
Inputs:  RESULTS (a results .jsonl, whose rows hold prompt_sha256), SESSIONS (the directory of session files).
Outputs: text on standard output. Nothing is written. Session files are read only.     Serves: #65, #51.     2026-11-19
Usage:   find_session_records_of_flagged_calls.py RESULTS SESSIONS
"""
import hashlib, json, pathlib, sys
res, sessions = map(pathlib.Path, sys.argv[1:3])
R = [json.loads(l) for l in res.open()]; flagged = [r for r in R if r.get("context_tokens_high")]
files = sorted(sessions.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-600:]
def first_user_hash(f):
    """SHA-256 of the first user message of a session file: the question as the tool received it."""
    for line in f.open():
        try: j = json.loads(line)
        except ValueError: continue
        m = j.get("message") or {}
        if j.get("type") == "user" and m.get("role") == "user":
            c = m.get("content"); text = c if isinstance(c, str) else "".join(b.get("text") or "" for b in c or [] if isinstance(b, dict))
            return hashlib.sha256(text.encode()).hexdigest()
by_hash = {}
for f in files: by_hash.setdefault(first_user_hash(f), []).append(f)
def flat(content):
    if isinstance(content, str): return [("text", content)]
    return [(b.get("type"), b.get("text") or b.get("thinking") or "") for b in content or [] if isinstance(b, dict)]
for r in flagged:
    hits = by_hash.get(r["prompt_sha256"], [])
    print(f"\n=== {r['accession']} {r['condition']}: input {r['input_tokens']}, output {r['output_tokens']}; session files whose first user message has the row's prompt hash: {len(hits)}")
    for f in hits:
        print(f"  -- {f.name}")
        for line in f.open():
            try: j = json.loads(line)
            except ValueError: continue
            m = j.get("message") or {}; u = m.get("usage") or {}
            parts = flat(m.get("content"))
            desc = "; ".join(f"{k} {len(v)} chars" + (f": {v[:160]!r}" if k == "text" and hashlib.sha256(v.encode()).hexdigest() != r["prompt_sha256"] else "") for k, v in parts)
            print(f"     {j.get('type')!s:10} {str(j.get('subtype') or m.get('role') or ''):10} stop={m.get('stop_reason')} in={u.get('input_tokens')} out={u.get('output_tokens')} "
                  f"meta={j.get('isMeta')} api_error={j.get('isApiErrorMessage')} {str(j.get('timestamp'))[11:19]}  {desc[:420]}")
