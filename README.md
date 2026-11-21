# Sequence to function with general language models

Can a general-purpose language model read a protein sequence directly? This
repository holds four small sequence-only tests of Claude Fable 5.2, Claude Opus
5.5 and Claude Opus 4.6, plus a Gemini extension and a draft preprint. The completed
Gemini API runs supplied no tools or system instruction in the request body.

Gemini 4 Neon detects all 20 kinase Asp-to-Asn substitutions at low effort and,
at medium effort, reaches 69.0% secondary-structure accuracy and 28.4% long-range
contact precision on the 12 novel-stratum proteins. At low effort, however, it shows no detectable next-residue
advantage over shuffled sequences and identifies none of the 15 obscure DUF
families. See [the Gemini methods, coverage, and results](gemini_experiment/README.md)
for the full extension, incomplete pilots, and limits of cross-model comparisons.

| Test | Folder | Question |
|---|---|---|
| NR | `experiments/next_residue/` | Does the model predict the next residue of an obscure protein better than of its shuffled copy? A subsample replication of Tu and Chen (2026). |
| FEAT | `experiments/features/` | Does it name Pfam domains with boundaries, transmembrane helices and signal peptides, and leave shuffled sequences blank? |
| PSEUDO | `experiments/pseudo/` | Does it notice one catalytic-residue substitution in an otherwise active enzyme? |
| STRFN | `experiments/structure/` | Does it predict secondary structure, contacts and function for recent structures stratified by prior homology? |

The manuscript is `manuscript.tex`, with a built copy in `manuscript.pdf`.

`experiments/decoy_control/` holds the decoy control for the PSEUDO test reported in the manuscript: the same substitution
at a non-catalytic position of each protein, and the PSEUDO mutants asked again on the same route. Its
`README.md` and `RESULTS.md` describe it. Its calls are not in the call totals of `expected/summary.txt`.

## Where this came from

