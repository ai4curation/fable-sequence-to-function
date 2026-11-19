#!/usr/bin/env bash
# Purpose: check that the public identifiers cited in the draft of 2026-11-18
#          (fable-sequence-to-function.pdf) resolve, and print the registry's
#          own title/name for each so it can be compared with the manuscript.
# Inputs:  none (identifiers are listed below); network access to CrossRef,
#          UniProt, RCSB and GitHub. All calls are anonymous: no mailto, no
#          contact details in the User-Agent.
# Outputs: plain text on stdout. Nothing is written to disk.
# Serves:  review/critique_content_v1.md and review/critique_format_v1.md.
# Date:    2026-11-18
set -u

UA="identifier-check/1.0"

echo "== CrossRef DOIs (reference list) =="
for doi in \
  10.1126/science.ade2574 \
  10.1038/s41467-022-32007-7 \
  10.1093/g3journal/jkaf169 \
  10.1126/scisignal.aav3810 \
  10.1093/nar/gkaa913 \
  10.1038/s41586-021-03819-2
do
  curl -s -m 30 -A "$UA" "https://api.crossref.org/works/${doi}" \
    | jq -r --arg d "$doi" '
        .message
        | [$d,
           (.title[0] // "NO TITLE"),
           (."container-title"[0] // "-"),
           ((.volume // "-") | tostring),
           ((.page // ."article-number" // "-") | tostring),
           ((.issued."date-parts"[0][0] // "-") | tostring),
           ([.author[]? | .family] | .[0:6] | join(", "))]
        | join(" | ")' 2>/dev/null \
    || echo "$doi | LOOKUP FAILED"
done

echo
echo "== UniProt accessions named in the text =="
for acc in Q95YD4 Q9VLA1 Q2PAY3 Q08651 P64636; do
  curl -s -m 30 -A "$UA" "https://rest.uniprot.org/uniprotkb/${acc}.json" \
    | jq -r --arg a "$acc" '
        [$a,
         (.entryType // "NO ENTRY"),
         (.proteinDescription.recommendedName.fullName.value
            // .proteinDescription.submissionNames[0].fullName.value // "-"),
         (.organism.scientificName // "-"),
         ((.sequence.length // "-") | tostring),
         ([.features[]? | select(.type=="Active site")
             | ((.location.start.value|tostring) + ":" + (.description // ""))]
            | join("; "))]
        | join(" | ")' 2>/dev/null \
    || echo "$acc | LOOKUP FAILED"
done

echo
echo "== PDB entries named in the text =="
for id in 9T71 9TGX 10CW 9YP0 27IQ; do
  body=$(curl -s -m 30 -A "$UA" -w '\n%{http_code}' \
    "https://data.rcsb.org/rest/v1/core/entry/${id}")
  code=$(printf '%s' "$body" | tail -n1)
  json=$(printf '%s' "$body" | sed '$d')
  if [ "$code" = "200" ]; then
    printf '%s' "$json" | jq -r --arg i "$id" '
      [$i,
       (.struct.title // "-"),
       (.rcsb_accession_info.deposit_date // "-"),
       (.rcsb_accession_info.initial_release_date // "-"),
       ((.exptl[0].method) // "-"),
       ((.rcsb_entry_info.resolution_combined[0] // "-") | tostring)]
      | join(" | ")'
  else
    echo "$id | HTTP $code"
  fi
done

echo
echo "== Repositories =="
for url in \
  "https://api.github.com/repos/XinmingTu/LLM-bioseq-probe" \
  "https://api.github.com/repos/XinmingTu/LLM-bioseq-probe/commits/0d8d086" \
  "https://api.github.com/repos/ai4curation/ai-gene-review" \
  "https://api.github.com/repos/ai4curation/ai-gene-review/contents/projects/LLM_SEQUENCE_PROBE"
do
  code=$(curl -s -m 30 -A "$UA" -o /dev/null -w '%{http_code}' "$url")
  echo "$url | HTTP $code"
done

echo
echo "== Blog post (reference 3) =="
curl -s -m 30 -A "$UA" -o /dev/null -w 'HTTP %{http_code}\n' -L \
  "https://xinmingtu.cn/blog/2026/claude-opus-5-5-protein-sequences/"
