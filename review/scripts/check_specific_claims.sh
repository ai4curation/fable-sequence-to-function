#!/usr/bin/env bash
# Purpose: check specific factual statements in the draft of 2026-11-18
#          (fable-sequence-to-function.pdf) against UniProt and RCSB:
#          (1) kin-32 (Q95YD4): are the kinase motifs the draft lists in the
#              sequence, and what does Swiss-Prot give as the basis for
#              "inactive"?
#          (2) Q9VLA1: are residues 317 and 318 both Glu?
#          (3) ROP17 (Q2PAY3), ENV9 (Q08651), YrfG (P64636): curated sites.
#          (4) PDB entries named in the text: entity names, mutation flags,
#              deposit vs release dates, primary citation.
#          (5) Did structures of the same protein families exist in the PDB
#              before 2026-06-01 (Rpp30, ASPRV1-like retropepsins)?
# Inputs:  none; anonymous network calls to rest.uniprot.org, data.rcsb.org
#          and search.rcsb.org.
# Outputs: plain text on stdout. Nothing is written to disk.
# Serves:  review/critique_content_v1.md.
# Date:    2026-11-18
set -u
UA="identifier-check/1.0"

up() { curl -s -m 30 -A "$UA" "https://rest.uniprot.org/uniprotkb/$1.json"; }

echo "== (1) kin-32 Q95YD4 =="
j=$(up Q95YD4)
seq=$(printf '%s' "$j" | jq -r '.sequence.value')
for motif in VAVK VAIK HRD DFG GXGXXG; do
  if [ "$motif" = "GXGXXG" ]; then
    pos=$(printf '%s' "$seq" | grep -ob 'G.G..G' | head -5 | tr '\n' ' ')
  else
    pos=$(printf '%s' "$seq" | grep -ob "$motif" | head -5 | tr '\n' ' ')
  fi
  echo "motif $motif (0-based offset:match): ${pos:-ABSENT}"
done
echo "-- comments (caution / domain / function / similarity):"
printf '%s' "$j" | jq -r '
  .comments[]?
  | select(.commentType=="CAUTION" or .commentType=="DOMAIN"
           or .commentType=="FUNCTION" or .commentType=="SIMILARITY")
  | .commentType + ": " + ([.texts[]?.value] | join(" "))'
echo "-- features (domain / binding / active site / region):"
printf '%s' "$j" | jq -r '
  .features[]?
  | select(.type=="Domain" or .type=="Binding site" or .type=="Active site")
  | .type + " " + (.location.start.value|tostring) + "-" + (.location.end.value|tostring)
    + " " + (.description // "") + " " + ((.ligand.name) // "")'

echo
echo "== (2) Q9VLA1 residues 315-320 =="
up Q9VLA1 | jq -r '.sequence.value' | cut -c315-320

echo
echo "== (3) curated sites: Q2PAY3, Q08651, P64636 =="
for acc in Q2PAY3 Q08651 P64636; do
  j=$(up "$acc")
  echo "-- $acc"
  printf '%s' "$j" | jq -r '
    .features[]?
    | select(.type=="Binding site" or .type=="Active site")
    | "   " + .type + " " + (.location.start.value|tostring) + "-" + (.location.end.value|tostring)
      + " " + (.description // "") + " " + ((.ligand.name) // "")
      + " evidence=" + ([.evidences[]?.evidenceCode] | unique | join(","))'
  s=$(printf '%s' "$j" | jq -r '.sequence.value')
  printf '%s' "$j" | jq -r '.features[]? | select(.type=="Active site") | .location.start.value' \
    | while read -r p; do
        a=$((p-2)); [ "$a" -lt 1 ] && a=1
        echo "   residues $a-$((p+2)) around active site $p: $(printf '%s' "$s" | cut -c${a}-$((p+2)))"
      done
done

echo
echo "== (4) PDB entities for entries named in the text =="
for id in 9T71 9TGX 10CW 9YP0 27IQ; do
  e=$(curl -s -m 30 -A "$UA" "https://data.rcsb.org/rest/v1/core/entry/${id}")
  echo "-- $id deposited $(printf '%s' "$e" | jq -r '.rcsb_accession_info.deposit_date[0:10]')" \
       "released $(printf '%s' "$e" | jq -r '.rcsb_accession_info.initial_release_date[0:10]')"
  echo "   primary citation: $(printf '%s' "$e" | jq -r '(.rcsb_primary_citation.title // "none") + " | " + (.rcsb_primary_citation.journal_abbrev // "-") + " | " + ((.rcsb_primary_citation.year // "-")|tostring) + " | doi=" + (.rcsb_primary_citation.pdbx_database_id_doi // "-")')"
  for n in $(printf '%s' "$e" | jq -r '.rcsb_entry_container_identifiers.polymer_entity_ids[]?'); do
    curl -s -m 30 -A "$UA" "https://data.rcsb.org/rest/v1/core/polymer_entity/${id}/${n}" \
      | jq -r '"   entity " + .rcsb_polymer_entity_container_identifiers.entity_id
               + ": " + (.rcsb_polymer_entity.pdbx_description // "-")
               + " | len=" + ((.entity_poly.rcsb_sample_sequence_length // "-")|tostring)
               + " | mutation=" + (.rcsb_polymer_entity.pdbx_mutation // "none")
               + " | organism=" + ([.rcsb_entity_source_organism[]?.ncbi_scientific_name] | join(","))
               + " | uniprot=" + ([.rcsb_polymer_entity_container_identifiers.uniprot_ids[]?] | join(","))'
  done
done

echo
echo "== (5) earlier PDB entries for the same protein families (released before 2026-06-01) =="
search() {
  # $1 = full-text query
  q=$(jq -n --arg t "$1" '{
    query: {type:"group", logical_operator:"and", nodes:[
      {type:"terminal", service:"full_text", parameters:{value:$t}},
      {type:"terminal", service:"text", parameters:{
         attribute:"rcsb_accession_info.initial_release_date",
         operator:"less", value:"2026-06-01"}}]},
    return_type:"entry",
    request_options:{paginate:{start:0, rows:5},
      sort:[{sort_by:"rcsb_accession_info.initial_release_date", direction:"asc"}]}}')
  r=$(curl -s -m 30 -A "$UA" -X POST -H 'Content-Type: application/json' \
        --data "$q" "https://search.rcsb.org/rcsbsearch/v2/query")
  echo "query \"$1\": total=$(printf '%s' "$r" | jq -r '.total_count // 0')" \
       "earliest=$(printf '%s' "$r" | jq -r '[.result_set[]?.identifier] | join(",")')"
}
search "Rpp30"
search "ASPRV1"
search "SASPase"
search "retroviral-like aspartic protease"
search "guanidine prenyltransferase"
search "AtDUC1"
