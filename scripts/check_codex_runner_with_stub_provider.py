"""Run gpt6_experiment/run_codex.py's call path against a local stub provider. Calls no model.

Purpose: #52. Shows, offline, that call_codex (1) sends only the one-line instruction, the two allowed
tools and the question (checked on the request the stub receives), (2) records the session's
response id, the model Codex requested, token counts, the context check and the check of each
request body Codex logged, (3) marks a reply that calls a tool,
a server error and a broken context as unusable, (4) uses the runner's own provider settings, with only
the base URL pointed at the stub, and marks a request sent over a websocket as unusable (#164), and
(5) stops at once on a login error (#165).
Inputs: the local Codex CLI. A scratch CODEX_HOME with no login under ~/agent-work (outside any git
repository, as the runner requires); the stub needs no login. The stub reports input tokens as a
quarter of the characters of instructions, tools and messages it received, so extra context in the
request pushes a row over the context limit as it would on a real call.
Outputs: one "ok"/"FAIL" line per check; exit 1 on any failure.
Date: 2026-11-20.
"""
import http.server
import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gpt6_experiment"))
import run_codex  # noqa: E402

FAILS = 0
REQUESTS = []
UPGRADES = []
MODE = {"kind": "answer"}
AGENTS_LINES = [l.strip() for l in (pathlib.Path.home() / ".codex" / "AGENTS.md").read_text().splitlines()
                if len(l.strip()) > 40][:5] if (pathlib.Path.home() / ".codex" / "AGENTS.md").exists() else []


def check(cond, what):
    global FAILS
    print(("ok   " if cond else "FAIL ") + what)
    FAILS += not cond


def sse(ev):
    return f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n".encode()


