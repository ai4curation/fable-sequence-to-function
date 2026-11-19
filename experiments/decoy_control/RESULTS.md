# Decoy-substitution control: results

All times are UTC and are the times calls returned (`asked_at` is written when a call returns). The decoy
calls returned on 2026-11-19 between 01:56 and 02:06. The catalytic-site mutants and wild types of test 3 were
asked again on the same route; those calls returned between 07:20 and 07:38 the same day. One Fable 5.2 row of
that rerun (P38991 asp_to_asn) returned at 01:56, during the decoy session; it was written by the first version
of `ask_decoys.py` and has no prompt hash. The stored run of test 3 that the first version of this note
compared with has no time in its rows; the repository's README dates it 2026-11-18.

Every count, rate and cost here is printed by `score_decoys.py` (its last section lists the times, row counts,
token ranges and costs of each file), whose output is frozen in `expected/decoy_control.txt` and recomputed by
`just check`. A few are sums or roundings of printed values (300, 174 and 299 rows, 116 replies, $21.62, $1.90,
$1.69), and the curated Lys position of P32328 (198) is from `pseudo/truth.json`.
`scripts/adhoc/find_note_numbers_missing_from_scorer_output.py` is a coarse screen: it lists the numbers of this
note that the output does not hold anywhere. Intervals are 95% Wilson intervals. Two of the tested models worked on this
control: Claude Fable 5.2 wrote the scripts, ran the calls and wrote the first version of this note, and
Claude Opus 5.5 revised the scripts and this note after review. Independent read-only reviews found the
problems listed in issues 11 to 17 and 66 to 76.

## Main result

On one call route, Fable 5.2 and Opus 5.5 called every decoy active and called the catalytic-site mutants of
the same proteins active in 3 and 8 of 58 cases. Neither listed a decoy position among the lost or the
catalytic residues. So for these two models a single substitution at an unannotated position, away from the
catalytic site, left the protein called active, while the substitution at the catalytic site did not. One
protein is an exception in the other direction: Opus 5.5 did not call the P26725 wild type active ("no" in the
rerun, "uncertain" in the stored run) but called its decoy active; that decoy is the second-to-last residue. The design does
not test a substitution at another conserved or functional position: the decoy rule excluded positions within
three residues of any annotated site and, in kinases, the catalytic loop, the DFG motif and the subdomain IX
Asp. The decoys are a median of 46 residues from the nearest curated catalytic position (minimum 5; 6 of 58
within 10).

Opus 4.6 at low effort called decoys, catalytic-site mutants and wild types active at similar rates.

"Called active" means the answer "yes". "No", "uncertain" and an answer without the field all count as not
called active, as in Figure 1.

| Model (effort) | Wild type called active | Catalytic-site mutant called active | Decoy called active |
|---|---|---|---|
| Fable 5.2 (high) | 38/38 (100%, 91-100) | 3/58 (5%, 2-14) | 58/58 (100%, 94-100) |
| Opus 5.5 (high) | 37/38 (97%, 87-100) | 8/58 (14%, 7-25) | 58/58 (100%, 94-100) |
| Opus 4.6 (low) | 34/38 (89%, 76-96) | 45/58 (78%, 65-86) | 50/58 (86%, 75-93) |

The three columns come from one route (see `README.md`) and cover the 38 proteins that have a decoy. Each
kinase has two mutants and two decoys, so the mutant and decoy columns count 58 and the wild-type column 38.
One Opus 5.5 mutant answer (Q8VYY5 lys_to_met) ends before the `catalytically_active` field and is counted as
not called active. Leaving it out gives 8/57 mutants called active.

**Paired tests.** The per-type tests below have one pair per protein. For Fable 5.2 and Opus 5.5, the decoy
was called active and the catalytic-site mutant was not in 20 of 20 Asp to Asn pairs (p = 1.9e-06, both
models), 20 and 15 of 20 Lys to Met pairs (p = 1.9e-06 and 6.1e-05), and 15 of 18 Site to Ala pairs (p =
6.1e-05, both). The reverse never happened. Pooled over the three types the counts are 55 and 50 of 58, but the
58 pairs come from 38 proteins, and 40 of them are kinases tested at the same two motif positions, so the
pooled p-values (5.6e-17 and 1.8e-15; 3.6e-15 for Opus 5.5 without Q8VYY5) overstate the evidence. For
Opus 4.6 the pooled counts were 6 and 1 (p = 0.12). Decoys were called active about as often as wild types,
so these tests mostly restate the wild-type against mutant contrast. What the control adds is the decoy
column.

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

**These counts mean little for Opus 4.6.** They compare position numbers, and Opus 4.6 numbers residues
loosely: of the catalytic residues it lists, the residue at the stated position of the given sequence is the
one it names for 68 of 316 in the rerun, 42 of 313 in the stored run and 48 of 191 in the decoy answers.
For Fable 5.2 and Opus 5.5 the rates are 583 of 584 and 690 of 697 in the rerun, and 395 of 397 and 460 of 465
in the decoy answers. Opus 4.6's wild-type answers also omit a curated catalytic position for 37 of the 40
kinases and enzymes in both runs.

Where Fable 5.2 or Opus 5.5 named a lost residue in a decoy answer, it was a natural departure from the family
consensus elsewhere in the wild-type sequence (for example a variant HRD or DFG motif, or degenerate EF-hands),
not the decoy.

In the decoy answers the curated catalytic residue was still listed in 56 of 58 (Fable 5.2) and 54 of 58
(Opus 5.5).
- **Both models:** the decoy answers for Q08651 and P64636 omit it. For Q08651 both list S173 where the
  curated position is 172. The wild-type answers for these two proteins omit it as well.
