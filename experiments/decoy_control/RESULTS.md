# Decoy-substitution control: results

Run on 2026-11-18. Numbers are copied from `results/score_output.txt`, the output of `score_decoys.py`.
Intervals are 95% Wilson intervals. One of the models tested, Claude Fable 5.2, ran and scored this.

## Main result

Fable 5.2 and Opus 5.5 called every decoy active and never named a decoy position as a lost catalytic residue.
In the stored original run the catalytic-site mutants of the same proteins were called active far less often.
Taken together this indicates that the two models respond to the catalytic position, not to any change in the
sequence. It is not yet a within-run comparison (limit 1). Opus 4.6 at low effort treated decoys, mutants and
wild types alike.

"Called active" means the answer "yes". "No" and "uncertain" both count as not called active, as in the
original figure. Of Opus 5.5's 48 mutants not called active, 3 were "uncertain"; no decoy answer from Fable 5.2
or Opus 5.5 was "uncertain".

| Model (effort) | Wild type called active | Catalytic-site mutant called active | Decoy called active |
|---|---|---|---|
| Fable 5.2 (high) | 38/38 (100%, 91-100) | 4/58 (7%, 3-16) | 58/58 (100%, 94-100) |
| Opus 5.5 (high) | 37/38 (97%, 87-100) | 10/58 (17%, 10-29) | 58/58 (100%, 94-100) |
| Opus 4.6 (low) | 31/38 (82%, 67-91) | 50/58 (86%, 75-93) | 50/58 (86%, 75-93) |

The wild-type and mutant columns are the stored answers from the original run, restricted to the 38 proteins
that have a decoy. Each kinase has two mutants and two decoys, so the mutant and decoy columns count 58 pairs
and the wild-type column counts 38 proteins. The decoy column is new.

Paired by protein, the decoy was called active and the catalytic-site mutant was not in 54 of 58 pairs for
Fable 5.2 and 48 of 58 for Opus 5.5; the reverse never happened (exact McNemar p = 1.1e-16 and 7.1e-15).
For Opus 4.6 the counts were 3 and 3 (p = 1). The 58 pairs come from 38 proteins, so they are not fully
independent; the per-type tests below have one pair per protein and give p values of 6.1e-05 or smaller for
Fable 5.2 and 0.00024 or smaller for Opus 5.5. Since decoys were called active as often as wild types, this
test mostly restates the original wild-type versus mutant contrast; what the control adds is the decoy column.

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
54 of 58 (Opus 5.5). The two Fable 5.2 exceptions are Q08651 and P64636. Both models also omit the curated
position for these two, and for P26725, in the stored wild-type answers.

## The models sometimes notice the decoy, from memory

The structured answer never lists the decoy, but the free text sometimes mentions it. The decoy position number
appears in 2 of 58 Fable 5.2 answers and 1 of 58 Opus 5.5 answers. In both Fable 5.2 cases (O48814, P0A6L2)
the model says the residue differs from the wild type it recalls, and that it lies outside the catalytic
residues. Opus 5.5 names the P0A6L2 substitution the same way. So the models can hold a remembered wild-type
sequence, notice a departure from it and still judge it harmless. This fits reading 1 in `README.md`, and it
also shows that the judgement draws on recalled sequences, not on the given sequence alone. Opus 4.6 listed one
decoy position (P32328, 188) as the catalytic lysine although the residue there is now Met.

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

Decoy calls: $8.30 (Fable 5.2), $2.87 (Opus 5.5), $1.37 (Opus 4.6). Canary calls with the original flags:
$1.90, of which $1.69 was the one call that carried 97,811 input tokens. One bridging rerun: $0.12. Route
checks on the cheapest model: under $0.05.
