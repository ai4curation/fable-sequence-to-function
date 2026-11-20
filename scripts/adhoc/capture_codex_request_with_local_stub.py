"""Capture the exact request `codex exec` sends, by pointing it at a local stub server. Calls no model.

Purpose: #52. `codex debug prompt-input` shows only the input list; instructions and tools can travel
as separate request fields. Here Codex is given a custom model provider whose base_url is a local
HTTP server that records each POST body and answers 500, so nothing leaves the machine. Each named
setting is run from an empty folder with an experiment-only CODEX_HOME (~/.codex is not read).
Inputs: the local Codex CLI. Outputs: .temp/codex_probe/request_<setting>.json and a summary.
Date: 2026-11-20.
"""
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / ".temp" / "codex_probe"
HOME = OUT / "home_stub"
EMPTY = OUT / "empty_cwd"
PROMPT = "PROBE-PROMPT-7f3a"
INSTR = OUT / "instructions.txt"
CAPTURED = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        CAPTURED.append({"path": self.path, "body": body.decode(errors="replace")})
        self.send_response(500)
        self.end_headers()
        self.wfile.write(b'{"error": "stub"}')

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
PROVIDER = ["-c", 'model_provider="stub"',
            "-c", f'model_providers.stub={{name="stub", base_url="http://127.0.0.1:{port}/v1", wire_api="responses", request_max_retries=0, stream_max_retries=0}}']
BASE = ["exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only", "--json", "-m", "gpt-6-astra"]
OFF = [x for f in ("shell_tool", "unified_exec", "multi_agent", "multi_agent_v2", "sleep_tool", "plugins", "skill_search",
                   "goals", "apps", "browser_use", "computer_use", "image_generation", "in_app_browser",
                   "code_mode_host", "code_mode_host_grpc", "incremental_tools", "deferred_tool_world_state")
       for x in ("--disable", f)]
CFG = ["-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0", "-c", "include_environment_context=false",
       "-c", "include_permissions_instructions=false", "-c", 'personality="none"',
       "-c", "include_skills_usage_instructions=false", "-c", "include_collaboration_mode_instructions=false",
       "-c", "include_plugin_usage_instructions=false", "-c", "include_apps_usage_instructions=false",
       "-c", "include_apps_instructions=false", "-c", "include_apply_patch_tool=false", "-c", "tools.view_image=false",
       "-c", "skills.include_instructions=false", "-c", "skills.bundled.enabled=false", "-c", "agents.max_threads=1"]
SETTINGS = {
    "user_config": ([], False),                       # ~/.codex as is, for comparison
    "isolated": (CFG + OFF, True),
    "isolated_instr": (CFG + OFF + ["-c", 'model_instructions="Answer the user\'s message."'], True),
    "isolated_instr_file": (CFG + OFF + ["-c", f'model_instructions_file="{INSTR}"'], True),
    "isolated_catalog": (CFG + OFF + ["-c", f'model_instructions_file="{INSTR}"',
                                      "-c", f'model_catalog_json="{OUT / "catalog_isolated.json"}"'], True),
}
SETTINGS["real_home_ignore_config"] = (["--ignore-user-config"] + SETTINGS["isolated_catalog"][0], False)
if len(sys.argv) > 1:
    SETTINGS = {k: v for k, v in SETTINGS.items() if k in sys.argv[1:]}

for name, (args, isolated) in SETTINGS.items():
    CAPTURED.clear()
    INSTR.write_text("Answer the user's message.")
    HOME.mkdir(parents=True, exist_ok=True)
    EMPTY.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CODEX_HOME=str(HOME)) if isolated else dict(os.environ)
    p = subprocess.run(["codex", *BASE, *PROVIDER, *args, PROMPT], cwd=EMPTY, env=env,
                       capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
    print(f"== {name}: exit {p.returncode}; {len(CAPTURED)} request(s) captured")
    if not CAPTURED:
        print("   " + (p.stderr or p.stdout).strip()[-400:])
        continue
    req = json.loads(CAPTURED[0]["body"])
    (OUT / f"request_{name}.json").write_text(json.dumps(req, indent=1))
    instr = req.get("instructions") or ""
    tools = req.get("tools") or []
    tnames = [t.get("name") or t.get("type") for t in tools]
    inp = req.get("input") or []
    print(f"   path {CAPTURED[0]['path']}; model {req.get('model')}; request {len(CAPTURED[0]['body'])} chars")
    print(f"   instructions {len(instr)} chars: {instr[:80]!r}")
    print(f"   tools {len(json.dumps(tools))} chars: {tnames}")
    for it in inp:
        if it.get("type") == "additional_tools":
            def names(t, pre=""):
                out = []
                for x in t:
                    out += names(x.get("tools", []), x["name"] + ".") if x.get("type") == "namespace" else [pre + (x.get("name") or x.get("type"))]
                return out
            print(f"   input additional_tools: {len(json.dumps(it))} chars: {names(it.get('tools', []))}")
            continue
        texts = [c.get("text", "") for c in it.get("content", []) if isinstance(c, dict)]
        print(f"   input {it.get('type')}/{it.get('role')}: " + "; ".join(f"{len(t)} chars {t[:60]!r}" for t in texts))
    agents = (pathlib.Path.home() / ".codex" / "AGENTS.md").read_text()
    marks = [l.strip() for l in agents.splitlines() if len(l.strip()) > 40][:5]
    body = CAPTURED[0]["body"]
    print(f"   ~/.codex/AGENTS.md lines found in request: {sum(m in body for m in marks)}/{len(marks)}")
    other = {k: v for k, v in req.items() if k not in ("instructions", "tools", "input")}
    print(f"   other fields: {json.dumps(other)[:300]}")
srv.shutdown()
