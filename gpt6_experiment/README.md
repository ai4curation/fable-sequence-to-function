# GPT-6 through `codex exec` (#52)

`run_codex.py` asks `gpt-6-astra` and `gpt-rosalind-astra` the same frozen questions as the Claude
and Gemini runs, through the Codex CLI signed in to ChatGPT (no OpenAI API key is used). Codex is a
coding agent and normally sends about 89,000 characters of its own context with each request; the
runner strips that for this experiment only. `~/.codex` is never read or changed.

## Where to run

**Run Rosalind only on EC2 through the paired Orca `rosalind` environment, never on the laptop.**
Use `orca environment list --json` to confirm the pairing and `orca repo list --environment rosalind --json`
to locate the remote checkout. Launch the runner in a terminal belonging to that environment, with
an experiment home and login on EC2. Verify the remote Codex version and run the offline stub checks
there before making live calls; this runner was validated with Codex 0.170.0. A local shell does not
become remote merely because an Orca environment is paired.

The stub checks call no model and may run locally. Each invocation uses its own scratch home so
checks in different checkouts cannot overwrite one another's evidence.

## Full comparison (#52)

After the remote preflight and one successful live question for each model, run on EC2:

```bash
uv run python gpt6_experiment/run_full.py --workers 4
```

This asks both models 1,008 distinct questions each: next residue at low effort with real, shuffled
and reversed sequences (408), next residue at high effort with real and shuffled sequences (272),
features (120), catalytic activity (120), structure (30), and decoy substitutions (58), the latter
four at high effort. Existing answered questions, including the structure canaries, are skipped.
The decoys use exactly the canonical test-3 prompt. Their comparator is the same model's new
test-3 run on this route, so no extra bridge calls are needed.

Each model runs one test at a time, in waves of at most four questions. Next-residue high runs last.
An unusable new reply, an unparsed JSON answer, a runner error, or a launch journal that prevents
progress stops further waves for both models; already-running calls finish. The controller never
passes `--retry-unusable`. Inspect the saved evidence before deciding how to handle missing answers.

Run under `nohup` with stdout/stderr redirected to a log for a detached batch. The experiment home's
`full_analysis/` holds the launch manifest (host, code commit, CLI, grid), per-model JSON progress,
wave logs and, after completion or a stop, `scores.txt`, `audit.txt`, and `decoys.txt`. Results remain
append-only under `gpt6_experiment/results/`. Re-running the command resumes without re-asking
attempted questions. Low-effort next-residue rows explicitly record `ncond=3` for the audit.

`report_full.py` produces `gpt6_experiment/RESULTS.md` with coverage and summary tables, the canonical
scores, sensitivity analyses, paired decoy comparisons and audit. It refuses incomplete grids unless
`--allow-partial` is explicitly requested, which labels the report incomplete.

For an unattended run, `finish_full.py PID --publish` waits for that controller process on EC2,
requires both models to complete and the audit to pass, regenerates the reports and checksums, then
commits and pushes the results to this PR branch without forcing. It records its outcome in
`<home>/full_analysis/completion.json`. A stopped run, an audit failure, changed unrelated data,
unexpected staged changes or an advanced remote branch prevents publication. The completion step
does not make model calls or retry any question.

Score the decoy comparison separately:

```bash
uv run python experiments/decoy_control/score_decoys.py \
  --results gpt6_experiment/results/decoy_control \
  --pseudo-results gpt6_experiment/results/pseudo
```

Codex does not report monetary cost; zero cost totals in the shared decoy report mean no recorded
cost, not free calls. The decoy interpretation and limitations in `experiments/decoy_control/README.md`
apply, including the lack of experimental activity measurements for the decoy substitutions.

## What the request carries

Measured offline by pointing `codex exec` at a local stub server
(`scripts/adhoc/capture_codex_request_with_local_stub.py`, `scripts/check_codex_runner_with_stub_provider.py`):

| | Default Codex | This runner |
|---|---|---|
| Instructions | 21,000+ characters of Codex's built-in instructions | "Answer the user's message." |
| Tools | 10 (code-mode `exec`, agent spawning and messaging, user input) | 2: `request_user_input`, `view_image` (about 2,000 characters) |
| Other context | skills guide, multi-agent text, the user's `AGENTS.md`, environment context | none |

