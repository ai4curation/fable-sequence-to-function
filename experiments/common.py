"""Shared rules for reading model replies and resuming runs. Imported by the ask/run and score scripts.

answer(text, keys)  The answer is the last complete JSON object in the reply that has at least two of the requested
                    keys (#50). A reply that contains a tool invocation has no answer (#49), even if it also holds
                    an answer object: the text cannot show whether the answer came from the question alone.
                    Known limits (#61): an example object written after the answer is taken as the answer, and an
                    answer wrapped in an outer object is not found. The scorers print the replies with more than
                    one object and those with a tool invocation, so both can be read by eye.
reparse(R, keys)    Apply answer() to stored rows, so the scorers read the reply text and not the `ans` stored at
                    run time. Returns the rows whose reply holds more than one such object.
resume(path, key, effort)   Questions already answered. Results files are append-only: an unusable row stays where it
                    is, the question is asked again, and the scorers skip the unusable row (#26, #56).
call(model, effort, prompt)   One question through the `claude` command line tool, with what the call carried.
unusable(r)         True for a row that is not an answer to the question alone: a failed call, an API error, or a
                    call whose input was larger than the question (attached context).
"""
import datetime, functools, hashlib, json, os, pathlib, re, subprocess
# The original runs used `claude -p --model M --system-prompt "" --tools "" --effort E --output-format json`. On a
# machine with user settings and account connectors those flags do not isolate the question (#13): instructions,
# skill listings and connector tools can be attached. EXTRA removes them; what is left is an environment block of
# about 600 tokens that the tool adds itself. Rows written by call() record EXTRA and the token counts.
EXTRA = ["--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-chrome"]
INPUT_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
# The parts of the tool's usage records that are kept in a row; a key a later tool version adds is not stored unseen.
USAGE_KEYS = INPUT_KEYS + ("output_tokens", "output_tokens_details", "server_tool_use", "service_tier", "cache_creation", "inference_geo", "speed", "iterations")
MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "webSearchRequests", "costUSD", "contextWindow", "maxOutputTokens",
                    "thinkingTokens", "cacheCreationEphemeral5mInputTokens", "cacheCreationEphemeral1hInputTokens", "canonicalModel", "provider", "costBasis")
