# Presentation assessment, version 1

**Manuscript:** "General-purpose language models read catalytic residues, domains and structure directly from protein sequence" (draft of 18 November 2026)
**File reviewed:** `manuscript.pdf` at the root of this repository, as committed at the head of pull request #6527 (`119ac18676`) in `ai4curation/ai-gene-review`.
**Review date:** 18 November 2026
**Companion file:** `critique_content_v1.md` (scientific assessment; issue numbers M1 to M10 refer to it).

**Disclosure.** Written by Claude Fable 5.2, one of the models the manuscript evaluates.

---

## 1. Overall

The draft is short (about 2,800 words, 7 pages, 2 figures, 2 tables, 10 references), plainly written and candid about its limits. A reader can follow the argument from the abstract alone. The prose has very few of the habits that mark machine-drafted text. The work needed is mostly in three places: the title and abstract say more than the Results, the Methods leave out details a reader needs to judge the tests, and the tables and figures hide denominators and spread.

No target venue is declared, so no word or figure limits were checked. The order Introduction, Methods, Results, Discussion suits a preprint.

---

## 2. Before posting (blocking)

1. **Two TODO markers remain in the text:** authors and affiliations on the title page, and funding in the Acknowledgements.
2. **The data and code statement points to a path that is not on the default branch yet** (M10). Cite a merged commit, a tag or an archived DOI.
3. **The PDF has no title or author metadata** (both fields are empty). Set them in the LaTeX preamble.
4. **Author accountability for AI-produced work.** The Acknowledgements say an AI agent ran the tests, did the analysis and wrote the first draft. That disclosure is good. It should be joined by a sentence saying what the human author verified, since one result (function grading) is also AI-graded.

---

## 3. Title and abstract

| Item | Problem | Suggestion |
|---|---|---|
| Title: "General-purpose language models" | Two models, one vendor (M1) | Name the models, or say "two recent" |
| Title: "structure" | The evidence is secondary structure and a contact list | "secondary structure" |
| Abstract, structure sentence | Q3 of 73 to 76% is given with no baseline, while contacts get "against 2% by chance" | Add "against 57% for a constant guess" |
| Abstract, Opus 4.6 | "18 of 20 for the older Claude Opus 4.6" omits that it ran at a lower effort setting | Add the setting, or drop the comparison from the abstract |
| Abstract, replication | The abstract opens with the earlier report and does not say that this study reproduced its direction and not its size | One clause |
| Abstract, mixed denominators | "35 to 39 of 45" is the sampled set; "0.86 to 0.87" pools 60 proteins | Use one set, or say which |
| Abstract, last sentence | "good enough to triage pseudoenzyme over-annotation" is a claim about a use that was not tested (M6) | "may be useful for" until tested |

The abstract is about 210 words in one paragraph, which is a normal length. Its closing clause, "and is not a citable source of evidence", is a good, plain ending.

---

## 4. Structure and Methods

**Details the Methods need and do not have.** All of these exist in the repository; none is in the paper.

- The prompts. All four are short. Put them in a supplementary box. The test 3 prompt explicitly asks for substituted residues, which a reader must know to judge the result.
- How "called active" was scored: only the answer "yes" counts, and "uncertain" is grouped with "no".
- How "reported as substituted" was scored: the mutated position must appear in the model's list of substituted or missing residues.
- How "chose to think" was determined: from the thinking-token count in the usage record, since the reasoning text is not returned.
- The novelty search settings: MMseqs2 through the RCSB sequence search, 30% identity, E-value 0.001; and the fact that entries with 1 to 19 earlier relatives were discarded.
- The version of the command-line tool and the date of the runs.
- The models' training cutoffs, with a source.
- The test 2 sampling procedure in place of "drawn haphazardly".

**Methods and Results disagree in one place.** The test 2 Methods say the model returned a name and a function. The Results never report them.

**Placement.** Section 3.3 is interrupted mid-sentence by Table 2 and the page break ("so this / set mostly measures recall"). Table 2 belongs with section 3.2. Figure 1 lands a page after the paragraph that cites it.

**Section 3.1** mixes a methods detail (the no-model heuristics and the 3,340 cut points, a number that is not explained in this paper) into the results. One clause of explanation would do: 668 proteins at five cut points each.

**Section headings state conclusions**, which helps the reader. Two of them state more than the section shows: 3.4 "function follows where the fold is catalytic" (M7) and 3.2 "shuffled sequences are left blank" (true for the two newer models only).

---

## 5. Tables

**Table 1**
- Add the number of questions per row. The caption mentions 132 of 136 for one row; a column is clearer.
- Add the source's accuracy on the same questions as a column. It is the comparison the text discusses, and the project page already has it (58.8%, 39.7 to 40.9%, 6.6%).
- Consider a column for the number of answers with thinking, since section 3.1 turns on it.
- The dashes under "Reversed" mean "not run". Say so in the caption.

**Table 2**
- Rows 1 and 2 are per set; rows 3 to 7 pool all 60 proteins. State this in the caption or split the rows.
- Explain the Opus 4.6 denominators (43, 59, 73): three answers could not be parsed.
- "Signal peptide, true / false positives: 9 / 0" needs the number of true signal peptides (9) so the reader sees that none was missed.
- Add recall of reference families (M8).
- "Shuffled sequences given any domain" is the control row. Set it apart visually.

---

