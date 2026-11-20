# Purpose: split the UniProt reviewed entries matched by protein_name:inactive by where "inactive" appears:
#          the recommended name, only an alternative name, or only an Includes/Contains (domain) name.
# Inputs:  review/uniprot_2026_04/uniprot_inactive_reviewed_2026_04.json and ..._kinase_reviewed_2026_04.json
#          (UniProt release 2026_04, fetched 2026-11-20 with
#          curl -G https://rest.uniprot.org/uniprotkb/stream --data-urlencode 'query=<q>' --data-urlencode format=json
#          --data-urlencode fields=accession,protein_name; queries as in review/scripts/pseudoenzyme_lookups.sh).
# Output:  stdout counts. Serves: NEXT_TASKS T15, issues #19 and #186, PR #183. Date: 2026-11-20.
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parents[2] / "review" / "uniprot_2026_04"


def names(pd, kinds):
    return " ".join(json.dumps(n).lower() for k in kinds for n in (pd.get(k) if isinstance(pd.get(k), list) else [pd.get(k)] if pd.get(k) else []))


for f in ("uniprot_inactive_reviewed_2026_04.json", "uniprot_inactive_kinase_reviewed_2026_04.json"):
    res = json.loads((HERE / f).read_text())["results"]
    rec = alt = other = 0
    for r in res:
        pd = r.get("proteinDescription") or {}
        if "inactive" in names(pd, ["recommendedName", "submissionNames"]):
            rec += 1
        elif "inactive" in names(pd, ["alternativeNames"]):
            alt += 1
        else:
            other += 1
    print(f"{f}: {len(res)} entries; recommended name {rec}; alternative name only {alt}; Includes/Contains name only {other}")
