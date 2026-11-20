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
HOME = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function" / "codex_stub_home_test"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
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

def run_main(fake_call, workers, interrupt_after=None):
    out_root = HOME / "main_check"
    shutil.rmtree(out_root, ignore_errors=True)
    saved = (run_codex.OUT_ROOT, run_codex.call_codex, run_codex.prepare_home, sys.argv)
    run_codex.OUT_ROOT = out_root
    run_codex.call_codex = fake_call
    run_codex.prepare_home = lambda *a, **k: prep
    sys.argv = ["run_codex.py", "structure", "gpt-6-astra", "--limit", "6", "--workers", str(workers), "--home", str(HOME)]
    timer = None
    if interrupt_after:
        import signal
        timer = threading.Timer(interrupt_after, lambda: os.kill(os.getpid(), signal.SIGINT))  # a real Ctrl-C signal
        timer.start()
    code = 0
    try:
        run_codex.main()
    except SystemExit as e:
        code = e.code
    finally:
        run_codex.OUT_ROOT, run_codex.call_codex, run_codex.prepare_home, sys.argv = saved
        import signal as _sig
        _sig.signal(_sig.SIGINT, _sig.default_int_handler)  # main() ignores SIGINT after the first one
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
stop.set()
run_codex.subprocess.run, launches = fake_codex("", "", code=1)
text, rec = run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, tries=3, timeout=30, stop=stop)
run_codex.subprocess.run = real_run
check(len(launches) == 1 and "stopped" in str(rec.get("error")), f"stop flag: no retry launched ({len(launches)} launches; {rec.get('error')})")

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
_signal.signal(_signal.SIGINT, _signal.default_int_handler)
check(code == 130 and len(rows) == len(CALLS) and len(CALLS) < 6,
      f"second Ctrl-C: every started call still written ({len(CALLS)} asked; {len(rows)} rows; exit {code})")

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
for test, n in (("next_residue", 2), ("structure", 1)):
    qs, _ = build_questions(test, "gpt-6-astra-high", 2)
    rows = []
    for _, prompt, meta in qs[:n]:
        MODE.clear()
        MODE.update(kind="answer")
        if test == "structure":
            MODE["text"] = json.dumps({"helices": [[2, 9]], "strands": [], "fold": "f", "contacts": [], "protein_name": "p",
                                       "function": "f", "functional_residues": [], "recognised": "no"})
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
