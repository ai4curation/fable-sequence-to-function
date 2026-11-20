"""Find out when `codex exec` sends the request over a websocket instead of an HTTP POST. Calls no model.

Purpose: #52 / PR #161. The first real GPT-6 canary (2026-11-20) got an answer, but Codex logged no
`codex_http_client::transport: POST` line, so the runner's request check found no request. The bundled
model catalog marks GPT-6 models `prefer_websockets: true`, and providers have `supports_websockets`.
This probe points Codex at a local stub (no login, no network) that records every HTTP request,
including websocket upgrade GETs, and answers POSTs with a minimal SSE reply. It runs the runner's own
arguments under a few websocket settings and reports which transport Codex tried and which trace
lines mention it.
Inputs: the local Codex CLI and gpt6_experiment/run_codex.py.
Outputs: ~/agent-work/fable-sequence-to-function/codex_ws_probe/<variant>.stderr and a printed summary.
Date: 2026-11-20.
"""
import http.server
import json
import pathlib
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gpt6_experiment"))
import run_codex as rc  # noqa: E402

OUT = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function" / "codex_ws_probe"
HOME = OUT / "home"
MODEL = "gpt-6-astra"
SEEN = []

SSE = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in [
    {"type": "response.created", "response": {"id": "resp_stub"}},
    {"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "id": "msg_stub",
                                                    "content": [{"type": "output_text", "text": "ok"}]}},
    {"type": "response.completed", "response": {"id": "resp_stub", "usage": {
        "input_tokens": 1, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 1,
        "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 2}}},
])


class Stub(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        SEEN.append(("GET", self.path, self.headers.get("Upgrade")))
        self.send_response(400)
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        SEEN.append(("POST", self.path, len(body)))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(SSE.encode())

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

HOME.mkdir(parents=True, exist_ok=True)
prep = rc.prepare_home(HOME, [MODEL], require_login=False)
catalog = json.loads(pathlib.Path(prep["catalog"]).read_text())


def catalog_with(prefer):
    d = json.loads(json.dumps(catalog))
    for m in d["models"]:
        if prefer is not None:
            m["prefer_websockets"] = prefer
    p = OUT / f"catalog_prefer_{prefer}.json"
    p.write_text(json.dumps(d))
    return p


VARIANTS = {  # name: (provider supports_websockets, catalog prefer_websockets)
    "provider_ws_off": (False, None),
    "provider_ws_on": (True, None),
    "provider_ws_on_prefer_true": (True, True),
    "provider_ws_on_prefer_false": (True, False),
}
for name, (supports, prefer) in VARIANTS.items():
    SEEN.clear()
    p = dict(prep, catalog=str(catalog_with(prefer)))
    provider = (f'model_providers.stub={{name="stub", base_url="http://127.0.0.1:{port}/v1", wire_api="responses", '
                f'request_max_retries=0, stream_max_retries=0, supports_websockets={str(supports).lower()}}}')
    args = rc.codex_args(MODEL, "high", p, ["-c", 'model_provider="stub"', "-c", provider, "PROBE-PROMPT"])
    env = rc.codex_env(HOME)
    env["RUST_LOG"] = "codex_http_client::transport=trace,codex_api=trace,codex_core::client=trace"
    proc = subprocess.run(args, cwd=HOME / "empty_cwd", env=env, capture_output=True, text=True,
                          timeout=180, stdin=subprocess.DEVNULL)
    (OUT / f"{name}.stderr").write_text(proc.stderr)
    ws_lines = [l for l in proc.stderr.splitlines() if "websocket" in l.lower()]
    post_lines = rc.requests_sent(proc.stderr)
    print(f"== {name}: exit {proc.returncode}; stub saw {SEEN}")
    print(f"   transport POST lines: {len(post_lines)}; websocket lines: {len(ws_lines)}")
    for l in ws_lines[:6]:
        print("   ", l[:240])
srv.shutdown()