def _num(x): return x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0   # a count that is missing or not a number is 0
def context_limit(prompt): return 700 + len(prompt)   # environment block plus at most one token per character of the question
@functools.cache
def cli_version(): return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
def call(model, effort, prompt, tries=3, timeout=3600):
    """Ask one question. Returns (reply text or None, record). The record always has effort, attempts, prompt_sha256,
    extra_flags, cli_version and asked_at; a failed call adds `error`, an answered one adds cost, served, token
    counts, is_error and context_tokens_high, and the tool's own turn count, stop reason and usage records. An
    API-error reply is tried again like a failed call; `attempt_errors` keeps the first line of each such reply and
    `cost_all_attempts` the cost of all attempts, since `cost` is that of the last one only.
    The tool can make more than one request for a question (#65). Its session records show three causes, all in
    the Opus 4.6 high-effort runs: the reply reached the output limit (64,000 tokens, all of it thinking), a
    safety classifier stopped the reply, or the reply had no visible text. Each time the tool added a message
    saying so and asked again; the
    later request carried 41, 54 or 99 more input tokens (99 when the tool also added a note that the date had
    changed), and nothing about the protein. The reported token counts are then sums over the requests, while
    `iterations` in the usage record lists the last response only. So `requests` is the tool's turn count, and a
    row is marked when the listed response (`context_tokens_max`) is larger than one request may be, or the sum
    is larger than `requests` such requests. Two limits: an attachment smaller than one request's allowance
    could go unmarked in a call that took several requests (the scorers count those replies), and a follow-up
    request that resent a long visible reply would be marked and asked again. `session_id` names the tool's
    local session record, which is not in the repository. Of the tool's usage records only USAGE_KEYS and
    MODEL_USAGE_KEYS are kept.
    """
    rec = dict(effort=effort, prompt_sha256=sha(prompt), extra_flags=EXTRA, cli_version=cli_version()); j = None; why = ""; errs = []; spent = 0.0
    for attempt in range(1, tries + 1):
        try:
            p = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", "", "--tools", "", "--effort", effort, "--output-format", "json"] + EXTRA,
                               input=prompt, capture_output=True, text=True, cwd="/tmp", timeout=timeout)
        except subprocess.TimeoutExpired: j = None; why = f"no reply within {timeout} s"; continue
        try: j = json.loads(p.stdout)
        except ValueError: j = None; why = p.stdout[-300:] + p.stderr[-300:]; continue
        if not isinstance(j, dict): j = None; why = p.stdout[-300:]; continue
        spent += j.get("total_cost_usd") or 0
        if not j.get("is_error"): break
        errs.append(((j.get("result") or "").strip().splitlines() or ["is_error"])[0][:200])
    rec.update(attempts=attempt, asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    if attempt > 1: rec.update(attempt_errors=errs, cost_all_attempts=spent)
    if j is None: return None, dict(rec, error=why or "no parseable output")
    u = j.get("usage"); u = u if isinstance(u, dict) else {}; mu = j.get("modelUsage"); mu = mu if isinstance(mu, dict) else {}
    context = sum(_num(u.get(k)) for k in INPUT_KEYS); turns = j.get("num_turns"); n = turns if isinstance(turns, int) and turns > 1 else 1
    its = u.get("iterations"); its = [i for i in its if isinstance(i, dict)] if isinstance(its, list) else []   # the last response only, also when the tool made two requests
    largest = max([sum(_num(i.get(k)) for k in INPUT_KEYS) for i in its] or [context]); details = u.get("output_tokens_details")
    rec.update(cost=j.get("total_cost_usd"), served=list(mu), thinking_tokens=details.get("thinking_tokens") if isinstance(details, dict) else None,
               input_tokens=u.get("input_tokens"), cache_creation_input_tokens=u.get("cache_creation_input_tokens"), cache_read_input_tokens=u.get("cache_read_input_tokens"),
               output_tokens=u.get("output_tokens"), context_tokens=context, context_tokens_max=largest, requests=n,
               context_tokens_high=largest > context_limit(prompt) or context > n * context_limit(prompt), is_error=bool(j.get("is_error")),
               num_turns=turns, stop_reason=j.get("stop_reason"), duration_ms=j.get("duration_ms"), session_id=j.get("session_id"),
               usage={k: u[k] for k in USAGE_KEYS if k in u}, model_usage={m: {k: v[k] for k in MODEL_USAGE_KEYS if k in v} for m, v in mu.items() if isinstance(v, dict)})
    return j.get("result") or "", rec
def unusable(r): return "error" in r or bool(r.get("is_error")) or bool(r.get("context_tokens_high"))
_dec = json.JSONDecoder()
# The keys each test's prompt asks for; an answer object has at least one of them.
KEYS = {"features": "pfam_domains transmembrane_helices signal_peptide protein_name ec_number function".split(),
        "pseudo": "protein_name enzyme_family catalytic_residues substituted_or_missing catalytically_active ec_number reason".split(),
        "structure": "helices strands fold contacts protein_name function functional_residues recognised".split()}
# A fenced shell block, a web request or tool-call markup: the model wrote a tool invocation.
TOOL_CALL = re.compile(r"```(?:bash|sh|shell|shell-session|zsh|console)\b|\bcurl\s+(?:-|https?://)|\bwget\s+(?:-|https?://)|\brequests\.(?:get|post)\(|\burlopen\("
                       r"|<function_calls>|<invoke\b|<tool_call>|\"type\"\s*:\s*\"(?:tool_use|function)\"")
def has_tool_call(text): return bool(TOOL_CALL.search(text or ""))
def json_objects(text, keys):
    """Complete JSON objects in the text that have at least two of `keys`, in order. Objects nested in one that
    parsed are not listed; the key test keeps the parts of a malformed object from being taken as an answer."""
    out, i, text = [], 0, text or ""
    while (i := text.find("{", i)) >= 0:
        try: obj, n = _dec.raw_decode(text[i:])
        except (ValueError, RecursionError): i += 1; continue
        if isinstance(obj, dict) and sum(k in obj for k in keys) >= 2: out.append(obj)
        i += n
    return out
def answer(text, keys):
    if has_tool_call(text): return None
    objs = json_objects(text, keys)
    return objs[-1] if objs else None
def reparse(R, keys):
    multi = []
    for r in R:
        r["ans"] = None if unusable(r) else answer(r.get("text"), keys)
        if len(json_objects(r.get("text"), keys)) > 1: multi.append(r)
    return multi
def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def resume(path, key, effort=None):
    """Return the keys of the questions that have a usable row in `path` (see unusable). Nothing is rewritten. Stops
    if the file holds rows asked at another effort: a second effort goes to its own file (--tag)."""
    path = pathlib.Path(path)
    if not path.exists(): return set()
    rows = [json.loads(l) for l in path.open() if l.strip()]
    other = sorted({r["effort"] for r in rows if r.get("effort")} - {effort})
    if effort and other: raise SystemExit(f"{path} holds rows asked at effort {', '.join(other)}; use --tag for a run at effort {effort}")
    return {key(r) for r in rows if not unusable(r)}
def out_path(here, model, effort, tag=None, by_effort=False):
    """results/MODEL.jsonl, or results/EFFORT/MODEL.jsonl for test 1. A TAG gives results/MODEL-TAG.jsonl, for a
    second run of a model at another effort."""
    d = here / "results" / effort if by_effort else here / "results"; d.mkdir(parents=True, exist_ok=True)
    return d / f"{model}{'-' + tag if tag else ''}.jsonl"
def options(argv):
    """Split a command line into positional arguments and the two options every call script takes:
    --tag TAG (write to MODEL-TAG.jsonl) and --limit N (ask at most N of the missing questions; N=1 is the canary)."""
    pos, tag, limit, i = [], None, None, 1
    while i < len(argv):
        if argv[i] == "--tag": tag = argv[i + 1]; i += 2
        elif argv[i] == "--limit": limit = int(argv[i + 1]); i += 2
        else: pos.append(argv[i]); i += 1
    return pos, tag, limit
def efforts(R):
    """The effort levels recorded in a file's rows, for the scorer headers."""
    e = sorted({r["effort"] for r in R if r.get("effort")}); return ", ".join(e) if e else "not recorded in rows"
def failed(R): return sum(unusable(r) for r in R)   # rows the scorers skip; the question is asked again on the next run
def tool_calls(R): return [r for r in R if not unusable(r) and has_tool_call(r.get("text"))]
def continued(R): return [r for r in R if not unusable(r) and max(r.get("requests") or 1, r.get("num_turns") or 1) > 1]
NOTE_FAILED = "calls that failed, returned an API error or carried attached context (not scored)"
NOTE_TOOL = "replies with a tool invocation (no answer taken)"
NOTE_CONTINUED = "replies that took more than one request (the tool asked again by itself after an output limit, a classifier stop or an empty reply; read like any other)"
