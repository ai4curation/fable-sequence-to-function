# Scientific assessment, version 1

**Manuscript:** "General-purpose language models read catalytic residues, domains and structure directly from protein sequence" (C. J. Mungall; draft of 18 November 2026; 7 pages)
**File reviewed:** `manuscript.pdf` at the root of this repository (SHA-256 `90117590609a8d74…`), as committed at the head of pull request #6527 (`119ac18676`) in `ai4curation/ai-gene-review`, from which this repository was split.
**Review date:** 18 November 2026
**Companion file:** `critique_format_v1.md` (presentation).

**Disclosure.** This review was written by Claude Fable 5.2, one of the two models the manuscript evaluates, running in Claude Code, the same tool that ran the tests and wrote the first draft. Judgements here about what the models can do are not independent. The recomputations and source look-ups are reproducible from the five scripts in `scripts/` beside this file.

**How to read the evidence labels.** "Verified" means I checked it in this session against the raw outputs or a public registry. "Inference" is my reading of verified facts. "Not checked" means what it says.

---

## 1. Summary

The manuscript asks a useful question: whether the next-residue ability reported for two recent Claude models translates into anything a curator needs. It answers with four small tests. The reporting is honest, the controls are well chosen for their size, and **every number in the tables, figures and text reproduces exactly from the committed raw outputs** (section 6).

The strongest result is test 3. Both newer models change their activity call when one catalytic residue is substituted in a kinase they otherwise call active (0 of 20 Asp→Asn mutants called active; 20 of 20 wild types), and they name the changed position. The mutant sequences were made for the study, so recall of an entry cannot explain it. This is new and it is the result the paper should be built around.

The other three tests support the story less firmly than the text says:

- The title and Discussion generalise from two models of one vendor to "general-purpose language models", and the cited source itself reports that other vendors' models show no signal.
- The command-line route used for all four tests gives very different next-residue accuracy from the original report on the same questions, and the reason is untested.
- The "novel, post-training" structure set is defined by 30% sequence identity to earlier PDB entries. It is not free of earlier homologs or of earlier literature. The paper's best example (AtDUC1) was described as a deubiquitinase in a preprint posted in December 2025.
- Structure accuracy is compared with weak baselines, and contact precision varies from 0% to 95% across the 12 proteins.

None of these invalidates the data. Most are fixed by rewording plus a small set of reruns; the project page puts the whole study's model cost at about 80 US dollars.

**Recommendation:** revise before posting. Items M1, M2, M4 and M6 below should be addressed first.

---

## 2. What holds up

| Claim in the draft | Status |
|---|---|
| Table 1, all cells and all five bootstrap intervals | Verified by recomputation |
| Thinking split: 22/38 vs 12/98 (Fable 5.2, low); 16/41 vs 9/91 (Opus 5.5, high) | Verified |
| Table 2, all cells | Verified, with the note that rows 3 to 7 pool all 60 proteins (M8) |
| Figure 1, all 18 bars; 57/60 and 47/60 mutated positions reported | Verified |
| Figure 2 and the text values (76.3/73.4% Q3; 36.6/19.0% contacts; 56.6% and 1.8% baselines) | Verified |
| Function grading tallies (6/5/1 and 4/7/1) | Match `structure/function_grading.yaml` |
| kin-32 (Q95YD4) contains a glycine loop, VAVK, HRD and DFG | Verified in the UniProt sequence (GGGQFG 374–379, K400, HRD 490–492, DFG 510–512) |
| Q9VLA1 has Glu at both 317 and 318; curated proton acceptor is 318 | Verified |
| 27IQ carries Asn where ASPRV1 has the catalytic Asp | Verified: construct has NSG; UniProt Q53RT3 has DSG with active site Asp212. RCSB's mutation field for the entry is empty, so the models noticed a substitution the entry does not flag. This strengthens the point and is worth saying. |
| The five PDB entries named in the text exist, with the titles described | Verified |
| No invalid or errored answers in test 1; every call reports the requested model | Verified, with one exception (M2) |
| Shuffled-sequence abstention: 1/60, 0/60, 4/59 | Verified |

