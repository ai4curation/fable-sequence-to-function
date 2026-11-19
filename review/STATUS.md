# What has happened to the review's major points

The files in this folder describe the draft of 18 November 2026. This note records, as of 19 November 2026,
what was done about each major point of `critique_content_v1.md`. It was written by Claude Code, which is
built on one of the models the manuscript evaluates.

| Point | Criticism | State |
|---|---|---|
| M1 | Title and discussion generalise beyond two models; Opus 4.6 ran at lower effort | Retitled and reworded (pull request 112). Opus 4.6 now reported at high effort in tests 2 to 4 (pull requests 98 and 114). |
| M2 | The call route lowers test-1 accuracy and the cause is untested | Open. Needs a rerun through the API. |
| M3 | The thinking split is self-selected | Reworded to rest on the low-versus-high effort contrast (pull request 112). |
| M4 | "Novel" structures are not unseen; AtDUC1 had a preprint | Strata defined by their criterion, preprint cited, recognition counts reported (pull request 112). Preprints for the other novel proteins were not searched. |
| M5 | Weak structure baselines, uneven contact precision | Open. |
| M6 | No neutral-substitution control; two misses may be reference errors | Decoy control added (pull requests 10 and 114). The two reference sites were adjudicated in favour of the models (pull request 138). Wild-type false-alarm rate, neutral prompt and real over-annotated entries are open. |
| M7 | Function grading is one unblinded pass | Open. |
| M8 | Test 2 lacks real negatives; mixed denominators | Denominators stated (pull request 9 and its review). Real negatives open. |
| M9 | One sample per question | Partly: the decoy control repeated the test-3 mutants and wild types on a second route. No repeats for tests 2 and 4. |
| M10 | Data statement pointed to a missing path | Fixed (pull request 8). |

The format critique and the 79 editing recommendations have not been worked through item by item.
