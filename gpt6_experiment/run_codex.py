"""Ask GPT-6 models the four tests through `codex exec`, with Codex's own context stripped (#52).

Only for this experiment, and without touching ~/.codex:
- an experiment-only CODEX_HOME (default ~/agent-work/fable-sequence-to-function/codex_home_gpt6)
  with its own ChatGPT login, so the user's AGENTS.md, config, skills and plugins are never read;
- a one-line instruction file in place of Codex's built-in instructions (model_instructions_file);
- a copy of Codex's model catalog in which the target model has no code-mode tools, no multi-agent
  mode, no patch tool and text-only input (model_catalog_json; see CATALOG_OVERRIDES);
- command-line settings turning off web search, project docs, environment context, personality,
  skills, plugins, apps and agent tools; a read-only sandbox; an empty working folder.
- its own model provider: the same ChatGPT login over plain HTTP, never a websocket, so each request
  body is in Codex's transport log (#164).
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
import signal
import subprocess
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "gemini_experiment"))
from common import KEYS, answer, context_limit, has_tool_call, sha  # noqa: E402
from run_agy import agy_unusable, build_questions  # noqa: E402

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
# The experiment's own model provider (#164). With a ChatGPT login the built-in `openai` provider sends
# the request over a Responses WebSocket, whose body is not in the HTTP transport log; built-in provider
# IDs cannot be overridden. This provider uses the same login over plain HTTP, so every request body is
# logged and checked. The stub test overrides only the base URL (and, for one check, websockets).
PROVIDER_ID = "fs2f_chatgpt_http"
CHATGPT_BASE_URL = "https://chatgpt.com/backend-api/codex"
WEBSOCKET_TARGET = "codex_api::endpoint::responses_websocket"


def provider_args(base_url: str, supports_websockets: bool = False) -> list:
    # Codex's own retries are off: by default it reconnects a dropped stream up to five times and sends
    # the question again each time, even after the model has replied (#168)
    fields = [f'name="{PROVIDER_ID}"', f'base_url="{base_url}"', 'wire_api="responses"', "requires_openai_auth=true",
              f"supports_websockets={str(supports_websockets).lower()}", "request_max_retries=0", "stream_max_retries=0"]
    return ["-c", f'model_provider="{PROVIDER_ID}"', "-c", f"model_providers.{PROVIDER_ID}={{{', '.join(fields)}}}"]


def codex_version() -> str:
    return subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()


def prepare_home(home: pathlib.Path, models, require_login=True, base_url=CHATGPT_BASE_URL,
                 supports_websockets=False) -> dict:
    """Write the instruction file and the experiment catalog into `home`; return their paths and hashes,
    and the provider settings every call from this home uses."""
    if (home / "auth.json").exists() and base_url != CHATGPT_BASE_URL:  # the login goes wherever the provider points (#164)
        raise SystemExit(f"{home} holds a login; refusing to send it to {base_url}")
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
    return dict(instructions=str(instr), catalog=str(cat), catalog_sha256=sha(cat.read_text()),
                base_url=base_url, provider=provider_args(base_url, supports_websockets))


def codex_env(home: pathlib.Path) -> dict:
    """The parent environment without OPENAI_* or CODEX_* variables, so no API key or endpoint override
    from the caller can take the call off the experiment's ChatGPT login (#162)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "CODEX_", "RUST_LOG"))}
    env["CODEX_HOME"] = str(home)
    # each HTTP request body sent (#163), and any use of a Responses WebSocket (#164)
    env["RUST_LOG"] = f"codex_http_client::transport=trace,{WEBSOCKET_TARGET}=info"
    env["NO_COLOR"] = "1"
    return env


TIMEOUT = 1800  # seconds; Rosalind took 509 s and 578 s on one test-4 question at high effort (#166)
TOKEN_LIKE = re.compile(r"Bearer \S+|eyJ[A-Za-z0-9_-]{20,}[A-Za-z0-9._-]*|sk-[A-Za-z0-9_-]{16,}|rt_[A-Za-z0-9._-]{16,}")  # #178


def masked(text, cap=400) -> str:
    """Text for a row field: anything token-like masked first, then capped (#170, #178)."""
    return TOKEN_LIKE.sub("[token-like]", text or "")[:cap]
