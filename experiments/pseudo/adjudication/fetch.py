"""Fetch and freeze the inputs for the adjudication of two disputed active sites. Usage: fetch.py

Needs network access and MAFFT. For each case it stores, in snapshot/CASE.json: the UniProt features of the query,
reviewed relatives that carry an experimentally supported active site (evidence ECO:0000269), any extra entries
named below, a MAFFT alignment of all of them, and a MAFFT alignment of the query with the first extra entry alone.
adjudicate.py reads these files and needs neither network nor MAFFT. The structural models in models/ were
downloaded by hand on 2026-11-19 (URLs in README.md).
"""
import datetime, json, pathlib, subprocess, tempfile, urllib.parse, urllib.request
HERE = pathlib.Path(__file__).parent
CASES = {
    "P64636": dict(query='(family:"HAD-like hydrolase superfamily") AND (reviewed:true) AND (ft_act_site_exp:*) AND (length:[150 TO 330])', extra=[]),
    "Q08651": dict(query='(xref:pfam-PF00106) AND (reviewed:true) AND (ft_act_site_exp:*) AND (length:[230 TO 360])', extra=["O93868"]),
}
def get(u): return json.load(urllib.request.urlopen(u, timeout=90))
def entry(a):
    d = get(f"https://rest.uniprot.org/uniprotkb/{a}.json"); s = d["sequence"]["value"]
    feats = [dict(type=f["type"], start=f["location"]["start"]["value"], end=f["location"]["end"]["value"], description=f.get("description", ""),
                  ligand=f.get("ligand", {}).get("name", ""), evidence=sorted({e.get("evidenceCode") for e in f.get("evidences", [])}),
                  source=sorted({f'{e.get("source")}:{e.get("id")}' for e in f.get("evidences", []) if e.get("source")}))
             for f in d["features"] if f["type"] in ("Active site", "Binding site")]
    return dict(accession=a, name=d["proteinDescription"].get("recommendedName", {}).get("fullName", {}).get("value", "?"), organism=d["organism"]["scientificName"],
                sequence=s, sequence_version=d["entryAudit"]["sequenceVersion"], entry_version=d["entryAudit"]["entryVersion"], features=feats,
                pdb=[x["id"] for x in d["uniProtKBCrossReferences"] if x["database"] == "PDB"])
def mafft(entries, *opts):
    with tempfile.NamedTemporaryFile("w", suffix=".fa", delete=False) as fh:
        fh.write("".join(f">{e['accession']}\n{e['sequence']}\n" for e in entries))
    out = subprocess.run(["mafft", *opts, "--quiet", fh.name], capture_output=True, text=True, check=True).stdout
    return {b.split("\n")[0].strip(): "".join(b.split("\n")[1:]) for b in out.split(">")[1:]}
version = subprocess.run(["mafft", "--version"], capture_output=True, text=True).stderr.strip()
for acc, c in CASES.items():
    hits = [r["primaryAccession"] for r in get("https://rest.uniprot.org/uniprotkb/search?format=json&size=40&fields=accession&query=" + urllib.parse.quote(c["query"]))["results"]]
    order = [acc] + [a for a in c["extra"] + sorted(hits) if a != acc]
    E = [entry(a) for a in dict.fromkeys(order)]
    snap = dict(query_accession=acc, uniprot_query=c["query"], extra=c["extra"], fetched=datetime.date.today().isoformat(), mafft=version,
                entries=E, alignment=mafft(E, "--auto"), pairwise=mafft(E[:2], "--localpair", "--maxiterate", "1000") if c["extra"] else None)
    (HERE / "snapshot" / f"{acc}.json").write_text(json.dumps(snap, indent=1))
    print(acc, len(E) - 1, "relatives")
