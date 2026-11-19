# Connecting the manuscript to "dead" proteins (pseudoenzymes)

Written 2026-11-18 by Claude Fable 5.2, one of the models the manuscript evaluates. Line numbers refer to
`manuscript.tex` on `main` (commit `3dbfa9b`). Look-ups are reproduced by `review/scripts/pseudoenzyme_lookups.sh`;
the saved output is `review/pseudoenzyme_lookups_2026-11-18.txt`.

## 1. Is there a database of dead proteins?

Not a single dedicated one that I could find. Two web searches and the reviews below turned up no cross-family
pseudoenzyme database; that is a search result, not a published statement, and the searches were not exhaustive.
What exists:

| Resource | What it offers | Checked how |
|---|---|---|
| UniProtKB/Swiss-Prot | Curated pseudoenzymes carry a name with "Inactive" or "Probable inactive". Today 688 reviewed entries have "inactive" in the protein name, 139 of them "probable inactive", and 107 are in the protein kinase superfamily. 465 of the 688 carry a caution comment. | Anonymous UniProt queries, 2026-11-18 |
| UniProt paper on the subject | Zaru et al. 2020 describe how UniProtKB curates pseudoenzymes and the problems in doing it consistently. | Abstract only; the publisher blocked the full text |
| M-CSA | Curated catalytic residues for reference enzymes. Ribeiro et al. 2020 used it with UniProtKB to find pseudoenzymes by comparison. | Abstracts |
| ProKinO pseudokinase classification | Kwon et al. 2019 (already cited) classified nearly 30,000 eukaryotic, 1,500 bacterial and 20 archaeal pseudokinase sequences into 86 families. | Abstract |
| MEROPS | Said to list non-peptidase homologues. | A search summary only; not checked at the source |

The manuscript's test 3 already draws its natural pseudokinases from Swiss-Prot by the "inactive" name, so it is
using the main resource without saying so.

## 2. What the literature says that bears on the manuscript

1. **Definition and names.** Pseudoenzymes are homologues of enzymes that are shown or predicted to have no
   enzyme activity because conserved catalytic residues have changed (Ribeiro et al. 2019). They are also called dead
   enzymes, non-enzymes, prozymes and zombie proteins (Murphy et al. 2017; Adrain 2020).
2. **How common.** Between 5 and 10% of the proteins in enzyme families (Ribeiro et al. 2019). About 10% of
   kinases in model vertebrates (Kwon et al. 2019).
3. **Dead is not functionless.** They act as allosteric regulators, scaffolds and substrate traps (Adrain 2020;
   Ribeiro et al. 2019). The annotation error is the catalytic term, not the presence of a function.
4. **Residue loss is a prediction, not proof.** Ribeiro et al. 2020 conclude from a survey of enzyme families
   that a mutated catalytic residue does not always indicate lack of activity, and that UniProtKB does not
   mark every inactive protein as such. Goldberg and Sreelatha 2023 note that in some pseudoenzymes the
   residues needed for catalysis have moved elsewhere in the sequence, leaving the protein active. The textbook
   case is WNK1, named for lacking the catalytic lysine at its usual position and nonetheless an active
   kinase (Xu et al. 2000).
5. **The reverse also happens.** A protein can keep every catalytic residue and be inactive. kin-32 in the
   manuscript is one: its Swiss-Prot name rests on an assay, not on a missing residue (see edit E4).

Points 4 and 5 are the ones the draft most needs. They set the limit of what any sequence-only reader can
claim, and two of the draft's own observations (kin-32 and ROP17) are instances of them.

## 3. Suggested edits

**E1. Introduction, lines 44 to 49. Change.** Name the concept, give its size and say where the cases are recorded.

> Next-residue accuracy does not say whether a model can do anything a curator needs. Function prediction
> tools make characteristic errors, and one of the most damaging is to assign a catalytic activity to a
> protein that keeps the fold of an enzyme and has lost the activity \citep{decrecy2025limitations}. Such
> proteins are called pseudoenzymes, or dead enzymes \citep{murphy2017biozombie,adrain2020dead}. They make up
> an estimated 5 to 10\% of the proteins in enzyme families \citep{ribeiro2019pseudoenzymes}, and many have
> regulatory roles that depend on the retained fold. Pseudokinases are the best-studied case
> \citep{kwon2019pseudokinases}. A model that only recognises the family will repeat the error; a model that
> reads the residues should not.