How:
- **Experiment-only `CODEX_HOME`** (`~/agent-work/fable-sequence-to-function/codex_home_gpt6`) with
  its own ChatGPT login, stored as a file:
  `CODEX_HOME=<that folder> codex login -c cli_auth_credentials_store="file"`.
  With the normal `~/.codex`, the user's `AGENTS.md` reaches the request even with
  `--ignore-user-config`.
- **`model_instructions_file`** with the one-line instruction.
- **`model_catalog_json`**: a copy of the login's model catalog in which the target model has
  `tool_mode`, `multi_agent_version` and `apply_patch_tool_type` unset, no experimental tools, and
  text-only input, and no search tool (`CATALOG_OVERRIDES`). Its hash is in each row.
- **Settings and feature switches** in `run_codex.py` (`SETTINGS`, `FEATURES_OFF`); Codex 0.170.0
  recognises all of them. Read-only sandbox, an empty working folder outside any git repository
  (Codex sends the folder path, and a repository's remote and commit, as request metadata; the
  runner refuses a home inside a repository).
- **No `OPENAI_*` or `CODEX_*` variables** from the caller's environment reach Codex, so an API key
  or endpoint override cannot take a call off the experiment's login.
- **One catalog file per model** (`catalog_isolated_<model>.json`), so Astra and Rosalind runs can
  share the home.
