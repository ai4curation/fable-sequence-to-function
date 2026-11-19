# Decoy-substitution control: results

Run on 2026-11-18. Numbers are copied from `results/score_output.txt`, the output of `score_decoys.py`.
Intervals are 95% Wilson intervals. One of the models tested, Claude Fable 5.2, ran and scored this.

## Main result

Fable 5.2 and Opus 5.5 called every decoy active and never named a decoy position as a lost catalytic residue.
The catalytic-site mutants of the same proteins were called active far less often, so the two models respond
to the catalytic position, not to any change in the sequence. Opus 4.6 at low effort treated decoys, mutants
and wild types alike.

| Model (effort) | Wild type called active | Catalytic-site mutant called active | Decoy called active |
|---|---|---|---|
| Fable 5.2 (high) | 58/58 (100%, 94-100) | 4/58 (7%, 3-16) | 58/58 (100%, 94-100) |
| Opus 5.5 (high) | 57/58 (98%, 91-100) | 10/58 (17%, 10-29) | 58/58 (100%, 94-100) |
| Opus 4.6 (low) | 49/58 (84%, 73-92) | 50/58 (86%, 75-93) | 50/58 (86%, 75-93) |

Wild-type and mutant columns are the stored answers from the original run, restricted to the 58 protein and
substitution pairs that have a decoy. The decoy column is new.

Paired by protein, the decoy was called active and the catalytic-site mutant was not in 54 of 58 pairs for
Fable 5.2 and 48 of 58 for Opus 5.5; the reverse never happened (exact McNemar p = 1.1e-16 and 7.1e-15).
For Opus 4.6 the counts were 3 and 3 (p = 1).

## By substitution type (decoy called active / catalytic-site mutant called active)

| Model | Asp to Asn, kinases | Lys to Met, kinases | Site to Ala, other enzymes |
|---|---|---|---|
| Fable 5.2 | 20/20 vs 0/20 | 20/20 vs 1/20 | 18/18 vs 3/18 |
| Opus 5.5 | 20/20 vs 0/20 | 20/20 vs 7/20 | 18/18 vs 3/18 |
| Opus 4.6 | 20/20 vs 18/20 | 18/20 vs 18/20 | 12/18 vs 14/18 |

## Which residue the model says is lost

| Model | Catalytic-site mutant: substituted position named | Decoy: decoy position named | Decoy: any residue named |
|---|---|---|---|
| Fable 5.2 | 55/58 (95%, 86-98) | 0/58 (0%, 0-6) | 3/58 |
| Opus 5.5 | 45/58 (78%, 65-86) | 0/58 (0%, 0-6) | 5/58 |
| Opus 4.6 | 0/58 (0%, 0-6) | 0/58 (0%, 0-6) | 7/58 |

Where Fable 5.2 or Opus 5.5 named a lost residue in a decoy answer, it was a natural departure from the family
consensus elsewhere in the wild-type sequence (for example a variant HRD or DFG motif, or degenerate EF-hands),
not the decoy. In no decoy answer from either model did the decoy position appear among the listed catalytic
residues.

In the decoy answers the curated catalytic residue was still listed as present in 56 of 58 (Fable 5.2) and
54 of 58 (Opus 5.5). The two Fable 5.2 exceptions are Q08651 and P64636, the two enzymes where both models
place the active site elsewhere than the curated position in the original test as well.

## What limits this

1. **Two routes.** The decoys ran here with four extra CLI flags (see `README.md`); the catalytic-site mutants
   are the stored answers from another machine. One mutant was rerun here (P38991, Asp to Asn, Fable 5.2) and
   gave the stored call. Rerunning all 58 mutants per model on this route would make the pairing clean.
2. **One answer per sequence.** No repeats, so the intervals describe sampling of proteins, not run-to-run change.
3. **The decoy label.** "No functional annotation" is not a measurement that the substitution is harmless.
   Because every decoy was called active, this cannot have inflated the result for Fable 5.2 or Opus 5.5; it
   could hide a tendency to miss substitutions that do matter outside the catalytic residues.
4. **One decoy per substitution.** A scan of every Asp or Lys in a few kinases would show whether the response
   is confined to the catalytic positions or also covers other conserved residues.
5. **Opus 4.6 ran at low effort,** as in the original. Its column says nothing about the model at high effort.
6. **Two enzymes have no decoy** (Q46925, P00358): no unannotated Cys other than the catalytic one.

## Cost

Decoy calls: $8.30 (Fable 5.2), $2.87 (Opus 5.5), $1.37 (Opus 4.6). Canary and route checks: about $2.05,
of which $1.69 was the one call that carried 97 connector tools.