## 6. Figures

Both figures are vector graphics with embedded fonts (verified: the PDF contains no raster images; labels are DejaVu Sans at about 7 to 8.5 points at a 6.6-inch width). They will print cleanly. Colours are consistent across the two figures, and bars carry value labels.

**Figure 1**
- Each bar is 20 sequences. Counts ("0/20") are more honest than percentages at this size, or give both.
- "Uncertain" answers are invisible. A three-part bar (yes, uncertain, no) would show them; Opus 4.6 has up to 4 of 20.
- The caption notes that Opus 4.6 ran at low effort. Put the effort setting in the legend label as well, where a reader who skips captions will see it.
- No interval or repeat is shown; the caption should say each sequence was asked once.

**Figure 2**
- The axis label "Novel (no prior homolog)" overstates the definition (M4). Use "no PDB entry at ≥30% identity".
- With 12 and 15 proteins per group, show the individual proteins as points over the bars. The spread is the main fact (contact precision runs from 0 to 95%).
- The left axis says "Q3"; the text never uses or defines that term. Use one name in both.
- The dashed baseline labels sit only beside the right-hand group. Label both, or move the label to the legend.
- The caption is otherwise complete (it gives group sizes and the one unparsed answer).

I did not simulate colour-vision deficiency. Because the bars are in a fixed order and directly labelled, the figures do not depend on colour alone.

---

## 7. Citations and references

- All ten references are cited, in numerical order of first appearance (verified by reading). All six DOIs resolve to the cited works (verified in CrossRef).
- **Uncited resources that the Methods rely on:** InterPro (the source of the Pfam matches), the RCSB sequence search or MMseqs2 (the novelty criterion), Swiss-Prot as distinct from UniProt generally, and the models and command-line tool themselves (model identifiers are given; a citable description with a date is not).
- **Unsupported statement:** "General-purpose language models were not expected to share this ability" has no citation.
- **Thin related work.** Two protein language model papers and one blog post carry the whole background. Earlier evaluations of general-purpose language models on sequence tasks are absent. The repository's notes already list this.
- **The foundation is a blog post** (reference 3) whose figures are dated the day before this draft and which carries an update dated the same day as the draft. That is acceptable for a rapid follow-up if the reference carries an access date and, ideally, an archived copy, as reference 4 does with its commit.
- Reference 8 (Pfam) is dated 2021 with a 2020 online date; either is acceptable, the volume and pages are right.

---

## 8. Terms a reader outside the project will trip on

| Term | Where | Issue |
|---|---|---|
| "effort" (low, high) | Methods onward | A product setting, never defined. One sentence. |
| "print mode" | Methods | Tool jargon. "Non-interactive mode" or drop it. |
| "Q3" | Figure 2 only | Undefined; the text says "three-state accuracy" |
| "IoU" | Table 2 caption, results | Defined only in the caption; define at first use in the text |
| "cut points" | Methods, test 1 | Understandable, but say that the model sees the sequence up to the cut |
| "family-size bin" | Methods, test 1 | The four bins are not given |
| "known" / "novel" | Test 4 | Defined, but the labels promise more than the definitions (M4) |
| "newer models", "older" | Throughout | Fine once; name the models in topic sentences |

Organism names are italicised correctly (*C. elegans*, *Toxoplasma*, *Arabidopsis*). *C. elegans* is abbreviated at first mention; spell the genus out once.

---

## 9. Prose

The writing is direct and mostly in short declarative sentences. I found no inflated vocabulary, no stacked hedges and no formulaic paragraph endings. Specific points:

- "The exception is informative:" (section 3.3) announces a point before making it, and the point it introduces is the weakest reading of that case (M6).
- "the point is that they are well above chance for a model given no alignment and no tools" (section 3.4): say it directly, and compare with a proper baseline (M5).
- "Two failure modes recurred." Each is supported by one named example. "Recurred" needs counts.
- "which we attribute, without having tested it, to sampled answers and the extra context" is admirably honest. It also marks the paper's largest open question (M2) in a subordinate clause. It deserves its own sentence in the Limitations.
- The Limitations paragraph is a list of ten short statements. It would read better grouped: sample size and repeats; the call route; reference labels; grading; what was not tested.
- Causal wording in the Discussion ("so the ability is recent and specific to certain models") outruns a comparison the Methods call confounded.
- **House style.** The draft uses British spelling and no serial comma, consistently ("residues, domains and structure"). The RRWrite review checklist asks for the serial comma. Since the draft is consistent, I would leave this to the author and the eventual venue.

---

## 10. Checklist steps not applicable or not run

| Step in the review checklist | Status |
|---|---|
| Venue guideline check | No venue declared |
| Live and earlier-version comment audit | No Google Doc or DOCX; the only inline markers are the two TODOs |
| Candidate-figure discovery deck | Not run. The figures are generated by the authors' script in their repository; there are no competing candidates in this workspace |
| Modern AI terminology pass | The draft's terms ("general-purpose language models", "protein language models") are precise; nothing to change |
| Bibliography file audit | `references.bib` is in this repository (64 lines); I checked the rendered list, not the file |
| Multi-format sync | One source (`manuscript.tex`) and one PDF (`manuscript.pdf`), the copy reviewed here |

**Note on where to edit.** The manuscript source is `manuscript.tex` at the root of this repository. The files in `review/` are commentary and are not part of the manuscript.