LOGIN_ERROR = re.compile(r"access token|refresh token|sign in again|log ?in again|not logged in|401 Unauthorized", re.I)
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
    question, for the named model and effort; otherwise what is wrong. Never raises (#177)."""
    try:
        return _check_request(body, model, effort, prompt)
    except Exception as e:
        return f"request body not checkable: {type(e).__name__}"


def _check_request(body, model, effort, prompt) -> str | None:
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
            "-c", f'model_instructions_file="{prep["instructions"]}"', "-c", f'model_catalog_json="{prep["catalog"]}"',
            *prep["provider"]]
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


def plain_stderr(stderr) -> str:
    """stderr without the request-body trace lines and websocket lines, with anything token-like masked (#170)."""
    return TOKEN_LIKE.sub("[token-like]", "\n".join(
        l for l in (stderr or "").splitlines() if "codex_http_client::transport" not in l and WEBSOCKET_TARGET not in l))


def parse_events(stdout) -> tuple:
    """Codex's JSON events, skipping lines that do not parse; returns (events, number of unparsable lines) (#171)."""
    events, bad = [], 0
    for line in (stdout or "").splitlines():
        if line.strip().startswith("{"):
            try:
                e = json.loads(line)
                events.append(e if isinstance(e, dict) else {})
            except json.JSONDecodeError:
                bad += 1
    return events, bad


def keep_attempt(home, thread, stdout, stderr, model, effort, prompt) -> dict:
    """Save one attempt's evidence in the experiment home (not the repository): Codex's JSON event stream,
    its stderr without the trace lines, and each logged request body; return the request summary (#166)."""
    d = home / "attempts"
    d.mkdir(exist_ok=True)
    name = thread or f"no-thread-{time.time_ns()}"
    (d / f"{name}_events.jsonl").write_text(TOKEN_LIKE.sub("[token-like]", stdout or ""))
    (d / f"{name}_stderr.txt").write_text(plain_stderr(stderr))
    sent = requests_sent(stderr or "")
    problems = [check_request(b, model, effort, prompt) for _, b in sent]
    for i, (_, b) in enumerate(sent):
        if b is not None:  # always masked, whatever the check found first (#170)
            (d / f"{name}_request_{i}.json").write_text(TOKEN_LIKE.sub("[token-like]", json.dumps(b, indent=1)))
    return dict(requests_logged=len(sent), request_problem=next((x for x in problems if x), None) if sent else "no request logged",
                websocket_log_lines=sum(WEBSOCKET_TARGET in l for l in (stderr or "").splitlines()))


