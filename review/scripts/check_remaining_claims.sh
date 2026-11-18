#!/usr/bin/env bash
# Purpose: three remaining source checks for the review of the draft of
#          2026-11-18 (fable-sequence-to-function.pdf):
#          (1) what the cited blog post itself reports for accuracy with and
#              without thinking, and its byline (raw page text, not a summary);
#          (2) YrfG (P64636): is there a DMDGT motif at 16-20, as the project
#              page says the models proposed, against UniProt's Asp9?
#          (3) AtDUC1 (A0A1P8B2L4): which InterPro entries already annotate
#              the protein (is a peptidase / deubiquitinase domain among them)?
# Inputs:  none; anonymous calls to xinmingtu.cn, rest.uniprot.org, ebi.ac.uk.
# Outputs: plain text on stdout. Nothing is written to disk.
# Serves:  review/critique_content_v1.md.
# Date:    2026-11-18
set -u
UA="identifier-check/1.0"

echo "== (1) blog post: byline and thinking statements =="
page=$(curl -s -m 40 -A "$UA" -L "https://xinmingtu.cn/blog/2026/claude-opus-5-5-protein-sequences/" \
        | sed -e 's/<script[^>]*>.*<\/script>//g' -e 's/<[^>]*>/ /g' | tr -s ' \n' ' ')
echo "page text length: ${#page}"
for pat in 'thinking' 'just as accurate' '54\.7' '48\.2' '35\.3' '34\.1' 'temperature' 'Leo Tianlai Chen' 'By Xinming' 'cutoff'; do
  echo "-- pattern: $pat"
  printf '%s' "$page" | grep -o -i -E ".{0,160}${pat}.{0,200}" | head -3
done

echo
echo "== (2) YrfG P64636 residues 1-25 and motif offsets =="
s=$(curl -s -m 30 -A "$UA" "https://rest.uniprot.org/uniprotkb/P64636.json" | jq -r '.sequence.value')
echo "1-25: $(printf '%s' "$s" | cut -c1-25)"
echo "DMDGT offset (0-based): $(printf '%s' "$s" | grep -ob 'DMDGT' | tr '\n' ' ')"
echo "D.D offsets (0-based) in first 30: $(printf '%s' "$s" | cut -c1-30 | grep -ob 'D.D' | tr '\n' ' ')"

echo
echo "== (3) InterPro entries on AtDUC1 A0A1P8B2L4 =="
curl -s -m 40 -A "$UA" "https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/A0A1P8B2L4?page_size=50" \
  | jq -r '.results[]? | .metadata
           | "   " + .accession + " | " + .source_database + " | " + .type + " | " + .name
             + " | " + ([.. | objects | select(has("fragments")) | .fragments[] | ((.start|tostring) + "-" + (.end|tostring))] | join(","))' 2>/dev/null \
  || echo "   lookup failed"
curl -s -m 30 -A "$UA" "https://rest.uniprot.org/uniprotkb/A0A1P8B2L4.json" \
  | jq -r '"   UniProt: " + .entryType + " | " + (.proteinDescription.recommendedName.fullName.value // .proteinDescription.submissionNames[0].fullName.value // "-") + " | len " + (.sequence.length|tostring)'

echo
echo "== (4) was the AtDUC1 work public before mid-2026? (CrossRef, journal articles and preprints) =="
curl -s -m 30 -A "$UA" -G "https://api.crossref.org/works" \
     --data-urlencode "query.bibliographic=A class of plant-specific deubiquitinases stabilizing endocytotic cargo at the plasma membrane" \
     --data-urlencode "rows=4" \
  | jq -r '.message.items[]?
      | "   " + (.DOI // "-") + " | " + (.type // "-") + " | " + (.title[0] // "-")[0:95]
        + " | " + (."container-title"[0] // (.institution[0].name // "-"))
        + " | first-date=" + ([.created."date-parts"[0][] | tostring] | join("-"))'
curl -s -m 30 -A "$UA" -G "https://api.crossref.org/works" \
     --data-urlencode "query.bibliographic=AtDUC1 deubiquitinase Arabidopsis plasma membrane endocytosis" \
     --data-urlencode "rows=4" \
  | jq -r '.message.items[]?
      | "   " + (.DOI // "-") + " | " + (.type // "-") + " | " + (.title[0] // "-")[0:95]
        + " | " + (."container-title"[0] // (.institution[0].name // "-"))
        + " | first-date=" + ([.created."date-parts"[0][] | tostring] | join("-"))'
