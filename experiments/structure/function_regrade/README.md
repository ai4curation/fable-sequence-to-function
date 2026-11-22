# Blinded regrading of the STRFN function calls

`function_grading.yaml` one level up is the first grading: one grader, unblinded, three grades, Fable 5.2
and Opus 5.5 only. This folder holds a second grading with a finer rubric.

- `items.json`: 36 items, one per (protein, model) for the 12 distinct proteins with no close earlier PDB
  match and three models (Fable 5.2, Opus 5.5, Gemini 4 Neon). Each item has the PDB entry's deposited
  title, molecule name, keywords, keyword text and source organism (`truth`) and the model's fold, function and recognition answers. Item ids hide the model
  and the order within a protein is shuffled.
- `key.json`: item id to model. The graders did not see it.
- `grader_A.json`, `grader_B.json`: two graders, each given `items.json` and the rubric below and nothing
  else. Both are separate instances of a Claude model (the same model family as two of the three models
  graded), run as subagents that could not see each other's output. They are not human graders.
- `summarise.py`: unblinds, counts and reports agreement. `just report` runs it.

Rubric, per item:

| field | values | meaning |
|---|---|---|
| `family` | correct, broader_only, wrong, none | protein family or superfamily named |
| `specific_function` | correct, wrong, generic, none | molecular function or substrate |
| `identity_claim` | correct, wrong, none | a claim about which protein or what origin it is |
| `true_abstention` | true, false | says it does not know and asserts nothing false |
| `overall` | correct, partly_correct, wrong, abstained | |

Truth is the PDB entry's deposited description only (title, molecule name, keywords, keyword text and
organism). The graders did not read the papers behind the entries, so a call that is right about something
that description does not say is not credited.