class Stub(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # a websocket upgrade: refused, so Codex falls back to HTTP as it would after a failure
        UPGRADES.append(self.headers.get("Upgrade"))
        self.send_response(400)
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        REQUESTS.append(json.loads(body))
        if MODE["kind"] in ("error", "login"):
            self.send_response(500 if MODE["kind"] == "error" else 401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if MODE["kind"] == "login":
                self.wfile.write(json.dumps({"error": {"message": "Your access token could not be refreshed because your "
                                                                  "refresh token was revoked. Please log out and sign in again.",
                                                       "code": "token_revoked"}}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        n = len(REQUESTS)
        req = REQUESTS[-1]
        sent = sum(len(json.dumps(it.get("tools"))) if it.get("type") == "additional_tools" else
                   sum(len(c.get("text", "")) for c in it.get("content", []) if isinstance(c, dict))
                   for it in req.get("input", [])) + len(req.get("instructions") or "") + len(json.dumps(req.get("tools") or []))
        tokens = MODE.get("tokens") or sent // 4
        if MODE["kind"] == "tool" and n == 1:
            item = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "request_user_input",
                    "arguments": json.dumps({"questions": [{"id": "q", "header": "h", "question": "?", "options": []}]})}
        else:
            item = {"type": "message", "id": f"msg_{n}", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": MODE.get("text", "MKVLAAGIVG"), "annotations": []}]}
        resp = {"id": f"resp_stub{n}", "object": "response", "model": "gpt-6-astra", "status": "in_progress", "output": []}
        done = dict(resp, status="completed", output=[item],
                    usage={"input_tokens": tokens, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 12,
                           "output_tokens_details": {"reasoning_tokens": 4}, "total_tokens": 524})
        if MODE["kind"] == "message_then_hang":  # a full reply, then the stream stays open past the timeout
            for ev in ({"type": "response.created", "response": resp}, {"type": "response.output_item.done", "output_index": 0, "item": item}):
                self.wfile.write(sse(ev))
                self.wfile.flush()
            threading.Event().wait(MODE.get("hang", 10))
            return
        if MODE["kind"] in ("message_then_cut", "reasoning_then_cut"):
            first = item if MODE["kind"] == "message_then_cut" else {"type": "reasoning", "id": f"rs_{n}", "summary": [{"type": "summary_text", "text": "thinking"}]}
            for ev in ({"type": "response.created", "response": resp}, {"type": "response.output_item.done", "output_index": 0, "item": first}):
                self.wfile.write(sse(ev))
                self.wfile.flush()
            return  # the connection closes without response.completed
        last = ({"type": "response.failed", "response": dict(resp, status="failed", error={"code": "server_error", "message": "stub failure after the reply"})}
                if MODE["kind"] == "fail_after_reply" else {"type": "response.completed", "response": done})
        for ev in ({"type": "response.created", "response": resp},
                   {"type": "response.output_item.done", "output_index": 0, "item": item}, last):
            self.wfile.write(sse(ev))
            self.wfile.flush()

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
STUB_URL = f"http://127.0.0.1:{srv.server_address[1]}/v1"
SCRATCH = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function"
SCRATCH.mkdir(parents=True, exist_ok=True)
HOME = pathlib.Path(tempfile.mkdtemp(prefix="codex_stub_home_test-", dir=SCRATCH))
print(f"Stub evidence: {HOME}")
prep = run_codex.prepare_home(HOME, ["gpt-6-astra"], require_login=False, base_url=STUB_URL)  # the real provider settings; only the URL differs (#168)
PROMPT = "Below is the beginning of a protein sequence.\n\n>sequence\nMKV"


def ask(kind, extra=(), **mode):
    MODE.clear()
    MODE.update(mode, kind=kind)
    REQUESTS.clear()
    return run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, extra=list(extra), tries=1, timeout=120)


# 1. a plain answer
text, rec = ask("answer")
req = REQUESTS[0] if REQUESTS else {}
inp = req.get("input", [])
dev = [c.get("text") for it in inp if it.get("role") == "developer" for c in it.get("content", [])]
users = [c.get("text") for it in inp if it.get("role") == "user" for c in it.get("content", [])]
tools = [t.get("name") for it in inp if it.get("type") == "additional_tools" for ns in it.get("tools", []) for t in ns.get("tools", [ns])]
check(dev == [run_codex.INSTRUCTION], "request: the only developer text is the one-line instruction")
check(users == [PROMPT], "request: the only user text is the question")
check(set(tools) <= {"request_user_input", "view_image"} and not req.get("tools"), f"request: only the two allowed tools ({tools})")
check(not any(m in json.dumps(req) for m in AGENTS_LINES), "request: nothing from ~/.codex/AGENTS.md")
check(req.get("reasoning", {}).get("effort") == "high", "request: effort high is sent")
check(text == "MKVLAAGIVG" and rec["status"] == "SUCCESS" and rec["tool_items"] == [], f"row: answer kept and usable, no warnings ({rec.get('tool_items')}, {rec.get('context_problem')})")
check(rec["context_ok"] and rec["response_ids"] == ["resp_stub1"] and rec["requested_model_logged"] == ["gpt-6-astra"],
      "row: session record gives context check, response id and the model Codex requested")
check(0 < rec["input_tokens"] <= rec["context_limit"] and rec["thinking_tokens"] == 4 and rec["num_turns"] == 1,
      f"row: token counts within the context limit ({rec['input_tokens']} of {rec['context_limit']}) and one turn")
check(rec["request_problem"] is None and rec["requests_logged"] == 1 and rec["request_hosts"] == [f"127.0.0.1:{srv.server_address[1]}"],
      f"row: the logged request body passes the request check ({rec.get('request_problem')})")
check(rec["request_sha256"] == [run_codex.sha(json.dumps(REQUESTS[0], sort_keys=True))], "row: the logged body is the body the server received")
check(rec["catalog_sha256"] == prep["catalog_sha256"] and rec["prompt_sha256"] == run_codex.sha(PROMPT), "row: catalog and prompt hashes")
check(json.loads(json.dumps(rec)) == rec, "row: JSON-serialisable")
check(rec["provider"] == run_codex.PROVIDER_ID and rec["base_url"] == STUB_URL and rec["websocket_log_lines"] == 0 and not UPGRADES,
      "row: the runner's own provider, over HTTP only (no websocket attempted)")
real_provider = run_codex.provider_args(run_codex.CHATGPT_BASE_URL)
check(prep["provider"] == [x.replace(run_codex.CHATGPT_BASE_URL, STUB_URL) for x in real_provider] and
      " ".join(prep["provider"]) in " ".join(run_codex.codex_args("gpt-6-astra", "high", prep)),
      "provider: the stub run uses the runner's provider settings, with only the base URL changed")

# 2. a reply that calls a tool
text, rec = ask("tool")
check(rec.get("status") == "UNUSABLE", f"tool call: row unusable (tool_items={rec.get('tool_items')}, session calls={rec.get('session_tool_calls')}, turns={rec.get('num_turns')})")
check(run_codex.codex_unusable(rec), "tool call: codex_unusable says so")

# 3. a server error
text, rec = ask("error")
check(len(REQUESTS) == 1 and rec.get("attempts") == 1 and run_codex.codex_unusable(rec),
      "server error after the request was sent: not retried (the model may have run), unusable")

# 4. a broken context (environment context switched back on) is caught by the session check
text, rec = ask("answer", ["-c", "include_environment_context=true"])
check(rec.get("context_ok") is False and rec.get("status") == "UNUSABLE", f"broken context: caught ({rec.get('context_problem')})")

# 5. extra tools on the longest real question: caught by the request check, whatever the length (#163)
sys.path.insert(0, str(ROOT / "gemini_experiment"))
from run_agy import build_questions  # noqa: E402

LONGEST = max((p for t in ("next_residue", "features", "pseudo", "structure") for _, p, _ in build_questions(t, "x", 2)[0]), key=len)
args_off = run_codex.FEATURES_OFF
run_codex.FEATURES_OFF = tuple(f for f in args_off if f not in ("shell_tool", "unified_exec"))
MODE.clear()
MODE.update(kind="answer")
text, rec = run_codex.call_codex("gpt-6-astra", "high", LONGEST, prep, HOME, tries=1, timeout=120)
run_codex.FEATURES_OFF = args_off
check(rec.get("status") == "UNUSABLE" and "request check" in (rec.get("unusable_because") or []) and "tools" in (rec.get("request_problem") or ""),
      f"extra tools, {len(LONGEST)}-character question: caught by the request check ({rec.get('request_problem')}; "
      f"token limit alone: {'caught' if rec.get('context_tokens_high') else 'missed'})")

# 5b. no request logged (trace log off): unusable, fail closed
real_env = run_codex.codex_env
run_codex.codex_env = lambda home: {k: v for k, v in real_env(home).items() if k != "RUST_LOG"}
text, rec = ask("answer")
run_codex.codex_env = real_env
check(rec.get("status") == "UNUSABLE" and rec.get("request_problem") == "no request logged", "no request logged: unusable")

# 5c. a provider that allows websockets: Codex tries one first, and the row is unusable (#164)
prep_ws = run_codex.prepare_home(HOME, ["gpt-6-astra"], require_login=False, base_url=STUB_URL, supports_websockets=True)
MODE.clear()
MODE.update(kind="answer")
UPGRADES.clear()
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep_ws, HOME, tries=1, timeout=120)
check(UPGRADES and rec.get("status") == "UNUSABLE" and rec.get("request_problem") == "websocket used",
      f"websocket attempted: unusable ({len(UPGRADES)} upgrade requests; {rec.get('request_problem')})")

# 5d. a login error is not retried and is marked for main to stop the run (#165)
MODE.clear()
MODE.update(kind="login")
REQUESTS.clear()
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=120)
check(rec.get("login_error") is True and rec.get("attempts") == 1 and len(REQUESTS) == 1 and run_codex.codex_unusable(rec),
      f"login error: one request, one attempt, marked, unusable ({len(REQUESTS)} requests; {rec.get('attempts')} attempts; {str(rec.get('error') or rec.get('attempt_failure'))[:80]})")

# 5e. a home holding a login is never pointed anywhere but the ChatGPT backend (#164)
guard = HOME.parent / "codex_stub_home_login_guard"
shutil.rmtree(guard, ignore_errors=True)
guard.mkdir()
(guard / "auth.json").write_text("{}")  # an empty placeholder, not a login
try:
    run_codex.prepare_home(guard, ["gpt-6-astra"], require_login=False, base_url=STUB_URL)
    refused = False
except SystemExit:
    refused = True
shutil.rmtree(guard, ignore_errors=True)
check(refused, "home with a login: any base URL other than the ChatGPT backend is refused")

# 5f. a failure reported after the reply arrived: not retried, kept and unusable, one request (#166)
MODE.clear()
MODE.update(kind="fail_after_reply")
REQUESTS.clear()
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=120)
log = rec.get("attempt_log") or [{}]
check(len(REQUESTS) == 1 and rec.get("attempts") == 1 and run_codex.codex_unusable(rec),
      f"failure after a reply: one request, no retry, unusable ({len(REQUESTS)} requests; {rec.get('attempts')} attempts; "
      f"{log[0].get('outcome')}; {rec.get('unusable_because') or str(rec.get('error'))[:60]})")

# 5g. a reply with a non-zero exit (Codex's exit code changed after the run): not retried, unusable (#166)
real_run = run_codex.subprocess.run
def exit_one(*a, **k):
    p = real_run(*a, **k)
    if a and a[0][:2] == ["codex", "exec"]:
        p.returncode = 1
    return p
run_codex.subprocess.run = exit_one
MODE.clear()
MODE.update(kind="answer")
REQUESTS.clear()
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=120)
run_codex.subprocess.run = real_run
REC_EXIT1 = rec
check(len(REQUESTS) == 1 and rec.get("attempts") == 1 and text == "MKVLAAGIVG" and rec.get("status") == "UNUSABLE"
      and "attempt failed after the request may have been sent" in (rec.get("unusable_because") or []),
      f"reply with exit 1: one request, reply kept, unusable ({len(REQUESTS)} requests; {rec.get('unusable_because')})")

# 5h. every attempt leaves its event stream, stderr and request body in the experiment home (#166)
t = rec.get("thread_id")
check(t and all((HOME / "attempts" / f"{t}_{x}").exists() for x in ("events.jsonl", "stderr.txt", "request_0.json"))
      and rec["attempt_log"][0]["requests_logged"] == 1 and rec["attempt_log"][0]["request_problem"] is None,
      "attempt evidence: event stream, stderr and checked request body saved")

