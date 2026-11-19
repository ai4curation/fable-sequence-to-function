"""Find the command line tool's own session record for marked or multi-request calls and show what requests it made.

Purpose: the `claude` tool keeps a session file per call under <config dir>/projects/-private-tmp/. For each row of
         a results file that is marked context_tokens_high, or took more than one request, this prints the
         sequence of records in its session: type, role, stop reason, token counts, and the length of each text
         part. That shows whether a second request followed an output limit or a classifier stop (#65).
Inputs:  RESULTS (a results .jsonl), SESSIONS (the directory of session files).
Outputs: text on standard output. Nothing is written. Session files are read only.     Serves: #65, #81, #51.
Usage:   find_session_records_of_flagged_calls.py RESULTS SESSIONS [--show-text]     2026-11-19

A row is matched by its session_id when it has one and that file exists, and otherwise by the hash of the session's
first user message (prompt_sha256). A hash can match several sessions (the call and later re-asks of the same
question); each record is printed with its full time stamp, and the row's asked_at for comparison. A session whose
first user message is not exactly the question, or whose first user record is one the tool added, is not found by
hash (#88). The request bodies (`api-request-blob`) and attachments (`attachment` records) are not read, so the
script cannot show attached context; use it to see the sequence of requests and their stop reasons.
By default no message text is printed, only lengths: session files hold the machine's environment block and, in a
call with attached context, the start of that context. --show-text prints the first 80 characters of the messages
the tool itself added (isMeta user messages) and of API-error messages, and nothing else. Do not paste that output
into an issue without reading it.
"""
import hashlib, json, pathlib, sys
args = [a for a in sys.argv[1:] if a != "--show-text"]; SHOW = "--show-text" in sys.argv
if len(args) != 2: sys.exit(__doc__)
res, sessions = map(pathlib.Path, args)
R = [json.loads(l) for l in res.open() if l.strip()]
rows = [r for r in R if r.get("context_tokens_high") or max(r.get("requests") or 1, r.get("num_turns") or 1) > 1]
def label(r): return " ".join(str(r[k]) for k in ("accession", "pdb", "condition", "variant", "cut") if k in r)
def records(f):
    for line in f.open():
        try: yield json.loads(line)
        except ValueError: continue
def text_of(content): return content if isinstance(content, str) else "".join(b.get("text") or "" for b in content or [] if isinstance(b, dict))
def first_user_hash(f):
    for j in records(f):
        m = j.get("message") or {}
        if j.get("type") == "user" and m.get("role") == "user": return hashlib.sha256(text_of(m.get("content")).encode()).hexdigest()
files = sorted(sessions.glob("*.jsonl")); by_hash = {}
print(f"{res}: {len(R)} rows, {len(rows)} marked or with more than one request; {len(files)} session files in {sessions}")
for r in rows:
    sid = r.get("session_id"); hits = [f for f in files if f.stem == sid] if sid else []
    how = "session id" if hits else "prompt hash"
    if not hits:   # no session id, or its file is gone: fall back to the hash
        if not by_hash:
            for f in files: by_hash.setdefault(first_user_hash(f), []).append(f)
        hits = by_hash.get(r.get("prompt_sha256"), [])
    print(f"\n=== {label(r)}: asked_at {r.get('asked_at')}, marked {bool(r.get('context_tokens_high'))}, requests {r.get('requests')}, turns {r.get('num_turns')}, "
          f"summed input {r.get('context_tokens', r.get('input_tokens'))}, output {r.get('output_tokens')}; matched by {how}: {len(hits)} session file(s)")
    for f in hits:
        print(f"  -- {f.name}")
        for j in records(f):
            if j.get("type") not in ("user", "assistant", "system"): continue
            m = j.get("message") or {}; u = m.get("usage") or {}; c = m.get("content"); added = j.get("isMeta") or j.get("isApiErrorMessage")
            parts = [("text", c)] if isinstance(c, str) else [(b.get("type"), b.get("text") or b.get("thinking") or "") for b in c or [] if isinstance(b, dict)]
            desc = "; ".join(f"{k} {len(v)} chars" + (f": {v[:80]!r}" if SHOW and added and k == "text" else "") for k, v in parts)
            print(f"     {str(j.get('timestamp'))[:19]} {j.get('type')!s:9} {str(j.get('subtype') or m.get('role') or ''):26} stop={m.get('stop_reason')} in={u.get('input_tokens')} out={u.get('output_tokens')} "
                  f"added_by_tool={bool(j.get('isMeta'))} api_error={bool(j.get('isApiErrorMessage'))}  {desc}")
