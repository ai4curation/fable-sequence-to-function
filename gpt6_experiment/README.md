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
(no headers). Each body is checked (`check_request`): the named model and effort, the one-line
instruction as the only developer text, the question as the only user text, no tools beyond
`request_user_input` and `view_image`, nothing token-like. The row keeps the bodies' SHA-256 and the
host they went to; the bodies are saved in the experiment home under `requests/`. A row with no
logged request is unusable, so a change in Codex's logging fails closed. The stub test shows the
logged body equals the body the server received, and that re-enabled shell tools are caught on the
longest real question (1,629 characters), where the token limit below misses them.

**Input tokens** above `common.context_limit` (700 plus one per character of the question, the
Claude rows' limit, `context_tokens_high`) also make a row unusable. It is a coarse check: it
catches extra tools only on short questions (#163).

**Not recorded: the model the server answered with.** Only the requested model is logged; a
substitution by the server would not be visible in these rows.

A row is usable only if: the request check and the context check pass; the reply calls no tool and Codex printed no
warning or error item; there is exactly one non-empty agent message and one model response; Codex
requested the named model; and the input tokens are within the limit. `unusable_because` lists the
reasons otherwise.

## Scoring and audit

Rows have the same layout as the Gemini rows (`build_row`), so the Gemini scorer and audit read them:

    uv run python gemini_experiment/score_gemini.py gpt6_experiment/results
    uv run python gemini_experiment/audit.py gpt6_experiment/results

For GPT-6 rows the audit also requires, of every usable row, a passing context check, the named
model requested, input tokens within the limit, and a passing request check. `scripts/check_codex_runner_with_stub_provider.py`
writes rows through the runner against a stub and runs both commands on them. Once real rows exist,
add both commands to `just report` and `just check` with frozen outputs in `expected/`.
`experiments/summary.py` totals the Claude calls only, as for the Gemini rows; the audit's coverage
lines give the GPT-6 counts.

## Not yet known (needs a live call)

- Whether Codex logs and sends the same request body on the ChatGPT backend as on the stub. The
  canary's request check shows this directly; its input-token count shows how much the instruction
  and two tools cost in tokens.
- Whether this account can use `gpt-rosalind-astra` (it is in the catalog).