**E2. Introduction, after E1. Add.** State the limit before the tests, so the Discussion does not have to walk a claim back.

> Reading the residues has a known limit. The loss of a catalytic residue predicts inactivity and does not
> prove it: some proteins first classed as pseudoenzymes are active through a relocated residue, as in the
> WNK kinases \citep{xu2000wnk1}, and a survey of enzyme families found that catalytic-residue mutation is
> not always a good indication of lack of activity \citep{ribeiro2020pitfalls}.

**E3. Methods, test 3, lines 79 to 85. Change.** The heading says "pseudoenzymes", but of the 120 sequences 60
are engineered mutants and only 20 are natural pseudoenzymes, and the two are different things.

- Change the heading to "Test 3, dead mutants and natural pseudoenzymes".
- Add one sentence of definition: a dead mutant is an active enzyme with one catalytic residue substituted by us;
  a natural pseudoenzyme is an evolved homologue, usually different at many positions.
- Add where the natural set comes from and how large the pool is:

> Swiss-Prot marks curated pseudoenzymes in the protein name \citep{zaru2020uniprot}; 688 reviewed entries
> carried ``inactive'' in the name when we queried it (18 November 2026), 107 of them in the protein kinase
> superfamily.

  The citation of Zaru et al. for the naming convention should be checked against the paper's text, which I could not open.

**E4. Results, lines 171 to 174. Change.** Replace "We did not examine the basis of the Swiss-Prot name." with the basis, which turns the exception into a finding.

> The Swiss-Prot name rests on an assay, not on the sequence: the entry records that the protein ``has
> apparently no tyrosine kinase activity in vitro when expressed in mammalian cells''. kin-32 is thus a
> pseudoenzyme that keeps its catalytic motifs, a class that no reading of catalytic residues can detect
> \citep{ribeiro2020pitfalls}.

**E5. Results, lines 180 to 181. Add** after "proposed that a nearby lysine would take its place".

> A relocated catalytic lysine is real in the WNK kinases \citep{xu2000wnk1}, so the argument has a
> precedent; here it was applied to a substitution we had introduced into an active kinase.

**E6. Discussion, lines 230 to 234. Change.** Bound the practical claim by points 4 and 5 above, and say what a flag should lead to.

> For annotation review, the practical use is narrow. A sequence-only read can flag a protein that has lost
> a canonical catalytic residue before a catalytic term is accepted. It cannot show that the protein is
> inactive, since residues can be relocated \citep{xu2000wnk1,goldberg2023pseudoenzymes}, and it cannot find
> pseudoenzymes that keep every catalytic residue, such as kin-32. A flag should prompt a curator to check
> the catalytic term; it says nothing against the protein having a function, since dead enzymes commonly
> act as regulators and scaffolds \citep{adrain2020dead}.

  Keep the existing sentences on provenance and confident errors after this.

**E7. Abstract, last sentence. Change.** "Good enough to triage pseudoenzyme over-annotation" is not what was
tested. The tests measured detection of substitutions we introduced and recall of named pseudokinases; no
over-annotated entry was examined. Either run experiment X3 below, or write:

> We conclude that sequence-only reading by these models can flag the loss of a catalytic residue for a
> curator to check, and is not a citable source of evidence.

**E8. Limitations, lines 236 to 243. Add.**

> Dead mutants made by one substitution are not natural pseudoenzymes, which usually differ from active
> relatives at many positions and can be inactive for reasons that leave the catalytic residues intact.

**E9. Results, test 3. Add** the decoy control from `experiments/decoy_control/` (pull request 10) once the
original mutants have been rerun on the same route. It answers the obvious objection to a dead-mutant test, that
the model reacts to any change.

**E10. Keywords and title.** If the journal takes keywords, add "pseudoenzyme". I would not put "dead" in the title.

## 4. Experiments the dead-protein resources make possible