# 5i. a row from before row_format 2 does not count, whatever its status (#166)
good = dict(rec, status="SUCCESS", unusable_because=None, num_turns=1)
check(not run_codex.codex_unusable(good) and run_codex.codex_unusable(dict(good, codex_row_format=1))
      and run_codex.codex_unusable({k: v for k, v in good.items() if k != "codex_row_format"}),
      "rows before codex_row_format 2 do not count (the runner, scorer and audit share this rule)")

# 5j. a stream cut after the reply, and one cut after reasoning only: Codex does not re-send the question
# (its own retries are off, #168) and the runner does not ask again (#169); one request each
for kind in ("message_then_cut", "reasoning_then_cut"):
    MODE.clear()
    MODE.update(kind=kind)
    REQUESTS.clear()
    text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=120)
    check(len(REQUESTS) == 1 and rec.get("attempts") == 1 and run_codex.codex_unusable(rec),
          f"{kind}: one request, no retry, unusable ({len(REQUESTS)} requests; {rec.get('attempts')} attempts; "
          f"{(rec.get('attempt_log') or [{}])[0].get('outcome')})")

# 5k. failure text in the row never carries trace lines (request bodies) (#170)
check(not any(x in json.dumps([rec_exit1.get(k) for k in ("attempt_failure", "attempt_log", "error", "stderr_tail")])
               for x in ("codex_http_client", "installation-id", "installation_id", "x-codex-window-id", "turn_metadata",
                         "client_metadata", "Answer the user"))
      if (rec_exit1 := globals().get("REC_EXIT1")) else False,
      "failure text: no trace lines or installation id in the row")

# 5l. saved request bodies are masked whatever else the check finds (#170)
fake = ('2026-01-01T00:00:00Z TRACE codex_http_client::transport: POST to http://127.0.0.1:1/v1/responses: '
        + json.dumps({"model": "other", "input": [], "note": "eyJ" + "a" * 40}))
kept = run_codex.keep_attempt(HOME, "masking-check", "", fake, "gpt-6-astra", "high", PROMPT)
saved = (HOME / "attempts" / "masking-check_request_0.json").read_text()
check(kept["requests_logged"] == 1 and "eyJ" not in saved and "[token-like]" in saved, "saved request body: token-like text masked")

# 5m. an unparsable output line: the attempt is still recorded and the reply kept, unusable (#171)
real_run = run_codex.subprocess.run
def broken_line(*a, **k):
    p = real_run(*a, **k)
    if a and a[0][:2] == ["codex", "exec"]:
        p.stdout = p.stdout + '{"type": "item.completed", "item": {"tex\n'
    return p
run_codex.subprocess.run = broken_line
MODE.clear()
MODE.update(kind="answer")
REQUESTS.clear()
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=120)
run_codex.subprocess.run = real_run
check(len(REQUESTS) == 1 and text == "MKVLAAGIVG" and rec.get("attempt_log") and run_codex.codex_unusable(rec)
      and (HOME / "attempts" / f"{rec.get('thread_id')}_events.jsonl").exists(),
      f"unparsable output line: attempt recorded, reply kept, unusable ({rec.get('unusable_because')})")

# 5n. main(): a login error stops the run before any further question; Ctrl-C asks nothing new and
# writes the rows of calls that finished (#165, #173). call_codex is faked here: no Codex runs.
import time as _time  # noqa: E402

HANDLERS_AFTER = []


def run_main(fake_call, workers, interrupt_after=None, sig=None, fresh=True, extra=(), limit=6, journal_default=False):
    """Run main() in-process: results and launch journal under the stub home, never in the repository."""
    import signal as _sig
    out_root = HOME / "main_check"
    if fresh:
        shutil.rmtree(out_root, ignore_errors=True)
    saved = (run_codex.OUT_ROOT, run_codex.JOURNAL_ROOT, run_codex.call_codex, run_codex.prepare_home, sys.argv)
    run_codex.OUT_ROOT = out_root
    run_codex.JOURNAL_ROOT = None if journal_default else out_root / "launched"
    if fake_call is not None:
        run_codex.call_codex = fake_call
    run_codex.prepare_home = lambda *a, **k: prep
    sys.argv = ["run_codex.py", "structure", "gpt-6-astra", "--limit", str(limit), "--workers", str(workers),
                "--home", str(HOME), *extra]
    if interrupt_after:
        threading.Timer(interrupt_after, lambda: os.kill(os.getpid(), sig or _sig.SIGINT)).start()  # a real signal
    code = 0
    try:
        run_codex.main()
    except SystemExit as e:
        code = e.code
    finally:
        run_codex.OUT_ROOT, run_codex.JOURNAL_ROOT, run_codex.call_codex, run_codex.prepare_home, sys.argv = saved
        HANDLERS_AFTER.append({s_: _sig.getsignal(s_) for s_ in (_sig.SIGINT, _sig.SIGTERM, _sig.SIGHUP)})
    f = out_root / "structure" / "gpt-6-astra-high.jsonl"
    return code, ([json.loads(l) for l in f.read_text().splitlines()] if f.exists() else [])

CALLS = []
def fake_login(model, effort, prompt, *a, **k):
    CALLS.append(prompt)
    _time.sleep(0.2)
    return None, dict(model=model, effort=effort, error="401 Unauthorized", login_error=True, codex_row_format=2)
code, rows = run_main(fake_login, 1)
check(len(CALLS) == 1 and len(rows) == 1 and code not in (0, None) and 'cli_auth_credentials_store="file"' in str(code),
      f"login stop: one question asked, one row, non-zero exit naming the login command ({len(CALLS)} asked; {len(rows)} rows; exit {code})")

CALLS.clear()
def fake_slow(model, effort, prompt, *a, **k):
    CALLS.append((round(_time.time() - T0, 2), prompt[:0]))
    _time.sleep(1.0)
    return "{}", dict(model=model, effort=effort, status="UNUSABLE", codex_row_format=2)
T0 = _time.time()
code, rows = run_main(fake_slow, 2, interrupt_after=1.5)
check(code == 130 and len(rows) == len(CALLS) and len(CALLS) < 6,
      f"Ctrl-C: nothing new asked, every finished call written ({len(CALLS)} asked of 6; {len(rows)} rows; exit {code})")

# 5o. second review of #167 (#175-#180)
import subprocess as _sp  # noqa: E402
import types as _types  # noqa: E402

def fake_codex(stdout, stderr="", code=1):
    """Replace Codex for one call: return the given output without running anything."""
    launches = []
    def run(*a, **k):
        if a and a[0][:2] == ["codex", "exec"]:
            launches.append(k)
            return _sp.CompletedProcess(a[0], code, stdout=stdout, stderr=stderr)
        return real_run(*a, **k)
    return run, launches

def ev(*xs):
    return "".join(json.dumps(x) + "\n" for x in xs)

