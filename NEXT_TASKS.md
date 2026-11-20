# Next tasks: manuscript text

This file tracks edits to the manuscript text (`manuscript.tex`, `references.bib`,
the README's prose about the paper) and decisions the authors must take about
wording. GitHub issues track code, data and scoring; an issue may point here for
the text edit that goes with it, and an item here names its issue.

Line numbers refer to `manuscript.tex` on `main` at 21c86e0 (2026-11-19) and drift
as the text changes; each item also quotes enough to find the place.

Status: `open`, `decide` (authors' call before anyone edits), `done` (say where).

## Before posting the preprint

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T1 | decide | Data availability names a private repository. Make it public or cite an archived release (DOI), then reword the statement. The licence itself is code work. | Data and code availability, l. 365–368 | #27 |
| T2 | open | Affiliations (l. 13–14) and funding (l. 378) are still marked TODO; the author list is in (#113). | front matter, Acknowledgements | README "Open before posting" |
| T3 | decide | Acknowledgements for the Gemini runs: confirm the Antigravity/Codex attribution. This text arrives with #115 (not on `main` yet). | Acknowledgements (PR #115) | #154 |

## Methods and route

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T4 | open | "adds about 1,400 tokens of its own context": the saved check (Haiku 5.5, one-sentence prompt, 2026-11-19) measured 5,851 input tokens per call on the original flags (4 runs) and 573 with the four extra flags (2 runs); one Fable 5.2 canary call on the original flags carried 97,813 (input plus cache tokens). State the measured figures or drop the number. | Models and access, l. 66–67 | `experiments/decoy_control/results/cli_context_check.json`, `canary-original-flags.jsonl`; #13 |
| T5 | decide | "Given only an amino-acid sequence and no tools" (abstract, l. 23), "no alignment and no tools" (l. 294) and `README.md:5`: the Methods now say built-in tools were turned off, and connector tools could reach a call on the original route. Keep, qualify or reword. | l. 23, l. 294, README l. 5 | #128 (the docstring part is fixed on `main`) |
| T6 | decide | "Model calls used Claude Code 2.1.327": no row of the original route records a tool version. Qualify, or cite a record of the original runs. | l. 372 | #122 |
| T7 | open | "Each question was one call" and "2,854 calls" count recorded rows; CLI retries in the original scripts were not recorded. Say "recorded answers", or say that retries are not counted. | l. 66, l. 80; README l. 82, 90, 182 | #40 |
| T8 | decide | Effort match for test 2 rests on a setting the rows do not record. Qualify "at the same effort setting" (l. 29), "matched for effort" (l. 329) and the low-versus-high test-2 contrast (l. 189–191), or leave as is. | l. 29, 189–191, 329 | #129 |
| T9 | open | State for the authors, from the PR #98 review: the six re-sampled test-2 answers (first answers give 29/60, not 28/60, shuffled with a domain); test 4 basis (12-protein set); bootstrap bound moves with the seed; two dates that cannot be shown from the files. Decide which to say. | Results test 2 and 4; Methods | #104 |
| T10 | decide | Scoring of answers that took more than one request, and of replies stopped by a safety classifier: the decision is the authors'; the text should then say what was done. The scorer side stays in #83. | Methods, Limitations | #83 |

## Results wording

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T11 | open | Opus 4.6 at high effort is above the single-state guess on the known stratum (Q3 57.8% against 55.4%, `expected/structure.txt`); the text mentions only the novel stratum. | Results test 4, l. 284–290 | #123 item 2 |
| T12 | open | Repeat counts: for Opus 4.6 the test-3 mutants and wild types were asked three times (low, high, low rerun). Check that the Limitations (l. 346–350) and README wording still hold after #125. #136 also said "later rows" holds within a file, not across files by time; l. 77 now reads "rows written by later versions of the revised route's code", so check whether that point is already settled. | l. 77, 346–350; README | #136 items 1–2 |
| T13 | decide | The two disputed active sites in test 3 (YrfG, ENV9): adopt the adjudication text in PR #138. | Results test 3 | PR #138 |

## Framing and references

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T14 | decide | Pseudoenzyme framing edits (introduction definition, test 3 naming, Discussion bounds, a limitation, seven references). Applied on the PR #18 branch, which also contains the PR #138 branch: merge #138 first. | Introduction, test 3, Discussion, Limitations, `references.bib` | PR #18 |
| T15 | open | Before T14 lands: read the full text of the seven pseudoenzyme references (only abstracts were read), confirm the WNK1, MEROPS and Gene Ontology statements, and pin the UniProt release behind the counts. | `review/pseudoenzyme_framing_v1.md` (PR #18) | #19 |
| T16 | open | Related work is thin: no protein language model baselines on the same items. Add a sentence or a comparison. | Introduction, Discussion | README "Open before posting" |

## Review notes (PR #1)

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T17 | decide | Go through `review/editing_recommendations_v1.md` and mark which recommendations are already applied by #112, #114 and #125, which to apply and which to drop. | PR #1 branch | PR #1 |
| T18 | open | Correct the critique where it overstates what it verified (Table 2 IoU 0.87; the "17 of 18" count; M10 stale after #8) and its two counting slips (multi-run replies over all conditions; Opus 4.6 gave 1 "uncertain" in the natural-pseudokinase cell). Or close PR #1 and record these here. | `review/critique_content_v1.md` (PR #1) | #32, #33 |

## Done

(Move items here with the commit or PR that did them.)
