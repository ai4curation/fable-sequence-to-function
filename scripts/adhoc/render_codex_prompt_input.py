"""Render what Codex would send the model, without calling a model, under several isolation settings.

Purpose: #52 (GPT-6 through `codex exec`). `codex debug prompt-input` prints the model-visible input
list as JSON. This runs it from an empty folder for each named setting and summarises each item
(type, role, size, and whether it contains text from the user's ~/.codex/AGENTS.md or config).
Inputs: the local Codex CLI and ~/.codex. No network model call is made by `codex debug`.
Outputs: .temp/codex_probe/<setting>.json (raw) and a summary on stdout.
Date: 2026-11-20.
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / ".temp" / "codex_probe"
EMPTY = OUT / "empty_cwd"
PROMPT = "PROBE-PROMPT-7f3a"
AGENTS = (pathlib.Path.home() / ".codex" / "AGENTS.md").read_text()
# a few distinctive lines of the user's AGENTS.md, to detect it in the rendered input
MARKERS = [l.strip() for l in AGENTS.splitlines() if len(l.strip()) > 40][:5]

HOME = OUT / "home_empty"  # an empty CODEX_HOME: no config.toml, AGENTS.md, skills or plugins
HOME.mkdir(parents=True, exist_ok=True)
INSTR = OUT / "instructions.txt"
INSTR.write_text("Answer the user's message.")
OFF = [x for f in ("shell_tool", "unified_exec", "multi_agent", "sleep_tool", "plugins", "skill_search",
                   "goals", "apps", "browser_use", "computer_use", "image_generation", "in_app_browser")
       for x in ("--disable", f)]
CFG = ["-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
       "-c", "include_environment_context=false", "-c", "include_permissions_instructions=false"]
SETTINGS = {
    "default": ([], {}),
    "empty_home": ([], {"CODEX_HOME": str(HOME)}),
    "empty_home_cfg": (CFG, {"CODEX_HOME": str(HOME)}),
    "empty_home_cfg_off": (CFG + OFF, {"CODEX_HOME": str(HOME)}),
    "empty_home_cfg_off_instr": (CFG + OFF + ["-c", f'base_instructions="{INSTR.read_text()}"'], {"CODEX_HOME": str(HOME)}),
    "min": (CFG + OFF + ["-c", 'personality="none"', "-c", "include_skills_usage_instructions=false",
                         "-c", "skills.enabled=false", "-c", "include_apply_patch_tool=false",
                         "-c", "tools.view_image=false"], {"CODEX_HOME": str(HOME)}),
}
SKILLS = sorted((HOME / "skills" / ".system").glob("*/SKILL.md"))
SKILL_OFF = "[" + ", ".join(f'{{path="{x}", enabled=false}}' for x in SKILLS) + "]"
SETTINGS["min_no_skills"] = (SETTINGS["min"][0] + ["-c", f"skills.config={SKILL_OFF}"], {"CODEX_HOME": str(HOME)})
EXTRA = ["-c", "include_collaboration_mode_instructions=false", "-c", "include_plugin_usage_instructions=false",
         "-c", "include_apps_usage_instructions=false", "-c", "include_apps_instructions=false",
         "-c", f'model_instructions_file="{INSTR}"', "-c", 'model_instructions="Answer the user\'s message."',
         "-c", "experimental_supported_tools=[]", "--disable", "multi_agent_v2"]
SETTINGS["min_extra"] = (SETTINGS["min_no_skills"][0] + EXTRA, {"CODEX_HOME": str(HOME)})
TRY = ["-c", "skills.include_instructions=false", "-c", "skills.bundled.enabled=false",
       "-c", "agents.enabled=false", "-c", "agents.max_threads=1",
       "--disable", "code_mode_host", "--disable", "code_mode_host_grpc", "--disable", "incremental_tools",
       "--disable", "deferred_tool_world_state"]
SETTINGS["min_try"] = (SETTINGS["min_extra"][0] + TRY, {"CODEX_HOME": str(HOME)})
if len(sys.argv) > 1:
    SETTINGS = {k: v for k, v in SETTINGS.items() if k in sys.argv[1:]}


def run(name, args, env_extra):
    EMPTY.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, **env_extra)
    p = subprocess.run(["codex", "debug", "prompt-input", *args, PROMPT], cwd=EMPTY, env=env,
                       capture_output=True, text=True, timeout=180)
    (OUT / f"{name}.json").write_text(p.stdout)
    (OUT / f"{name}.err").write_text(p.stderr)
    print(f"== {name}: exit {p.returncode}, {len(p.stdout)} chars of JSON, stderr {len(p.stderr)} chars")
    if p.returncode:
        print("   " + p.stderr.strip()[:400])
        return
    data = json.loads(p.stdout)
    items = data if isinstance(data, list) else data.get("input", data)
    for i, it in enumerate(items):
        s = json.dumps(it)
        hits = sum(m in s for m in MARKERS)
        print(f"   [{i}] type={it.get('type')} role={it.get('role')} chars={len(s)} agents_md_markers={hits}/{len(MARKERS)} prompt={'yes' if PROMPT in s else 'no'}")
        texts = [c.get("text", "") for c in it.get("content", []) if isinstance(c, dict)]
        for t in texts:
            print(f"        text {len(t)} chars: " + t[:90].replace("\n", " "))


for name, (args, env_extra) in SETTINGS.items():
    run(name, args, env_extra)