STARTED = ({"type": "thread.started", "thread_id": "fake-thread"}, {"type": "turn.started"})
REPLY = {"type": "item.completed", "item": {"id": "i0", "type": "agent_message", "text": "MKVLAAGIVG"}}

# a timeout after the reply arrived: reply kept, unusable, never retried (#176)
MODE.clear()
MODE.update(kind="message_then_hang", hang=12)
REQUESTS.clear()
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=5)
check(len(REQUESTS) == 1 and text == "MKVLAAGIVG" and rec.get("attempts") == 1 and run_codex.codex_unusable(rec)
      and rec["attempt_log"][0]["outcome"] == "timeout",
      f"timeout after the reply: one request, reply kept, unusable ({len(REQUESTS)} requests; {text!r}; {rec.get('unusable_because') or rec.get('error')})")

# Codex runs in its own session, so a terminal Ctrl-C reaches only the runner (#175)
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, REPLY, {"type": "turn.completed", "usage": {"input_tokens": 9}}), code=0)
run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=1, timeout=30)
run_codex.subprocess.run = real_run
check(launches and launches[0].get("start_new_session") is True, "Codex runs in its own session (a terminal Ctrl-C does not kill a running call)")

# no new attempt once the stop flag is set, even if the first failed before any request (#175)
stop = threading.Event()
inner_run, launches = fake_codex("", "", code=1)
def run_then_stop(*a, **k):  # the stop arrives while the first attempt runs
    r = inner_run(*a, **k)
    if a and a[0][:2] == ["codex", "exec"]:
        stop.set()
    return r
run_codex.subprocess.run = run_then_stop
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30, stop=stop)
run_codex.subprocess.run = real_run
check(len(launches) == 1 and "stopped before a retry" in str(rec.get("error")), f"stop flag: no retry launched ({len(launches)} launches; {rec.get('error')})")

# without a trace log, a started turn still counts as reached: no retry (#179)
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, {"type": "turn.failed", "error": {"message": "stream disconnected"}}))
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.subprocess.run = real_run
check(len(launches) == 1 and run_codex.codex_unusable(rec), f"turn started, no request logged: no retry ({len(launches)} launches)")

# a reply followed by a 401: the reply is kept and the run is told to stop (#172)
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, REPLY, {"type": "turn.failed", "error": {"message": "unexpected status 401 Unauthorized"}}))
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.subprocess.run = real_run
check(len(launches) == 1 and text == "MKVLAAGIVG" and rec.get("login_error") is True and run_codex.codex_unusable(rec),
      "login error after a reply: reply kept, login_error set, unusable")

# failure text: masked (keys, refresh tokens, JWTs) and capped (#178)
secret = "sk-proj-" + "A" * 30 + " rt_" + "B" * 30 + " eyJ" + "C" * 40
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, {"type": "turn.failed", "error": {"message": secret + " " + "x" * 20000}}))
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.subprocess.run = real_run
fail_text = json.dumps([rec.get("attempt_failure"), rec.get("attempt_log")])
check(not any(x in fail_text for x in ("sk-proj-A", "rt_BBBB", "eyJCCCC")) and len(rec.get("attempt_failure") or "") <= 400,
      f"failure text: tokens masked, capped at 400 characters ({len(rec.get('attempt_failure') or '')} characters)")

# an unreadable session record, a body that cannot be checked, evidence that cannot be saved: reply kept (#171, #177)
real_read = run_codex.read_session
run_codex.read_session = lambda *a, **k: (_ for _ in ()).throw(OSError("unreadable"))
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, REPLY, {"type": "turn.completed", "usage": {"input_tokens": 9}}), code=0)
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.read_session = real_read
check(len(launches) == 1 and text == "MKVLAAGIVG" and rec.get("context_ok") is False and run_codex.codex_unusable(rec),
      "unreadable session record: one launch, reply kept, unusable")
check(isinstance(run_codex.check_request({"model": "gpt-6-astra", "reasoning": "high", "input": []}, "gpt-6-astra", "high", PROMPT), str),
      "request check: an unexpected body shape is a problem, not an exception")
real_keep = run_codex.keep_attempt
run_codex.keep_attempt = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.keep_attempt = real_keep
run_codex.subprocess.run = real_run
check(len(launches) == 2 and text == "MKVLAAGIVG" and run_codex.codex_unusable(rec) and "evidence" in json.dumps(rec.get("attempt_log")),
      f"evidence not saved: no retry, reply kept, unusable ({len(launches) - 1} launch)")

# a second Ctrl-C while running calls finish: their rows are still written (#175)
CALLS.clear()
T0 = _time.time()
import signal as _signal  # noqa: E402
second = threading.Timer(2.0, lambda: os.kill(os.getpid(), _signal.SIGINT))
second.start()
code, rows = run_main(fake_slow, 2, interrupt_after=1.5)
check(code == 130 and len(rows) == len(CALLS) and len(CALLS) < 6,
      f"second Ctrl-C: every started call still written ({len(CALLS)} asked; {len(rows)} rows; exit {code})")

# 5p. third review of #167 (#181, #182)
# SIGTERM and SIGHUP are handled like Ctrl-C: running calls finish and are written, exit 128 + signal (#181)
for name in ("SIGTERM", "SIGHUP"):
    CALLS.clear()
    T0 = _time.time()
    code, rows = run_main(fake_slow, 2, interrupt_after=1.5, sig=getattr(_signal, name))
    check(code == 128 + int(getattr(_signal, name)) and len(rows) == len(CALLS) and 0 < len(CALLS) < 6,
          f"{name}: handled like Ctrl-C, every started call written ({len(CALLS)} asked; {len(rows)} rows; exit {code})")

# the launch journal: written before each call; a question launched by a killed run is not asked again (#181)
JOURNAL = HOME / "main_check" / "launched" / "structure" / "gpt-6-astra-high.jsonl"
seen_in_journal = []
def fake_check_journal(model, effort, prompt, *a, **k):
    seen_in_journal.append(JOURNAL.exists() and len(JOURNAL.read_text().splitlines()))
    return "{}", dict(model=model, effort=effort, status="UNUSABLE", codex_row_format=2)
code, rows = run_main(fake_check_journal, 1, limit=2)
check(seen_in_journal == [1, 2], f"journal: each question on disk before its call ({seen_in_journal})")
launched_first = [r["pdb"] for r in rows]  # the two questions of the first run
(HOME / "main_check" / "structure" / "gpt-6-astra-high.jsonl").write_text("")  # as if the run had been killed: journal, no rows
code, rows2 = run_main(fake_slow, 1, fresh=False, limit=3)
code, rows3 = run_main(fake_slow, 1, fresh=False, limit=5, extra=["--retry-unusable"])
asked2 = [r["pdb"] for r in rows2]
asked3 = [r["pdb"] for r in rows3][len(rows2):]
check(len(launched_first) == 2 and len(asked2) == 3 and not set(asked2) & set(launched_first) and set(launched_first) <= set(asked3),
      f"journal: questions launched without a row are skipped by default and asked with --retry-unusable "
      f"(launched {launched_first}; next run asked {asked2}; with --retry-unusable asked {asked3})")

