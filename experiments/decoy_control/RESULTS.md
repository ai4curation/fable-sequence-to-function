# Decoy-substitution control: results

Decoys asked on 2026-11-18; the catalytic-site mutants and wild types of test 3 asked again on the same route on
2026-11-19. Numbers are copied from `expected/decoy_control.txt`, the output of `score_decoys.py`, which
`just check` recomputes; the few counts it does not print come from
`scripts/adhoc/decoy_results_note_facts.py`. Intervals are 95% Wilson intervals. One of the models tested,
Claude Fable 5.2, ran and scored this.

## Main result

Fable 5.2 and Opus 5.5 called every decoy active and never named a decoy position as a lost catalytic residue.
Asked on the same route, they called the catalytic-site mutants of the same proteins active in 3 and 8 of 58
cases. The two models respond to the catalytic position, not to any change in the sequence. Opus 4.6 at low
effort treated decoys, mutants and wild types nearly alike.

"Called active" means the answer "yes". "No", "uncertain" and a missing value all count as not called active,
as in Figure 1.

| Model (effort) | Wild type called active | Catalytic-site mutant called active | Decoy called active |
|---|---|---|---|
| Fable 5.2 (high) | 38/38 (100%, 91-100) | 3/58 (5%, 2-14) | 58/58 (100%, 94-100) |
| Opus 5.5 (high) | 37/38 (97%, 87-100) | 8/58 (14%, 7-25) | 58/58 (100%, 94-100) |
| Opus 4.6 (low) | 34/38 (89%, 76-96) | 45/58 (78%, 65-86) | 50/58 (86%, 75-93) |

All three columns were collected on the same route (see `README.md`), restricted to the 38 proteins that have a
decoy. Each kinase has two mutants and two decoys, so the mutant and decoy columns count 58 pairs and the
wild-type column counts 38 proteins. Of the mutants not called active, none was "uncertain" for Fable 5.2 or
Opus 5.5 (one Opus 5.5 answer left the field empty); 10 were "uncertain" for Opus 4.6.

Paired by protein, the decoy was called active and the catalytic-site mutant was not in 55 of 58 pairs for
Fable 5.2 and 50 of 58 for Opus 5.5; the reverse never happened (exact McNemar p = 5.6e-17 and 1.8e-15).
For Opus 4.6 the counts were 6 and 1 (p = 0.12). The 58 pairs come from 38 proteins, so they are not fully
independent; the per-type tests below have one pair per protein and give p = 6.1e-05 or smaller for both
Fable 5.2 and Opus 5.5. Since decoys were called active as often as wild types, this test mostly restates the
wild-type versus mutant contrast; what the control adds is the decoy column.

## By substitution type (decoy called active / catalytic-site mutant called active, same route)

| Model | Asp to Asn, kinases | Lys to Met, kinases | Site to Ala, other enzymes |
|---|---|---|---|
| Fable 5.2 | 20/20 vs 0/20 | 20/20 vs 0/20 | 18/18 vs 3/18 |
| Opus 5.5 | 20/20 vs 0/20 | 20/20 vs 5/20 | 18/18 vs 3/18 |
| Opus 4.6 | 20/20 vs 15/20 | 18/20 vs 19/20 | 12/18 vs 11/18 |

## Which residue the model says is lost

| Model | Catalytic-site mutant: substituted position named | Decoy: decoy position named | Decoy: any residue named |
|---|---|---|---|
| Fable 5.2 | 55/58 (95%, 86-98) | 0/58 (0%, 0-6) | 3/58 |
| Opus 5.5 | 48/58 (83%, 71-90) | 0/58 (0%, 0-6) | 5/58 |
| Opus 4.6 | 2/58 (3%, 1-12) | 0/58 (0%, 0-6) | 7/58 |

Where Fable 5.2 or Opus 5.5 named a lost residue in a decoy answer, it was a natural departure from the family
consensus elsewhere in the wild-type sequence (for example a variant HRD or DFG motif, or degenerate EF-hands),
not the decoy. No decoy answer from either model lists the decoy position among the catalytic residues
(0/58 each). Opus 4.6 listed one (P32328, position 188) as the catalytic lysine although the residue there is
now Met.

In the decoy answers the curated catalytic residue was still listed as present in 56 of 58 (Fable 5.2) and
54 of 58 (Opus 5.5). The two Fable 5.2 exceptions are Q08651 and P64636. Both models also omit the curated
position for these two in their wild-type answers on this route, and Opus 5.5 omits it for P26725 as well.

## The rerun against the stored run

The catalytic-site mutants and wild types of the 40 kinases and enzymes (100 questions per model) were asked
again on the route of the decoys. The call (active or not) is the same as in the stored run of 2026-11-18 for
99 of 100 questions (Fable 5.2), 96 of 100 (Opus 5.5) and 88 of 100 (Opus 4.6 at low effort). All differences
are listed in `expected/decoy_control.txt`. For Fable 5.2 and Opus 5.5 every difference is a Lys to Met
kinase mutant. With one answer per question, this cannot separate an effect of the route from run-to-run
variation. The same table computed against the stored run is also in `expected/decoy_control.txt`: 4/58 and
10/58 mutants called active for Fable 5.2 and Opus 5.5, and 50/58 for Opus 4.6.

All 300 rerun calls and all 174 decoy calls were usable: none failed and none was marked for input size. The
299 rerun rows that store the tool's usage record each show one request and no web search or fetch request;
the decoy rows and one earlier rerun row were written before that record was stored.

## The models sometimes notice the decoy, from memory

The structured answer never lists the decoy as lost, but the reply sometimes mentions it. The decoy position
number appears in 2 of 58 Fable 5.2 replies and 1 of 58 Opus 5.5 replies (`score_decoys.py` lists them). In
both Fable 5.2 cases (O48814, P0A6L2) the model says the residue differs from the wild type it recalls, and
that it lies outside the catalytic residues. Opus 5.5 names the P0A6L2 substitution the same way. So the
models can hold a remembered wild-type sequence, notice a departure from it and still judge it harmless. This
fits reading 1 in `README.md`, and it also shows that the judgement draws on recalled sequences, not on the
given sequence alone. The one Opus 4.6 reply with the number is the P32328 case above.

## What limits this

1. **One answer per sequence.** No repeats, so the intervals describe sampling of proteins, not run-to-run
   change. The rerun shows the size of that change for the mutants: up to 4 of 100 calls for the two newer
   models.
2. **The decoy label.** "No functional annotation" is not a measurement that the substitution is harmless.
   Because every decoy was called active, this cannot have inflated the result for Fable 5.2 or Opus 5.5; it
   could hide a tendency to miss substitutions that do matter outside the catalytic residues.
3. **One decoy per substitution.** A scan of every Asp or Lys in a few kinases would show whether the response
   is confined to the catalytic positions or also covers other conserved residues.
4. **Easy decoys.** Enzyme decoys have no domain restriction; three are in places a model could dismiss without
   reading the catalytic site (see `README.md`).
5. **Recall.** These are well-studied proteins. The control does not show what the models do with a protein
   they cannot recall.
6. **Opus 4.6 ran at low effort,** as in the original. Its row says nothing about the model at high effort.
7. **Two enzymes have no decoy** (Q46925, P00358): no unannotated Cys other than the catalytic one.

## Cost

Decoy calls: $8.30 (Fable 5.2), $2.87 (Opus 5.5), $1.37 (Opus 4.6). Rerun of the mutants and wild types:
$14.48, $5.12 and $2.01. Canary calls with the original flags: $1.90, of which $1.69 was the one call that
carried 97,811 input tokens. Route checks on the cheapest model: under $0.05.
