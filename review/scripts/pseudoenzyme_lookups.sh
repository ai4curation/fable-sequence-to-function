#!/usr/bin/env bash
# Purpose: reproduce the look-ups behind review/pseudoenzyme_framing_v1.md: how many Swiss-Prot entries are named
#          "inactive", what UniProt records as the basis for kin-32, and whether each suggested reference resolves.
# Inputs:  none. Calls UniProt REST and CrossRef anonymously (no email address, default curl user agent).
# Outputs: plain text on standard output; the saved copy is review/pseudoenzyme_lookups_2026-11-18.txt.
# Serves:  branch review/pseudoenzyme-framing of ai4curation/fable-sequence-to-function. Date: 2026-11-18.
set -u
echo "# Run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "## UniProt entry counts"
count() {
  n=$(curl -s --max-time 60 -D - -o /dev/null -G "https://rest.uniprot.org/uniprotkb/search" --data-urlencode "query=$1" --data-urlencode "size=1" --data-urlencode "fields=accession" | grep -i '^x-total-results' | tr -d '\r' | awk '{print $2}')
  printf '%s\t%s\n' "${n:-FAILED}" "$1"; sleep 1
}
count 'reviewed:true'
count 'reviewed:true AND protein_name:inactive'
count 'reviewed:true AND protein_name:"probable inactive"'
count 'reviewed:true AND protein_name:pseudokinase'
count 'reviewed:true AND protein_name:inactive AND family:"protein kinase superfamily"'
count 'reviewed:true AND protein_name:inactive AND ec:*'
count 'reviewed:true AND protein_name:inactive AND ft_act_site:*'
count 'reviewed:true AND protein_name:inactive AND cc_caution:*'
count 'reviewed:false AND protein_name:inactive'
echo "## UniProt Q95YD4 (kin-32): name and function comment"
curl -s --max-time 60 "https://rest.uniprot.org/uniprotkb/Q95YD4.json" | python3 -I -c '
import json, sys
e = json.load(sys.stdin); print(e["proteinDescription"]["recommendedName"]["fullName"]["value"], "| entry version", e["entryAudit"]["entryVersion"])
for c in e.get("comments", []):
    if c["commentType"] in ("FUNCTION", "CAUTION"):
        for t in c.get("texts", []): print(c["commentType"], "|", t["value"], "|", [v.get("evidenceCode") for v in t.get("evidences", [])])'
echo "## CrossRef records for the suggested references"
for doi in 10.1042/bst20160400 10.1186/s12915-016-0322-x 10.1126/scisignal.aat9797 10.1111/febs.15142 10.1111/febs.15100 10.1111/febs.15535 10.1042/bcj20220373 \
           10.1016/s0969-2126\(02\)00861-4 10.1016/j.jmb.2004.04.063 10.1093/nar/gkx1012 10.1074/jbc.275.22.16795 10.1016/j.str.2004.04.014 10.1126/science.1075762; do
  sleep 1
  curl -s --max-time 40 "https://api.crossref.org/works/$doi" | python3 -I -c '
import json, sys
try:
    m = json.load(sys.stdin)["message"]
    print(m["DOI"], "|", m["title"][0], "|", ", ".join(a.get("family", "?") for a in m.get("author", [])[:6]), "|", m["container-title"][0], m["issued"]["date-parts"][0][0], m.get("volume"), m.get("page"))
except Exception as err: print("FAILED", sys.argv[1], err)' "$doi"
done