# main passes the stop flag into call_codex: Ctrl-C during a retry's backoff launches nothing new (#175, #182)
real_sleep = run_codex.time.sleep
run_codex.time.sleep = lambda secs: real_sleep(0.8)  # the same module as _time: call the saved function
run_codex.subprocess.run, launches = fake_codex("", "", code=1)  # fails before any request: would be retried
code, rows = run_main(None, 1, interrupt_after=0.3, limit=1)
run_codex.subprocess.run = real_run
run_codex.time.sleep = real_sleep
check(len(launches) == 1 and code == 130 and len(rows) == 1 and "stopped" in str(rows[0].get("error")),
      f"stop during backoff, through main: no second launch, row written ({len(launches)} launches; exit {code}; {[r.get('error') for r in rows]})")

# a timeout with no output at all still counts as reached: no retry (#176, #182)
def raise_timeout(*a, **k):
    if a and a[0][:2] == ["codex", "exec"]:
        launches.append(k)
        raise _sp.TimeoutExpired(a[0], 1, output=b"", stderr=b"")
    return real_run(*a, **k)
launches = []
run_codex.subprocess.run = raise_timeout
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.subprocess.run = real_run
check(len(launches) == 1 and "timeout" in json.dumps(rec.get("attempt_log")), f"silent timeout: no retry ({len(launches)} launches)")

# evidence that cannot be saved: no retry even with no output, the row is unusable, and the error is masked (#182)
run_codex.keep_attempt = lambda *a, **k: (_ for _ in ()).throw(OSError("Bearer abcdefghijklmnopqrstuvwxyz0123"))
run_codex.subprocess.run, launches = fake_codex("", "", code=1)
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30)
run_codex.subprocess.run = real_run
run_codex.keep_attempt = real_keep
check(len(launches) == 1 and "abcdefghijklmnop" not in json.dumps(rec), f"evidence not saved, no output: no retry, error masked ({len(launches)} launches)")
MODE.clear()
MODE.update(kind="answer")
run_codex.keep_attempt = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=120)
run_codex.keep_attempt = real_keep
check(rec.get("status") == "UNUSABLE" and "attempt evidence not saved" in (rec.get("unusable_because") or []),
      f"evidence not saved on a real (stub) call: unusable ({rec.get('unusable_because')})")

# caffeinate runs in its own session (#175, #182)
popen_kwargs = []
real_popen = run_codex.subprocess.Popen
run_codex.subprocess.Popen = lambda *a, **k: popen_kwargs.append((a[0][0], k))
code, rows = run_main(fake_slow, 1, limit=1)
run_codex.subprocess.Popen = real_popen
check(sys.platform != "darwin" or (popen_kwargs and popen_kwargs[0][0] == "caffeinate" and popen_kwargs[0][1].get("start_new_session") is True),
      f"caffeinate in its own session ({popen_kwargs[:1]})")

# the results file cannot be opened: nothing is asked (#182)
CALLS.clear()
bad = HOME / "main_check" / "structure" / "gpt-6-astra-high.jsonl"
shutil.rmtree(HOME / "main_check", ignore_errors=True)
bad.mkdir(parents=True)  # a folder where the file should be
code, rows = None, None
try:
    run_main(fake_slow, 2, fresh=False, limit=4)
except Exception as e:
    code = type(e).__name__
check(len(CALLS) == 0, f"results file unwritable: no question asked ({len(CALLS)} asked; {code})")
shutil.rmtree(HOME / "main_check", ignore_errors=True)

# masking: case-insensitive bearer, no over-masking inside words; session-record errors masked (#182)
check(run_codex.masked("bearer abcdefghijklmnopqrstuv and Basic QUJDREVGR0hJSktMTU5PUA==") .count("[token-like]") == 2
      and run_codex.masked("bearer proteins and basic KRKRKRKRKRKRKRKRKRKR") == "bearer proteins and basic KRKRKRKRKRKRKRKRKRKR"
      and all(run_codex.masked(t) == "[token-like]" for t in ("Bearer%20abcdefghijklmnop", 'Bearer "abcdefghijklmnop', "bearer=abcdefghijklmnop",
                                                              "Bearer+abcdefghijklmnop", "Bearer%3Aabcdefghijklmnop", "bearer\\tabcdefghijklmnop"))
      and run_codex.masked("report_error_abcdefghijklmnopqrstu risk-assessment-abcdefghijklmnop") == "report_error_abcdefghijklmnopqrstu risk-assessment-abcdefghijklmnop"
      and run_codex.masked("key sk-proj-abcdefghijklmnopqrst rt_abcdefghijklmnopqrstu").count("[token-like]") == 2,
      "masking: bearer/basic in any case, sk-/rt_ only as whole tokens")
run_codex.read_session = lambda *a, **k: (_ for _ in ()).throw(ValueError("Bearer abcdefghijklmnopqrstuvwxyz"))
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, REPLY, {"type": "turn.completed", "usage": {"input_tokens": 9}}), code=0)
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=1, timeout=30)
run_codex.subprocess.run = real_run
run_codex.read_session = real_read
check("abcdefghijklmnop" not in str(rec.get("context_problem")), f"session-record error masked ({rec.get('context_problem')})")

# 5q. fourth review of #167 (#184, #185)
import signal as _signal  # noqa: E402

class BrokenOut:  # a closed terminal or pipe: every write fails
    def write(self, *a):
        raise OSError(5, "Input/output error")
    def flush(self):
        raise OSError(5, "Input/output error")

def keys_unique(rows):
    return len({json.dumps(r.get("pdb")) for r in rows}) == len(rows)

# a stop signal with stdout gone: every started call is still written (#184)
CALLS.clear()
T0 = _time.time()
real_stdout = sys.stdout
sys.stdout = BrokenOut()
try:
    code, rows = run_main(fake_slow, 2, interrupt_after=1.5, sig=_signal.SIGHUP)
finally:
    sys.stdout = real_stdout
check(len(rows) == len(CALLS) and 0 < len(CALLS) < 6 and keys_unique(rows),
      f"closed terminal: every started call written, no duplicates ({len(CALLS)} asked; {len(rows)} rows; exit {code})")

# two stop signals in quick succession: every started call written once (#185)
CALLS.clear()
T0 = _time.time()
threading.Timer(1.55, lambda: os.kill(os.getpid(), _signal.SIGTERM)).start()
code, rows = run_main(fake_slow, 2, interrupt_after=1.5, sig=_signal.SIGTERM)
check(len(rows) == len(CALLS) and 0 < len(CALLS) < 6 and keys_unique(rows) and code == 128 + int(_signal.SIGTERM),
      f"two signals: every started call written once ({len(CALLS)} asked; {len(rows)} rows; exit {code})")

# a run started under nohup keeps ignoring SIGHUP (#185)
CALLS.clear()
T0 = _time.time()
_signal.signal(_signal.SIGHUP, _signal.SIG_IGN)
code, rows = run_main(fake_slow, 2, interrupt_after=1.5, sig=_signal.SIGHUP)
check(code in (0, None) and len(rows) == 6 and HANDLERS_AFTER[-1][_signal.SIGHUP] is _signal.SIG_IGN,
      f"nohup: SIGHUP ignored, all 6 questions written, handler left as ignored ({len(rows)} rows; exit {code})")
