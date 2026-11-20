# GPT-6 through `codex exec` (#52)

`run_codex.py` asks `gpt-6-astra` and `gpt-rosalind-astra` the same frozen questions as the Claude
and Gemini runs, through the Codex CLI signed in to ChatGPT (no OpenAI API key is used). Codex is a
coding agent and normally sends about 89,000 characters of its own context with each request; the
runner strips that for this experiment only. `~/.codex` is never read or changed.

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
- **No second answer to a question** (#166, #168, #169).
  - **Codex's own retries are off** (`request_max_retries=0`, `stream_max_retries=0`). By default
    Codex reconnects a dropped stream up to five times and sends the question again each time, even
    after the model has replied.
  - **The runner retries an attempt only if nothing shows the question reached the model:** no logged
    request, no websocket line, no output item, no token counts, no response in the session record.
  - **Otherwise the attempt is kept and marked unusable** (`attempt failed after the request was
    sent`). This includes a server error or rate limit after a logged request, since the runner can't
    tell whether the model ran.
  - **A timeout (1,800 s) is never retried.**
  - **Re-asking is left to `--retry-unusable`.**
- **Every attempt is recorded**: `attempt_log` in the row (thread, outcome, exit code, failure,
  requests logged, request check).
  - **Saved before parsing:** the experiment home's `attempts/` folder keeps each attempt's JSON event
    stream, its stderr without the trace lines, and its request bodies. They are saved before any
    parsing, with anything token-like masked.
  - **Unparsable lines** in Codex's output are counted and make the row unusable, but they don't lose
    the attempt (#171).
  - **Failure text** in the row is built from the filtered, masked stderr (#170).
- **Stopping** (#165, #173).
  - **A login error** stops the run, and no further question starts.
  - **Ctrl-C** starts no new question either. The rows of calls that finish are written, and the run
    exits with 130. A terminal Ctrl-C also reaches the running Codex processes; those rows are
    unusable.
- **Idle sleep is blocked during a run** (`caffeinate -i -w <runner pid>`). One canary call stalled
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
writes rows through the runner against a stub and runs both commands on them. Once real rows exist,
add both commands to `just report` and `just check` with frozen outputs in `expected/`.
`experiments/summary.py` totals the Claude calls only, as for the Gemini rows; the audit's coverage
lines give the GPT-6 counts.

## Canary record

The results are append-only. None of these rows counts: all are from before `codex_row_format` 2.

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
