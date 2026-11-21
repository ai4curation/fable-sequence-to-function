# The 20 kinase-fold proteins named "inactive"

`build.py` selected the `pseudo` group of `truth.json` by one criterion: a reviewed UniProt entry in the
protein kinase superfamily whose recommended name contains "inactive" (human, mouse and rat excluded). No
label was checked against the literature. Agreement between a model and this set is agreement with a
Swiss-Prot name.

## Labels a reviewer has questioned

These were raised in an external review of the manuscript (the issue on natural pseudokinase labels). They
are recorded here as leads. The sources have **not** been read in this repository's checks.

| Protein | Claim in the review | Source named | Status |
|---|---|---|---|
| RLK902, Q9LVI6 | Autophosphorylation reported; later work reports phosphorylation of BSK1 | Tarutani et al. 2004, Biosci Biotechnol Biochem 68:2581 (PMID 15618630) | Not confirmed. The abstract describes a yeast two-hybrid screen with the kinase domains and does not mention autophosphorylation. Needs the full text. |
| RKL1, Q9LP77 | Autophosphorylation of the recombinant kinase domain | same | Not confirmed, as above. |
| kin-32, Q95YD4 | No detectable activity under the assay used; may be active in the worm | PMID 18297732 | UniProt's function note, with this paper as its evidence, reads "Has apparently no tyrosine kinase activity in vitro when expressed in mammalian cells". Full text not read. |

Fable 5.2, Opus 5.5 and Gemini 4 Neon call RLK902 and RKL1 inactive and kin-32 active.