_signal.signal(_signal.SIGHUP, _signal.SIG_DFL)

# signal handlers are restored when main returns (#185)
sentinel = lambda *a: None  # noqa: E731
_signal.signal(_signal.SIGTERM, sentinel)
code, rows = run_main(fake_slow, 1, limit=1)
check(HANDLERS_AFTER[-1][_signal.SIGTERM] is sentinel, "signal handlers restored after the run")
_signal.signal(_signal.SIGTERM, _signal.SIG_DFL)

# one run per tag: a second run while the journal is held refuses to start (#185)
import fcntl as _fcntl  # noqa: E402
held = HOME / "main_check" / "launched" / "structure" / "gpt-6-astra-high.jsonl"
shutil.rmtree(HOME / "main_check", ignore_errors=True)
held.parent.mkdir(parents=True)
hf = held.open("a")
_fcntl.flock(hf, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
CALLS.clear()
code, rows = run_main(fake_slow, 1, fresh=False, limit=2)
hf.close()
check(len(CALLS) == 0 and "another run" in str(code), f"concurrent run of the same tag refused ({len(CALLS)} asked; {code})")

# a damaged journal line stops the run before any call, naming the line (#185)
shutil.rmtree(HOME / "main_check", ignore_errors=True)
held.parent.mkdir(parents=True)
held.write_text('{"key": "15AY"}\n{"key": "37D')
CALLS.clear()
code, rows = run_main(fake_slow, 1, fresh=False, limit=2)
check(len(CALLS) == 0 and "line 2 is damaged" in str(code), f"damaged journal line: nothing asked, line named ({code})")

# the journal sits in the experiment home by default, not in the checkout (#185)
check(run_codex.JOURNAL_ROOT is None, "journal: kept under the experiment home by default")

# every question key of every test survives the journal round trip (#185 D8)
bad_keys = [k for t in ("next_residue", "features", "pseudo", "structure") for k, _, _ in build_questions(t, "x", 2)[0]
            if run_codex.key_from_json(json.loads(json.dumps(run_codex.key_to_json(k)))) != k]
check(not bad_keys, f"journal keys round-trip for all four tests ({len(bad_keys)} failures)")

# the request check uses the full mask; runner errors in rows are masked (#185 D2, D5)
check(run_codex.check_request({"model": "gpt-6-astra", "reasoning": {"effort": "high"},
                               "input": [{"type": "message", "role": "user", "content": [{"text": "sk-proj-" + "a" * 20}]}]},
                              "gpt-6-astra", "high", PROMPT) is not None, "request check: an sk- key in the body is a problem")
def fake_raise(*a, **k):
    raise RuntimeError("Bearer " + "z" * 30)
code, rows = run_main(fake_raise, 1, limit=1)
check(rows and "zzzzzzzzzz" not in json.dumps(rows), f"runner error masked in the row ({[r.get('error') for r in rows]})")

# 5r. fifth review of #167 (#190, #191)
# an exception in the loop: the rows of calls that finish afterwards are still written, nothing new starts (#190)
CALLS.clear()
T0 = _time.time()
real_unusable = run_codex.codex_unusable
boom = {"n": 0}
def unusable_once(row):
    boom["n"] += 1
    if boom["n"] == 1:
        raise RuntimeError("injected")
    return real_unusable(row)
run_codex.codex_unusable = unusable_once
err = None
try:
    code, rows = run_main(fake_slow, 3, limit=3)
except RuntimeError as e:
    err = e
run_codex.codex_unusable = real_unusable
f_rows = HOME / "main_check" / "structure" / "gpt-6-astra-high.jsonl"
rows = [json.loads(l) for l in f_rows.read_text().splitlines()] if f_rows.exists() else []
check(len(rows) == len(CALLS) == 3, f"error in the loop: every finished call still written ({len(CALLS)} asked; {len(rows)} rows; {err!r})")

# a journal write failure: that question is not asked, gets a not-asked row, and the others are written (#190)
CALLS.clear()
real_fsync = run_codex.os.fsync
fs = {"n": 0}
def fsync_fails_third(fd):
    fs["n"] += 1
    if fs["n"] == 3:
        raise OSError(5, "Input/output error")
    return real_fsync(fd)
run_codex.os.fsync = fsync_fails_third
code, rows = run_main(fake_slow, 1, limit=3)
run_codex.os.fsync = real_fsync
check(len(CALLS) == 2 and len(rows) == 3 and sum(bool(r.get("not_asked")) for r in rows) == 1,
      f"journal write fails: not asked, row says so, others written ({len(CALLS)} asked; {len(rows)} rows)")
# ... and a not-asked row does not count as asked on the next run (#191)
not_asked_key = next(r["pdb"] for r in rows if r.get("not_asked"))
CALLS.clear()
code, rows = run_main(fake_slow, 1, fresh=False, limit=1)
check(len(CALLS) == 1 and rows[-1]["pdb"] == not_asked_key,
      f"a not-asked row is asked on the next run (expected {not_asked_key}, got {rows[-1]['pdb']})")

# A failed submit must not discard futures for calls already launched (#190).
real_executor = run_codex.ThreadPoolExecutor
started = threading.Event()
release = threading.Event()
class FailingSubmitExecutor(real_executor):
    def submit(self, *args, **kwargs):
        if started.is_set():
            release.set()
            raise RuntimeError("injected submit failure")
        future = super().submit(*args, **kwargs)
        assert started.wait(5), "first call did not start"
        return future

def fake_pending(model, effort, prompt, *a, **k):
    CALLS.append(prompt)
    started.set()
    assert release.wait(5), "submit failure did not release the call"
    return "{}", dict(model=model, effort=effort, status="UNUSABLE", codex_row_format=2)

CALLS.clear()
run_codex.ThreadPoolExecutor = FailingSubmitExecutor
submit_error = None
try:
    run_main(fake_pending, 1, limit=3)
except RuntimeError as e:
    submit_error = str(e)
finally:
    run_codex.ThreadPoolExecutor = real_executor
rows = [json.loads(l) for l in f_rows.read_text().splitlines()] if f_rows.exists() else []
check(submit_error == "injected submit failure" and len(rows) == len(CALLS) == 1,
      f"submit failure: already launched call is written ({len(CALLS)} calls; {len(rows)} rows)")

# A known unlaunched call is released even from another checkout; an older ambiguous
# attempt for the same question must remain blocked (including legacy journal lines).
first_key = build_questions("structure", "gpt-6-astra-high", 2)[0][0][0]
jpath = HOME / "main_check" / "launched" / "structure" / "gpt-6-astra-high.jsonl"
cancelled_launch = dict(key=first_key, launch_id="cancelled", results="/elsewhere/results.jsonl")
for legacy in (None, True, False):
    f_rows.write_text("")
    entries = [cancelled_launch, dict(cancelled_launch, not_asked=True)]
    if legacy is not None:
        older = dict(key=first_key, results="/elsewhere/results.jsonl")
        if not legacy:
            older["launch_id"] = "older-ambiguous"
        entries.insert(0, older)
    jpath.write_text("".join(json.dumps(e) + "\n" for e in entries))
    CALLS.clear()
    code, rows = run_main(fake_slow, 1, fresh=False, limit=1)
    check(len(CALLS) == 1 and (rows[0]["pdb"] == first_key) == (legacy is None),
          f"cancelled launch: releases only its own attempt, across checkouts (older legacy={legacy})")

# a stop that arrives after a question was taken: no Codex launch (#191)
stop = threading.Event()
stop.set()
run_codex.subprocess.run, launches = fake_codex(ev(*STARTED, REPLY, {"type": "turn.completed", "usage": {"input_tokens": 9}}), code=0)
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30, stop=stop)
run_codex.subprocess.run = real_run
check(not launches and rec.get("not_asked") is True and "before the call" in str(rec.get("error")),
      f"stop before the first launch: Codex not started ({len(launches)} launches; {rec.get('error')})")