- **Its own model provider, over HTTP only** (`fs2f_chatgpt_http`: the ChatGPT Codex backend,
  `requires_openai_auth=true`, `supports_websockets=false`; `provider_args`). With a ChatGPT login,
  the built-in `openai` provider opens a Responses WebSocket first, and the websocket body is not in
  the HTTP transport log. The first real canary got an answer and no logged request that way (#164).
  Built-in provider IDs can't be overridden. The stub test uses the same provider settings, with only
  the base URL changed, plus one case with websockets on. With a login in the home, the runner refuses
  any other base URL, because the provider sends the login wherever it points.
- **No second answer to a question** (#166, #168, #169, #176, #179).
  - **Codex's own stream and request retries are off** (`request_max_retries=0`,
    `stream_max_retries=0`). By default Codex reconnects a dropped stream up to five times and sends
    the question again each time, even after the model has replied. With these off, the stub received
    exactly one request for every stream cut, HTTP error and error event tried.
  - **Codex still reconnects when it can't reach the server at all** ("Reconnecting... waiting for
    network"). If the server is down, the question waits until the timeout. After a brief network
    drop, the reply can arrive and still leave the row unusable, because more requests were logged
    than responses. `--retry-unusable` would then ask that question again (#179).
  - **The runner retries an attempt only if nothing shows the question may have reached the model:**
    no started turn, no logged request, no websocket line, no output item, no token counts, no
    response in the session record. A started turn counts even when the trace log is missing, because
    it comes before the request.
  - **Otherwise the attempt is kept and marked unusable** (`attempt failed after the request may have
    been sent`). This includes a server error or rate limit after the request, and a timeout (1,800 s,
    reply kept).
  - **Re-asking is left to `--retry-unusable`.**
- **Every attempt is recorded**: `attempt_log` in the row (thread, outcome, exit code, failure,
  number of unparsable output lines, requests logged, request check).
  - **Evidence folder:** the experiment home's `attempts/` keeps each attempt's JSON event stream,
    its stderr without the trace lines, and its request bodies, with anything token-like masked.
  - **If saving fails,** the attempt counts as having reached the model, and the row is unusable
    (`attempt evidence not saved`; #177, #182).
  - **The request check never raises** on an unexpected body shape; it reports a problem instead.
  - **Failure text and error fields** in the row are masked and capped at 400 characters (#170, #178,
    #182). The mask covers bearer tokens of 16 or more characters after a space, `%20`, `%3A`, `+`,
    `=`, `:` or an escaped space or tab, in any case; basic credentials containing a digit or base64
    punctuation; JWTs; and `sk-` keys and `rt_` refresh tokens standing as separate tokens. It matches no
    saved reply or question in the repository. It is a safeguard, not a guarantee.
- **Launch journal** (#181, #185).
  - **Where:** before each call, the runner appends the question to
    `<experiment home>/launched/<test>/<model>-<effort>.jsonl` and syncs it to disk. The journal sits beside the
    Codex session records, so every checkout that uses the home sees it.
  - **Killed runs:** a question in the journal with no row (because the runner was killed) counts as
    asked on the next run, since the model may have answered and been billed. The run prints how many
    there are. `--retry-unusable` asks them again.
  - **One run per tag at a time:** the journal is locked before anything else, and a second run of the
    same test, model and effort refuses to start without touching the experiment home.
  - **Other checkouts:** each line records the results file it was written for. A question launched by a
    run writing another results file is reported as such and not asked again unless `--retry-unusable` is given.
  - **Not asked:** if writing the journal line fails, or a stop arrives before Codex starts, the question
    gets a row marked `not_asked`. An append-only cancellation entry releases that specific launch
    for the next run, including from another checkout. It cannot release an older attempt that may
    have reached the model. If saving the cancellation fails, `journal_error` records the failure;
    check the journal and its evidence before retrying.
  - **Damaged lines:** a damaged journal line stops the run before any call, naming the line.
- **Stopping** (#165, #173, #175, #181, #184, #185).
  - **What stops a run:** a login error, Ctrl-C, SIGTERM or a closed terminal (SIGHUP). After one, no
    new question starts and no running question gets a new attempt.
  - **Signals never interrupt the runner.** They only set a flag, and the main loop checks it.
  - **Codex runs in its own session,** so these signals reach only the runner. Running calls finish,
    and each row is written before anything is printed. Printing is best-effort, so a closed terminal
    or pipe can't stop rows being written.
  - **Exit status:** 128 plus the number of the first signal (130 for Ctrl-C), even with stdout closed.
    A login error takes precedence and exits with its message.
  - **Errors:** if anything fails inside the loop, nothing new starts, and the rows of calls that finish
    are still written (#190).
  - **`nohup`:** a run started under `nohup` keeps ignoring SIGHUP.
  - **To abandon running calls,** kill their Codex processes (`pgrep -f "catalog_isolated_<model>.json"`).
    The runner then writes an unusable row for each.
  - **Ctrl-\\ (SIGQUIT) or `kill -9`** ends the runner at once. Running calls continue unrecorded, and
    the journal keeps those questions from being asked again.
- **After an outage,** the questions asked during it have unusable rows. `--retry-unusable` asks them
  again, but it also re-asks any unusable row where the model did answer. Check `attempt_log` before
  using it.
- **Idle sleep is blocked during a run** (`caffeinate -i -w <runner pid>`, in its own session, so it
  outlives a Ctrl-C). One canary call stalled
  when the Mac slept, and the timeout doesn't count time asleep. Closing the lid or choosing Sleep
  still stops a call.
- **Efforts** low, medium, high, xhigh and max. Codex 0.170.0 sends `ultra` as `xhigh`, so `ultra`
  is not offered.

## What each row records, and when it is usable

From `codex exec --json` and the saved session record (which stays in the experiment home; the row
keeps its path and SHA-256): reply text, token counts, thread id (and those of failed attempts),
response id(s), the model Codex requested (`requested_model_logged`), and a context check. The check
reads the session record: instructions used, which instruction blocks were included, effort,
multi-agent mode, sandbox, any extra context message.

**The request itself.** The runner turns on trace logging for Codex's HTTP transport only
(`RUST_LOG=codex_http_client::transport=trace`), which logs the body of every request Codex sends
(no headers), plus Codex's websocket connection messages at info level. Each body is checked (`check_request`): the named model and effort, the one-line
instruction as the only developer text, the question as the only user text, no tools beyond
`request_user_input` and `view_image`, nothing token-like. Any websocket activity also fails the
check, and so does a host other than the provider's, or a number of logged requests different from
the number of model responses. The row keeps the provider, its base URL and the bodies' SHA-256 and the
host they went to, along with the count of websocket log lines. The bodies are saved in the experiment home under `attempts/`. A row with no
logged request is unusable, so a change in Codex's logging fails closed. The stub test shows the
logged body equals the body the server received, and that re-enabled shell tools are caught on the
longest real question (1,629 characters), where the token limit below misses them.

**Input tokens** above `common.context_limit` (700 plus one per character of the question, the
Claude rows' limit, `context_tokens_high`) also make a row unusable. It is a coarse check: it
catches extra tools only on short questions (#163).

**Codex sets `text.verbosity` to `low`** in every request, and it sends session and installation
IDs as `client_metadata`, which the model doesn't see. Neither can be turned off from the command line.

**Not recorded: the model the server answered with.** Only the requested model is logged; a
substitution by the server would not be visible in these rows.

A row is usable only if: the request check and the context check pass; the reply calls no tool and Codex printed no
warning or error item; there is exactly one non-empty agent message and one model response; Codex
requested the named model; the input tokens are within the limit; and the attempt that gave the reply
reported no failure. Rows from before `codex_row_format` 2 never count: the runner then kept no record
of discarded attempts. This rule sits in `run_agy.agy_unusable`, which the scorer and audit share. `unusable_because` lists the
reasons otherwise.

## Scoring and audit

Rows have the same layout as the Gemini rows (`build_row`), so the Gemini scorer and audit read them:

    uv run python gemini_experiment/score_gemini.py gpt6_experiment/results
    uv run python gemini_experiment/audit.py gpt6_experiment/results

For GPT-6 rows the audit also requires, of every usable row, a passing context check, the named
model requested, input tokens within the limit, a passing request check, the runner's provider,
and no websocket log lines. `scripts/check_codex_runner_with_stub_provider.py`
writes rows through the runner against a stub and runs both commands on them. `just report` and
`just check` include the committed canaries, with frozen outputs in `expected/gpt6.txt` and
`expected/gpt6_audit.txt`. Their raw results are covered by `SHA256SUMS`.
`experiments/summary.py` totals the Claude calls only, as for the Gemini rows; the audit's coverage
lines give the GPT-6 counts.

## Canary record

The results are append-only. For the initial canary question, only the final format-2 row counts;
its earlier rows predate `codex_row_format` 2. Subsequent questions are scored independently.

**Canary with the fixed runner** (commit 0f5a631, 2026-11-20), first test-4 question, high effort.
Each model took one attempt. Each sent one logged request to chatgpt.com, which passed the request
check, with no websocket and a passing context check. Each gave one response, and the audit passes.

| Model | Input tokens | Output tokens (thinking) | Time |
|---|---|---|---|
| `gpt-6-astra` | 656 | 4,584 (4,381) | 224 s |
| `gpt-rosalind-astra` | 656 | 19,974 (19,682) | 684 s |

Earlier rows:

`results/structure/gpt-6-astra-high.jsonl`, first test-4 question, high effort:
1. **The login was rejected**, and no request was sent.
2. **Built-in provider:** the model answered, with 656 input tokens and 4,288 output tokens. The row
   is unusable because no request was logged (#164).
3. **Own HTTP provider:** passed every check. One logged request to chatgpt.com, 656 input tokens
   (the same as try 2, so the same content) and 4,420 output tokens.

`results/structure/gpt-rosalind-astra-high.jsonl`, same question. The account can use Rosalind.
1. **Stalled, no row.** Thread `01a1fa19-d1ab-7632-8115-dafaa02844bd` started at 09:55 PST on
   2026-11-20. The Mac slept from 09:57, the stream stopped at 09:59, and the run was stopped by
   hand about 1.5 hours later.
2. **Rerun with sleep blocked.**
   - Attempt 1 (`01a1fa70-2e04-77d2-9ecb-5e0a5d172e18`) got a complete reply: 15,414 output tokens in
     509 s.
   - The runner then asked again, for a reason it didn't record (#166).
   - Attempt 2 (`01a1fa78-1bca-70a2-8405-f438b1710165`) gave 18,126 output tokens in 578 s. Only
     that answer is in the row.
   - By the authors' decision the row doesn't count, being a second answer to the same question.
