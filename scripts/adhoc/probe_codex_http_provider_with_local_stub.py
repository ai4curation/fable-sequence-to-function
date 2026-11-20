"""Check offline that an experiment provider with requires_openai_auth=true and supports_websockets=false
sends one logged HTTP POST and no websocket upgrade. Calls no model.

Purpose: #52 / PR #161. The built-in `openai` provider uses websockets with a ChatGPT login, and
built-in provider IDs cannot be overridden, so the runner would name its own provider. Here the
provider points at a local stub (no network); the stub home has no login, which shows whether Codex
needs one before it sends. Inputs: local Codex CLI, gpt6_experiment/run_codex.py.
Outputs: printed summary; stderr in ~/agent-work/fable-sequence-to-function/codex_ws_probe/http_provider.stderr.
Date: 2026-11-20.
"""
import pathlib, subprocess, sys, threading, http.server, json
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gpt6_experiment")); sys.path.insert(0, str(ROOT / "scripts" / "adhoc"))
import run_codex as rc  # noqa: E402
OUT = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function" / "codex_ws_probe"
SEEN = []
SSE = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in [
    {"type": "response.created", "response": {"id": "resp_stub"}},
    {"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "id": "m", "content": [{"type": "output_text", "text": "ok"}]}},
    {"type": "response.completed", "response": {"id": "resp_stub", "usage": {"input_tokens": 1, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 1, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 2}}}])
class Stub(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        SEEN.append(("GET", self.path, self.headers.get("Upgrade"))); self.send_response(400); self.end_headers()
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        SEEN.append(("POST", self.path, len(body), "auth header" if self.headers.get("Authorization") else "no auth header"))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers(); self.wfile.write(SSE.encode())
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), Stub); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
home = OUT / "home"; prep = rc.prepare_home(home, ["gpt-6-astra"], require_login=False)
prov = (f'model_providers.exp={{name="exp", base_url="http://127.0.0.1:{port}/v1", wire_api="responses", '
        'requires_openai_auth=true, supports_websockets=false, request_max_retries=0, stream_max_retries=0}')
args = rc.codex_args("gpt-6-astra", "high", prep, ["-c", 'model_provider="exp"', "-c", prov, "PROBE-PROMPT"])
p = subprocess.run(args, cwd=home / "empty_cwd", env=rc.codex_env(home), capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
(OUT / "http_provider.stderr").write_text(p.stderr)
print("exit", p.returncode, "stub saw", SEEN, "logged POSTs", len(rc.requests_sent(p.stderr)))
print("websocket lines", sum("websocket" in l.lower() for l in p.stderr.splitlines()))
print("stdout tail", p.stdout.strip()[-300:])
srv.shutdown()
