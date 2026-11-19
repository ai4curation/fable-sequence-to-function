# Decoy-substitution control for the catalytic-activity test

Added 2026-11-18. One of the three models tested here, Claude Fable 5.2, also wrote these scripts and this
note, so a second reader should check the decoy rule and the scoring.

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
| `uniprot_features_snapshot.json` | The UniProt feature tables the rule used, fetched anonymously on 2026-11-18. |
| `decoys.json` | 58 decoy sequences for 38 proteins, with the position, the number of candidates and the motif positions that were excluded. |
| `ask_decoys.py` | Asks a model. The question is read from the original `pseudo/ask.py` as text, so the wording is identical. |
| `score_decoys.py` | Prints the result tables. |
| `results/MODEL.jsonl` | One line per decoy answer, with token counts, cost and the CLI version. |
| `results/bridge-MODEL.jsonl` | Original mutants rerun on this route, to check that it gives the same answers as the stored run. |
| `results/canary-original-flags.jsonl` | The first two calls, made with the original flags. Not scored; kept as the record of the route problem below. |

## How to run

`PROBE_DIR` is a checkout of `projects/LLM_SEQUENCE_PROBE` from `ai4curation/ai-gene-review`. The original
answers used here are from commit `119ac18676`.

```bash
python3 experiments/decoy_control/build_decoys.py PROBE_DIR          # only to rebuild; decoys.json is committed
python3 experiments/decoy_control/ask_decoys.py PROBE_DIR claude-fable-5-2 high
python3 experiments/decoy_control/ask_decoys.py PROBE_DIR claude-opus-5-5 high
python3 experiments/decoy_control/ask_decoys.py PROBE_DIR claude-opus-4-6 low
python3 experiments/decoy_control/score_decoys.py PROBE_DIR
```

Efforts match the original run. `ask_decoys.py` bills each call to the signed-in account and resumes if stopped.
Add `--only ACCESSION:VARIANT` for a single call, and `--set original` to rerun the original mutants.

## The decoys

- **Kinases (20):** one Asp to Asn and one Lys to Met, each inside the UniProt "Protein kinase" domain.
- **Other enzymes (18 of 20):** one residue of the same type as the curated active-site residue, changed to Ala.
  Two enzymes (Q46925, P00358) have a catalytic Cys and no other unannotated Cys, so they have no decoy.
- **Excluded positions:** within three residues of any UniProt active site, binding site, site, modified residue,
  disulfide bond, cross-link, lipidation, glycosylation or mutagenesis feature; inside a cleaved peptide; and,
  for kinases, the catalytic loop, the DFG motif and the invariant Asp of subdomain IX.
- **Choice:** one position drawn from the remainder with a generator seeded by accession and variant. The rule
  was fixed before any model saw a decoy.

**Limit of the label.** A decoy position has no functional annotation. That is not a measurement that the
substitution is harmless. Some decoys fall in conserved stretches, and a few may reduce activity or stability
in the real protein. A model that calls such a decoy inactive is not necessarily wrong.

## The route, and a finding about it

The original run called `claude -p --model M --system-prompt "" --tools "" --effort E --output-format json`.
On the machine used here (CLI 2.1.328, 2026-11-18) that command does not isolate the question:

| Flags | What reached the model with a one-sentence prompt |
|---|---|
| Original, connectors ready in time | 97 connector tools attached; 97,266 input tokens |
| Original, connectors not ready | No tools; 5,866 input tokens (user instructions and skill listings) |
| Original plus `--setting-sources "" --strict-mcp-config --disable-slash-commands --no-chrome` | No tools; 588 input tokens |

`--tools ""` removes the built-in tools only. Whether connector tools are attached depends on timing, so two
identical calls can differ. The remaining 588 tokens are an environment block the CLI adds even with an empty
system prompt; the model described it as naming the working directory, platform, shell, date and model, with
some file-handling guidance. Removing it needs `--bare`, which needs an API key.

All scored calls here use the four extra flags. The full question for one kinase then arrived with 1,133 input
tokens. `ask_decoys.py` marks any call above 2,500 input tokens and `score_decoys.py` leaves it out.

**What this means for the stored run.** Its rows do not record input tokens. No test 3 call in it cost more than
$0.40 for Fable 5.2, and a call with the 97 tools attached cost $1.69 here, so tools of that size were not
attached there. Whether a few thousand tokens of user instructions were present cannot be told from the stored
rows. This is an inference from cost, not a measurement.

## Results

See `RESULTS.md`, written from the output of `score_decoys.py`.
