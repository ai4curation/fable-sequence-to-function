# Gemini extension, 19 November 2026

These runs reuse the original test sets and sequence prompts. The main result is
that Gemini 4 Neon detects kinase substitutions (low effort) and predicts secondary
structure and contacts above baseline (medium effort), but at low effort shows no
detectable real-minus-shuffled next-residue advantage and identifies none of the 15
obscure DUF families. Opus 5.5 at low effort also showed no detectable advantage, but
Neon thought on every test-1 question and Opus 5.5 at low effort on none, so the
effort labels do not match and the result is not attributed to model or setting. Flash Lite at high effort is below
both structure baselines on the novel stratum.
Model identifiers below are those recorded by the endpoints; they are not claims
about public availability, training dates, or comparable reasoning budgets.

## Reproduce without calling a model

From the repository root:

```sh
just check
uv run python gemini_experiment/score_gemini.py results_vertex
uv run python gemini_experiment/score_gemini.py results
uv run python gemini_experiment/audit.py
```

`SHA256SUMS` covers every saved JSONL file here. The three commands above are also
part of `just report` and `just check`, with frozen output in
`expected/gemini_vertex.txt`, `expected/gemini_pilots.txt`, and
`expected/gemini_audit.txt`. The structure scores use the original scorer directly;
other tests follow its original rules and share `experiments/common.py` for JSON
answer extraction; their rules are copied from `experiments/*/score.py`, so change
both together. The audit checks that every Gemini question is one of the Claude
questions (equal prompt hashes wherever a Claude row records one: 8 test-1, 126
test-2, 120 test-3 and 30 test-4 rows; equal targets and families for all 272 test-1
questions), that each row's model and effort match its file name, that usable
replies parse, and that the stored next-residue scores recompute
(`scripts/adhoc/mutation_check_gemini_audit.sh` plants one defect of each kind and
shows that the audit fails on it). It also checks each test-1 row's family and, for
API rows, that the endpoint's model version equals the requested model. It does not authenticate the remote service or establish
training-data independence.

## Runs and coverage

| Route / directory | Model and effort | Tests and usable questions |
|---|---|---|
| Vertex AI / `results_vertex` | Gemini 4 Neon, low | Next residue 271/272; features 120/120; pseudoenzymes 120/120 |
| Vertex AI / `results_vertex` | Gemini 4 Neon, medium | Structure 30/30 |
| Vertex AI / `results_vertex` | Gemini 3.1 Pro Preview, high | Structure 30/30 |
| Gemini REST API / `results` | Gemini 3.1 Flash Lite, high | Pseudoenzymes 120/120; structure 30/30 |
| Antigravity CLI / `results` | Gemini 4 Neon, medium | Incomplete pilots: features 70/120; pseudoenzymes 58/120 |
| Gemini REST API / `results` | Gemini 2.5 Flash and Gemini 3 Flash Preview, high | Incomplete structure pilots: 13/30 and 7/30 |
| Vertex AI / `results_vertex` | Gemini 4 Carbon, medium | Incomplete structure pilot: 1/30 |

The incomplete pilots are kept and scored for transparency; they are not
full-test performance estimates. The Carbon pilot sits in `results_vertex/` and the
complete Flash Lite runs sit in `results/` with the pilots; the file name, not the
folder, says which is which. The two CLI pilots carried median inputs of about
9,800 and 9,900 tokens per call, against a few hundred
for the question alone; nothing in the rows says what that context was. Their item subsets differ. The CLI pilots were
stopped after unwanted authentication windows; the Flash and Carbon pilots were
limited by quota/resource errors. The retained files do not contain every failed
diagnostic call mentioned in the interactive session.

## Main findings

