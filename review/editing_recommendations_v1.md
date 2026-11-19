# Editing recommendations, version 1

**Manuscript:** "General-purpose language models read catalytic residues, domains and structure directly from protein sequence" (C. J. Mungall; draft of 18 November 2026)
**File reviewed:** `manuscript.pdf` at the root of this repository, as committed at the head of pull request #6527 (`119ac18676`) in `ai4curation/ai-gene-review`.
**Date:** 18 November 2026

This is the full list of recommendations from `critique_content_v1.md` and `critique_format_v1.md`, regrouped by where the edit lands in the manuscript. Each item says what to add, change or delete. The evidence behind each item is in those two files; the checks are reproducible from `scripts/`.

**Disclosure.** Written by Claude Fable 5.2, one of the two models the manuscript evaluates. Judgements about what the models can do are not independent.

**Where to edit.** The manuscript source is `manuscript.tex` at the root of this repository. The files in `review/` are commentary.

---

## Before posting

1. Fill in the two TODO markers: authors and affiliations, and funding.
2. Fix the data and code statement. The folder is only in open pull request #6527, not on the default branch. Merge it and cite a commit, tag or archived DOI.
3. Add title and author to the PDF metadata (both fields are empty).
4. Add a sentence saying what the human author verified, since an AI agent ran, analysed, drafted and partly graded the work.

## Title

5. Change "General-purpose language models" to name what was tested, for example "Two recent Claude models".
6. Change "structure" to "secondary structure".

## Abstract

7. Add the baseline to the secondary-structure numbers: "against 57% for a constant guess".
8. Add that Opus 4.6 ran at a lower effort setting, or delete the comparison.
9. Add one clause saying the earlier result was reproduced in direction but not in size (25 to 41% against 58.8% on the same questions).
10. Use one protein set in the domain sentence. "35 to 39 of 45" is the sampled set; "0.86 to 0.87" pools all 60.
11. Change "good enough to triage pseudoenzyme over-annotation" to "may be useful for", unless a real over-annotation set is tested.

## Introduction

12. Add a citation for "General-purpose language models were not expected to share this ability", or delete the sentence.
13. Replace "comparable to dedicated protein language models" with the source's specifics: Fable 5.2 exceeded every open model it ran, and Opus 5.5 matched the largest.
14. Add related work on earlier tests of general-purpose models on sequence tasks.
15. Mention the source's own 56-protein post-cutoff test (its Appendix G).
16. Check that reference 5 actually supports the claim it carries. This was not checked in the review.

## Methods

17. Add all four prompts in a supplementary box. Say in the text that the test 3 prompt asks for residues "that this sequence lacks" and that the test 4 prompt asks whether the model recognises the protein.
18. Add the scoring rules:
    - only "yes" counts as active, and "uncertain" is grouped with "no";
    - a substitution counts as reported when the mutated position is in the model's list;
    - "chose to think" comes from the thinking-token count;
    - the next-residue scorer takes the last run of five or more residue letters.
19. Add the command-line tool's version and the run date. Define "effort" and replace "print mode".
20. Add each model's training cutoff with a source. Justify the 1 June and 1 August dates, and note that entries released in June and July are uncounted on either side.
21. Add the novelty search settings (MMseqs2 via RCSB, 30% identity, E-value 0.001) and that entries with 1 to 19 earlier relatives were discarded.
22. Replace "drawn haphazardly" with the actual procedure (random length, random sort key, random pick from the first 25 hits). Add that every real protein was required to have a Pfam match.
23. Either report the name and function outputs of test 2 or delete them from the Methods.
24. Explain or exclude the three Opus 5.5 high-effort calls whose usage record lists a second model.
25. Add the four family-size bins, and explain 3,340 cut points as 668 proteins at five cuts each.
26. State the definitions of correct, abstain and wrong used in function grading.

## Results 3.1 (next residue)

27. Qualify "both newer models": the Opus 5.5 low-effort interval includes zero (−1.5 to +16.2).
28. Limit the reversed-sequence claim to Fable 5.2 at low effort. For Opus 5.5, reversed (12.5%) sits between shuffled (9.6%) and real (16.9%).
29. Rest the reasoning claim on the low-versus-high effort contrast on the same questions (25.0% to 41.2% real; 7.4% to 11.8% shuffled).
30. Describe the with/without-thinking split as descriptive, and give the selection evidence:
    - thinking on 38 of 136 real questions against 15 shuffled and 17 reversed;
    - thinking on 18 of 34 in the largest family bin against 4 of 34 in the two smallest;
    - 41.2% when thinking was forced on every question, against 57.9% in the self-selected subset.
31. Add that thinking did not help on shuffled sequence (0/15 against 10/121).
32. State the size of the unexplained gap with the source: 12.2% without thinking here against 54.7% there, and thinking on 28% of answers here against 9% there.

## Results 3.2 (domains)

