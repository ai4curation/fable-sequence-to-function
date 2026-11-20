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
prep = run_codex.prepare_home(HOME, ["gpt-6-astra"], require_login=False, base_url=STUB_URL, retries=0)
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
real_provider = run_codex.provider_args(run_codex.CHATGPT_BASE_URL, retries=0)
check(prep["provider"] == [x.replace(run_codex.CHATGPT_BASE_URL, STUB_URL) for x in real_provider] and
      " ".join(prep["provider"]) in " ".join(run_codex.codex_args("gpt-6-astra", "high", prep)),
      "provider: the stub run uses the runner's provider settings, with only the base URL and retries changed")

# 2. a reply that calls a tool
text, rec = ask("tool")
check(rec.get("status") == "UNUSABLE", f"tool call: row unusable (tool_items={rec.get('tool_items')}, session calls={rec.get('session_tool_calls')}, turns={rec.get('num_turns')})")
check(run_codex.codex_unusable(rec), "tool call: codex_unusable says so")

# 3. a server error
text, rec = ask("error")
check(text is None and "error" in rec and run_codex.codex_unusable(rec), "server error: error row, unusable")

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
prep_ws = run_codex.prepare_home(HOME, ["gpt-6-astra"], require_login=False, base_url=STUB_URL, supports_websockets=True, retries=0)
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
check(text is None and rec.get("login_error") is True and rec.get("attempts") == 1,
      f"login error: one attempt, marked ({rec.get('attempts')} attempts; {str(rec.get('error'))[:80]})")

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
check(len(REQUESTS) == 1 and rec.get("attempts") == 1 and text == "MKVLAAGIVG" and rec.get("status") == "UNUSABLE"
      and "attempt failed after a reply" in (rec.get("unusable_because") or []),
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
