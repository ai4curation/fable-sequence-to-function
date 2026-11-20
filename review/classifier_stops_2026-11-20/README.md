# Classifier stops in the Opus 4.6 high-effort runs (#83, NEXT_TASKS T10)

The results rows don't record why the tool asked again. The command line tool's own session records do,
but they are local to the machine that ran the calls and aren't in this repository.

**How these files were made.** On 2026-11-20, `scripts/adhoc/find_session_records_of_flagged_calls.py` was
run on each `claude-opus-4-6-high.jsonl` (tests 2, 3 and 4) with that machine's session folder. The output
gives, for every marked or multi-request row, the sequence of requests with stop reasons and lengths, and
no message text. The folder path is replaced by a placeholder.

A reply stopped by a safety classifier shows as `stop=refusal`.

| Test | Question | Row | Scored? |
|---|---|---|---|
| 2 | A0A919RPG7 real | asked 2026-11-19T07:48:15Z, 2 turns | yes |
| 2 | A0A919RPG7 real | asked 06:21:38Z, marked | no (asked again) |
| 2 | A0ABS5VAT3 real | asked 06:21:40Z, marked | no; its replacement took one request |
| 3 | Q2PAY3 asp_to_asn | asked 08:11:19Z, 2 turns | yes |
| 3 | Q9V422 wt | asked 09:01:46Z, 2 turns | yes |
| 4 | 9T71 | asked 08:42:38Z, 2 turns | yes |

So four scored answers, all from Opus 4.6 at high effort, rest on a reply the tool continued after a
classifier stop. All four are scored like any other answer. In test 4, `experiments/structure/score.py`
also prints every line without the nine continued replies (`expected/structure.txt`).