- **Next residue:** Neon low effort scores 8.8% on real and 10.4% on shuffled
  sequences. The family-averaged gap is -1.5 percentage points (95% bootstrap
  interval -8.1 to +5.1; 68 families; rows are scored in question order, #142). There are no exact ten-residue matches.
  One shuffled question (A0A6J4GRP3, cut 445) was safety-blocked and excluded.
  There was no reversed-sequence run. This is absence of a detectable advantage
  in this configuration, not evidence that all Gemini configurations lack it.
- **Features:** Neon identifies a correct Pfam family in 20/45 sampled proteins
  and 0/15 obscure DUFs. Of 28 predicted domains, 23 have the right accession
  (82.1%); boundary IoU on those 23 is 0.802. No shuffled sequence receives a
  Pfam domain (0/60). All 74 reference membrane helices are recovered under the
  >=10-residue overlap rule, but 82 helices are predicted; counts are exact for
  54/60 proteins. Signal-peptide calls give 9 TP, 0 FN, 0 FP, and 51 TN.
- **Pseudoenzymes:** All 20 kinase wild types are called active; all 20 Asp-to-Asn
  mutants are called inactive with the mutated position flagged. For Lys-to-Met,
  16/20 are called inactive and flagged; 4/20 remain active. Natural pseudokinases
  are called inactive in 19/20 cases, all 19 also named inactive/pseudokinase in
  the response. Kin-32 (Q95YD4) is the shared active call across Neon, Fable, and
  Opus 5.5; this alone does not adjudicate the reference annotation. Non-kinase
  wild types receive 18 yes, 1 no, and 1 uncertain; alanine mutants receive
  8 yes, 11 no, and 1 uncertain, with 11/20 mutated positions flagged.
- **Structure:** With ASPRV1 counted once, Neon medium reaches 69.0% Q3 and 28.4%
  long-range contact precision on 12 novel-stratum proteins (baselines 56.6% and
  1.8%); its top-five contact precision is 43.3%. On 15 known-stratum proteins,
  Q3 is 78.6%, contact precision 48.0%, and top-five precision 54.7%. Gemini 3.1
  Pro reaches 60.7%/12.6% on the novel stratum; Flash Lite reaches 43.7%/1.0%.
  These are descriptive comparisons across model classes, routes, and efforts.

## Function calls: qualitative review, not a new aggregate grade

Neon correctly names the polynucleotide kinase family for 9ZWQ and the
AHL-responsive LuxR regulator family for 10ZI. For the retained ASPRV1 entry
(27IK), it predicts a retroviral-like aspartic protease but names DDI2 and assigns
DDI2-specific substrate biology. That supports family-level recognition only;
the specific identity/function is wrong. It names ASPRV1 correctly in 27JP, a
repeat excluded from the distinct-protein score. It does not identify the
catalytic substitution in 27IQ. Other concrete errors include a TyrA-family
dehydrogenase assignment to PanG (37QB), and a metabolic-enzyme assignment to
Rpp30 (10CW). Generic guesses must not automatically be described as abstentions.
No new function-accuracy count is claimed without a recorded, consistent grading
pass. The original Claude grading remains in `experiments/structure/function_grading.yaml`.

## Collection and interpretation limits

`run_vertex.py` calls the global Vertex AI `generateContent` endpoint using an
existing `gcloud auth print-access-token` credential. Its request body contains
the sequence prompt and thinking level, with no tools or system instruction.
`run_api.py` uses the Gemini REST API with `GEMINI_API_KEY`; `run_agy.py` records
the earlier CLI route, which added `Do not call or invoke any tools.` to the
base prompt. CLI hashes cover the base prompt only. Do not pool these routes.
Offline reproduction needs neither credentials nor authentication windows.

The JSONL records preserve reply text, prompt hashes, effort (or a CLI model name
encoding effort), times, attempt counts, and available token/model metadata.
Retries are transport/error recovery, not deliberate independent replicates.
Intermediate failed attempts and their token usage were not fully retained; costs
and total billed requests cannot be reconstructed. The scripts evolved during
collection: for example, some Pro rows record four attempts although the final
Vertex runner defaults to three. Current code is not an exact snapshot of every
historical invocation. No temperature was specified. Successful API responses
used here all finish with `STOP`. One rule, `agy_unusable` in `run_agy.py`, decides
both which questions the runners ask again on resume and which rows the scorer and
the audit count: an error, a status other than SUCCESS, a turn count other than 1,
or a finish other than `STOP` (#144). For the 2.5 models, `run_api.py` sends a
thinking budget (`high` = 8,192 tokens) rather than a thinking level; rows record
only the requested label (#141).

Six Neon test-1 rows (A0A8J3A1V5 shuffled cuts 276 and 280, A0A6J4GRP3 real cuts
445 and 484, A0A0H3J4F4 real cut 185 and shuffled cut 224, all asked between
16:27:29 and 16:29:55 UTC, a window in which 144 of the 272 rows were asked) record 764 to 921 input tokens, 1.3 to 1.9 per prompt
character, against at most 0.5 for the other 265. What the extra input was is not
known (#143).

The novel stratum means no PDB entity at >=30% identity released before
2026-06-01, with targets released from 2026-08-01. It is not proof that a target
was absent from Gemini training, or that its sequence or distant homologs were
unseen. Cross-provider effort labels are not equivalent; the original Claude CLI
also carried additional context. The observed differences do not isolate model
generation, architecture, training exposure, or reasoning effort.

Structure scores are per-protein averages over observed residues and eligible
predicted contacts, with the original scorer's filtering. For example, unresolved
residues leave 17 eligible pairs for Neon's 9T71 answer. The random-contact
baseline is a weak reference, not a dedicated structure-prediction method.
Repeated stochastic runs, matched effort/route comparisons, and blinded function
grading remain follow-up work.
