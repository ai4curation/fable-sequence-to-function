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
(request_user_input, view_image). Every request body Codex sends is read from its trace log and
checked for exactly that (`request_problem`); the saved session record is checked for the
instructions, effort and context blocks Codex used (`context_ok`); a reply that calls any tool is
unusable.

Usage:
    python gpt6_experiment/run_codex.py TEST MODEL --effort high [--limit N] [--workers N]
Rows go to gpt6_experiment/results/<test>/<model>-<effort>.jsonl. Codex's session records stay in the
experiment CODEX_HOME (sessions/); each row keeps the record's path and SHA-256.
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
from common import KEYS, answer, context_limit, has_tool_call, sha  # noqa: E402
from run_agy import build_questions  # noqa: E402

OUT_ROOT = HERE / "results"
DEFAULT_HOME = pathlib.Path.home() / "agent-work" / "fable-sequence-to-function" / "codex_home_gpt6"
INSTRUCTION = "Answer the user's message."
CATALOG_OVERRIDES = dict(tool_mode=None, multi_agent_version=None, experimental_supported_tools=[],
                         apply_patch_tool_type=None, input_modalities=["text"], supports_search_tool=False)
ALLOWED_TOOLS = {"request_user_input", "view_image"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")  # "ultra" is sent as "xhigh" by Codex 0.170.0 (#162)
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
    probe = home
    while not probe.exists():
        probe = probe.parent
    inside = subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if inside.returncode == 0:  # Codex would send the repository's remote and commit as request metadata (#162, #163)
        raise SystemExit(f"{home} is inside the git repository {inside.stdout.strip()}; use a home outside any repository")
    if require_login and not (home / "auth.json").exists():
        raise SystemExit(f"{home} has no login; run: CODEX_HOME={home} codex login -c cli_auth_credentials_store=\"file\"")
    (home / "empty_cwd").mkdir(parents=True, exist_ok=True)
    instr = home / "instructions.txt"
    instr.write_text(INSTRUCTION)
    p = subprocess.run(["codex", "debug", "models"], env=codex_env(home),
                       capture_output=True, text=True, timeout=120)
    catalog = json.loads(p.stdout)
    entries = catalog.get("models", catalog) if isinstance(catalog, dict) else catalog
    for m in models:
        hit = [e for e in entries if e.get("slug") == m]
        if not hit:
            raise SystemExit(f"{m} is not in the Codex model catalog for this login")
        hit[0].update(CATALOG_OVERRIDES, base_instructions=INSTRUCTION)
    cat = home / f"catalog_isolated_{'_'.join(sorted(models))}.json"  # one file per model set: runs can share a home (#162)
    cat.write_text(json.dumps(catalog))
    return dict(instructions=str(instr), catalog=str(cat), catalog_sha256=sha(cat.read_text()))


def codex_env(home: pathlib.Path) -> dict:
    """The parent environment without OPENAI_* or CODEX_* variables, so no API key or endpoint override
    from the caller can take the call off the experiment's ChatGPT login (#162)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "CODEX_", "RUST_LOG"))}
    env["CODEX_HOME"] = str(home)
    env["RUST_LOG"] = "codex_http_client::transport=trace"  # logs each request body sent (#163)
    env["NO_COLOR"] = "1"
    return env


REQUEST_LINE = re.compile(r"codex_http_client::transport: POST to (\S+): (\{.*\})\s*$")


def requests_sent(stderr: str) -> list:
    """The request bodies Codex logged as sent (URL, parsed JSON). Only the body is kept; Codex logs no
    headers on this line, and the body is checked for anything token-like before it is stored."""
    out = []
    for line in stderr.splitlines():
        m = REQUEST_LINE.search(re.sub(r"\x1b\[[0-9;]*m", "", line))
        if m:
            try:
                out.append((m.group(1), json.loads(m.group(2))))
            except json.JSONDecodeError:
                out.append((m.group(1), None))
    return out


def check_request(body, model, effort, prompt) -> str | None:
    """None if a logged request carries only the one-line instruction, the two allowed tools and the
    question, for the named model and effort; otherwise what is wrong."""
    if body is None:
        return "request body not readable"
    if body.get("model") != model:
        return f"model {body.get('model')}"
    if (body.get("reasoning") or {}).get("effort") != effort:
        return f"effort {(body.get('reasoning') or {}).get('effort')}"
    if body.get("instructions") or body.get("tools"):
        return "instructions or tools parameter set"
    developer, users, tools = [], [], []
    for it in body.get("input") or []:
        if it.get("type") == "additional_tools":
            stack = list(it.get("tools") or [])
            while stack:
                x = stack.pop()
                if x.get("type") == "namespace":
                    stack += x.get("tools") or []
                else:
                    tools.append(x.get("name") or x.get("type"))
        elif it.get("type") == "message":
            texts = [c.get("text", "") for c in it.get("content") or []]
            (developer if it.get("role") in ("developer", "system") else users).extend(texts)
        else:
            return f"input item {it.get('type')}"
    if developer != [INSTRUCTION]:
        return f"developer text {[d[:40] for d in developer]}"
    if users != [prompt]:
        return "user text other than the question"
    if not set(tools) <= ALLOWED_TOOLS:
        return f"tools {sorted(set(tools) - ALLOWED_TOOLS)}"
    if re.search(r"Bearer |eyJ[A-Za-z0-9_-]{20,}", json.dumps(body)):
        return "token-like string in the body"
    return None


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
            served.add((pl.get("thread_settings") or {}).get("model"))  # the model Codex requested, as it logs it
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
                response_ids=response_ids, requested_model_logged=sorted(x for x in served if x), session_tool_calls=tool_calls,
                session_file=str(files[0]), session_sha256=hashlib.sha256(files[0].read_bytes()).hexdigest())


def call_codex(model, effort, prompt, prep, home, extra=(), tries=3, timeout=900):
    """One question. Returns (text, row fields); text is None if no usable reply arrived.

    Each request body Codex sends is read from its HTTP-transport trace log and checked: only the one-line
    instruction, the two allowed tools and the question, for the named model and effort (#163). A row
    with no logged request is unusable. Input tokens above common.context_limit are a further, coarser
    check (#162). Codex does not log the model the server answered with: `requested_model_logged` is the
    model Codex asked for.
    """
    rec = dict(model=model, effort=effort, prompt_sha256=sha(prompt), cli_version=f"codex-exec {codex_version()}",
               catalog_sha256=prep["catalog_sha256"], instruction=INSTRUCTION, row_format=1,
               context_limit=context_limit(prompt))
    t0 = time.time()
    attempt_threads = []
    for attempt in range(1, tries + 1):
        if attempt > 1:
            time.sleep(min(10 * 2 ** (attempt - 2), 60))
        try:
            p = subprocess.run(codex_args(model, effort, prep, extra) + [prompt], cwd=home / "empty_cwd",
                               env=codex_env(home), capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            why = "timeout"
            attempt_threads.append("timeout")
            continue
        events = [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")]
        thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
        attempt_threads.append(thread)
        items = [e["item"] for e in events if e.get("type") == "item.completed" and isinstance(e.get("item"), dict)]
        messages = [i.get("text", "") for i in items if i.get("type") == "agent_message"]
        other_items = [i.get("type") for i in items if i.get("type") not in ("agent_message", "reasoning")]
        usage = next((e.get("usage") for e in events if e.get("type") == "turn.completed"), None)
        failed = [e for e in events if e.get("type") in ("turn.failed", "error")]
        if p.returncode == 0 and usage is not None and not failed:
            break
        why = (json.dumps(failed[-1]) if failed else (p.stderr or p.stdout)[-400:]) or f"exit {p.returncode}"
    else:
        return None, dict(rec, attempts=attempt, attempt_threads=attempt_threads, error=why,
                          duration_seconds=round(time.time() - t0, 3),
                          asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    session = read_session(home, thread, prompt, effort) if thread else dict(context_ok=False, context_problem="no thread id")
    text = messages[-1] if messages else ""
    sent = requests_sent(p.stderr)
    request_problems = [check_request(b, model, effort, prompt) for _, b in sent]
    if thread:  # keep the bodies for inspection, in the experiment home (not in the repository)
        (home / "requests").mkdir(exist_ok=True)
        for i, (_, b) in enumerate(sent):
            if b is not None and not check_request(b, model, effort, prompt) == "token-like string in the body":
                (home / "requests" / f"{thread}_{i}.json").write_text(json.dumps(b, indent=1))
    rec.update(requests_logged=len(sent), request_hosts=sorted({u.split("/")[2] for u, _ in sent if "//" in u}),
               request_sha256=[sha(json.dumps(b, sort_keys=True)) for _, b in sent if b is not None],
               request_problem=next((x for x in request_problems if x), None) if sent else "no request logged")
    rec.update(attempts=attempt, attempt_threads=attempt_threads, duration_seconds=round(time.time() - t0, 3),
               asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               thread_id=thread, event_types=[e.get("type") for e in events], tool_items=other_items,
               stderr_tail="\n".join(l for l in (p.stderr or "").splitlines() if "codex_http_client::transport" not in l)[-300:] or None,
               num_turns=len(session.get("response_ids") or []) or None,
               input_tokens=usage.get("input_tokens"), cached_input_tokens=usage.get("cached_input_tokens"),
               output_tokens=usage.get("output_tokens"), thinking_tokens=usage.get("reasoning_output_tokens"),
               thinking=usage.get("reasoning_output_tokens"), **session)
    rec["usage_unreadable"] = not isinstance(rec["input_tokens"], int)
    rec["context_tokens_high"] = not rec["usage_unreadable"] and rec["input_tokens"] > rec["context_limit"]
    problems = [name for name, bad in (
        ("request check", rec["request_problem"] is not None), ("usage unreadable", rec["usage_unreadable"]),
        ("context check", not rec["context_ok"]), ("tool or warning items", bool(other_items)),
        ("tool call in session", bool(session.get("session_tool_calls"))), ("not one agent message", len(messages) != 1),
        ("empty reply", not text.strip()), ("not one model response", rec["num_turns"] != 1),
        ("other model requested", rec.get("requested_model_logged") != [model]),
        ("input tokens above the context limit", rec["context_tokens_high"])) if bad]
    rec.update(status="UNUSABLE" if problems else "SUCCESS", unusable_because=problems or None)
    return text, rec


def codex_unusable(row: dict) -> bool:
    return "error" in row or row.get("status") != "SUCCESS"


def build_row(test, meta, text, rec):
    """The stored row for one question, in the same layout as the Gemini rows, so that
    gemini_experiment/score_gemini.py and audit.py read it unchanged."""
    if text is None:
        return dict(meta, **rec)
    if test == "next_residue":
        cands = re.findall(r"[ACDEFGHIKLMNPQRSTVWY]{5,}", text.replace(" ", ""))
        pred = cands[-1] if cands else ""
        valid = bool(pred) and not has_tool_call(text)
        return dict(meta, text=text, pred=pred, valid=valid, first_correct=valid and pred[0] == meta["target"][0],
                    exact10=valid and pred[:10] == meta["target"], **rec)
    return dict(meta, text=text, ans=answer(text, KEYS[test]), **rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["next_residue", "features", "pseudo", "structure"])
    ap.add_argument("model", choices=["gpt-6-astra", "gpt-rosalind-astra"])
    ap.add_argument("--effort", choices=EFFORTS, default="high")
    ap.add_argument("--home", type=pathlib.Path, default=DEFAULT_HOME)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ncond", type=int, default=2)
    ap.add_argument("--retry-unusable", action="store_true",
                    help="ask again questions whose stored row is unusable (default: any stored row counts as asked, "
                         "so a systematic failure is not billed again on every rerun)")
    args = ap.parse_args()

    prep = prepare_home(args.home, [args.model])
    out_dir = OUT_ROOT / args.test
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}-{args.effort}"
    out_path = out_dir / f"{tag}.jsonl"
    qs, key_fn = build_questions(args.test, tag, args.ncond)
    done = set()
    if out_path.exists():
        rows = [json.loads(l) for l in out_path.read_text().splitlines() if l.strip()]
        done = {key_fn(r) for r in rows if not (args.retry_unusable and codex_unusable(r))}
    todo = [q for q in qs if q[0] not in done][: args.limit]
    print(f"[{args.test}] {tag}: {len(qs)} total, {len(done)} done, {len(todo)} to run", flush=True)

    def ask_one(item):
        _, prompt, meta = item
        try:  # one bad call, or a bad reply, must not stop the batch (#162, #163)
            text, rec = call_codex(args.model, args.effort, prompt, prep, args.home)
            return build_row(args.test, meta, text, rec)
        except Exception as e:
            return dict(meta, model=args.model, effort=args.effort, prompt_sha256=sha(prompt), error=f"runner: {e!r}"[:400])

    with ThreadPoolExecutor(args.workers) as ex, out_path.open("a") as fh:
        futs = [ex.submit(ask_one, item) for item in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            flag = "" if not codex_unusable(row) else f" UNUSABLE ({row.get('error') or row.get('unusable_because')})"
            print(f"  [{args.test}] {tag}: {i}/{len(todo)} input_tokens={row.get('input_tokens')}{flag}", flush=True)


if __name__ == "__main__":
    main()
