# Purpose: split UniProt reviewed entries matched by protein_name:inactive into those with "inactive" in the
#          recommended name vs. only in alternative/domain names. Inputs: UniProt stream JSON (saved under
#          t15_sources/, release 2026_04). Output: stdout counts. Serves: NEXT_TASKS T15, issue #19 item 5
#          (492 of 688; 90 of 107 in the kinase superfamily). Date: 2026-11-20.
# Fetch: curl -G https://rest.uniprot.org/uniprotkb/stream --data-urlencode 'query=<q>' --data-urlencode format=json
#        --data-urlencode fields=accession,protein_name
import json, sys
d = json.load(open(sys.argv[1]))["results"]
rec = sum(1 for e in d if "inactive" in e["proteinDescription"].get("recommendedName", {}).get("fullName", {}).get("value", "").lower())
print(len(d), "recommended-name hits:", rec, "other-name only:", len(d) - rec)
