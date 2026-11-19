# Sequence to function with general language models

Can a general-purpose language model read a protein sequence directly? This
repository holds four small tests of Claude Fable 5.2, Claude Opus 5.5 and
Claude Opus 4.6, each given only an amino-acid sequence and no tools, together
with a draft preprint describing the results.

| Test | Folder | Question |
|---|---|---|
| 1 | `experiments/next_residue/` | Does the model predict the next residue of an obscure protein better than of its shuffled copy? A subsample replication of Tu and Chen (2026). |
| 2 | `experiments/features/` | Does it name Pfam domains with boundaries, transmembrane helices and signal peptides, and leave shuffled sequences blank? |
| 3 | `experiments/pseudo/` | Does it notice one catalytic-residue substitution in an otherwise active enzyme? |
| 4 | `experiments/structure/` | Does it predict secondary structure, contacts and function for structures released after its training? |

The manuscript is `manuscript.tex`, with a built copy in `manuscript.pdf`.

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
(`SHA256SUMS`), re-runs the scoring scripts, and compares their output with the
committed files in `expected/`. It prints "All reported numbers reproduce." when
they match. Every number in the manuscript and both figures come from these
scripts; none is typed in by hand.

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

## What is reproducible, and what is not

| Layer | Status |
|---|---|
| Scoring, statistics, figures | Deterministic from committed files. The bootstrap uses a fixed seed. |
| Test sets (`truth.json`, `upstream/`) | Committed exactly as drawn on 2026-11-18. The `build.py` scripts record how, but they query live UniProt, InterPro and RCSB services, so re-running them draws different entries. Do not re-run them to check the paper. |
| Model answers (`results/*.jsonl`) | Committed in full, including raw reply text, thinking-token counts, cost and the models listed in each call's usage record. Re-asking will not give identical answers: the route used does not expose temperature, and models change. |
| Function grading (`structure/function_grading.yaml`) | One unblinded manual pass, committed with a note per protein. |

## Where each number comes from

| Manuscript item | Command | Frozen output |
|---|---|---|
| Table 1, thinking split, authors' accuracy on the same questions | `uv run python experiments/next_residue/score.py` | `expected/next_residue.txt` |
| No-model heuristics on all 3,340 cut points | `uv run python experiments/next_residue/baselines.py` | `expected/next_residue_baselines.txt` |
| Table 2 (`set all` lines for rows 3 to 7); overlap of 0.85 in the abstract and Results (`set B` lines) | `uv run python experiments/features/score.py` | `expected/features.txt` |
| Figure 1, mutant positions flagged, recall of "inactive" names | `uv run python experiments/pseudo/score.py` | `expected/pseudo.txt` |
| Figure 2, structure scores with ASPRV1 counted once, function grading counts | `uv run python experiments/structure/score.py` | `expected/structure.txt` |
| Call totals in Methods (2,570 calls; 6 listing a second model) | `uv run python experiments/summary.py` | `expected/summary.txt` |

## How the model answers were collected

- **Date:** 2026-11-18.
- **Models:** `claude-fable-5-2`, `claude-opus-5-5`, `claude-opus-4-6`.
- **Route:** Claude Code 2.1.327 in print mode, one call per question:
  `claude -p --model MODEL --system-prompt "" --tools "" --effort EFFORT --output-format json`.
  No tools were available to the model. The exact prompt is the string `P` (or
  the `prompt` function) in each test's `ask.py` or `run.py`.
- **Limits of that route:** temperature cannot be set, and the tool adds about
  1,400 tokens of its own context to each call.
- **Effort:** recorded per answer. Fable 5.2 and Opus 5.5 ran at high effort in
  tests 2 to 4; Opus 4.6 ran at low effort because it did not finish at high
  effort. Test 1 has low and high runs.
- **One answer per question.** There are no repeat runs.
- **Calls listing a second model:** for 6 of the 2,570 calls, the tool's usage
  record (the `served` field, from `modelUsage`) lists a second model besides
  the one requested. Three are Opus 5.5 next-residue calls at high effort; three
  are in test 4 (PDB 29BS for Fable 5.2, 15AY and 7IMP for Opus 5.5). The record
  has no per-model token counts, so it does not show which model wrote the
  answer. One of them, Opus 5.5 on 7IMP, returned an API error instead of an
  answer and is counted as unanswered. These calls are kept in the reported
  numbers; `expected/next_residue.txt` and `expected/structure.txt` also give
  tests 1 and 4 without them.
  `expected/summary.txt` gives the totals.
- **Incomplete run:** the Opus 5.5 high-effort run of test 1 has 264 of 272
  answers; a container restart stopped it.
- **Random seeds:** question sampling uses `random.Random(20261118)`; shuffled
  sequences use the upstream seed, the CRC32 of the accession.

To collect new answers (this costs money and appends to the results files, so
the checksums and expected outputs will no longer match until you run
`just checksums` and `just report`):

```bash
just ask pseudo claude-opus-5-5 high
```

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
- Repeat runs, to give intervals for tests 2 to 4.
- Opus 4.6 at high effort, for a like-for-like comparison.
- A blinded second grader for function in test 4.
- Two enzymes where both models disagree with the curated active-site position
  (Q08651, P64636) have not been adjudicated.
- Related work is thin: protein language model baselines on the same items are
  not included.