33. Scope the heading "shuffled sequences are left blank" to the two newer models.
34. Add recall of reference families: 46 of 56 and 39 of 56 in the sampled set; 9 of 17 and 3 of 17 in the obscure set.
35. Add a sentence that the reference labels are HMM matches a tool reproduces exactly, so the result is tool-free approximation, not competition.
36. Add that shuffled sequences are easy negatives and that no real protein without a Pfam match was tested.

## Results 3.3 (pseudoenzymes)

37. Explain the natural-pseudokinase counts: 18 "no", 1 "yes" and 1 uncertain or empty answer per model. This is why the text says 18 of 20 while the figure shows 5%.
38. Add the wild-type flag rate: a substituted or missing residue was listed for 2 of 20 unmutated kinases (Fable 5.2) and 3 of 20 (Opus 5.5).
39. Give the 20 other enzymes more space and list their families. They are the stronger evidence of generality.
40. For kin-32, add the Swiss-Prot basis ("apparently no tyrosine kinase activity in vitro") and reframe the case as something sequence cannot show.
41. For ENV9 and YrfG, add that the reference sites are annotated by similarity, and adjudicate them. Do not count them as misses until then.
42. Replace "Two failure modes recurred" with counts.

## Results 3.4 (structure and function)

43. Rename the stratum "no PDB entry at ≥30% identity" in the text, Figure 2 and the Discussion.
44. Add the recognition counts: Fable 5.2 said it recognised 5 of 15 novel entries (2 of 12 distinct proteins). Excluding them gives 76.1% and 33.9%.
45. Add intervals and medians for contact precision: 19.8 to 54.4% (Fable 5.2) and 9.4 to 29.6% (Opus 5.5); per-protein range 0 to 95%.
46. Add the separation-matched chance rate (4.0% and 3.2%) beside the 1.8%.
47. Note that Fable 5.2 is below the constant-guess baseline on 9TGX (82% against 86%).
48. Disclose the AtDUC1 preprint of 8 December 2025 (DOI 10.64898/2025.12.04.692294). Add that InterPro lists only a C2 domain and a domain of unknown function for it.
49. Soften the heading "function follows where the fold is catalytic"; no test separates fold from family recognition.
50. Note that two of the 12 proteins are de novo designs.
51. Add that in the known stratum Fable 5.2 recognised 14 of 15 proteins yet reached only 48% contact precision, which argues against pure recall.
52. Add that RCSB does not flag the 27IQ substitution, so the models noticed an unannotated change.

## Discussion and Limitations

53. Delete or qualify "The older Opus 4.6 does none of this, so the ability is recent and specific to certain models". It found all 9 signal peptides and 51 of 73 helices, and its run was at low effort.
54. Give the call-route question its own sentence in Limitations.
55. Add the missing limitations: no neutral-substitution control, AI grading, by-similarity reference sites, the novelty definition, and depositor-defined secondary structure.
56. Group the Limitations: sample size and repeats; call route; reference labels; grading; what was not tested.

## Tables

57. Table 1: add columns for the number of questions, the source's accuracy on the same questions, and the number of answers with thinking. Say the dashes mean "not run".
58. Table 2: say that rows 3 to 7 pool all 60 proteins, or split them.
59. Table 2: explain the Opus 4.6 denominators (three unparsed answers).
60. Table 2: add the number of true signal peptides (9) and a recall row.
61. Move Table 2 next to section 3.2; it currently splits a sentence in 3.3.

## Figures

62. Figure 1: show counts out of 20, split bars into yes, uncertain and no, and put the effort setting in the legend.
63. Figure 2: relabel the novel group, add per-protein points, define or replace "Q3", and label both baselines.

## References and terms

64. Add citations for InterPro, the RCSB sequence search or MMseqs2, Swiss-Prot, and the models and command-line tool.
65. Add an access date and an archived copy for the blog post.
66. Define "IoU" at first use in the text, and spell out *Caenorhabditis elegans* once.

## Prose

67. Rewrite "The exception is informative:" and "the point is that…" to state the point directly.
68. Leave the British spelling and absent serial comma as they are; the draft is consistent.

## New analyses, in order of value for cost

69. Rerun the 136 next-residue questions through the API at the source's settings.
70. Add a neutral-substitution control to test 3.
71. Run Fable 5.2 and Opus 5.5 at low effort on tests 2 to 4.
72. Adjudicate YrfG and ENV9 against a family alignment or structure.
73. Record the earliest public description of each of the 12 novel proteins and report the clean subset.
74. Repeat tests 2 to 4 three to five times.
75. Add single-sequence structure baselines and DSSP truth.
76. Have two blinded human graders score function, with an InterPro column.
77. Add real proteins with no Pfam match as negatives in test 2.
78. Add one intermediate Claude model and one non-Claude model to test 3.
79. Test a small set of real over-annotated pseudoenzymes.

The first five analyses (69 to 73) would, in the reviewer's judgement, be enough to post.
