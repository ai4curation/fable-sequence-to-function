# Results: Qwen base models on protein sequences, and weight writes

Run on 2026-11-19. Every number here is printed by `score.py` into
[`expected/qwen_wsp.txt`](../../expected/qwen_wsp.txt).

**Summary.** None of the three Qwen base models (1.7B, 8B, 14B) predicts the next
residue of a real protein better than of its shuffled copy at the test's cut points, and
none recognises Pfam families or catalytic residues. The weight writes fitted on the
1.7B model did not improve sequence reading on held-out proteins and damaged its
answers to ordinary questions. Putting a family member in the prompt did help, which
the weight write failed to reproduce.

## 1. Unedited models

### Next residue (3,340 cut points; top-ranked residue correct)

| Model | Real | Shuffled | Gap, 95% CI over 167 families |
|---|---|---|---|
| Qwen3-1.7B-Base | 10.2% | 10.9% | −0.7 pts (−2.1 to +0.7) |
| Qwen3-8B-Base | 10.7% | 11.3% | −0.6 pts (−2.1 to +0.9) |
| Qwen3-14B-Base | 10.7% | 11.0% | −0.3 pts (−1.8 to +1.1) |
| Always answer leucine | 10.0% | 10.4% | |

The models put 99% of their next-token probability on residue tokens, so they follow
the format; they predict from residue frequencies. Writing the sequence without spaces
gives the same picture (gaps of +1.0 to +1.2 points, each interval including zero).

On the 136 questions that were also asked of the Claude models, the Qwen models score
10.3%, 11.8% and 9.6% on real sequences against 12.5%, 11.8% and 13.2% on shuffled
ones. Fable 5.2 at high effort scored 41.2% against 11.8%.

One small signal grows with model size. Over every position of every protein, rather
than only the cut points inside Pfam domains, real sequences are predicted slightly
better than shuffled ones: +0.6, +0.7 and +1.1 points for the three sizes, with
intervals that exclude zero. This comparison was not in the protocol, and the cut-point
result shows it does not come from the domains.

### Catalytic residues

At a catalytic site the models prefer the wild-type residue to the substituted one in
39, 36 and 42 of 60 cases. At decoy sites with the same substitution they do so in 39,
42 and 42 of 58. The preference is no stronger at catalytic sites in any model, so it
reflects which residues are common, not which are catalytic.

### Features of the 60 test 2 proteins

| Model | Pfam name top-ranked of 66 (real / shuffled) | Signal peptide AUROC (real / shuffled) | Transmembrane helix AUROC (real / shuffled) |
|---|---|---|---|
| Qwen3-1.7B-Base | 3/59 / 3/59 | 0.54 / 0.67 | 0.46 / 0.46 |
| Qwen3-8B-Base | 3/59 / 3/59 | 0.69 / 0.67 | 0.90 / 0.71 |
| Qwen3-14B-Base | 1/59 / 1/59 | 0.55 / 0.49 | 0.81 / 0.67 |

- **Pfam names:** no recognition; the same score on shuffled copies means the few hits
  come from which names the model favours.
- **Transmembrane helices:** the 8B and 14B models separate membrane proteins from the
  rest. Much of this survives shuffling, so it is largely hydrophobic composition; the
  higher score on real sequences suggests some sensitivity to order. With 18 membrane
  proteins this is an indication, not an estimate.
- **Signal peptides:** nothing consistent.

## 2. Weight writes on the 1.7B model

Selection on validation proteins chose the MLP write at layer 24, strength 0.5
(validation accuracy 12.2% against 10.8% unedited). No output-row write beat the
unedited model, so none was selected or tested.

Top-ranked residue correct on test proteins:

| Condition | Seen families, real | Seen, shuffled | Unseen families, real | Unseen, shuffled | Control questions correct |
|---|---|---|---|---|---|
| Unedited | 10.4% | 10.8% | 9.5% | 11.6% | 9/14 |
| Family member in the prompt | 23.0% | 12.2% | 17.3% | 11.7% | 9/14 |
| MLP write | 12.2% | 12.2% | 10.4% | 11.0% | 6/14 |
| Reversed write | 9.2% | 10.2% | 9.0% | 10.9% | 7/14 |
| Three random writes | 10.2–11.2% | 10.6–11.2% | 9.6–9.9% | 11.9–12.2% | 7–8/14 |

Seen families have 500 cut points and unseen families 1,340.

- **No gain in sequence reading.** In seen families the write gains 1.8 points on real
  sequences (95% CI +0.4 to +3.2) and 1.4 points on shuffled ones, so by the rule fixed
  in the protocol the gain is composition. One random write also gained 0.8 points
  (+0.2 to +1.6). In unseen families the gain is 0.9 points (−0.0 to +1.9).
- **Damage outside proteins.** Five of 14 held-out control answers changed, and greedy
  answers to English questions turned into residue strings (for the electron transport
  chain question: "P TFFKQKQKQKQ…"). The ten calibration controls had shown no change,
  so the selection rule did not detect this. Random writes of the same size also
  changed four or five answers.
- **The write is not small.** It changes all 12.6 million entries of the layer's output
  matrix and its norm is 2.6 times that of the original matrix.
- **No effect on catalytic residues.** The substitution scores are unchanged.
- **The information helps when it is in the prompt.** A family member in context more
  than doubles accuracy in seen families and nearly doubles it in unseen ones, with no
  effect on shuffled sequences. Only 5 of the 500 seen-family cut points share their
  preceding ten residues with a fitting protein, so this is not simple copying of
  identical stretches.

This matches qwen2obo's own finding for knowledge updates: the writes shift scores on
the fitting examples but do not install a capability, and a small control set
under-reports the damage.

## Departures from the plan

- **The protocol was not committed before the model ran.** It was written first, and
  each result manifest records its hash (`bf0f3fd4…`), but there is no commit to prove
  the order.
- **The 8B and 14B models were added after the 1.7B results were seen.** They are not
  in `protocol.json`. Only the unedited tests were run on them; no weight writes.
- **Two baseline runs on the laptop stopped with a GPU error** in the unspaced
  next-residue step. Moving one summation from the GPU to the CPU fixed it. The parts
  that had finished reproduced byte for byte in the rerun.
- **The all-position comparison** in section 1 was added after the results were seen.

## Where it ran

| Model | Machine | Run time |
|---|---|---|
| Qwen3-1.7B-Base, baseline and weight writes | M1 Max laptop (MPS) | 26 min and 32 min |
| Qwen3-8B-Base, baseline | Lawrencium `es1`, one A40, job 28069493 | 16 min |
| Qwen3-14B-Base, baseline | Lawrencium `es1`, one A40, job 28069494 | 27 min |

The Lawrencium jobs, with a 4.5-minute canary (job 28069300), used 6.3 core-hours
(about 6 SU of `pc_chemrof`).

## What was not tested

- Weight writes on the larger models.
- The 30B and 35B mixture-of-experts base models, which do not fit one A40.
- More than one write method: only qwen2obo's two closed-form writes, with one fitting
  set and one grid.
- Repeat runs with other splits or seeds.
