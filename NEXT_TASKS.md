# Next tasks: manuscript text

This file tracks edits to the manuscript text (`manuscript.tex`, `references.bib`,
the README's prose about the paper) and decisions the authors must take about
wording. GitHub issues track code, data and scoring; an issue may point here for
the text edit that goes with it, and an item here names its issue.

Line numbers refer to `manuscript.tex` on `main` at 21c86e0 (2026-11-19) and drift
as the text changes (they are badly out of date after the readability edit of 2026-11-20, #198); each item
also quotes enough to find the place. Updated 2026-11-21 after #183, #188 and #209. Main has since been restructured (tests renamed NR, FEAT, PSEUDO, STRFN; strata unmatched and matched), so quoted wording in older items may have moved or changed.

Status: `open`, `decide` (authors' call before anyone edits), `done` (say where).

## Before posting the preprint

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T1 | open | The repository is now public (checked 2026-11-21), and the Data availability names it and the results site. Still missing: a licence file, a tagged release and an archived DOI (for example Zenodo). Add those, then cite the DOI. | Data and code availability, l. 365–368 | #27 |
| T2 | done | Affiliation and funding are in (Lawrence Berkeley National Laboratory; DOE contract DE-AC02-05CH11231), done by #200 and #228. | front matter, Acknowledgements | README "Open before posting" |
| T3 | done | #228 removed the agent and Antigravity/Codex sentences, leaving the Acknowledgements funding-only, and closed #154. | Acknowledgements (PR #115) | #154 |

## Methods and route

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T4 | done | "adds about 1,400 tokens of its own context": the saved check (Haiku 5.5, one-sentence prompt, 2026-11-19) measured 5,851 input tokens per call on the original flags (4 runs) and 573 with the four extra flags (2 runs); one Fable 5.2 canary call on the original flags carried 97,813 (input plus cache tokens). State the measured figures or drop the number. | Models and access, l. 66–67 | `experiments/decoy_control/results/cli_context_check.json`, `canary-original-flags.jsonl`; #13 |
| T5 | done | "Given only an amino-acid sequence and no tools" (abstract, l. 23), "no alignment and no tools" (l. 294) and `README.md:5`: the Methods now say built-in tools were turned off, and connector tools could reach a call on the original route. Keep, qualify or reword. | l. 23, l. 294, README l. 5 | #128 (the docstring part is fixed on `main`) |
| T6 | done | "Model calls used Claude Code 2.1.327": no row of the original route records a tool version. Qualify, or cite a record of the original runs. | l. 372 | #122 |
| T7 | done | "Each question was one call" and "2,854 calls" count recorded rows; CLI retries in the original scripts were not recorded. Say "recorded answers", or say that retries are not counted. | l. 66, l. 80; README l. 82, 90, 182 | #40 |
| T8 | done | Effort match for test 2 rests on a setting the rows do not record. Qualify "at the same effort setting" (l. 29), "matched for effort" (l. 329) and the low-versus-high test-2 contrast (l. 189–191), or leave as is. | l. 29, 189–191, 329 | #129 |
| T9 | open | Left from the PR #98 review: the six re-sampled FEAT answers (the first answers give 29/60, not 28/60, shuffled with a domain) are not stated with that figure, and the bootstrap seed is not mentioned. The STRFN 12-protein basis and the dates are now handled. | Results test 2 and 4; Methods | #104 |
| T10 | done | Scoring of answers that took more than one request, and of replies stopped by a safety classifier: the decision is the authors'; the text should then say what was done. The scorer side stays in #83. | Methods, Limitations | #83 |

## Results wording

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T11 | done | Opus 4.6 at high effort is above the single-state guess on the known stratum (Q3 57.8% against 55.4%, `expected/structure.txt`); the text mentions only the novel stratum. | Results test 4, l. 284–290 | #123 item 2 |
| T12 | done | Repeat counts: for Opus 4.6 the test-3 mutants and wild types were asked three times (low, high, low rerun). Check that the Limitations (l. 346–350) and README wording still hold after #125. #136 also said "later rows" holds within a file, not across files by time; l. 77 now reads "rows written by later versions of the revised route's code", so check whether that point is already settled. | l. 77, 346–350; README | #136 items 1–2 |
| T13 | done | The two disputed active sites in test 3 (YrfG, ENV9): adopt the adjudication text in PR #138. | Results test 3 | PR #138 |

## Framing and references

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T14 | done | Pseudoenzyme framing edits (introduction definition, test 3 naming, Discussion bounds, a limitation, seven references). Applied on the PR #18 branch, which also contains the PR #138 branch: merge #138 first. | Introduction, test 3, Discussion, Limitations, `references.bib` | PR #18 |
| T15 | open (part done) | Read the five pseudoenzyme references checked by abstract only (Xu 2000, Murphy 2017, Adrain 2020, Ribeiro 2019 and 2020) in full. The other three were read in full, and the UniProt release is pinned (#183). | `review/pseudoenzyme_framing_v1.md` (PR #18) | #19 |
| T16 | decide | Related work now has a PG-LLM paragraph and says no specialised tools or protein language models were benchmarked. What is left is a decision: run a baseline, or leave it as a stated limitation. | Introduction, Discussion | README "Open before posting" |

## Review notes (PR #1)

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T17 | decide | Go through `review/editing_recommendations_v1.md` and mark which recommendations are already applied by #112, #114 and #125, which to apply and which to drop. | PR #1 branch | PR #1 |
| T18 | open | Correct the critique where it overstates what it verified (Table 2 IoU 0.87; the "17 of 18" count; M10 stale after #8) and its two counting slips (multi-run replies over all conditions; Opus 4.6 gave 1 "uncertain" in the natural-pseudokinase cell). Or close PR #1 and record these here. | `review/critique_content_v1.md` (PR #1) | #32, #33 |

## Added 2026-11-20

| # | Status | Task | Where | Source |
|---|---|---|---|---|
| T19 | done | Done in #183. The abstract has since been rewritten (c114542) and names no model; its "frontier models" claim is about performance above chance, not the curator-flag claim T19 was about. | Abstract, last sentence | #183 |
| T20 | done | README table row back to "Claude call totals". | README | #183 |
| T21 | open | Before posting, remove the remaining LaTeX author note: MEROPS/GO in the Discussion ("% NOTE for the authors (T15 source check …"). The T3 note went with #228. | Acknowledgements, Discussion | #183 review |
| T22 | open | Methods, decoy control: "in kinases, the catalytic loop, the DFG motif and the subdomain IX aspartate" were excluded. The subdomain IX pattern finds nothing in 7 of 20 kinases, so there the Asp stayed a candidate (none was drawn). Say "where the pattern finds it". | Methods, decoy control | #14 |
| T23 | open | Limitations: some enzyme decoys are easy (the second-to-last residue of P26725, a disordered region in P23594, a transmembrane helix in Q8RX88). The text doesn't say so; `experiments/decoy_control/README.md` does. | Limitations | #16 |
| T24 | open | Limitations or Methods: the decoy rule was revised twice after looking at the positions it picked, before any model call, and git cannot show the order. The text says only that two tested models helped write the rule. | Limitations, decoy control | #15 |
| T25 | decide | GPT-6 Astra and Rosalind: STRFN at high effort is answered for both models, 30 of 30 each (PR #167, not merged), and Chris's EC2 run covers the full grid. Nothing from GPT-6 is in the text yet. Decide which runs the paper reports, then add a section. | Results, Methods | #52 |
| T26 | open | The new Figure 1 (#227) says the model received "an amino-acid sequence, nothing else", while the Methods say the first Claude route cannot rule out extra context or connector tools. Qualify the figure text as T5 did elsewhere. | Figure 1 | #158 review |
| T27 | open | The README's "Open before posting" list is out of date: it says affiliations and funding are TODO, asks for a blinded second grader (two are now reported) and says related work is thin. | README | #158 review |

## Done

(Move items here with the commit or PR that did them.)

- **T4, T5, T6, T7, T8, T11, T12, T15 (part), T19, T20:** PR #183 (merge 86fcdb5). T15 checked the eight
  pseudoenzyme references; three were read in full and five as abstracts only, so T15 stays open for those (#19).
- **T10:** scoring in PR #188 (merge 16ae8c2); text in PR #209 (merge f4d0ab0). PR #209 also restores the
  T11 sentence, which #187 dropped.
- **T13:** PR #138. **T14:** PR #18.
- **T2, T3:** PRs #200 and #228 (affiliation, funding, funding-only Acknowledgements; #154 closed).
