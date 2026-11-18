# LLM sequence probe: manuscript

Draft of a short preprint on four sequence-only tests of general-purpose
language models on protein sequence.

## Where this came from

This repository was split from the `projects/LLM_SEQUENCE_PROBE/manuscript`
folder of [`ai4curation/ai-gene-review`](https://github.com/ai4curation/ai-gene-review),
pull request #6527, at commit `119ac18676`. The commit history of that folder
is preserved here.

The tests themselves stay in the original repository: the scripts that build
each test set, the raw model outputs and the scoring code are in
`projects/LLM_SEQUENCE_PROBE/` there, and are described on its
[project page](https://github.com/ai4curation/ai-gene-review/blob/119ac1867699227b129baf1f400c10f271193475/projects/LLM_SEQUENCE_PROBE.md).
Nothing here duplicates them.

## Files

- `manuscript.tex`: the manuscript source. Start here.
- `references.bib`: bibliography. Entries with a DOI were checked against Europe PMC.
- `figures/make_figures.py`: draws both figures from the model outputs in the
  original repository's `pseudo/` and `structure/` folders. Nothing in it is
  typed in by hand.
- `figures/*.pdf`: figures used by the manuscript. `figures/*.png` are copies for
  the project page.
- `manuscript.pdf`: a committed reading copy.

## Build

The figure script needs a checkout of the original repository for its data.
Pass the path of its `projects/LLM_SEQUENCE_PROBE` folder:

```bash
uv run --with matplotlib python figures/make_figures.py /path/to/ai-gene-review/projects/LLM_SEQUENCE_PROBE
pdflatex manuscript && bibtex manuscript && pdflatex manuscript && pdflatex manuscript
```

The committed figures were made with Matplotlib 3.10.5.

`manuscript.pdf` is a committed reading copy; rebuild and recommit it when the source changes.

## Open before posting

- Author list, affiliations and funding (marked `TODO` in the source).
- Every question was asked once. Repeat runs would give intervals for tests 2 to 4.
- Opus 4.6 ran at low effort; a like-for-like comparison needs it at high effort.
- Function grading for the novel structures is one unblinded pass by the agent
  that ran the tests. A blinded second grader is needed.
- The two enzymes where both models disagree with the curated active-site
  position (Q08651, P64636) have not been adjudicated.
- Related work is thin: protein language model baselines on the same items, and
  prior tests of general language models on sequence, are not yet covered.
