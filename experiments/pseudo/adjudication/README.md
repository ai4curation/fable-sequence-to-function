# Adjudication of two disputed active sites in test 3

In test 3, Fable 5.2 and Opus 5.5 placed the catalytic residue of two enzymes at a different position from
UniProt, in the wild type and in the mutant, and so called the mutants active. This folder asks which
position is better supported by alignment and structural evidence, without using the tested models' answers as evidence.

| Protein | UniProt (by similarity) | Models | Verdict |
|---|---|---|---|
| YrfG, *E. coli* (P64636) | nucleophile Asp9 | Asp16 | Strong support for Asp16. |
| ENV9, yeast (Q08651) | catalytic serine Ser172 | Ser173 | Ser173 favoured, tentatively. |

## Evidence

**YrfG**
- The experimentally supported nucleophiles of all 7 aligned reviewed relatives in the haloacid dehalogenase
  superfamily map to Asp16, and the one experimentally supported proton donor maps to Asp18.
- In both structural models Asp16 is 2.6 A from Lys149 and 3.1 to 3.3 A from the magnesium ion. Asp9 is
  more than 20 A from every other active-site residue.
- UniProt's other sites for this entry (Lys149, Asp174) agree with the models; only the first motif differs.
- Its SWISS-MODEL template is also distant: 3opx chain A, with 14.16% sequence identity. The stronger
  case for YrfG comes from agreement with seven experimentally annotated nucleophiles and the large
  spatial separation of Asp9, rather than high template identity.

**ENV9**
- UniProt cites O93868 as the source of its positions. The serine of that entry (Ser149) aligns with Ser173
  of ENV9, in the family alignment and in a pairwise alignment. Its tyrosine and lysine align with Tyr202 and
  Lys206, as UniProt has them.
- O93868 Ser149 is annotated with ECO:0000305 (curator inference), citing
  [Hörer et al. (2001)](https://doi.org/10.1074/jbc.M102850200), which assigns the catalytic triad
  from the NADP-bound crystal structure (PDB 1H5Q). Thus the `no ECO:0000269` label in the report
  means the feature lacks ECO:0000269; it does not mean the source lacks experimental structural data.
- In both structural models the Ser173 side chain points at the Tyr202 hydroxyl (3.2 and 4.5 A) and the
  Ser172 side chain points away (7.0 and 6.8 A).
- The SWISS-MODEL template is 1yxm chain A, with 18.48% sequence identity (recorded in the PDB header).
  Its side-chain geometry is supporting evidence, not a direct observation of ENV9.
- [Siddiqah et al. (2017)](https://doi.org/10.1007/s00294-017-0702-y) (PMID 28540421; full text read
  2026-11-21) assayed two ENV9 mutants: N146L, in the predicted active site, and G23-24A, in the
  cofactor-binding motif. Both left only residual oxidoreductase activity. The paper names
  `Y202AMSK206` as the key active-site residues, which agrees with UniProt and with the models. It
  neither mutates nor names a catalytic serine: the text has no mention of Ser172 or Ser173. So it
  does not test either candidate, and does not establish the activity of the S172A mutant used here.

## Limits

- Neither protein has an experimental structure. Both structural models are predictions, and they are not
  independent of sequence homology.
- The two ENV9 candidates are adjacent residues, so the alignment evidence is one column wide.
- No catalytic serine with ECO:0000269 was found among the aligned ENV9 relatives; the sites carrying
  that code are tyrosines. O93868 supplies structural inference for its serine, as described above.
- The relatives are those returned by one UniProt query per case, given in `fetch.py`.

## Effect on test 3

The evidence questions whether these substitutions removed the intended catalytic residues. It does not
establish that D9A YrfG or S172A ENV9 retains activity: a substitution can affect activity without removing
the assigned catalytic residue. Neither mutant's activity was measured here.
`experiments/pseudo/score.py` prints the other-enzyme mutants with and without the two proteins as a
sensitivity analysis. These cases were selected after inspecting the model answers. The figure,
`truth.json`, and the main counts keep all 20; the exclusion does not relabel the mutants as active.

## Files

| File | What it is |
|---|---|
| `fetch.py` | Fetches UniProt features and relatives and aligns them with MAFFT. Needs network and MAFFT. |
| `snapshot/*.json` | Its frozen output, fetched 2026-11-19 (MAFFT 7.505). |
| `adjudicate.py` | Prints the evidence from the snapshot and the models. Offline; compared by `just check` with `expected/adjudication.txt`. |
| `models/alphafill_*.cif` | AlphaFold models with transplanted ligands, from `https://alphafill.eu/v1/aff/ACCESSION`. CC BY 4.0. |
| `models/swissmodel_*.pdb` | SWISS-MODEL Repository homology models, from `https://swissmodel.expasy.org/repository/uniprot/ACCESSION.pdb`. CC BY-SA 4.0. |

The models were downloaded on 2026-11-19 and are committed unchanged.