# the first stop signal sets the exit status (#191)
CALLS.clear()
T0 = _time.time()
threading.Timer(1.6, lambda: os.kill(os.getpid(), _signal.SIGINT)).start()
code, rows = run_main(fake_slow, 2, interrupt_after=1.5, sig=_signal.SIGTERM)
check(code == 128 + int(_signal.SIGTERM) and len(rows) == len(CALLS), f"first signal sets the exit status (exit {code})")

# Check the actual flush, not worker scheduling: a worker may start its next question
# before the main thread collects its previous future (#185, #191).
syncs = {"n": 0}
def counting_fsync(fd):
    syncs["n"] += 1
    return real_fsync(fd)
flushed_rows = []
real_path_open = pathlib.Path.open
class FlushObserver:
    def __init__(self, fh): self.fh = fh
    def __getattr__(self, name): return getattr(self.fh, name)
    def __enter__(self): return self
    def __exit__(self, *args): return self.fh.__exit__(*args)
    def flush(self):
        self.fh.flush()
        with real_path_open(f_rows) as source:
            flushed_rows.append(len(source.read().splitlines()))
def observe_open(path, mode="r", *args, **kwargs):
    fh = real_path_open(path, mode, *args, **kwargs)
    return FlushObserver(fh) if path == f_rows and mode == "a" else fh
def fake_fast(model, effort, prompt, *a, **k):
    return "{}", dict(model=model, effort=effort, status="UNUSABLE", codex_row_format=2)
shutil.rmtree(HOME / "launched", ignore_errors=True)
run_codex.os.fsync = counting_fsync
pathlib.Path.open = observe_open
try:
    code, rows = run_main(fake_fast, 1, limit=3, journal_default=True)
finally:
    run_codex.os.fsync = real_fsync
    pathlib.Path.open = real_path_open
home_journal = HOME / "launched" / "structure" / "gpt-6-astra-high.jsonl"
check(home_journal.exists() and len(home_journal.read_text().splitlines()) == 3 and syncs["n"] == 3 and flushed_rows == [1, 2, 3],
      f"journal in <home>/launched, synced per call, each row flushed ({syncs['n']} syncs; rows on flush {flushed_rows})")
shutil.rmtree(HOME / "launched", ignore_errors=True)

# a journal line from a run writing another results file: not asked here, reported as such (#191)
shutil.rmtree(HOME / "main_check", ignore_errors=True)
jpath = HOME / "main_check" / "launched" / "structure" / "gpt-6-astra-high.jsonl"
jpath.parent.mkdir(parents=True)
first_two = [k for k, _, _ in build_questions("structure", "gpt-6-astra-high", 2)[0][:2]]
jpath.write_text(json.dumps({"key": first_two[0], "results": "/elsewhere/results.jsonl"}) + "\n")
CALLS.clear()
code, rows = run_main(fake_slow, 1, fresh=False, limit=1)
check(rows and rows[0]["pdb"] != first_two[0], f"a question asked from another checkout is not asked again here ({[r['pdb'] for r in rows]})")

