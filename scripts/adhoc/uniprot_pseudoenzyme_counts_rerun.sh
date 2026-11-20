#!/usr/bin/env bash
# Purpose: re-run the UniProt count queries of review/scripts/pseudoenzyme_lookups.sh and record the release headers.
# Inputs: none (anonymous UniProt REST). Output: stdout, saved as review/pseudoenzyme_lookups_2026-11-20_rerun.txt.
# Serves: NEXT_TASKS T15, issue #19 item 5. Date: 2026-11-20.
set -u
echo "# Run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
for q in 'reviewed:true' 'reviewed:true AND protein_name:inactive' 'reviewed:true AND protein_name:"probable inactive"' \
  'reviewed:true AND protein_name:pseudokinase' 'reviewed:true AND protein_name:inactive AND family:"protein kinase superfamily"' \
  'reviewed:true AND protein_name:inactive AND ec:*' 'reviewed:true AND protein_name:inactive AND ft_act_site:*' \
  'reviewed:true AND protein_name:inactive AND cc_caution:*' 'reviewed:false AND protein_name:inactive'; do
  h=$(curl -s -A "Mozilla/5.0" --max-time 60 -D - -o /dev/null -G "https://rest.uniprot.org/uniprotkb/search" --data-urlencode "query=$q" --data-urlencode "size=1" --data-urlencode "fields=accession" | tr -d '\r')
  printf '%s\t%s\t%s\t%s\n' "$(echo "$h" | awk -F': ' 'tolower($1)=="x-total-results"{print $2}')" "$(echo "$h" | awk -F': ' 'tolower($1)=="x-uniprot-release"{print $2}')" "$(echo "$h" | awk -F': ' 'tolower($1)=="x-uniprot-release-date"{print $2}')" "$q"
  sleep 1
done