A further point in the draft's favour that it does not make: in the "known" stratum Fable 5.2 says it recognises 14 of 15 proteins, yet its contact precision there is only 48%. If the model were reciting memorised structures, that number should be much higher. This argues against pure recall and could be stated.

---

## 3. Major issues

### M1. The title and Discussion claim more generality than two models support

- The title says "General-purpose language models". The tests cover two models from one vendor, plus one older model from the same vendor.
- The cited source (reference 3) reports that GPT and Gemini models "stay near zero" on next-residue prediction. On the draft's own premise that function reading builds on sequence knowledge, the title's generalisation is contradicted by its key reference.
- The Discussion says "The older Opus 4.6 does none of this, so the ability is recent and specific to certain models." Opus 4.6 ran at low effort in tests 2 to 4 while the newer models ran at high effort. The Methods say this confounds the comparison; the Discussion and abstract then use the comparison without the caveat.
- Opus 4.6 at low effort scored below the constant-guess baseline on secondary structure (48.1% against 56.6%; 10 of 12 novel proteins at or below baseline; verified). An answer worse than guessing one state suggests low-effort answers were poor in general, so this run says little about what the model can do.
- "Does none of this" is also too strong on the draft's own Table 2: Opus 4.6 found all 9 signal peptides (with 6 false positives) and 51 of 73 transmembrane helices.
- The source reports a graded series between the endpoints (real-minus-shuffled gaps of about +8 to +15 points for Opus 4.7, 4.8, 5 and Fable 5.1). The draft tests only the two ends.

**Fix.** Retitle to name what was tested, for example "Two recent Claude models read catalytic residues, domains and secondary structure from protein sequence alone". Rerun tests 2 to 4 for Fable 5.2 and Opus 5.5 at low effort so that all three models are compared at one setting. If budget allows, add one intermediate Claude model and one non-Claude model to test 3: a dose-response between next-residue gap and catalytic-residue detection would be the strongest available evidence that the function calls rest on sequence knowledge.

### M2. The call route changes the result, and the cause is untested

