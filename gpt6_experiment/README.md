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
  text-only input (`CATALOG_OVERRIDES`). Its hash is in each row.
- **Settings and feature switches** in `run_codex.py` (`SETTINGS`, `FEATURES_OFF`); Codex 0.170.0
  recognises all of them. Read-only sandbox, empty working folder.

## What each row records, and when it is usable

From `codex exec --json` and the saved session record: reply text, token counts, thread id,
response id(s), the model the thread used, the effort, and a context check. The check reads the
session record (instructions used, which instruction blocks were included, effort, multi-agent
mode, sandbox, any extra context message). The session record does not list the tools; the stub
test checks those on the request, and on real calls the input-token count shows them.

A row is usable only if the context check passes, the reply calls no tool, Codex printed no warning
or error item, there was exactly one model response, and the thread used the requested model.

## Not yet known (needs a live call)

- Whether the ChatGPT backend honours the custom catalog as the stub did. The input-token count of
  the first real call should be close to the question's length plus about 500 tokens.
- Whether this account can use `gpt-rosalind-astra` (it is in the catalog).