def call_codex(model, effort, prompt, prep, home, extra=(), tries=3, timeout=TIMEOUT, stop=None):
    """One question. Returns (text, row fields); text is None if no usable reply arrived.

    Each request body Codex sends is read from its HTTP-transport trace log and checked: only the one-line
    instruction, the two allowed tools and the question, for the named model and effort (#163). A row
    with no logged request is unusable. Input tokens above common.context_limit are a further, coarser
    check (#162). Codex does not log the model the server answered with: `requested_model_logged` is the
    model Codex asked for.
    """
    rec = dict(model=model, effort=effort, prompt_sha256=sha(prompt), cli_version=f"codex-exec {codex_version()}",
               catalog_sha256=prep["catalog_sha256"], instruction=INSTRUCTION, row_format=1,
               codex_row_format=2,  # every attempt recorded, no retry after a reply (#166); earlier rows do not count
               context_limit=context_limit(prompt), provider=PROVIDER_ID, base_url=prep["base_url"])
    t0 = time.time()
    attempt_threads, attempt_log = [], []

    def stamp():
        return dict(attempts=len(attempt_log), attempt_threads=attempt_threads, attempt_log=attempt_log,
                    duration_seconds=round(time.time() - t0, 3),
                    asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))

    login = False
    for attempt in range(1, tries + 1):
        if attempt > 1:
            if stop is not None and stop.is_set():  # nothing new after Ctrl-C or a login error (#175)
                return None, dict(rec, error="stopped before a retry", **stamp())
            time.sleep(min(10 * 2 ** (attempt - 2), 60))
            if stop is not None and stop.is_set():
                return None, dict(rec, error="stopped before a retry", **stamp())
        timed_out = False
        try:  # own session: a terminal Ctrl-C reaches only the runner, and running calls finish (#175)
            p = subprocess.run(codex_args(model, effort, prep, extra) + [prompt], cwd=home / "empty_cwd",
                               env=codex_env(home), capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL, start_new_session=True)
        except subprocess.TimeoutExpired as e:  # handled like any failed attempt: reply kept, never retried (#166, #176)
            timed_out = True
            p = types.SimpleNamespace(
                stdout=e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or ""),
                returncode=None)
        events, unparsable = parse_events(p.stdout)
        thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
        attempt_threads.append(thread)
        try:  # before anything else can fail (#171, #177)
            kept = keep_attempt(home, thread, p.stdout, p.stderr, model, effort, prompt)
        except Exception as e:
            kept = dict(requests_logged=None, request_problem=f"attempt evidence not saved: {type(e).__name__}",
                        websocket_log_lines=None, evidence_error=masked(repr(e)))
        items = [e["item"] for e in events if e.get("type") == "item.completed" and isinstance(e.get("item"), dict)]
        messages = [i.get("text", "") for i in items if i.get("type") == "agent_message"]
        other_items = [i.get("type") for i in items if i.get("type") not in ("agent_message", "reasoning")]
        usage = next((e.get("usage") for e in events if e.get("type") == "turn.completed"), None)
        failed = [e for e in events if e.get("type") in ("turn.failed", "error")]
        why = None
        if timed_out:
            why = f"timeout after {timeout} s"
        elif not (p.returncode == 0 and usage is not None and not failed and not unparsable):
            why = (masked(json.dumps(failed[-1])) if failed
                   else f"{unparsable} unparsable output lines" if unparsable
                   else masked(plain_stderr(p.stderr)[-400:]) or f"exit {p.returncode}")
        try:
            session_responses = bool(thread and read_session(home, thread, prompt, effort).get("response_ids"))
        except Exception:
            session_responses = True  # unreadable: assume the model may have answered
        # Any sign that the question may have reached the model: then never ask again here (#166, #169, #179).
        # A turn start comes before the request in every observed stream, so it counts even if the trace log fails.
        reached = bool(timed_out or kept["requests_logged"] is None or kept["requests_logged"] or kept["websocket_log_lines"]
                       or any(e.get("type") == "turn.started" for e in events)
                       or items or messages or usage is not None or session_responses or unparsable)
        attempt_log.append(dict(thread=thread, outcome="ok" if why is None else "timeout" if timed_out else
                                ("failed after the request may have been sent" if reached else "failed before any request"),
                                exit=p.returncode, failure=why, unparsable_lines=unparsable, **kept))
        if why is None:
            break
        login = bool(LOGIN_ERROR.search(why))  # will not fix itself: main stops the run (#165)
        if reached:  # keep whatever arrived, unusable; re-asking is left to --retry-unusable (#166, #169, #172)
            break
        if login:
            return None, dict(rec, error=why, login_error=True, **stamp())
    else:
        return None, dict(rec, error=why, **stamp())
    usage = usage or {}  # a reply can arrive without token counts when the turn then fails (#166)
    try:
        session = read_session(home, thread, prompt, effort) if thread else dict(context_ok=False, context_problem="no thread id")
    except Exception as e:  # never lose the reply to an unreadable session record (#171)
        session = dict(context_ok=False, context_problem=f"session record unreadable: {e!r}"[:200])
    text = messages[-1] if messages else ""
    sent = requests_sent(p.stderr)
    request_problems = [check_request(b, model, effort, prompt) for _, b in sent]
    expected_host = prep["base_url"].split("/")[2]
    hosts = sorted({u.split("/")[2] for u, _ in sent if "//" in u})
    websocket_lines = sum(WEBSOCKET_TARGET in l for l in (p.stderr or "").splitlines())
    n_responses = len(session.get("response_ids") or [])
    problem = next((x for x in request_problems if x), None) if sent else "no request logged"
    if problem is None and websocket_lines:
        problem = "websocket used"  # its body is not logged (#164)
    if problem is None and hosts != [expected_host]:
        problem = f"request hosts {hosts}, expected {expected_host}"
    if problem is None and len(sent) != n_responses:
        problem = f"{len(sent)} requests logged for {n_responses} responses"
    rec.update(websocket_log_lines=websocket_lines,
               requests_logged=len(sent), request_hosts=hosts,
               request_sha256=[sha(json.dumps(b, sort_keys=True)) for _, b in sent if b is not None],
               request_problem=problem)
    if login:
        rec["login_error"] = True
    rec.update(**stamp(), attempt_failure=why, thread_id=thread, event_types=[e.get("type") for e in events], tool_items=other_items,
               stderr_tail=plain_stderr(p.stderr)[-300:] or None,
               num_turns=len(session.get("response_ids") or []) or None,
               input_tokens=usage.get("input_tokens"), cached_input_tokens=usage.get("cached_input_tokens"),
               output_tokens=usage.get("output_tokens"), thinking_tokens=usage.get("reasoning_output_tokens"),
               thinking=usage.get("reasoning_output_tokens"), **session)
    rec["usage_unreadable"] = not isinstance(rec["input_tokens"], int)
    rec["context_tokens_high"] = not rec["usage_unreadable"] and rec["input_tokens"] > rec["context_limit"]
    problems = [name for name, bad in (
        ("request check", rec["request_problem"] is not None), ("usage unreadable", rec["usage_unreadable"]),
        ("attempt failed after the request may have been sent", why is not None),
        ("an earlier attempt sent a request", any(a.get("requests_logged") or a.get("websocket_log_lines") for a in attempt_log[:-1])),
        ("context check", not rec["context_ok"]), ("tool or warning items", bool(other_items)),
        ("tool call in session", bool(session.get("session_tool_calls"))), ("not one agent message", len(messages) != 1),
        ("empty reply", not text.strip()), ("not one model response", rec["num_turns"] != 1),
        ("other model requested", rec.get("requested_model_logged") != [model]),
        ("input tokens above the context limit", rec["context_tokens_high"])) if bad]
    rec.update(status="UNUSABLE" if problems else "SUCCESS", unusable_because=problems or None)
    return text, rec