- **Opus 5.5 only:** P26725 is omitted in the decoy and wild-type answers alike. The Q8VYY5 Asp decoy answer
  lists D338 where the curated position is 339.

**How far the decoy was from what the model calls catalytic.** In each decoy answer, the distance from the
decoy to the nearest residue the answer lists as catalytic, in the model's own numbering, has a median of 33.5
residues for Fable 5.2 and 32 for Opus 5.5. It is within 10 residues in 15 and 17 of 58 answers, and within 5
in 4 and 5.

## The rerun against the stored run

The catalytic-site mutants and wild types of the 40 kinases and enzymes (100 questions per model) were asked
again on the route of the decoys. The call (active or not) is the same as in the stored run for 99 of 100
questions (Fable 5.2), 96 of 100 (Opus 5.5) and 88 of 100 (Opus 4.6 at low effort).
- **Fable 5.2:** the one difference is a Lys to Met kinase mutant.
- **Opus 5.5:** all four differences are Lys to Met kinase mutants, three turning from yes to no and one from
  no to yes, so 7 of 20 Lys to Met mutants called active became 5 of 20.

`expected/decoy_control.txt` lists each difference. With one answer per question, this cannot separate an
effect of the route from run-to-run variation.

The same comparison against the stored run is also printed there. Mutants called active were 4/58, 10/58 and
50/58 for Fable 5.2, Opus 5.5 and Opus 4.6.

**Opus 4.6 used thinking more often in the rerun.** Answers with thinking tokens:

| Opus 4.6 run | Answers with thinking tokens |
|---|---|
| Stored run | 4 of 100 |
| Rerun | 16 of 100 |
| Decoys | 12 of 58 |

In the rerun, 5 of the 10 mutant answers with thinking were not called active, against 8 of the 50 without.
The files cannot show why the rate differs (route, time or serving). The agreement of 88 of 100 should be read
with this in mind. It also qualifies the Opus 4.6 row of the main table. Fable 5.2 and Opus 5.5 used thinking
in every answer of all three runs.

All 300 rerun calls and all 174 decoy calls were usable: none failed and none was marked for input size.
- **Prompt hash:** 299 of the 300 rerun rows record the hash of the question sent. For each, it equals the hash
  of the test 3 prompt plus that question's sequence. The decoy rows and the first rerun row predate the hash
  field.
- **Requests and web access:** the same 299 rows each show one request and no web search or fetch request in
  the tool's usage record.

## The models sometimes notice the decoy, from memory

The structured answer never lists the decoy, but the reply text sometimes mentions it. The decoy position
number appears in 2 of 58 Fable 5.2 replies and 1 of 58 Opus 5.5 replies; `score_decoys.py` lists them. In
both Fable 5.2 cases (O48814, P0A6L2) the model says the residue differs from the wild type it recalls and
lies outside the catalytic residues. Opus 5.5 names the P0A6L2 substitution the same way. So the models can
hold a remembered wild-type sequence, notice a departure from it and still judge it harmless. This is seen in
3 of 116 replies, so it shows that recall can enter the judgement, not how often it does. The Opus 5.5 P0A6L2
reply does not say it is recalling, and it also mentions substitutions near the N-terminus, where the given
sequence does not differ from the wild type.

The one Opus 4.6 reply that holds a decoy number (P32328, position 188) does not notice the decoy. Its
Lys-decoy answer lists K188 as the catalytic lysine although the given sequence has Met there, and calls the
protein active; that is the one "decoy position listed as catalytic" in `expected/decoy_control.txt`. Opus 4.6
lists K188 for this protein in its stored wild-type answer too (the wild type has a Lys at 188; the curated
catalytic Lys is 198), so the answer repeats a remembered or misnumbered residue rather than reading the
decoy.

## What limits this

1. **What the decoy tests.** A substitution at an unannotated position away from the catalytic site. Not a
   change at another conserved or functional position. A scan of every Asp or Lys in a few kinases would show
   whether the response is confined to the catalytic positions.
2. **One answer per sequence in each run.** The scored decoys were asked once and the mutants and wild types
   twice at the same effort (the rerun); the intervals describe sampling of proteins, not run-to-run
   change. The rerun shows the size of that change for the mutants: up to 4 of 100 calls for the two newer
   models, all in Lys to Met kinase mutants.
3. **The decoy label.** "No functional annotation" is not a measurement that the substitution is harmless.
   Because every decoy was called active by Fable 5.2 and Opus 5.5, this cannot have inflated their result. It
   could hide a tendency to miss substitutions that do matter outside the catalytic residues.
4. **Easy decoys.** Enzyme decoys have no domain restriction; three are in places a model could dismiss without
   reading the catalytic site (see `README.md`).
5. **Recall.** These are well-studied proteins. The control does not show what the models do with a protein
   they cannot recall.
6. **Decoy rows cannot be tied to `decoys.json` by hash.** They were written before rows recorded the
   question's hash. Their input token counts and the residues their answers list are consistent with the decoy
   sequences.
7. **Opus 4.6 ran at low effort,** as in the stored run. Its row says nothing about the model at high effort.
8. **Two enzymes have no decoy** (Q46925, P00358): no unannotated Cys other than the catalytic one.

## Cost

| Calls | Fable 5.2 | Opus 5.5 | Opus 4.6 |
|---|---|---|---|
| Decoys | $8.30 | $2.87 | $1.37 |
| Rerun of the mutants and wild types | $14.48 | $5.12 | $2.01 |

The rerun cost $21.62 in total.
- **Canary calls with the original flags:** $1.90, of which $1.69 was the one call that carried 97,813 input
  tokens.
- **Route checks on the cheapest model:** $0.0008 for the seven saved calls in `cli_context_check.json`. An
  earlier, unsaved check (the 97-tool observation in `README.md`) has no recorded cost.