This repository was split from the `projects/LLM_SEQUENCE_PROBE/manuscript`
folder of [`ai4curation/ai-gene-review`](https://github.com/ai4curation/ai-gene-review)
at commit `119ac18676`; the commit history of that folder is preserved here.
The tests were first run in `projects/LLM_SEQUENCE_PROBE/` there, described on its
[project page](https://github.com/ai4curation/ai-gene-review/blob/119ac1867699227b129baf1f400c10f271193475/projects/LLM_SEQUENCE_PROBE.md).
The scripts, test sets and raw model outputs have since been copied into
`experiments/` here, which is now the reproducible version. Test sets and model
outputs are byte-identical to that commit; the scoring scripts were extended.

## Reproducing the reported numbers

Needs [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/). No
network access, model access or API key is needed.

```bash
just check
```

This verifies the checksums of every test set and raw model output
including the Gemini extension (`SHA256SUMS`), re-runs the scoring scripts, and compares their output with the
committed files in `expected/`. It prints "All reported numbers reproduce." when
they match. The manuscript tables transcribe these deterministic summaries; the two original
Claude figures are generated directly from the scoring code. The figure script takes its values from the
same scoring code, and `expected/figures.txt` lists the plotted values.

```bash
just figures
```

```bash
just pdf
```

`just pdf` needs `pdflatex` and `bibtex`.

The figure script also accepts another data folder, such as a checkout of the
original project folder: `uv run python figures/make_figures.py /path/to/LLM_SEQUENCE_PROBE`.
The committed figures were made with Matplotlib 3.10.5; `uv.lock` pins that version.
A rebuild gives the same bars and values, but the PNG files can differ by about a
pixel, so they are not byte-for-byte reproducible.

## What is reproducible, and what is not

| Layer | Status |
|---|---|
| Scoring, statistics, figures | Deterministic from committed files. The bootstrap uses a fixed seed. |
| Test sets (`truth.json`, `upstream/`) | Committed exactly as drawn on 2026-11-18. The `build.py` scripts record how, but they query live UniProt, InterPro and RCSB services, so re-running them draws different entries. Do not re-run them to check the paper. |
| Model answers (`results/*.jsonl`, `gemini_experiment/results*/*/*.jsonl`) | Saved reply text and available usage metadata. Gemini retry records do not include all failed responses, their tokens, or total cost. Re-asking will not give identical answers; temperature and access routes vary and models change. |
| Function grading (`structure/function_grading.yaml`) | One unblinded manual pass, committed with a note per protein. |

## Where each number comes from

| Manuscript item | Command | Frozen output |
|---|---|---|
| Table 2 (Claude rows), thinking split, authors' accuracy on the same questions | `uv run python experiments/next_residue/score.py` | `expected/next_residue.txt` |
| No-model heuristics on all 3,340 cut points | `uv run python experiments/next_residue/baselines.py` | `expected/next_residue_baselines.txt` |
| Table 3 (Claude columns; `set all` lines for rows 3 to 7); overlap of 0.85 in the Results (`set B` lines) | `uv run python experiments/features/score.py` | `expected/features.txt` |
| Figure 1 and Table 4 (Claude models), recall of "inactive" names | `uv run python experiments/pseudo/score.py` | `expected/pseudo.txt` |
| Figure 2 and Table 6 (Claude models), structure scores with ASPRV1 counted once, function grading counts | `uv run python experiments/structure/score.py` | `expected/structure.txt` |
| Claude call totals in Methods (2,854 recorded calls; 6 listing a second model) | `uv run python experiments/summary.py` | `expected/summary.txt` |
| Values plotted in Figures 1 and 2 | `uv run python figures/make_figures.py --values-only` | `expected/figures.txt` |
| Adjudication of the two disputed active sites (YrfG, ENV9) | `uv run python experiments/pseudo/adjudication/adjudicate.py` | `expected/adjudication.txt` |
| Decoy-substitution control for the PSEUDO test (Table 5) | `uv run python experiments/decoy_control/score_decoys.py` | `expected/decoy_control.txt` |

The Gemini extension adds the following reports; the original figure and Claude
report values remain unchanged.

| Manuscript item | Command | Frozen output |
|---|---|---|
| Gemini next-residue row, feature and pseudoenzyme results, Neon structure row (and a Pro structure row not reported in the manuscript) | `uv run python gemini_experiment/score_gemini.py results_vertex` | `expected/gemini_vertex.txt` |
| Flash Lite structure row (not reported in the manuscript); other API and CLI pilots (incomplete runs identified) | `uv run python gemini_experiment/score_gemini.py results` | `expected/gemini_pilots.txt` |
| Recorded thinking tokens alongside Claude (including zeros; scored rows only) | `uv run python gemini_experiment/thinking.py` | `expected/gemini_thinking.txt` |
| Coverage, safety blocks, retries, prompt integrity, recorded route and model version | `uv run python gemini_experiment/audit.py` | `expected/gemini_audit.txt` |

## How the original Claude answers were collected

- **Date:** 2026-11-18.
- **Models:** `claude-fable-5-2`, `claude-opus-5-5`, `claude-opus-4-6`.
- **Route:** Claude Code 2.1.327 (the authors' record; the rows of 2026-11-18 do not store the version) in
  print mode, one recorded call per question (the scripts tried
  up to three times when the output was not valid JSON and kept only the last attempt):
  `claude -p --model MODEL --system-prompt "" --tools "" --effort EFFORT --output-format json`.
  `--tools ""` turns off the tool's built-in tools; on a machine with account
  connectors this route could still let connector tools into the call (see
  *Rows that record a prompt hash* below). The exact prompt is the string `P` (or
  the `prompt` function) in each test's `ask.py` or `run.py`.
- **Limits of that route:** temperature cannot be set, and the tool adds context of
  its own, whose size the rows of 2026-11-18 do not record. Measured on 2026-11-19 with the same context
  flags and Claude Code 2.1.328 (`experiments/decoy_control/results/cli_context_check.json`,
  `canary-original-flags.jsonl`): 5,851 input tokens for a one-sentence prompt to Haiku 5.5 (573 for that
  prompt with the extra flags of the revised route), and 97,813 and 6,413 for two questions with the PSEUDO
  prompt to Fable 5.2, the larger most likely because the account's connector tools were attached. Whether
  the stored calls carried such an attachment is not known: the rows record cost, not tokens, and repeated
  context is cached, so cost does not bound it.
- **Effort:** Fable 5.2 and Opus 5.5 ran at high effort in tests 2 to 4; the
  rows of the FEAT runs of 2026-11-18 do not record the effort setting. On
  2026-11-18 Opus 4.6 ran at low effort in every test; the authors record
  that it did not finish at high effort that day (that attempt left no rows). On 2026-11-19 UTC, through `call()`, Opus 4.6 was asked
  tests 2 to 4 at high effort and answered every question
  (`results/claude-opus-4-6-high.jsonl`, #51). Nine of the 30 STRFN answers
  took more than one request: eight after reaching the 64,000-token output
  limit and one after a safety-classifier stop. In the FEAT test the six answers
  that took more than one request were replaced by fresh answers, because
  the input check of that time marked them, and one of the fresh answers
  (A0A919RPG7) also took more than one request; tests 3 and 4 keep theirs
  (#104). The manuscript reports these high-effort runs for Opus 4.6 in
  tests 2 to 4 (Tables 3, 4 and 6, Figures 1 and 2) and gives the low-effort values in
  the text; both are in the Methods call totals. The NR test has low and high runs;
  for Opus 4.6 at high effort only one canary question of the NR test was asked,
  and its row is not committed.
- **Rows that record a prompt hash** (`prompt_sha256`; written from
  2026-11-19 UTC) come from `call()` in `experiments/common.py`. It adds
  four flags to the command above (`--setting-sources "" --strict-mcp-config
  --disable-slash-commands --no-chrome`), because on a machine with user
  settings and account connectors the original flags let instructions, skill
  listings or connector tools into the call. Each of these rows records the
  effort, the number of attempts, a hash of the question, the flags, the tool
  version and the time the call returned (UTC); a row with an answer also
  records the token counts and whether it was marked, and a failed call
  records the error instead. Fields were added as the code changed, so rows
  written earlier lack the later ones:
  - from commit `1ad08a5`: the tool's turn count (`num_turns`), stop reason,
    duration, and its usage records (`usage`, `model_usage`, which include
    its count of web search and fetch requests);
  - from `4d3da97`: `requests`, `context_tokens_max` and `session_id`. In rows
    written by `4d3da97` itself `requests` is wrong (1 where the turn count is
    2 or 3); the scorers read the turn count as well;
  - from `dbd62ed`: `attempt_errors` and `cost_all_attempts` on rows that
    took more than one attempt;
  - from `bf728f4`: only known top-level keys of the usage records;
  - from `c7221b5`: known keys at every level, `usage_keys_dropped` and
    `usage_unreadable` when they apply;
  - from the fix for #105: `requests_by_tokens`, and `cost_reported` when
    the tool reports a cost that is not a number (`cost` is then empty).

  A call whose input is larger than the question allows (about 600 tokens of
  the tool's own context plus the question) is marked `context_tokens_high`
  and is not scored. The allowance is loose: in the rows of the Opus 4.6
  high-effort runs scored as one request the input was 710 to 1,147 tokens
  below it, so a smaller attachment would not be marked. A row with no usage
  record, or one whose input counts are not non-negative numbers, is marked
  `usage_unreadable` and is not scored either.
- **More than one request per question.** The tool sometimes makes a second
  request by itself: when a reply reaches the model's output limit, when a
  safety classifier stops it, or when it has no visible text, it adds a
  short message saying so and asks again; and a request that fails inside
  the tool is retried without counting as a turn (#105). Its token counts
  are then sums over the requests, and its usage record lists the last
  response only. So `requests` is the turn count, plus at most one retry
  inferred from the summed input (`requests_by_tokens` records the sum
  divided by the listed response); a row is marked when the listed response
  is larger than one request may be or the sum is larger than that many
  requests; and the scorers print how many replies took more than one
  request. An attachment resent with every request is marked; one present
  only in earlier requests is marked once the sum passes that many limits
  (in real rows roughly two limits, for example about 3,700 tokens for a
  question with a limit of 1,858), and passes below that (#109, #111). A call with two or more uncounted
  retries would be marked although clean, and asked again.
- **How a reply is read** (`experiments/common.py`, used by every scorer): the
  answer is the last complete JSON object in the reply that has at least two
  of the requested keys. Three Opus 4.6 replies in the FEAT test hold two objects,
  the second a correction; `expected/features.txt` also gives the headline
  counts with the first object and with those replies left out. A reply that
  contains a written-out tool call (a shell block, a web request or tool-call
  markup) has no answer. In the NR test it is invalid and counts as wrong; in
  tests 2 to 4 it is left out like any reply without an answer, and the
  scorer lists it. There is one: the Opus 5.5 high-effort NR reply for
  A0A518ICW8 (shuffled, cut 301) is a `curl` command with an HTTP response,
  not a prediction. The stored record cannot show whether anything was run.
  Two limits: an example object written after the answer would be taken as
  the answer, and an answer wrapped in an outer object would not be found.
- **At most one scored answer per question, model, effort and run.** Fable 5.2 and
  Opus 5.5 answered the NR test at low and high effort, and Opus 4.6 answered FEAT,
  PSEUDO and STRFN at both. The decoy control asked the PSEUDO mutants and wild types
  again at the same effort on the revised route (`experiments/decoy_control/`).
  Calls marked as carrying attached context, or whose attempt failed, were
  asked again; the marked rows stay in the files and are not scored, and neither are the two rows of
  `experiments/decoy_control/results/canary-original-flags.jsonl`.
- **Calls listing a second model:** for 6 of the 2,854 recorded calls, the tool's usage
  record (the `served` field, from `modelUsage`) lists a second model besides
  the one requested. Three are Opus 5.5 next-residue calls at high effort; three
  are in the STRFN test (PDB 29BS for Fable 5.2, 15AY and 7IMP for Opus 5.5). The record
  has no per-model token counts, so it does not show which model wrote the
  answer. One of them, the Opus 5.5 call for 7IMP, returned an API error
  instead of an answer and is excluded from the scores (so Opus 5.5 has 14
  known-stratum entries). The other calls are kept in the reported
  numbers; `expected/next_residue.txt` and `expected/structure.txt` also give
  tests 1 and 4 without them.
  `expected/summary.txt` gives the totals.
- **Completed run:** the Opus 5.5 high-effort run of the NR test stopped at 264 of
  272 answers when a container restarted on 2026-11-18. The 8 missing
  questions were asked on 2026-11-19 UTC through `call()`; they are the rows
  of that file with a prompt hash.
- **Random seeds:** question sampling uses `random.Random(20261118)`; shuffled
  sequences use the upstream seed, the CRC32 of the accession.

To collect new answers (this costs money and appends to the results files, so
the checksums and expected outputs will no longer match until you run
`just checksums` and `just report`):

```bash
just ask pseudo claude-opus-5-5 high
```

A run resumes where it stopped, and results files are only ever appended to.
A failed call, an API-error reply and a call with attached context each leave
a row; the scorers skip it, `expected/summary.txt` counts it, and the next run
asks the question again. Do not start two runs on the same file. A run at
another effort stops unless it gets its own file: `--tag high` writes to
`results/MODEL-high.jsonl`. `--limit 1` asks a single question, as a canary
before a batch. `just check-calls` tests all of this, and the reply-reading
rules, against a stub in place of the `claude` tool; it calls no model.

## Third-party data

`experiments/next_residue/upstream/` holds the test set
(`confirm_sequences.tsv`) and, for the questions asked here, the stored model
answers (`authors_outputs_subset.jsonl`) from
[XinmingTu/LLM-bioseq-probe](https://github.com/XinmingTu/LLM-bioseq-probe) at
commit `0d8d086`, under the MIT licence included in that folder. Protein
sequences and annotations are from UniProt and InterPro; structures are from the
RCSB Protein Data Bank.

## Open before posting the preprint

- Author list, affiliations and funding (marked `TODO` in `manuscript.tex`).
- This repository has no licence file yet.
- Repeat runs, to measure sampling variability in tests 2 to 4.
- Matched effort and access-route comparisons across providers; labels such as
  "high" are not equivalent reasoning budgets.
- Training-cutoff evidence for any claim that a target was absent from training;
  the PDB date/homology strata alone do not establish this.
- Opus 4.6 was not asked the decoy control at high effort, and not the NR test at high effort.
- A blinded second grader for function in the STRFN test.
- The two disputed active sites (YrfG Asp9, ENV9 Ser172) have not been reported to UniProt.
- Related work is thin: protein language model baselines on the same items are
  not included.