def codex_unusable(row: dict) -> bool:
    return agy_unusable(row)  # one rule with the scorer and audit, which also drop rows before codex_row_format 2 (#166)


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
    if sys.platform == "darwin":  # sleep stalls a call, and the timeout does not count time asleep (#166)
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], start_new_session=True)  # survives Ctrl-C (#175)
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

    stop = threading.Event()  # set on a login error or Ctrl-C: no new question is started after it (#173)

    def ask_one(item):
        _, prompt, meta = item
        if stop.is_set():
            return None
        try:  # one bad call, or a bad reply, must not stop the batch (#162, #163)
            text, rec = call_codex(args.model, args.effort, prompt, prep, args.home, stop=stop)
            if rec.get("login_error"):
                stop.set()  # in the worker, before it can take the next question (#173)
            return build_row(args.test, meta, text, rec)
        except Exception as e:
            return dict(meta, model=args.model, effort=args.effort, prompt_sha256=sha(prompt), error=f"runner: {e!r}"[:400])

    ex = ThreadPoolExecutor(args.workers)
    futs = [ex.submit(ask_one, item) for item in todo]
    written = set()
    login_failed = interrupted = False
    with out_path.open("a") as fh:
        def write(fut, i):
            row = fut.result()
            if row is not None:  # None: skipped after a stop
                fh.write(json.dumps(row) + "\n")
                fh.flush()
            written.add(fut)  # only once written (#175)
            if row is None:
                return
            flag = "" if not codex_unusable(row) else f" UNUSABLE ({row.get('error') or row.get('unusable_because')})"
            print(f"  [{args.test}] {tag}: {i}/{len(todo)} input_tokens={row.get('input_tokens')}{flag}", flush=True)
            return row

        try:
            for i, fut in enumerate(as_completed(futs), 1):
                if fut.cancelled():
                    continue
                row = write(fut, i)
                if row and row.get("login_error") and not login_failed:  # later questions would fail the same way (#165)
                    login_failed = True
                    stop.set()
                    for f in futs:
                        f.cancel()
        except KeyboardInterrupt:  # ask nothing new; keep the rows of calls that finish (#173)
            interrupted = True
            stop.set()
            for f in futs:
                f.cancel()
            print("interrupted: waiting for running calls to finish and writing their rows", flush=True)
        finally:
            if interrupted:  # a second Ctrl-C must not lose the rows of calls still running (#175)
                signal.signal(signal.SIGINT, signal.SIG_IGN)
                print("running calls continue; their rows will be written (further Ctrl-C ignored)", flush=True)
            ex.shutdown(wait=True, cancel_futures=True)
            for fut in futs:
                if fut not in written and fut.done() and not fut.cancelled() and fut.exception() is None:
                    write(fut, len(written) + 1)
    if login_failed:
        raise SystemExit(f'stopped on a login error; sign in again: CODEX_HOME={args.home} codex login -c cli_auth_credentials_store="file"')
    if interrupted:
        raise SystemExit(130)

if __name__ == "__main__":
    main()
