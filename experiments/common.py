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
unusable(r)         True for a row that is not an answer to the question alone: a failed call, an API error, a
                    call whose input was larger than the question (attached context), or a call whose usage record
                    gives an input count that is not a number.
"""
import datetime, functools, hashlib, json, math, os, pathlib, re, subprocess
# The original runs used `claude -p --model M --system-prompt "" --tools "" --effort E --output-format json`. On a
# machine with user settings and account connectors those flags do not isolate the question (#13): instructions,
# skill listings and connector tools can be attached. EXTRA removes them; what is left is an environment block of
# about 600 tokens that the tool adds itself. Rows written by call() record EXTRA and the token counts.
EXTRA = ["--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-chrome"]
INPUT_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
# The parts of the tool's usage records that are kept in a row, at every level; a key a later tool version adds is not
# stored unseen, and its name is listed in `usage_keys_dropped`.
USAGE_KEYS = INPUT_KEYS + ("output_tokens", "output_tokens_details", "server_tool_use", "service_tier", "cache_creation", "inference_geo", "speed", "iterations")
ITERATION_KEYS = INPUT_KEYS + ("output_tokens", "cache_creation", "type")
SERVER_TOOL_KEYS = ("web_search_requests", "web_fetch_requests")
CACHE_KEYS = ("ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens")
DETAIL_KEYS = ("thinking_tokens",)
MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "webSearchRequests", "costUSD", "contextWindow", "maxOutputTokens",
                    "thinkingTokens", "cacheCreationEphemeral5mInputTokens", "cacheCreationEphemeral1hInputTokens", "canonicalModel", "provider", "costBasis")
def _finite(x):
    try: return math.isfinite(x)
    except OverflowError: return False   # an int too large for a float
def _ratio(a, b):
    """a / b as a float, or infinity when it cannot be represented (#111)."""
    try: return a / b
    except (OverflowError, ZeroDivisionError): return math.inf
def _num(x): return x if isinstance(x, (int, float)) and not isinstance(x, bool) and _finite(x) else 0   # for costs: anything else is 0
def _count(x):
    """An input-token count: None if it is missing, the number if it is a finite number, and False if it is something else.
    A row with a count that is present but unreadable is marked (`usage_unreadable`), not read as 0 (#84)."""
    if x is None: return None
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and _finite(x) and x >= 0 else False   # negative counts are unreadable too
def _int(x):
    """A turn or request count as an int, or None: accepts an int, an integral float and a string of digits (#84)."""
    if isinstance(x, bool): return None
    if isinstance(x, int): return x
    if isinstance(x, float) and math.isfinite(x) and x == int(x): return int(x)
    if isinstance(x, str) and x.strip().isascii() and x.strip().isdecimal() and len(x.strip()) < 10: return int(x.strip())   # not "²", which isdigit() accepts
    return None
def _keep(d, keys, dropped, where):
    """The entries of d whose key is in keys; the names of the others go to `dropped`."""
    dropped.extend(f"{where}{k}" for k in d if k not in keys); return {k: d[k] for k in keys if k in d}
def _usage(u, dropped):
    out = _keep(u, USAGE_KEYS, dropped, "")
    if isinstance(out.get("server_tool_use"), dict): out["server_tool_use"] = _keep(out["server_tool_use"], SERVER_TOOL_KEYS, dropped, "server_tool_use.")
    if isinstance(out.get("cache_creation"), dict): out["cache_creation"] = _keep(out["cache_creation"], CACHE_KEYS, dropped, "cache_creation.")
    if isinstance(out.get("output_tokens_details"), dict): out["output_tokens_details"] = _keep(out["output_tokens_details"], DETAIL_KEYS, dropped, "output_tokens_details.")
    if isinstance(out.get("iterations"), list):
        out["iterations"] = [_keep(i, ITERATION_KEYS, dropped, "iterations.") if isinstance(i, dict) else i for i in out["iterations"]]
        for i in out["iterations"]:
            if isinstance(i, dict) and isinstance(i.get("cache_creation"), dict): i["cache_creation"] = _keep(i["cache_creation"], CACHE_KEYS, dropped, "iterations.cache_creation.")
    return out
MAX_UNCOUNTED_RETRIES = 1   # requests the tool may retry inside one call without counting a turn (#105, #109); real data shows one
def context_limit(prompt): return 700 + len(prompt)   # environment block plus at most one token per character of the question
@functools.cache
def cli_version(): return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
def call(model, effort, prompt, tries=3, timeout=3600):
    """Ask one question. Returns (reply text or None, record). The record always has effort, attempts, prompt_sha256,
    extra_flags, cli_version and asked_at; a failed call adds `error`, an answered one adds cost, served, token
    counts, is_error and context_tokens_high, and the tool's own turn count, stop reason and usage records. An
    API-error reply is tried again like a failed call; `attempt_errors` keeps the first line of each such reply and
    `cost_all_attempts` the sum of the costs the attempts reported (`cost` is that of the last one only; an attempt
    that timed out or returned no parseable output reports none and adds nothing).
    The tool can make more than one request for a question (#65). Its session records show four causes, all in
    the Opus 4.6 high-effort runs: the reply reached the output limit (64,000 tokens, all of it thinking), a
    safety classifier stopped the reply, the reply had no visible text, or a request failed inside the tool and
    was retried (#105). For the first three the tool added a message saying so and asked again; each later
    request carried 20 to 99 more input tokens than the one before (99 when the tool also added a note that the
    date had changed), and nothing about the protein. A request retried after a failure is counted in the token
    sums but not in the turn count. The reported token counts are sums over the requests, while `iterations` in
    the usage record lists the last response only. So `requests` is the turn count, plus at most
    MAX_UNCOUNTED_RETRIES (1) when the summed input divided by the listed response (`requests_by_tokens`) is
    larger; with no `iterations` it is the turn count and the listed size is the sum divided by it. A row is
    marked when the listed response (`context_tokens_max`) is larger than one request may be, or the sum is larger
    than `requests` such requests (#109).
    Limits of the mark: the allowance of 700 tokens plus one per character of the question is loose. In the
    rows of the Opus 4.6 high-effort runs scored as one request the input was 710 to 1,147 tokens below it, so an
    attachment of up to about that size goes unmarked in any call. An attachment resent with every request is
    marked through the listed response. One present only in earlier, unlisted requests is marked once the sum
    exceeds `requests` limits: about the limit plus, for each request, the unused part of the allowance (for
    Q9VLA1 about 3,700 tokens, roughly two limits); below that it passes as a retry (#111). More than
    one uncounted retry in a call would mark a clean reply, which would then be asked again. A follow-up request
    that resent a
    long visible reply would be marked and asked again. `session_id` names the tool's local session record,
    which is not in the repository. Of the tool's usage records only the keys listed above are kept, and the
    names of any others are in `usage_keys_dropped`.
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
        spent += _num(j.get("total_cost_usd"))
        if not j.get("is_error"): break
        errs.append((str(j.get("result") or "").strip().splitlines() or ["is_error"])[0][:200])
    rec.update(attempts=attempt, asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    if attempt > 1: rec.update(attempt_errors=errs, cost_all_attempts=spent)
    if j is None: return None, dict(rec, error=why or "no parseable output")
    u = j.get("usage"); bad = not isinstance(u, dict); u = u if isinstance(u, dict) else {}; mu = j.get("modelUsage"); mu = mu if isinstance(mu, dict) else {}
    turns = j.get("num_turns")
    top = [_count(u.get(k)) for k in INPUT_KEYS]; its = u.get("iterations"); its = [i for i in its if isinstance(i, dict)] if isinstance(its, list) else []
    each = [[_count(i.get(k)) for k in INPUT_KEYS] for i in its]; bad = bad or any(c is False for c in top + sum(each, []))
    bad = bad or all(c is None for c in top)   # a usage record without any input count: the input size is unknown (#110)
    context = sum(c or 0 for c in top); listed = max([sum(c or 0 for c in e) for e in each] or [0])
    # Requests: the turn count, plus at most MAX_UNCOUNTED_RETRIES when the summed input holds more requests than
    # that (a request that failed inside the tool and was retried is summed but not counted as a turn, #105). The
    # bound keeps the sum test working: input beyond that many requests is marked (#109). Dividing the sum by the
    # listed response gives the count exactly up to 3 requests with the observed increments; beyond that it can
    # be one low (#110).
    turns_n = max(_int(turns) or 1, 1)
    ratio = _ratio(context, listed) if listed else 0
    by_tokens = round(ratio) if _finite(ratio) and ratio >= 1 else turns_n   # an infinite sum is marked below; no input count gives the turn count (#111)
    n = turns_n + min(max(by_tokens - turns_n, 0), MAX_UNCOUNTED_RETRIES)
    largest = listed or _ratio(context, n)   # the listed response; without one, the mean request
    details = u.get("output_tokens_details"); dropped = []
    c = j.get("total_cost_usd"); ok_cost = _num(c) == c and not isinstance(c, bool) and c is not None and c >= 0
    rec.update(cost=c if ok_cost else None, served=list(mu), thinking_tokens=details.get("thinking_tokens") if isinstance(details, dict) else None,
               input_tokens=u.get("input_tokens"), cache_creation_input_tokens=u.get("cache_creation_input_tokens"), cache_read_input_tokens=u.get("cache_read_input_tokens"),
               output_tokens=u.get("output_tokens"), context_tokens=context, context_tokens_max=largest, requests=n, requests_by_tokens=by_tokens,
               context_tokens_high=largest > context_limit(prompt) or context > n * context_limit(prompt), is_error=bool(j.get("is_error")),
               num_turns=turns, stop_reason=j.get("stop_reason"), duration_ms=j.get("duration_ms"), session_id=j.get("session_id"),
               usage=_usage(u, dropped), model_usage={m: _keep(v, MODEL_USAGE_KEYS, dropped, f"modelUsage.{m}.") for m, v in mu.items() if isinstance(v, dict)})
    if bad: rec["usage_unreadable"] = True   # no usage record, or an input count that is not a non-negative number: the input size is unknown
    if dropped: rec["usage_keys_dropped"] = sorted(set(dropped))
    if rec["cost"] is None and c is not None: rec["cost_reported"] = c   # a cost that is not a number is kept apart, so the scorers' sums still work
    text = j.get("result"); return (text if isinstance(text, str) else "" if text is None else json.dumps(text)), rec
def unusable(r): return "error" in r or bool(r.get("is_error")) or bool(r.get("context_tokens_high")) or bool(r.get("usage_unreadable"))
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
def requests_made(r):
    """Requests the tool made for a row. Rows written by commit 4d3da97 hold requests=1 and the right turn count, so both are read."""
    return max(_int(r.get("requests")) or 1, _int(r.get("num_turns")) or 1)
def continued(R): return [r for r in R if not unusable(r) and requests_made(r) > 1]
NOTE_FAILED = "calls that failed, returned an API error, carried attached context or had an unreadable usage record (not scored)"
NOTE_TOOL = "replies with a tool invocation (no answer taken)"
def cost_unknown(R): return [r for r in R if r.get("cost_reported") is not None]   # rows whose reported cost was not a usable number
NOTE_COST = "rows whose reported cost is not a non-negative number (left out of the cost total; see cost_reported)"
def no_turn_count(R):
    """Scored rows (not failed, not an API-error reply) that record no turn count (#189, #192)."""
    return [r for r in R if not unusable(r) and not r.get("is_error") and not (r.get("text") or "").lstrip().startswith("API Error")
            and r.get("requests") is None and r.get("num_turns") is None]
NOTE_NO_TURNS = "usable rows that record no turn count, so whether the reply was continued is not known"
NOTE_CONTINUED = "replies that took more than one request (the tool asked again by itself after an output limit, a classifier stop or an empty reply, or retried a failed request; read like any other)"
