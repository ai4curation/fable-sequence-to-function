# Pseudoenzyme references: source check (NEXT_TASKS T15, issue #19)

Done on 2026-11-20 against `manuscript.tex` as merged on `main` (2c6c045). The check was made by a
Claude Opus 5.5 agent, which is one of the models the paper evaluates. Quotes are from the full text
where it could be opened, and otherwise from the Europe PMC abstract.

**Full texts read:** Kwon et al. 2019 (PMC6997932), Zaru et al. 2020 (PMC7160037), Goldberg and
Sreelatha 2023 (PMC10211241).

**Abstracts only:** Xu et al. 2000, Murphy et al. 2017, Adrain 2020, Ribeiro et al. 2019 and 2020.
Publisher pages refused automated access. Someone with a browser session could read Xu (jbc.org),
Ribeiro 2020 and Adrain (Wiley).

| Statement in the text | Source | Verdict | Source passage |
|---|---|---|---|
| "called pseudoenzymes, or dead enzymes" | Murphy 2017; Adrain 2020 | Supported (abstracts) | Murphy: "variously referred to as pseudoenzymes, non-enzymes, dead enzymes, prozymes or 'zombie' proteins". Adrain: "These pseudoenzymes, sometimes called 'dead enzymes'". |
| "an estimated 5 to 10% of the proteins in enzyme families" (as first checked; the text now gives both figures, each with its source) | Ribeiro 2019 | Supported (abstract); other estimates differ | "between 5 and 10% of proteins that make up enzyme families are pseudoenzymes". Zaru 2020 (full text, Introduction) gives "between 10-15% of the members". |
| "many act as regulators"; "dead enzymes commonly act as regulators" | Adrain 2020 | Supported (abstract) | "frequently appearing more versatile as biochemical regulators than their catalytic cousins" |
| "Pseudokinases are the best-studied case" | Kwon 2019 | Supported (full text) | "Protein pseudokinases represent the best understood members of the growing classes of pseudoenzymes" |
| "A survey of enzyme families found that mutation of catalytic residues is not always a good indication of lack of activity" | Ribeiro 2020 | Supported (abstract) | The analyses "challenge ... that mutations in the catalytic residues of enzyme homologues are always a good indication of lack of activity" (UniProtKB and M-CSA, many enzyme families). |
| "residues needed for catalysis have moved elsewhere"; "catalytic residues can be displaced" | Goldberg 2023 | Supported (full text) | "some pseudoenzymes may have migrated amino acids necessary for catalysis"; on WNK1, "migration of the conserved lysine from the β3 VAIK motif to the β2 strand". |
| WNK1 (introduction; Results test 3) | Xu 2000 | Supported (abstract); text now names the subdomain and residue | "lack the invariant catalytic lysine in subdomain II"; "lysine 233 in kinase subdomain I may provide this function. Mutation of this lysine residue to methionine eliminates WNK1 activity"; WNK1 "phosphorylates the exogenous substrate myelin basic protein as well as itself". |
| "UniProt curates pseudoenzymes in Swiss-Prot" | Zaru 2020 | Supported (full text) | Curators "now include the word 'inactive' followed by the missing enzymatic activity in the official name or in a synonym"; "using the search term 'inactive' in the 'Protein name' field allows the retrieval of pseudoenzymes". |
| 688 reviewed entries, 107 kinases | UniProt REST | Supported; text now pins the release and says "a protein name" (any name, with the recommended-name share) | `review/pseudoenzyme_lookups_2026-11-20_rerun.txt`: same counts in release 2026_04 (4 November 2026, still current on 20 November). The original lookup (run at 2026-11-19T02:27Z) recorded no release, so its release is inferred. `protein_name:` matches every protein name: of the 688, 492 have "inactive" in the recommended name, 185 only in an alternative name and 11 only in an Includes/Contains name; of the 107 kinases, 90, 16 and 1 (`scripts/adhoc/uniprot_inactive_name_split.py` on the entry lists in `review/uniprot_2026_04/`). |

**The two estimates are not independent.** Zaru is a co-author of Ribeiro 2019, and Zaru 2020 cites no
source for its 10–15%.

**Caveat from Zaru 2020.** Entries with one active and one inactive domain are annotated as active
enzymes, with an alternative name that describes the lost activity. A name search therefore also
returns some active enzymes.

**Still open.** Five of the eight references were read as abstracts only, so T15 and issue #19 stay
open for a full-text read of those five.

**For the authors (left as LaTeX comments in the Discussion)**
- **MEROPS** (release 12.5 glossary): "A protein of known sequence that can be placed in a peptidase
  family but lacks one or more of the expected catalytic residues is described as a non-peptidase
  homologue. Some non-peptidase homologues are enzymes of other kinds."
- **Gene Ontology:** no guidance specific to pseudoenzymes was found. GO_REF:0000047 covers a NOT
  annotation with IKR evidence where key residues are missing. Zaru 2020: "There is no GO term as such to
  describe the lack of catalytic activity. Instead, the NOT qualifier is used".