- On the identical 136 real questions, the source's stored answers score 58.8% for Fable 5.2; this study gets 25.0% at low effort and 41.2% at high effort (verified from the project page table and my recomputation).
- The source reports that Fable 5.2 answers without thinking are right 54.7% of the time across its full set (verified in the post's own text). Here, answers without thinking are right 12.2% of the time (12/98; verified). That is a four-fold difference in the same condition.
- The source reports thinking on 9% of Fable 5.2 answers at low effort. Here it is 28% (38/136).
- The draft attributes the gap to sampled answers and the tool's roughly 1,400 tokens of added context, "without having tested it". The source used each model's API at temperature 0 where accepted.
- All of tests 2 to 4 went through the same route. Whatever lowers test 1 may also affect them. The likely direction is that the reported numbers understate the models (inference), but the paper cannot currently say so.
- Three of the 264 Opus 5.5 high-effort calls list two models in their usage record (`claude-opus-5` as well as `claude-opus-5-5`; verified). The Methods say every call was confirmed single-turn. These three should be explained or excluded.

**Fix.** Rerun the 136 questions through the API at the source's settings. If that restores about 59%, the route is the cause; then either rerun tests 2 to 4 through the API or state plainly that they were run through a route known to depress accuracy. Report the command-line tool's version.

### M3. "Accuracy depended on whether the model reasoned" is an observational split

The draft compares questions on which the model chose to think with those on which it did not. The model's choice is not random (all verified):

- Fable 5.2 at low effort thought on 38 of 136 real questions, but on only 15 of 136 shuffled and 17 of 136 reversed ones.
- It thought on 18 of 34 questions in the largest family-size bin and on 4 of 34 in each of the two smallest.
- When thinking was forced on every question (high effort), accuracy was 41.2%, well below the 57.9% of the self-selected subset.

The model appears to think when it recognises something (inference). The split therefore measures which questions are easy as much as what thinking does. The clean evidence is already in Table 1: the same questions at low and high effort give 25.0% and 41.2% on real sequence, and 7.4% and 11.8% on shuffled. The draft should rest the claim on that contrast and describe the self-selected split as descriptive. It should also say that on shuffled sequence the thinking answers were no better (0/15 against 10/121), which the project page reports and the draft omits.

### M4. The "novel, post-training" structure set is weaker than the labels say

1. **The definition is narrower than the wording.** "Novel" means no PDB entity at 30% identity or more (MMseqs2, E ≤ 0.001) released before 1 June 2026. Figure 2 labels it "no prior homolog" and the Discussion says "no earlier structural homolog". Remote homologs are not excluded. Example: an Rpp30 structure from *Thermococcus kodakarensis* (PDB 3WZ0) was released in 2015 (verified); the novel-set entry 10CW is Rpp30 from another archaeon. I did not measure their identity.
2. **The sequences are not new.** Eight of the 12 distinct proteins have UniProt accessions (verified from `truth.json`), so their sequences, and in general their predicted structures, were public long before training. Two others are de novo designs.
3. **The structures were deposited long before release.** The five entries named in the text were deposited between October 2025 and June 2026 (verified), 3 to 12 months before the "post-training" release dates. Deposition is often accompanied by a preprint.
4. **The best example has a literature leak.** The AtDUC1 work was posted on bioRxiv on 8 December 2025 under the title "DUCs are C2 domain containing plant-specific deubiquitinases stabilizing endocytic cargo at the…" (DOI 10.64898/2025.12.04.692294; verified in CrossRef). The draft presents Fable 5.2's "possibly a deubiquitinase" call as inference from fold. A model trained after that preprint could have learned that this family are deubiquitinases. That path is not shown to have been used, and it is not excluded.
   For the other named entries I found journal dates after mid-2026 (NosH: *Science*, 22 October 2026; Rpp30: *Nucleic Acids Research*, first registered 29 July 2026). I did not search for preprints of those, and found no CrossRef record for the ASPRV1 paper.
5. **No training cutoff is stated.** The source says its 1 July cutoff "is an assumption". This draft uses 1 June for prior homologs and 1 August for release without giving a reason, which also leaves entries released in June and July uncounted on either side.
6. **Recognition is recorded but not reported.** The prompt asks the model whether it recognises the protein. Fable 5.2 said yes for 5 of the 15 novel entries (2 of the 12 distinct proteins: ASPRV1 and MrtR); Opus 5.5 for none (verified). The project page reports this; the draft does not. Excluding the two recognised proteins changes little (Q3 76.1%, contacts 33.9%), which is worth saying.

**Fix.** Rename the stratum by its definition ("no PDB entry at ≥30% identity"). State each model's documented cutoff and cite it. For each of the 12 proteins, record the earliest public description (preprint or paper) and report results for the subset with none before the cutoff. Report the recognition counts.

### M5. Structure baselines are weak and contact precision is very uneven

- **Secondary structure.** 76% and 73% are compared with a 57% constant guess. The relevant comparison is a single-sequence predictor run on the same 12 proteins. From memory, such tools reach the low-to-mid 70s; I did not check this and no such baseline was run. The abstract gives the Q3 values with no baseline at all, next to contact values that do have one.
- **Contacts, chance level.** The 1.8% chance rate is over all pairs at least 24 apart. The models' picks are not spread evenly over separations. Matching chance to the separations the models actually chose gives 4.0% for Fable 5.2 and 3.2% for Opus 5.5 (my computation from `truth.json`). The conclusion stands, but the stated baseline is about half the fair one.
- **Contacts, spread.** Bootstrap intervals over the 12 proteins are 19.8 to 54.4% (Fable 5.2) and 9.4 to 29.6% (Opus 5.5). Per protein, Fable 5.2 ranges from 0% (9TGX, 9YP0) to 95% (9ZWQ); the median is about 28%, against a mean of 37%. The three highest (9ZWQ polynucleotide kinase 95%, 37QB ketopantoate reductase 80%, ASPRV1 75%) are proteins from large, structurally well-known families whose function the model also named. The mean is therefore driven by cases where recall of a family's fold is plausible (inference), which bears directly on M4.
- **One protein is below baseline.** For the all-helical 9TGX, Fable 5.2's Q3 (82%) is below the constant guess (86%).
- **Truth definition.** Helix and strand truth comes from depositors' records, which differ between depositors. A uniform DSSP assignment would be cleaner. The project page says this; the draft's Limitations do not.

**Fix.** Add a single-sequence secondary-structure predictor and a protein language model contact baseline on the same items. Use DSSP. Show per-protein points in Figure 2 and report medians and intervals.

### M6. Test 3 needs one more control, and two "failures" may be reference errors

- **No neutral-substitution control.** The design shows the models flag a substitution at a catalytic position. It does not show they would leave the call unchanged for a substitution elsewhere. A model that treats any deviation from a familiar sequence as inactivating would look the same. Adding, for the same 40 proteins, one substitution at a non-conserved position would settle it.
- **Wild-type specificity is unreported.** On unmutated kinases, Fable 5.2 listed at least one "substituted or missing" residue in 2 of 20 answers and Opus 5.5 in 3 of 20 (plus 1 of 20 other enzymes), though all were still called active (verified). These may be true non-canonical residues or false alarms; I did not read them individually. Either way the rate belongs in the paper, because it is the false-alarm side of a triage tool.
- **The prompt asks for substitutions.** It requests a list of canonical catalytic residues "that this sequence lacks". The unprompted ASPRV1 case shows the behaviour can occur without that cue, but it is one case. A neutral "annotate this protein" prompt on the mutants would show how often it happens when nobody asks.
- **Kinases are the easiest case.** The catalytic motifs of protein kinases are the most stereotyped in enzymology. The 20 other enzymes are the stronger evidence of generality (17/20 and 15/20 positions reported). They deserve more space, with the enzyme families listed.
- **Some reference sites are annotated by similarity.** For the two enzymes where both models disagree with the reference (Q08651, P64636), UniProt's active-site evidence code is ECO:0000250, "by similarity" (verified). For YrfG (P64636) the models place the nucleophile at Asp16; the sequence reads `…VLLDMDGTLLD…` at 13–23, a textbook haloacid dehalogenase motif I, whereas UniProt's Asp9 sits in `WQDVD` (sequence verified; the motif reading is mine). If the models are right, the Asp9→Ala mutant is correctly called active and should not count as a miss. Adjudicating this against a family alignment or a structure could turn a reported failure into the paper's most interesting observation: a model flagging a probable annotation error.
- **kin-32.** The draft says it did not examine the basis of the Swiss-Prot name. The entry's function note reads "Has apparently no tyrosine kinase activity in vitro when expressed in mammalian cells" (verified). The name rests on an assay, not on a missing residue. The case therefore shows what a sequence-only read cannot know, which is a more useful framing than "the exception is informative".
- **"Uncertain" answers are folded into "not active".** The figure plots only "yes". For natural pseudokinases each newer model gave 18 "no", 1 "yes" and 1 uncertain or empty answer (verified), which is why the text says 18 of 20 inactive while the figure shows 5% active. Opus 4.6 gave 2 to 4 "uncertain" answers per cell. The Methods should state the rule, and the figure could show three segments.
- **The practical claim is untested.** The abstract concludes the models are "good enough to triage pseudoenzyme over-annotation". The evidence is engineered point mutants of well-characterised Swiss-Prot enzymes. The use case is unreviewed proteins that have drifted from an active ancestor, often with several changes. A small set of real over-annotated entries would test the claim that is actually made.

### M7. The function result in test 4 does not show that "function follows fold"

- Grading was done once, unblinded, by the AI agent that ran the tests, with a lenient definition of correct (right enzyme family counts). The draft discloses this. It remains the weakest measurement in the paper, and it is a Claude model grading Claude models.
- The heading says function follows "where the fold is catalytic". No test separates structure-based inference from plain family recognition. Most correct calls are well-known families (CD-NTase, LuxR-type regulator, ketopantoate reductase, P-loop polynucleotide kinase), and two name the specific human protein (ASPRV1, N4BP2). A Pfam search would probably return the same families; I did not run it per protein.
- AtDUC1 is the exception: InterPro lists only an NT-type C2 domain and a domain of unknown function for it (verified). That is the case where the model added something. It is also the case with the preprint (M4).
- Two of the 12 proteins are de novo designs, for which "function" has no evolutionary answer.

**Fix.** Two blinded human graders. Add an "InterPro says" column so the reader sees where the model adds anything. Add an ablation that asks for function without the structure prediction.

### M8. Test 2 lacks real negatives, and its table mixes denominators

- **Negatives.** Every real protein was required to have a Pfam match, so the only negatives are shuffled sequences. A model with any sense of sequence statistics will find a shuffle unnatural. Declining to annotate shuffles does not show calibrated abstention on real proteins with no known family. Real proteins without a Pfam match are the missing control.
- **Recall is not reported.** The table gives precision of predicted domains (62/70, 45/51). Of the reference families in the 45 sampled proteins, Fable 5.2 recovered 46 of 56 and Opus 5.5 39 of 56; in the 15 obscure proteins, 9 of 17 and 3 of 17 (my computation).
- **Pooled rows.** Rows 1 and 2 are per set (45 and 15). Rows 3 to 7 pool all 60 proteins (verified: 62/70 is 52/59 plus 10/11). The caption does not say so, and the abstract puts a pooled value (0.86 to 0.87) beside a 45-protein count.
- **Opus 4.6 denominators** of 43, 59 and 73 come from three unparsed answers (verified). Say so.
- **Name and function were requested and not scored.** The Methods list them among the outputs; the Results report nothing on them except two anecdotes. Score them or drop them from the Methods.
- **"Drawn haphazardly"** hides a definite procedure (random length, random sort key and direction, random pick from the first 25 hits). Describe it; it is reproducible, and its bias toward the ends of each sort order is then visible.
- **What the test can show.** The reference labels are HMM matches, which a tool reproduces perfectly. The result is that the models approximate that tool with no tool. The paper should say this, so that the reader does not take 39/45 as competitive.

### M9. Tests 2 to 4 have no uncertainty, and every answer is a single sample

Answers were sampled at an unknown non-zero temperature and each question was asked once. Tests 2 to 4 report no intervals. For orientation, 0 of 20 has an exact 95% upper bound of about 17%. Three to five repeats per question would give within-item variability and allow intervals everywhere, at low cost. The headline 0-of-20 result is the one most worth repeating.

### M10. The data and code statement is not yet true

The statement points to `projects/LLM_SEQUENCE_PROBE` in `ai4curation/ai-gene-review`. At the time of review that path returns HTTP 404 on the default branch (verified, anonymous request). The folder exists only in open pull request #6527. Before posting, merge it and cite a commit or tag, or an archived DOI.

---

## 4. Minor issues

1. **Opus 5.5 at low effort.** The interval for the gap includes zero (−1.5 to +16.2). "Both newer models predicted real sequence better than shuffled sequence" is supported at high effort and for Fable 5.2, not for Opus 5.5 at low effort.
2. **Reversed control.** "Reversed sequence scored like shuffled sequence" holds for Fable 5.2 (8.8% against 7.4%). For Opus 5.5, reversed (12.5%) sits between shuffled (9.6%) and real (16.9%). The control was run at low effort only.
3. **"Comparable to dedicated protein language models."** The source says Fable 5.2 exceeded every open protein language model it ran left-to-right, that Opus 5.5 matched the largest, and that ESM-2 given residues on both sides did better than Opus 5.5. A sentence with those specifics would be more accurate than "comparable".
4. **"General-purpose language models were not expected to share this ability"** has no citation. Either cite prior tests of such models on sequence tasks or delete it. The repository's own notes list this gap.
5. **Reference 5** carries a specific claim (assigning catalysis to a protein that has lost its catalytic residues is among the most damaging errors). The reference exists; I did not check that it says this.
6. **Answer parsing.** The scorer takes the last run of five or more residue letters in a reply. Between 0 and 10 replies per run contained more than one run (verified). The effect is small; mention the rule.
7. **The source's own post-cutoff test.** Reference 3 added a 56-protein set first public in August 2026 (its Appendix G). It is directly relevant to test 4 and is not mentioned.
8. **Same-day entries.** Two novel entries (12WN, 9T71) were released on the day of the test. This is harmless and worth one clause, since it is the cleanest part of the "post-training" claim for structures.

---

## 5. Additions, ranked by value for cost

1. Rerun test 1's 136 questions through the API at the source's settings (resolves M2).
2. Neutral-substitution control for test 3, and report wild-type flags (M6).
3. Fable 5.2 and Opus 5.5 at low effort on tests 2 to 4 (M1).
4. Adjudicate YrfG and ENV9 against a family alignment or structure (M6).
5. Earliest-public-description date for each of the 12 novel proteins; report the clean subset (M4).
6. Three to five repeats of tests 2 to 4 (M9).
7. Single-sequence structure baselines, DSSP truth, separation-matched chance (M5).
8. Blinded human grading of function, with an InterPro column (M7).
9. Real proteins with no Pfam match as negatives in test 2 (M8).
10. One intermediate Claude model and one non-Claude model on test 3 (M1).
11. A small set of real over-annotated pseudoenzymes from unreviewed entries (M6).

Items 1 to 5 would, in my judgement, be enough to post.

---

## 6. Verification log

| Check | Method | Result |
|---|---|---|
| PDF identical to repository copy | SHA-256, text diff | Identical |
| Tables 1 and 2, Figures 1 and 2, in-text counts | `scripts/recompute_from_pr6527.py` on the raw outputs at `119ac18676`, without running the authors' code | All reproduce |
| Six DOIs in the reference list | CrossRef, anonymous | All resolve to the cited title, journal, volume and pages |
| References 3 and 4 | HTTP request; post text; commit lookup | Both exist; commit `0d8d086` exists; post lists both authors |
| Source's settings and thinking numbers | Raw text of the post | Temperature 0 where accepted; low effort; 54.7% without thinking, 48.2% with (Fable 5.2) |
| UniProt accessions Q95YD4, Q9VLA1, Q2PAY3, Q08651, P64636 | UniProt REST | Exist; names, sites and sequences as described above |
| PDB entries 9T71, 9TGX, 10CW, 9YP0, 27IQ | RCSB REST | Exist; titles, dates, entity names as described above |
| AtDUC1 prior publication | CrossRef | bioRxiv preprint, first registered 8 December 2025 |
| AtDUC1 existing annotation | InterPro API | NT-type C2 domain and DUF8490 only |
| Data folder on default branch | GitHub API, anonymous | 404; present in open pull request #6527 |

**Not checked:** the content of references 1, 2, 5, 6, 8 and 10 against the claims they support; preprints for the novel proteins other than AtDUC1; whether AlphaFold Database models exist for each novel protein; the identity between 10CW and 3WZ0; the individual wild-type answers that list a substituted residue; the authors' stored outputs in the source repository (the 58.8% figure is taken from the project page). An RCSB sequence search for earlier remote homologs of the five named entries failed with server errors for four of them and is not used here.

**Raw outputs.** When this review was written the raw outputs were not in this repository. They have since been copied, unchanged, from `ai4curation/ai-gene-review` at `119ac18676` to `review/pr6527_snapshot/`, and `scripts/recompute_from_pr6527.py` reads that folder by default. Its output is saved in `review/recompute_output_pr6527.txt`.
