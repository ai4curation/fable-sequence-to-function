#!/usr/bin/env bash
# Purpose: test the draft's "novel / no prior homolog" and "post-training"
#          framing for the five PDB entries it names (draft of 2026-11-18):
#          (1) does 27IQ carry Asn where UniProt Q53RT3 has the catalytic Asp
#              (the draft says DSG -> NSG; RCSB lists no mutation)?
#          (2) RCSB sequence search (MMseqs2) for each entry's entity 1 with
#              no identity floor, keeping hits released before 2026-06-01:
#              are there earlier structures below the draft's 30% cut-off?
#          (3) when did the entries' primary citations appear (CrossRef)?
# Inputs:  none; anonymous calls to data.rcsb.org, search.rcsb.org,
#          rest.uniprot.org and api.crossref.org. Only public PDB sequences
#          and public article titles are sent.
# Outputs: plain text on stdout. Nothing is written to disk.
# Serves:  review/critique_content_v1.md.
# Date:    2026-11-18
set -u
UA="identifier-check/1.0"

entity_seq() {
  curl -s -m 30 -A "$UA" "https://data.rcsb.org/rest/v1/core/polymer_entity/$1/1" \
    | jq -r '.entity_poly.pdbx_seq_one_letter_code_can' | tr -d '\n'
}

echo "== (1) 27IQ catalytic motif =="
s=$(entity_seq 27IQ)
echo "27IQ entity 1 length: ${#s}"
echo "DSG offsets (0-based): $(printf '%s' "$s" | grep -ob 'DSG' | tr '\n' ' ')"
echo "NSG offsets (0-based): $(printf '%s' "$s" | grep -ob 'NSG' | tr '\n' ' ')"
u=$(curl -s -m 30 -A "$UA" "https://rest.uniprot.org/uniprotkb/Q53RT3.json")
us=$(printf '%s' "$u" | jq -r '.sequence.value')
echo "UniProt Q53RT3 active sites: $(printf '%s' "$u" | jq -r '[.features[]? | select(.type=="Active site") | (.location.start.value|tostring)] | join(",")')"
echo "UniProt Q53RT3 DSG offsets (0-based): $(printf '%s' "$us" | grep -ob 'DSG' | tr '\n' ' ')"
# locate the PDB construct inside the UniProt sequence by a 12-mer downstream of the motif
tail12=$(printf '%s' "$s" | sed -E 's/.*[DN]SG//' | cut -c1-12)
echo "12-mer after the motif in 27IQ: $tail12 ; in UniProt at offset: $(printf '%s' "$us" | grep -ob "$tail12" | tr '\n' ' ')"

echo
echo "== (2) earlier PDB structures by sequence search (released before 2026-06-01) =="
for id in 9T71 9TGX 10CW 9YP0 27IQ; do
  s=$(entity_seq "$id")
  q=$(jq -n --arg s "$s" '{
    query: {type:"group", logical_operator:"and", nodes:[
      {type:"terminal", service:"sequence", parameters:{
         evalue_cutoff: 1, identity_cutoff: 0, sequence_type:"protein", value:$s}},
      {type:"terminal", service:"text", parameters:{
         attribute:"rcsb_accession_info.initial_release_date",
         operator:"less", value:"2026-06-01"}}]},
    return_type:"polymer_entity",
    request_options:{results_verbosity:"verbose", scoring_strategy:"sequence",
                     paginate:{start:0, rows:5}}}')
  resp=$(curl -s -m 60 -A "$UA" -w '\n%{http_code}' -X POST \
           -H 'Content-Type: application/json' --data "$q" \
           "https://search.rcsb.org/rcsbsearch/v2/query")
  code=$(printf '%s' "$resp" | tail -n1)
  json=$(printf '%s' "$resp" | sed '$d')
  if [ "$code" = "200" ]; then
    echo "-- $id (len ${#s}): HTTP 200, hits=$(printf '%s' "$json" | jq -r '.total_count')"
    printf '%s' "$json" | jq -r '
      .result_set[]?
      | "   " + .identifier + "  identity="
        + ((.services[]?.nodes[]?.match_context[0]?.sequence_identity // "NA") | tostring)
        + "  evalue="
        + ((.services[]?.nodes[]?.match_context[0]?.evalue // "NA") | tostring)'
  else
    echo "-- $id (len ${#s}): HTTP $code (204 = no hits)"
  fi
done

echo
echo "== (3) publication dates of the entries' primary citations (CrossRef) =="
for t in \
  "Natural product biosynthesis by guanidine prenyltransferases in plants and bacteria" \
  "Crystal structures of type T archaeal ribonuclease P Rpp30, Rpp30/Pop5, and L7Ae provide insights into a reduced RNase P" \
  "Structure and enzymatic properties of human retroviral-like aspartic protease 1 and functional roles of disease-associated mutations"
do
  curl -s -m 30 -A "$UA" -G "https://api.crossref.org/works" \
       --data-urlencode "query.bibliographic=$t" --data-urlencode "rows=2" \
    | jq -r '.message.items[]?
        | "   " + (.DOI // "-") + " | " + (.title[0] // "-")[0:90]
          + " | " + (."container-title"[0] // .type // "-")
          + " | first-date=" + ([.created."date-parts"[0][] | tostring] | join("-"))
          + " | published=" + ([(.published."date-parts"[0] // [])[] | tostring] | join("-"))'
  echo "   --"
done
