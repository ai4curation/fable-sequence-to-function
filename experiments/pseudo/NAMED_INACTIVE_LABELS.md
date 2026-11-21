# The 20 kinase-fold proteins named "inactive"

`build.py` selected the `pseudo` group of `truth.json` by one criterion: a reviewed UniProt entry in the
protein kinase superfamily whose recommended name contains "inactive" (human, mouse and rat excluded). No
label was checked against the literature. Agreement between a model and this set is agreement with a
Swiss-Prot name.

## Labels checked against the full text

Three labels were raised in an external review of the manuscript (the issue on natural pseudokinase
labels). The full text of both sources was read on 21 November 2026. The other 17 labels have not been
checked.

| Protein | Source | What the paper reports |
|---|---|---|
| RLK902, Q9LVI6 | Tarutani et al. 2004, Biosci Biotechnol Biochem 68:2581-2587, doi 10.1271/bbb.68.2581 (PMID 15618630); J-STAGE PDF | Results, "Autophosphorylation of the kinase domains of RLK902 and RKL1": GST fusions of both kinase domains, purified from E. coli and incubated with radiolabelled ATP, gave phosphorylated bands (their Fig. 1). "This result indicated that RLK902 and RKL1 are functional protein kinases capable of autophosphorylation." The Discussion adds that the recombinant kinases did not phosphorylate the three interacting clones. No kinase-dead control is shown for the assay. |
| RKL1, Q9LP77 | same | Same assay and conclusion as RLK902. |
| kin-32, Q95YD4 | Cram, Fontanez and Schwarzbauer 2008, Dev Dyn 237:837-846, doi 10.1002/dvdy.21457 (PMID 18297732); PMC3937857 | HA-KIN-32 immunoprecipitated from transfected NIH3T3 cells was tested in vitro against polyglutamine-tyrosine. "No measurable activity was detected in the HA-KIN-32 sample suggesting that KIN-32 is not an active kinase." The Discussion hedges: "It is possible that KIN-32 is a kinase in C. elegans, but was not activated by adhesion when expressed in 3T3 cells. However, it seems more likely that differences in critical functional residues between mammalian FAK and KIN-32 explain the lack of kinase activity." KIN-32 lacks the equivalent of FAK Y397. |

The review's further claim that later work reports RLK902 phosphorylating BSK1 was not checked.

So for RLK902 and RKL1 the Swiss-Prot name "inactive" is contradicted by one published in vitro assay,
and for kin-32 it is supported by one. Neither settles activity in the organism.

Fable 5.2, Opus 5.5, Gemini 4 Neon and Opus 4.6 (high effort) call RLK902 and RKL1 inactive and kin-32 active.
