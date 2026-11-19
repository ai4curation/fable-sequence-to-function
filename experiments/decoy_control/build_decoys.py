"""Build decoy substitutions for the catalytic-activity test (test 3). Usage: build_decoys.py PROBE_DIR

Purpose: the original test changes a catalytic residue and asks whether the protein is still active. It has no
         substitution at a non-catalytic position, so it cannot tell "the catalytic residue is gone" from
         "this sequence differs from the known one". This script adds one matched decoy per original mutant:
         the same substitution type at a position with no functional annotation.
Inputs:  PROBE_DIR/pseudo/truth.json (a checkout of projects/LLM_SEQUENCE_PROBE from ai4curation/ai-gene-review,
         commit 119ac18676). UniProt REST, called anonymously, for each protein's feature table.
Outputs: decoys.json (the decoy sequences and how each position was chosen) and uniprot_features_snapshot.json
         (the feature tables used, so the choice can be repeated offline) beside this file.
Serves:  branch experiment/decoy-substitution-control of ai4curation/fable-sequence-to-function. Date: 2026-11-18.

Rule, fixed before any model was asked:
  kinase  one Asp -> Asn and one Lys -> Met, each inside the UniProt "Protein kinase" domain.
  enzyme  one residue of the same type as the curated active-site residue -> Ala.
  A position is excluded if it lies within PAD residues of any UniProt active site, binding site, site, modified
  residue, disulfide bond, cross-link, lipidation, glycosylation or mutagenesis feature, or inside a signal
  peptide, transit peptide, propeptide or initiator methionine. For kinases three more places are excluded, since
  UniProt does not annotate them in every entry: the catalytic loop (catalytic Asp -2..+7); the DFG motif (first
  D[FLYWM][GT] that starts 10 to 45 residues after the catalytic Asp); and the invariant structural Asp of
  subdomain IX (any D.W[SAG] that starts 30 to 110 residues after the catalytic Asp; Hanks and Hunter 1995).
  One position is drawn from what remains with a random generator seeded by SEED, accession and variant.
"Decoy" therefore means "no functional annotation", not "measured to be harmless".
"""
import json, pathlib, random, re, sys, time, urllib.request
if len(sys.argv) != 2: sys.exit(__doc__)
HERE = pathlib.Path(__file__).parent; PROBE = pathlib.Path(sys.argv[1]); SEED = 20261118; PAD = 3
SNAP = HERE / "uniprot_features_snapshot.json"
PROTECT = {"Active site", "Binding site", "Site", "Modified residue", "Disulfide bond", "Cross-link", "Lipidation", "Glycosylation", "Mutagenesis"}
CLEAVED = {"Signal", "Transit peptide", "Propeptide", "Initiator methionine"}

def fetch(acc):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"https://rest.uniprot.org/uniprotkb/{acc}.json", timeout=90) as r: e = json.load(r)
            break
        except Exception as err: last = err; time.sleep(2 * (attempt + 1))
    else: sys.exit(f"UniProt look-up failed for {acc}: {last}")
    feats = [dict(type=f["type"], description=f.get("description", ""), start=f["location"]["start"].get("value"), end=f["location"]["end"].get("value"))
             for f in e.get("features", [])]
    return dict(entry_version=e["entryAudit"]["entryVersion"], sequence_version=e["entryAudit"]["sequenceVersion"], sequence=e["sequence"]["value"], features=feats)

def span(f): return range(f["start"], f["end"] + 1) if f["start"] and f["end"] else range(0)
def mut(seq, pos, new): return seq[:pos - 1] + new + seq[pos:]

truth = [t for t in json.loads((PROBE / "pseudo/truth.json").read_text()) if t["group"] in ("kinase", "enzyme")]
snap = json.loads(SNAP.read_text()) if SNAP.exists() else {}
for t in truth:
    if t["accession"] not in snap: snap[t["accession"]] = fetch(t["accession"]); time.sleep(0.2)
SNAP.write_text(json.dumps(snap, indent=1, sort_keys=True))

out = []; skipped = []
for t in truth:
    acc = t["accession"]; wt = t["variants"]["wt"]; u = snap[acc]
    if u["sequence"] != wt: skipped.append((acc, "UniProt sequence no longer equals the test sequence")); continue
    blocked = set()
    for f in u["features"]:
        if f["type"] in PROTECT:
            ends = [f["start"], f["end"]] if f["type"] in ("Disulfide bond", "Cross-link") else list(span(f))   # a bond joins two residues; it does not cover the stretch between them
            for p in ends:
                if p: blocked.update(range(p - PAD, p + PAD + 1))
        if f["type"] in CLEAVED: blocked.update(span(f))
    if t["group"] == "kinase":
        dom = [f for f in u["features"] if f["type"] == "Domain" and "Protein kinase" in f["description"] and f["start"] and f["end"]]
        if len(dom) != 1: skipped.append((acc, f"{len(dom)} 'Protein kinase' domain features")); continue
        allowed = set(span(dom[0])); asp = t["asp"]
        blocked.update(range(asp - 2 - PAD, asp + 7 + PAD + 1)); blocked.update(range(t["lys"] - PAD, t["lys"] + PAD + 1))
        dfg = re.compile("D[FLYWM][GT]").search(wt, asp + 9, asp + 48)
        if dfg: blocked.update(range(dfg.start() + 1 - PAD, dfg.start() + 3 + PAD + 1))
        ix = [m.start() + 1 for m in re.compile("D.W[SAG]").finditer(wt, asp + 29, asp + 114)]
        for p in ix: blocked.update(range(p - PAD, p + PAD + 1))
        plans = [("asp_decoy_to_asn", "D", "N", "asp_to_asn"), ("lys_decoy_to_met", "K", "M", "lys_to_met")]
        extra = dict(domain=[dom[0]["start"], dom[0]["end"]], dfg_asp=dfg.start() + 1 if dfg else None, subdomain_ix_asp=ix)
    else:
        allowed = set(range(1, len(wt) + 1)); blocked.update(range(t["site"] - PAD, t["site"] + PAD + 1))
        plans = [("site_decoy_to_ala", t["site_residue"], "A", "site_to_ala")]; extra = {}
    for variant, old, new, paired in plans:
        cands = sorted(p for p in allowed if wt[p - 1] == old and p not in blocked)
        if not cands: skipped.append((acc, f"no candidate {old} for {variant}")); continue
        pos = random.Random(f"{SEED}:{acc}:{variant}").choice(cands)
        out.append(dict(accession=acc, group=t["group"], name=t["name"], variant=variant, paired_original_variant=paired, position=pos,
                        wild_type_residue=old, new_residue=new, candidates=len(cands), uniprot_entry_version=u["entry_version"], sequence=mut(wt, pos, new), **extra))
(HERE / "decoys.json").write_text(json.dumps(out, indent=1))
for d in out:
    assert sum(a != b for a, b in zip(d["sequence"], next(t for t in truth if t["accession"] == d["accession"])["variants"]["wt"])) == 1
print(f"{len(out)} decoys written for {len({d['accession'] for d in out})} proteins; skipped: {skipped or 'none'}")
for d in out: print(f"  {d['group']:6s} {d['accession']:8s} {d['variant']:17s} {d['wild_type_residue']}{d['position']}{d['new_residue']}  ({d['candidates']} candidates)")