| | Experiment | What it adds | Caveat |
|---|---|---|---|
| X1 | Natural pseudoenzymes outside kinases: sample from the 581 Swiss-Prot entries named "inactive" that are not in the kinase superfamily, each with an active paralogue. | Extends the natural set beyond one family. | Recall: score separately the answers whose protein name already says inactive, as the draft does for kinases. |
| X2 | Obscure pseudokinases: bacterial and archaeal sequences from the Kwon et al. classification. | Natural cases the model is unlikely to know by name. | The classification is itself based on motifs, so agreement is partly circular. |
| X3 | Over-annotation proper: unreviewed entries that carry an EC number but lack the catalytic residue of their reference homologue. | Tests the use the abstract claims. | Needs an alignment to a Swiss-Prot or M-CSA reference to define truth. |
| X4 | The 41 Swiss-Prot entries named "inactive" that still carry an active-site feature, and the 39 that carry an EC number. | A small set of curated edge cases. | I did not look at what these entries are. |

X1 is the cheapest and closest to the existing script.

## 5. References to add (all resolve in CrossRef; see the saved look-up output)

| Key | Reference | DOI |
|---|---|---|
| `murphy2017biozombie` | Murphy JM, Farhan H, Eyers PA. Bio-Zombie: the rise of pseudoenzymes in biology. Biochem Soc Trans 2017;45:537-544. | 10.1042/BST20160400 |
| `ribeiro2019pseudoenzymes` | Ribeiro AJM, Das S, Dawson N, et al. Emerging concepts in pseudoenzyme classification, evolution, and signaling. Sci Signal 2019;12:eaat9797. | 10.1126/scisignal.aat9797 |
| `ribeiro2020pitfalls` | Ribeiro AJM, Tyzack JD, Borkakoti N, Thornton JM. Identifying pseudoenzymes using functional annotation: pitfalls of common practice. FEBS J 2020;287:4128-4140. | 10.1111/febs.15142 |
| `zaru2020uniprot` | Zaru R, Magrane M, Orchard S, UniProt Consortium. Challenges in the annotation of pseudoenzymes in databases: the UniProtKB approach. FEBS J 2020;287:4114-4127. | 10.1111/febs.15100 |
| `adrain2020dead` | Adrain C. Pseudoenzymes: dead enzymes with a lively role in biology. FEBS J 2020;287:4102-4105. | 10.1111/febs.15535 |
| `goldberg2023pseudoenzymes` | Goldberg T, Sreelatha A. Emerging functions of pseudoenzymes. Biochem J 2023;480:715-728. | 10.1042/BCJ20220373 |
| `xu2000wnk1` | Xu B, English JM, Wilsbacher JL, et al. WNK1, a novel mammalian serine/threonine protein kinase lacking the catalytic lysine in subdomain II. J Biol Chem 2000;275:16795-16801. | 10.1074/jbc.275.22.16795 |

Optional, for a fuller background sentence: Todd, Orengo and Thornton 2002 (Structure 10:1435-1451,
10.1016/S0969-2126(02)00861-4); Pils and Schultz 2004 (J Mol Biol 340:399-404, 10.1016/j.jmb.2004.04.063);
Eyers and Murphy 2016 (BMC Biol 14:98, 10.1186/s12915-016-0322-x); M-CSA, Ribeiro et al. 2018 (Nucleic Acids Res
46:D618-D623, 10.1093/nar/gkx1012); Min et al. 2004, the WNK1 kinase domain structure (Structure 12:1303-1311,
10.1016/j.str.2004.04.014).

## 6. What I did and did not verify

- **Verified:** every DOI above resolves in CrossRef to the stated title, authors, journal, volume and pages.
  Abstracts of the six reviews and of Kwon et al. were read through Europe PMC; statements attributed to them
  above paraphrase those abstracts. For WNK1 I relied on the article title. UniProt counts and the kin-32 comment come from
  anonymous UniProt queries on 2026-11-18.
- **Not verified:** the full text of any of these papers (the publisher and PubMed Central pages refused the
  request). That matters most for E3, which cites Zaru et al. for the naming convention, and for any number
  beyond the abstracts.
- **Not verified:** that WNK1's catalytic lysine sits in subdomain I, which is my recollection; check Xu et al.
  or Min et al. before saying where it moved to. The suggested text avoids stating the location.
- **Not verified:** the MEROPS statement; whether CASK, another kinase reclassified as active, is a suitable
  second example (I confirmed only that a paper titled "CASK functions as a Mg2+-independent neurexin kinase"
  exists); and what the Gene Ontology guidance says about annotating pseudoenzymes.
- **The counts will drift.** They are from the live UniProt release on the query date, not a pinned release.
