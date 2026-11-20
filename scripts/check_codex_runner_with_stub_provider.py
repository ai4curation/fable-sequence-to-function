"""Run gpt6_experiment/run_codex.py's call path against a local stub provider. Calls no model.

Purpose: #52. Shows, offline, that call_codex (1) sends only the one-line instruction, the two allowed
tools and the question (checked on the request the stub receives), (2) records the session's
response id, served model, token counts and context check, (3) marks a reply that calls a tool,
a server error and a broken context as unusable.
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
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        REQUESTS.append(json.loads(body))
        if MODE["kind"] == "error":
            self.send_response(500)
            self.end_headers()
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
        for ev in ({"type": "response.created", "response": resp},
                   {"type": "response.output_item.done", "output_index": 0, "item": item},
                   {"type": "response.completed", "response": done}):
            self.wfile.write(sse(ev))
            self.wfile.flush()

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PROVIDER = ["-c", 'model_provider="stub"',
            "-c", f'model_providers.stub={{name="stub", base_url="http://127.0.0.1:{srv.server_address[1]}/v1", '
                  'wire_api="responses", request_max_retries=0, stream_max_retries=0}']
HOME = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function" / "codex_stub_home_test"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
prep = run_codex.prepare_home(HOME, ["gpt-6-astra"], require_login=False)
PROMPT = "Below is the beginning of a protein sequence.\n\n>sequence\nMKV"


def ask(kind, extra=(), **mode):
    MODE.clear()
    MODE.update(mode, kind=kind)
    REQUESTS.clear()
    return run_codex.call_codex("gpt-6-astra", "high", PROMPT, prep, HOME, extra=list(PROVIDER) + list(extra), tries=1, timeout=120)


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
check(rec["catalog_sha256"] == prep["catalog_sha256"] and rec["prompt_sha256"] == run_codex.sha(PROMPT), "row: catalog and prompt hashes")
check(json.loads(json.dumps(rec)) == rec, "row: JSON-serialisable")

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

# 5. extra context shows as input tokens above the limit: re-enable the shell tool
args_off = run_codex.FEATURES_OFF
run_codex.FEATURES_OFF = tuple(f for f in args_off if f not in ("shell_tool", "unified_exec"))
text, rec = ask("answer")
run_codex.FEATURES_OFF = args_off
tools5 = [t.get("name") for it in REQUESTS[0].get("input", []) if it.get("type") == "additional_tools" for ns in it.get("tools", []) for t in ns.get("tools", [ns])] if REQUESTS else []
check(len(tools5) > 2 and rec.get("context_tokens_high") and rec.get("status") == "UNUSABLE",
      f"extra tools: row unusable through the token limit ({tools5}; {rec.get('input_tokens')} > {rec.get('context_limit')})")

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

# 9. a home inside a git repository is refused (Codex would send the remote and commit)
try:
    run_codex.prepare_home(ROOT / ".temp" / "codex_home_in_repo", ["gpt-6-astra"], require_login=False)
    refused = False
except SystemExit:
    refused = True
check(refused, "home inside a git repository: refused")

srv.shutdown()
sys.exit(1 if FAILS else 0)
