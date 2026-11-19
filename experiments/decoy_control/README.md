# Decoy-substitution control for the catalytic-activity test

First committed on 2026-11-18 by the committer's clock; the first calls returned at 01:53 UTC on
2026-11-19. Two of the three models tested here worked on it: Claude Fable 5.2 wrote the scripts and the first version of these notes, and Claude
Opus 5.5 revised them after review. A human reader should check the decoy rule and the scoring. Times below are
UTC unless marked.

## Question

Test 3 of the manuscript changes a catalytic residue and asks whether the protein is still active. The models
call wild types active and catalytic-site mutants inactive. That contrast cannot separate two readings:

1. the model sees that the catalytic residue is gone;
2. the model sees that the sequence differs from one it knows, and calls any changed sequence inactive.

The original set has no substitution at a non-catalytic position. This control adds one per original mutant:
the same substitution type, in the same protein, at a position with no functional annotation. Reading 1
predicts that decoys are still called active and that the decoy position is not named as a lost catalytic
residue. Reading 2 predicts the opposite.

## Files

| File | What it is |
|---|---|
| `build_decoys.py` | Picks the decoy positions by a seeded rule and writes `decoys.json`. The rule is in its header. |
| `uniprot_features_snapshot.json` | The UniProt feature tables the rule used, fetched anonymously by `build_decoys.py`. |
| `decoys.json` | 58 decoy sequences for 38 proteins, with the position, the number of candidates and the motif positions that were excluded. |
| `ask_decoys.py` | Asks a model through `call()` in `experiments/common.py`. The question is read from `pseudo/ask.py` as text, so the wording is identical. |
| `score_decoys.py` | Prints the result tables; `just check` compares them with `expected/decoy_control.txt`. |
| `check_cli_context.py` | Measures what the command line attaches to a one-sentence prompt; writes `results/cli_context_check.json`. |
| `results/MODEL.jsonl` | One line per decoy answer, with token counts, cost and the CLI version. |
| `results/bridge-MODEL.jsonl` | The catalytic-site mutants and wild types of the 40 kinases and enzymes of test 3, asked again on this route (100 questions per model, returned 2026-11-19 07:20 to 07:38 UTC; one Fable 5.2 row at 01:56), so that decoys and mutants are compared within one route. |
| `results/canary-original-flags.jsonl` | The first two calls, made with the original flags. Not scored; kept as the record of the route problem below. |

## How to run

The question and the stored answers of test 3 are read from `experiments/pseudo/`. `build_decoys.py` still
takes that folder's parent as its argument.

```bash
python3 experiments/decoy_control/build_decoys.py experiments          # only to rebuild; decoys.json is committed
python3 experiments/decoy_control/ask_decoys.py claude-fable-5-2 high
python3 experiments/decoy_control/ask_decoys.py claude-opus-5-5 high
python3 experiments/decoy_control/ask_decoys.py claude-opus-4-6 low
python3 experiments/decoy_control/ask_decoys.py claude-fable-5-2 high --set original   # and the other two models
python3 experiments/decoy_control/score_decoys.py
```

Efforts match the original run. `ask_decoys.py` bills each call to the signed-in account. Its files are
append-only and a run resumes: a failed or marked call leaves a row, and its question is asked again. Add
`--limit 1` for a single canary call, `--only ACCESSION:VARIANT` for named items, `--set original` for the
mutants and wild types of test 3, and `--tag NAME` for a run at another effort, which needs its own file.
`just check-calls` tests the script against a stub in place of the `claude` tool.

## The decoys

- **Kinases (20):** one Asp to Asn and one Lys to Met, each inside the UniProt "Protein kinase" domain.
- **Other enzymes (18 of 20):** one residue of the same type as the curated active-site residue, changed to Ala.
  Two enzymes (Q46925, P00358) have a catalytic Cys and no other unannotated Cys, so they have no decoy.
- **Excluded positions:** within three residues of any UniProt active site, binding site, site, modified residue,
  disulfide bond, cross-link, lipidation, glycosylation or mutagenesis feature; inside a cleaved peptide; and,
  for kinases, the catalytic loop, the DFG motif and the invariant Asp of subdomain IX.
