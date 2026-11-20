# Stretch test: a small open model, and weight writes to improve it

Two questions, asked of `Qwen/Qwen3-1.7B-Base` running locally (the first also of the 8B and 14B base models, on Lawrencium):

1. Does it read protein sequences at all, on the test sets of this repository?
2. Do the closed-form weight writes of [qwen2obo](https://github.com/cmungall/qwen2obo)
   (its "knowledge update" experiment) improve next-residue prediction on proteins
   the fitting never saw?

Results are in [RESULTS.md](RESULTS.md). The numbers there are printed by
`score.py` into `expected/qwen_wsp.txt` and checked by `just check`.
This test is not in the manuscript.

## What is measured

A local model gives its whole next-token distribution, so these tests read
probabilities directly and nothing is sampled. The sequence is given as a short header
followed by one token per residue.

| Part | Items | Measure |
|---|---|---|
| Next residue | The 668 proteins of test 1 and their shuffled copies, 3,340 cut points each | Is the top-ranked residue the true one? |
| Substitutions | The 60 catalytic-residue substitutions of test 3 and the 58 decoy substitutions | Does the model prefer the wild-type residue to the substituted one, and more so at catalytic sites than at decoy sites? |
| Features | The 60 proteins of test 2 and shuffled copies | Rank of the true Pfam name among the 66 names in the set; yes-or-no margin for signal peptide and transmembrane helices |

## The weight writes

Both writes come from qwen2obo at commit `c4eb160` and use no gradients.

- **MLP write.** At 4,096 positions inside the Pfam domains of 200 fitting proteins,
  record what one MLP block (layer 16 or 24, counted from zero) outputs with and
  without another member of the same family in context. Solve a ridge regression for
  the change to that block's output matrix that reproduces the difference.
- **Output write.** At the same positions, solve for a change to the 20 residue rows of
  the output matrix that raises the logit of the true next residue by 4.

Strength and layer are chosen on 100 validation proteins, subject to ten control
questions keeping their answers. The chosen writes are then scored once on test
proteins: 100 from families that supplied fitting proteins ("seen") and 268 from 67
families that supplied none ("unseen"). Each chosen write is compared with its reverse,
with three random writes of the same size, and with putting a family member in the
prompt instead.

How to read the outcome is fixed in `protocol.json`: a gain that also appears on
shuffled sequences is residue composition, a gain only in seen families is
memorisation of those families, and only a gain in unseen families beyond the shuffled
gain would count as better sequence reading.

## Files

| File | Content |
|---|---|
| `protocol.json`, `splits.json`, `controls.json` | Written by `prepare` before any model call |
| `tasks.py` | Test items and splits (standard library only) |
| `lm.py` | Scoring and patch fitting (needs torch and qwen2obo) |
| `cli.py` | Commands `prepare`, `baseline`, `edit` |
| `score.py` | Prints every reported number from `results/` |
| `results/` | Per-protein scores for every condition; `results/local/` holds the weight patches and is not committed |

## Running it

Scoring needs only the main environment (`just report`, `just check`). The model
commands have their own environment in this folder, download about 4 GB of weights on
first use, and were run on an M1 Max laptop.

```bash
just qwen-test
just qwen baseline
just qwen edit
```

A rerun on other hardware may differ in the last digits, since the model runs in
16-bit floating point.

`just qwen baseline --model Qwen/Qwen3-8B-Base` scores another model listed in
`data/model_revisions.json`; results go to `results/MODEL-NAME/`. The 8B and 14B
models need a GPU with about 20 and 32 GB of memory.

The qwen2obo repository is private. Without access to it the model commands cannot be
installed, but scoring the committed results still works.