# a refused run (lock held) touches nothing: prepare_home is not run (#191)
shutil.rmtree(HOME / "main_check", ignore_errors=True)
jpath.parent.mkdir(parents=True)
hf = jpath.open("a")
_fcntl.flock(hf, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
prepared = []
real_prep = run_codex.prepare_home
saved_argv = sys.argv
run_codex.OUT_ROOT, run_codex.JOURNAL_ROOT = HOME / "main_check", HOME / "main_check" / "launched"
run_codex.prepare_home = lambda *a, **k: prepared.append(1) or prep
sys.argv = ["run_codex.py", "structure", "gpt-6-astra", "--limit", "1", "--home", str(HOME)]
try:
    run_codex.main()
    msg = None
except SystemExit as e:
    msg = str(e.code)
run_codex.prepare_home, sys.argv = real_prep, saved_argv
run_codex.OUT_ROOT, run_codex.JOURNAL_ROOT = ROOT / "gpt6_experiment" / "results", None
hf.close()
check(not prepared and "another run" in str(msg), f"refused run: the experiment home is not touched ({len(prepared)} prepare_home calls)")

# a closed stdout: rows written and the exit status is still 128 + signal, not 120 (#191); run in a child process
child = HOME / "closed_stdout_child.py"
child.write_text(f"""
import json, sys, time, threading, os, signal, pathlib
sys.path.insert(0, {str(ROOT / "gpt6_experiment")!r})
import run_codex
out = pathlib.Path({str(HOME / "closed_stdout_check")!r})
run_codex.OUT_ROOT, run_codex.JOURNAL_ROOT = out, out / "launched"
run_codex.prepare_home = lambda *a, **k: {{"provider": [], "base_url": "x", "catalog": "x", "instructions": "x", "catalog_sha256": "x"}}
def fake(model, effort, prompt, *a, **k):
    time.sleep(1.0)
    return "{{}}", dict(model=model, effort=effort, status="UNUSABLE", codex_row_format=2)
run_codex.call_codex = fake
sys.argv = ["run_codex.py", "structure", "gpt-6-astra", "--limit", "4", "--workers", "2", "--home", {str(HOME)!r}]
run_codex.main()
""")
shutil.rmtree(HOME / "closed_stdout_check", ignore_errors=True)
import subprocess as _sp2  # noqa: E402
proc = _sp2.Popen([sys.executable, str(child)], stdout=_sp2.PIPE, stderr=_sp2.DEVNULL, start_new_session=True)
proc.stdout.close()  # the reader is gone
_time.sleep(1.5)
proc.send_signal(_signal.SIGTERM)
rc = proc.wait(timeout=60)
crow = HOME / "closed_stdout_check" / "structure" / "gpt-6-astra-high.jsonl"
n_child_rows = len(crow.read_text().splitlines()) if crow.exists() else 0
check(rc == 128 + int(_signal.SIGTERM) and n_child_rows >= 2, f"closed stdout: exit {rc} (want {128 + int(_signal.SIGTERM)}), {n_child_rows} rows written")

# 6. an empty reply is unusable
text, rec = ask("answer", text="")
check(rec.get("status") == "UNUSABLE" and "empty reply" in (rec.get("unusable_because") or []), "empty reply: unusable")

# 7. API keys and endpoint overrides in the caller's environment are not passed on
os.environ["OPENAI_API_KEY"] = "sk-should-not-pass"
os.environ["CODEX_API_KEY"] = "should-not-pass"
env = run_codex.codex_env(HOME)
check("OPENAI_API_KEY" not in env and "CODEX_API_KEY" not in env and env["CODEX_HOME"] == str(HOME), "environment: OPENAI_*/CODEX_* dropped, CODEX_HOME set")
del os.environ["OPENAI_API_KEY"], os.environ["CODEX_API_KEY"]

# 8. preparing another model in the same home leaves this model's catalog alone
before = pathlib.Path(prep["catalog"]).read_text()
other = run_codex.prepare_home(HOME, ["gpt-6-sol"], require_login=False)
check(other["catalog"] != prep["catalog"] and pathlib.Path(prep["catalog"]).read_text() == before, "catalog: one file per model, runs can share a home")

# 9. a home inside a git repository is refused before anything is created there
inside = ROOT / ".temp" / "codex_home_inside_repo_check" / "home"
shutil.rmtree(inside.parent, ignore_errors=True)
try:
    run_codex.prepare_home(inside, ["gpt-6-astra"], require_login=False)
    refused = False
except SystemExit:
    refused = True
check(refused and not inside.parent.exists(), "home inside a git repository: refused, nothing created")

# 10. rows written as the runner writes them are read by the scorer and the audit (#52)
import subprocess  # noqa: E402

RESULTS = HOME / "results"
shutil.rmtree(RESULTS, ignore_errors=True)
for test, n in (("next_residue", 2), ("structure", 1), ("decoy_control", 1)):
    qs, _ = build_questions(test, "gpt-6-astra-high", 2)
    rows = []
    for _, prompt, meta in qs[:n]:
        MODE.clear()
        MODE.update(kind="answer")
        if test == "structure":
            MODE["text"] = json.dumps({"helices": [[2, 9]], "strands": [], "fold": "f", "contacts": [], "protein_name": "p",
                                       "function": "f", "functional_residues": [], "recognised": "no"})
        if test == "decoy_control":
            MODE["text"] = json.dumps({"protein_name": "stub", "catalytically_active": "yes", "catalytic_residues": []})
        text, rec = run_codex.call_codex("gpt-6-astra", "high", prompt, prep, HOME, tries=1, timeout=120)
        rows.append(run_codex.build_row(test, meta, text, rec))
    (RESULTS / test).mkdir(parents=True, exist_ok=True)
    (RESULTS / test / "gpt-6-astra-high.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
score = subprocess.run([sys.executable, str(ROOT / "gemini_experiment" / "score_gemini.py"), str(RESULTS)],
                       capture_output=True, text=True, cwd=ROOT)
check(score.returncode == 0 and "== gpt-6-astra-high: 2 usable" in score.stdout and "== gpt-6-astra-high: 1 usable" in score.stdout,
      "scorer: reads the GPT-6 rows (2 test-1 rows, 1 test-4 row usable)")
audit = subprocess.run([sys.executable, str(ROOT / "gemini_experiment" / "audit.py"), str(RESULTS)],
                       capture_output=True, text=True, cwd=ROOT)
check(audit.returncode == 0 and "gpt-6-astra-high.jsonl" in audit.stdout, f"audit: passes on the GPT-6 rows ({audit.stderr.strip()[-200:]})")
decoy_score = subprocess.run([sys.executable, str(ROOT / "experiments/decoy_control/score_decoys.py"),
                             "--results", str(RESULTS / "decoy_control"), "--pseudo-results", str(RESULTS / "pseudo")],
                            capture_output=True, text=True, cwd=ROOT)
check(decoy_score.returncode == 0 and "1 answers scored" in decoy_score.stdout, "decoy scorer: reads Codex rows")
decoy_path = RESULTS / "decoy_control/gpt-6-astra-high.jsonl"
decoy_row = json.loads(decoy_path.read_text())
decoy_row["status"] = "UNUSABLE"
decoy_path.write_text(json.dumps(decoy_row) + "\n")
decoy_score = subprocess.run([sys.executable, str(ROOT / "experiments/decoy_control/score_decoys.py"),
                             "--results", str(RESULTS / "decoy_control"), "--pseudo-results", str(RESULTS / "pseudo")],
                            capture_output=True, text=True, cwd=ROOT)
check(decoy_score.returncode == 0 and "0 answers scored" in decoy_score.stdout, "decoy scorer: excludes unusable Codex replies")

_, prompt, meta = next(q for q in build_questions("next_residue", "gpt-6-astra-low", 3)[0] if q[2]["condition"] == "reversed")
MODE.clear()
MODE.update(kind="answer")
text, rec = run_codex.call_codex("gpt-6-astra", "low", prompt, prep, HOME, tries=1, timeout=120)
reversed_row = run_codex.build_row("next_residue", dict(meta, ncond=3), text, rec)
reversed_path = RESULTS / "next_residue/gpt-6-astra-low.jsonl"
reversed_path.write_text(json.dumps(reversed_row) + "\n")
audit = subprocess.run([sys.executable, str(ROOT / "gemini_experiment/audit.py"), str(RESULTS)], capture_output=True, text=True, cwd=ROOT)
check(audit.returncode == 0 and "expected 408" in audit.stdout, "audit: includes declared reversed-sequence Codex condition")
reversed_row["ncond"] = 2
reversed_path.write_text(json.dumps(reversed_row) + "\n")
audit = subprocess.run([sys.executable, str(ROOT / "gemini_experiment/audit.py"), str(RESULTS)], capture_output=True, text=True, cwd=ROOT)
check(audit.returncode != 0 and "unexpected question" in audit.stderr, "audit: rejects reversed sequences in a two-condition run")
reversed_path.unlink()
bad = [json.loads(l) for l in (RESULTS / "structure" / "gpt-6-astra-high.jsonl").read_text().splitlines()]
bad[0]["context_ok"] = False
(RESULTS / "structure" / "gpt-6-astra-high.jsonl").write_text("".join(json.dumps(r) + "\n" for r in bad))
audit = subprocess.run([sys.executable, str(ROOT / "gemini_experiment" / "audit.py"), str(RESULTS)],
                       capture_output=True, text=True, cwd=ROOT)
check(audit.returncode != 0 and "context check" in audit.stderr, "audit: fails a usable GPT-6 row whose context check failed")
bad[0]["context_ok"] = True
bad[0]["websocket_log_lines"] = 1
(RESULTS / "structure" / "gpt-6-astra-high.jsonl").write_text("".join(json.dumps(r) + "\n" for r in bad))
audit = subprocess.run([sys.executable, str(ROOT / "gemini_experiment" / "audit.py"), str(RESULTS)],
                       capture_output=True, text=True, cwd=ROOT)
check(audit.returncode != 0 and "context check" in audit.stderr, "audit: fails a usable GPT-6 row that used a websocket (#164)")

srv.shutdown()
sys.exit(1 if FAILS else 0)
