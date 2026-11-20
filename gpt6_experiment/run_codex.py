"""Ask GPT-6 models the four tests through `codex exec`, with Codex's own context stripped (#52).

Only for this experiment, and without touching ~/.codex:
- an experiment-only CODEX_HOME (default ~/agent-work/fable-sequence-to-function/codex_home_gpt6)
  with its own ChatGPT login, so the user's AGENTS.md, config, skills and plugins are never read;
- a one-line instruction file in place of Codex's built-in instructions (model_instructions_file);
- a copy of Codex's model catalog in which the target model has no code-mode tools, no multi-agent
  mode, no patch tool and text-only input (model_catalog_json; see CATALOG_OVERRIDES);
- command-line settings turning off web search, project docs, environment context, personality,
  skills, plugins, apps and agent tools; a read-only sandbox; an empty working folder.
What still reaches the model besides the question: the instruction line and two tool definitions
(request_user_input, view_image). Every call's saved session record is checked for exactly that
(`context_ok`), and a reply that calls any tool is unusable.

Usage:
    python gpt6_experiment/run_codex.py TEST MODEL --effort high [--limit N] [--workers N]
Rows go to gpt6_experiment/results/<test>/<model>-<effort>.jsonl, session records beside them.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "gemini_experiment"))
from common import KEYS, answer, has_tool_call, sha  # noqa: E402
from run_agy import build_questions  # noqa: E402

OUT_ROOT = HERE / "results"
DEFAULT_HOME = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function" / "codex_home_gpt6"
INSTRUCTION = "Answer the user's message."
CATALOG_OVERRIDES = dict(tool_mode=None, multi_agent_version=None, experimental_supported_tools=[],
                         apply_patch_tool_type=None, input_modalities=["text"])
FEATURES_OFF = ("shell_tool", "unified_exec", "multi_agent", "multi_agent_v2", "sleep_tool", "plugins",
                "skill_search", "goals", "apps", "browser_use", "computer_use", "image_generation",
                "in_app_browser", "code_mode_host", "code_mode_host_grpc", "incremental_tools",
                "deferred_tool_world_state")
SETTINGS = ('web_search="disabled"', "project_doc_max_bytes=0", "include_environment_context=false",
            "include_permissions_instructions=false", 'personality="none"',
            "include_collaboration_mode_instructions=false",
            "include_apps_instructions=false", "skills.include_instructions=false", "skills.bundled.enabled=false", "agents.max_threads=1",
            'cli_auth_credentials_store="file"')  # Codex 0.170.0 recognises every one of these (no warnings)


def codex_version() -> str:
    return subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()


def prepare_home(home: pathlib.Path, models, require_login=True) -> dict:
    """Write the instruction file and the experiment catalog into `home`; return their paths and hashes."""
    if require_login and not (home / "auth.json").exists():
        raise SystemExit(f"{home} has no login; run: CODEX_HOME={home} codex login -c cli_auth_credentials_store=\"file\"")
    (home / "empty_cwd").mkdir(exist_ok=True)
    instr = home / "instructions.txt"
    instr.write_text(INSTRUCTION)
    p = subprocess.run(["codex", "debug", "models"], env=dict(os.environ, CODEX_HOME=str(home)),
                       capture_output=True, text=True, timeout=120)
    catalog = json.loads(p.stdout)
    entries = catalog.get("models", catalog) if isinstance(catalog, dict) else catalog
    for m in models:
        hit = [e for e in entries if e.get("slug") == m]
        if not hit:
            raise SystemExit(f"{m} is not in the Codex model catalog for this login")
        hit[0].update(CATALOG_OVERRIDES, base_instructions=INSTRUCTION)
    cat = home / "catalog_isolated.json"
    cat.write_text(json.dumps(catalog))
    return dict(instructions=str(instr), catalog=str(cat), catalog_sha256=sha(cat.read_text()))


def codex_args(model: str, effort: str, prep: dict, extra=()) -> list:
    args = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "--json", "-m", model,
            "-c", f'model_reasoning_effort="{effort}"',
            "-c", f'model_instructions_file="{prep["instructions"]}"', "-c", f'model_catalog_json="{prep["catalog"]}"']
    for s in SETTINGS:
        args += ["-c", s]
    for f in FEATURES_OFF:
        args += ["--disable", f]
    return args + list(extra)


def read_session(home: pathlib.Path, thread_id: str, prompt: str, effort: str) -> dict:
    """What the saved session record shows about the call, and whether its context is as intended.

    Codex records the instructions it used (session_meta.base_instructions), which instruction blocks
    were included (world_state), the effort, multi-agent mode and sandbox (turn_context), any extra
    context messages, every tool call and every response id. It does not record the tool list; the
    stub test checks that on the request itself, and the input-token count shows it on real calls.
    """
    files = sorted((home / "sessions").rglob(f"rollout-*-{thread_id}.jsonl"))
    if not files:
        return dict(context_ok=False, context_problem="no session record")
    lines = [json.loads(l) for l in files[0].read_text().splitlines() if l.strip()]
    meta, world, turn = {}, {}, {}
    extra_context, response_ids, served, tool_calls = [], [], set(), []
    for e in lines:
        t, pl = e.get("type"), e.get("payload") or {}
        if t == "session_meta":
            meta = pl
        elif t == "world_state":
            world = pl.get("state") or {}
        elif t == "turn_context":
            turn = pl
        elif t == "response_item":
            if pl.get("type") == "additional_tools":
                extra_context.append("additional_tools item")
            elif pl.get("type") == "message" and pl.get("role") in ("developer", "system"):
                extra_context += [c.get("text", "")[:60] for c in pl.get("content", [])]
            elif pl.get("type") == "message" and pl.get("role") == "user":
                texts = [c.get("text", "") for c in pl.get("content", [])]
                if texts != [prompt]:
                    extra_context += [x[:60] for x in texts]
            elif pl.get("type") in ("function_call", "custom_tool_call", "local_shell_call", "web_search_call"):
                tool_calls.append(pl.get("name") or pl.get("type"))
        elif t == "token_usage_record" and pl.get("response_id"):
            response_ids.append(pl["response_id"])
        elif t == "event_msg" and pl.get("type") == "thread_settings_applied":
            served.add((pl.get("thread_settings") or {}).get("model"))
    checks = {
        "instructions are the one line": (meta.get("base_instructions") or {}).get("text") == INSTRUCTION,
        "no AGENTS.md": not world.get("agents_md"),
        "no skills, plugin or app instructions": not ((world.get("skills") or {}).get("includeInstructions")
                                                      or (world.get("host_skills") or {}).get("includeInstructions")
                                                      or world.get("plugins_instructions") or world.get("apps_instructions")),
        "effort as requested": turn.get("effort") == effort,
        "multi-agent disabled": turn.get("multi_agent_version") == "disabled",
        "read-only sandbox": (turn.get("sandbox_policy") or {}).get("type") == "read-only",
        "no extra context messages": not extra_context,
    }
    failed = [k for k, v in checks.items() if not v]
    return dict(context_ok=not failed, context_problem="; ".join(failed) or None, extra_context=extra_context,
                response_ids=response_ids, served=sorted(x for x in served if x), session_tool_calls=tool_calls,
                session_file=str(files[0]), session_sha256=hashlib.sha256(files[0].read_bytes()).hexdigest())


def call_codex(model, effort, prompt, prep, home, extra=(), tries=3, timeout=900):
    rec = dict(model=model, effort=effort, prompt_sha256=sha(prompt), cli_version=f"codex-exec {codex_version()}",
               catalog_sha256=prep["catalog_sha256"], instruction=INSTRUCTION, row_format=1)
    t0 = time.time()
    for attempt in range(1, tries + 1):
        try:
            p = subprocess.run(codex_args(model, effort, prep, extra) + [prompt], cwd=home / "empty_cwd",
                               env=dict(os.environ, CODEX_HOME=str(home)), capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            why = "timeout"
            continue
        events = [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")]
        thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
        items = [e["item"] for e in events if e.get("type") == "item.completed" and isinstance(e.get("item"), dict)]
        messages = [i.get("text", "") for i in items if i.get("type") == "agent_message"]
        other_items = [i.get("type") for i in items if i.get("type") not in ("agent_message", "reasoning")]
        usage = next((e.get("usage") for e in events if e.get("type") == "turn.completed"), None)
        failed = [e for e in events if e.get("type") in ("turn.failed", "error")]
        if p.returncode == 0 and usage is not None and not failed:
            break
        why = (json.dumps(failed[-1]) if failed else (p.stderr or p.stdout)[-400:]) or f"exit {p.returncode}"
    else:
        return None, dict(rec, attempts=attempt, duration_seconds=round(time.time() - t0, 3), error=why,
                          asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    session = read_session(home, thread, prompt, effort) if thread else dict(context_ok=False, context_problem="no thread id")
    text = messages[-1] if messages else ""
    rec.update(attempts=attempt, duration_seconds=round(time.time() - t0, 3),
               asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               thread_id=thread, event_types=[e.get("type") for e in events], tool_items=other_items,
               num_turns=len(session.get("response_ids") or []) or None,
               input_tokens=usage.get("input_tokens"), cached_input_tokens=usage.get("cached_input_tokens"),
               output_tokens=usage.get("output_tokens"), thinking_tokens=usage.get("reasoning_output_tokens"),
               thinking=usage.get("reasoning_output_tokens"), **session)
    ok = (rec["context_ok"] and not other_items and not session.get("session_tool_calls")
          and len(messages) == 1 and rec["num_turns"] == 1 and served_ok(rec, model))
    rec.update(status="SUCCESS" if ok else "UNUSABLE", finish_reason="STOP" if ok else None)
    return text, rec


def served_ok(rec, model):
    return rec.get("served") == [model]


def codex_unusable(row: dict) -> bool:
    return "error" in row or row.get("status") != "SUCCESS"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["next_residue", "features", "pseudo", "structure"])
    ap.add_argument("model", choices=["gpt-6-astra", "gpt-rosalind-astra"])
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max", "ultra"], default="high")
    ap.add_argument("--home", type=pathlib.Path, default=DEFAULT_HOME)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ncond", type=int, default=2)
    args = ap.parse_args()

    prep = prepare_home(args.home, [args.model])
    out_dir = OUT_ROOT / args.test
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}-{args.effort}"
    out_path = out_dir / f"{tag}.jsonl"
    qs, key_fn = build_questions(args.test, tag, args.ncond)
    done = set()
    if out_path.exists():
        done = {key_fn(r) for r in map(json.loads, out_path.read_text().splitlines()) if not codex_unusable(r)}
    todo = [q for q in qs if q[0] not in done][: args.limit]
    print(f"[{args.test}] {tag}: {len(qs)} total, {len(done)} done, {len(todo)} to run", flush=True)

    def ask_one(item):
        _, prompt, meta = item
        text, rec = call_codex(args.model, args.effort, prompt, prep, args.home)
        if text is None:
            return dict(meta, **rec)
        if args.test == "next_residue":
            cands = re.findall(r"[ACDEFGHIKLMNPQRSTVWY]{5,}", text.replace(" ", ""))
            pred = cands[-1] if cands else ""
            valid = bool(pred) and not has_tool_call(text)
            return dict(meta, text=text, pred=pred, valid=valid, first_correct=valid and pred[0] == meta["target"][0],
                        exact10=valid and pred[:10] == meta["target"], **rec)
        return dict(meta, text=text, ans=answer(text, KEYS[args.test]), **rec)

    with ThreadPoolExecutor(args.workers) as ex, out_path.open("a") as fh:
        futs = [ex.submit(ask_one, item) for item in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            flag = "" if not codex_unusable(row) else f" UNUSABLE ({row.get('error') or row.get('context_problem') or row.get('tool_items')})"
            print(f"  [{args.test}] {tag}: {i}/{len(todo)} input_tokens={row.get('input_tokens')}{flag}", flush=True)


if __name__ == "__main__":
    main()