- **Choice:** one position drawn from the remainder with a generator seeded by accession and variant.
- **When the rule was set:** it was revised twice after looking at which positions it picked (the DFG pattern
  was widened and the subdomain IX exclusion added), and last changed before the first model call. Git cannot
  show this: the first commit of the rule is later than the first call, and answer rows do not store the
  sequence. `decoys.json` has not changed since that first commit.
- **Known gaps:** the subdomain IX pattern finds nothing in 7 of the 20 kinases, so their invariant Asp stayed a
  candidate, though none was drawn. Enzyme decoys have no domain restriction, and some are easy: one is the
  second-to-last residue (P26725), one lies in a disordered region (P23594) and one in a transmembrane helix
  (Q8RX88).

**Limit of the label.** A decoy position has no functional annotation. That is not a measurement that the
substitution is harmless. Some decoys fall in conserved stretches, and a few may reduce activity or stability
in the real protein. A model that calls such a decoy inactive is not necessarily wrong.

## The route, and a finding about it

The original run called `claude -p --model M --system-prompt "" --tools "" --effort E --output-format json`.
On the machine used here (CLI 2.1.328, 2026-11-19 UTC) that command does not isolate the question.

Saved evidence, from `check_cli_context.py` (one-sentence prompt, cheapest model, `results/cli_context_check.json`):

| Flags | Runs | Tools attached | Input tokens |
|---|---|---|---|
| Original | 4 | 0 (seven account connectors still pending) | 5,851 each |
| Original plus `--setting-sources "" --strict-mcp-config --disable-slash-commands --no-chrome` | 2 | 0 (no connectors) | 573 each |

Saved evidence, from the first two canary calls with the original flags (`results/canary-original-flags.jsonl`):
the first carried 97,813 input tokens and cost $1.69; the second, 23 seconds later (01:53:36 and 01:53:59), carried 6,413
and cost $0.21.
The two calls had different sequences of the same length, so the 91,400-token gap is not the question.

Seen once and not saved: a one-sentence call with the original flags whose start-up record listed 97 tools, all
from account connectors, with the connectors connected, and 97,266 input tokens. The four saved runs above did
not repeat it. The reading that fits all of this is that `--tools ""` removes only the built-in tools and that
connector tools are attached when the connectors finish connecting before the request is sent. That is an
interpretation of three observations, not a documented behaviour.

The remaining 573 tokens are added by the CLI even with an empty system prompt. Asked to describe them, the
model listed account context, environment details (working directory, operating system, shell, date), guidance
on handling downloaded files, the model name and knowledge cutoff, and a token budget note. That is the model's
own account. The CLI help says `--bare` skips more, and that it accepts only an API key; it was not tried.

All scored calls here use the four extra flags. A full kinase question then arrived with 1,128 to
1,414 input tokens for Fable 5.2 and Opus 5.5 and 871 to 1,056 for Opus 4.6, depending on the length of the sequence. The decoy rows (returned 01:56 to 02:06) were marked above
2,500 input tokens; rows written since are marked by `call()` in `experiments/common.py` when the input is
larger than the question allows, and
`score_decoys.py` leaves marked rows out. None of the 174 decoy calls and none of the 300 rerun calls is marked
under either limit.

**What this means for the stored run.** Its rows do not record input tokens. No test 3 call in it cost more than
$0.40 for Fable 5.2, and a call with the 97 tools attached cost $1.69 here, so tools of that size were not
attached there. This is an inference from cost, not a measurement. The independent reviewer of this folder
went further: fitting cost to tokens on the rows here and applying it to the stored rows, every stored call
costs slightly more than this route predicts, by a near-constant amount that would correspond to several
hundred more input tokens per call. That estimate has not been rechecked here. The mutants and wild types have
since been asked again on this route (`results/bridge-MODEL.jsonl`), and `RESULTS.md` compares the decoys with
those answers. The rerun gave the same call as the stored run for 99, 96 and 88 of 100 questions (Fable 5.2,
Opus 5.5, Opus 4.6 at low effort); with one answer per question that cannot separate the route from run-to-run
variation.

## Results

See `RESULTS.md`, written from `expected/decoy_control.txt`, the output of `score_decoys.py`.
