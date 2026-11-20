"""Adjudicate two disputed active-site positions of test 3 from frozen inputs. Usage: adjudicate.py

For YrfG (P64636) UniProt gives the nucleophile as Asp9; the models place it at Asp16. For ENV9 (Q08651) UniProt gives
the catalytic serine as Ser172; the models place it at Ser173. Both UniProt positions are annotated by similarity.
Two lines are printed for each: (1) which query residue aligns with active-site residues of reviewed
relatives, and (2) distances in two structural models. Inputs: snapshot/*.json (written by fetch.py) and models/.
The two lines share homology information. Nothing here calls a language model, and no answer of a tested model is used as evidence.
"""
import collections, json, math, pathlib, sys
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent)); from common import KEYS, reparse

def atoms_cif(path):
    out = []; keys = []
    for l in open(path):
        if l.startswith("_atom_site."): keys.append(l.strip().split(".")[1])
        elif keys and l.startswith(("ATOM", "HETATM")):
            d = dict(zip(keys, l.split()))
            if d.get("pdbx_PDB_model_num", "1") != "1": continue
            out.append(dict(het=d["group_PDB"] == "HETATM", atom=d["label_atom_id"].strip('"'), res=d["label_comp_id"], chain=d["auth_asym_id"],
                            num=int(d["auth_seq_id"]), xyz=(float(d["Cartn_x"]), float(d["Cartn_y"]), float(d["Cartn_z"]))))
        elif keys and out and l.startswith("#"): break
        elif keys and not out and l.startswith("#"): keys = []
    return out
def atoms_pdb(path):
    out = []
    for l in open(path):
        if l.startswith(("ATOM", "HETATM")):
            out.append(dict(het=l.startswith("HETATM"), atom=l[12:16].strip(), res=l[17:20].strip(), chain=l[21], num=int(l[22:26]),
                            xyz=(float(l[30:38]), float(l[38:46]), float(l[46:54]))))
        if l.startswith("ENDMDL"): break
    return out
def sel(at, num, names): return [a for a in at if not a["het"] and a["chain"] == "A" and a["num"] == num and a["atom"] in names]
def dmin(A, B): return min((math.dist(a["xyz"], b["xyz"]) for a in A for b in B), default=float("nan"))
def col(aln, acc, pos):
    n = 0
    for i, c in enumerate(aln[acc]):
        n += c != "-"
        if n == pos and c != "-": return i
def at_col(aln, acc, i):
    c = aln[acc][i]; return "gap" if c == "-" else f"{c}{sum(x != '-' for x in aln[acc][:i + 1])}"
def MODELS(acc):
    path = HERE / "models" / f"swissmodel_{acc}.pdb"
    template = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if fields[:2] == ["REMARK", "3"] and len(fields) == 4 and fields[2] in ("PDBID", "CHAIN", "SID"):
            assert fields[2] not in template, "Expected one SWISS-MODEL template"
            template[fields[2]] = fields[3]
    label = f"SWISS-MODEL homology model, chain A; template {template['PDBID']}.{template['CHAIN']}, sequence identity {template['SID']}%"
    return (("AlphaFill (AlphaFold model with ligands transplanted from homologous structures)", atoms_cif(HERE / "models" / f"alphafill_{acc}.cif")),
            (label, atoms_pdb(path)))

def uniprot(snap, types=("Active site",)):
    q = snap["entries"][0]
    print(f"{q['accession']} {q['name']}, {q['organism']}; {len(q['sequence'])} residues; sequence version {q['sequence_version']}, entry version {q['entry_version']}, fetched {snap['fetched']}; PDB entries: {len(q['pdb'])}")
    for f in q["features"]:
        if f["type"] in types or f["ligand"].startswith("Mg"):
            print(f"  UniProt {f['type']:12s} {q['sequence'][f['start'] - 1]}{f['start']:<4d} {f['description'] or f['ligand']:30s} evidence {','.join(f['evidence'])} {' '.join(f['source'])}")
def alignment(snap, experimental_only_for=()):
    q = snap["query_accession"]; aln = snap["alignment"]; tally = collections.Counter()
    print(f"  Alignment of {len(snap['entries']) - 1} reviewed relatives ({snap['mafft']}); UniProt query: {snap['uniprot_query']}" + (f"; plus {', '.join(snap['extra'])}" if snap["extra"] else ""))
    for e in snap["entries"][1:]:
        for f in e["features"]:
            if f["type"] != "Active site": continue
            exp = "ECO:0000269" in f["evidence"]
            if not exp and e["accession"] not in snap["extra"]: continue
            to = at_col(aln, q, col(aln, e["accession"], f["start"])); tally[(f["description"], "experimental" if exp else "no ECO:0000269", to)] += 1
            print(f"    {e['accession']:7s} {e['name'][:40]:40s} {e['organism'][:24]:24s} {e['sequence'][f['start'] - 1]}{f['start']:<4d} {f['description'][:30]:30s} {'experimental' if exp else 'no ECO:0000269':16s} PDB {len(e['pdb']):2d} -> query {to}; evidence {','.join(f['evidence'])}; source {','.join(f['source']) or 'not recorded'}")
    for (desc, ev, to), n in sorted(tally.items()): print(f"    tally: {n} x {desc} ({ev}) -> query {to}")
def answers(acc, site, variant):
    print(f"  What the tested models listed (not used as evidence): catalytic positions returned for {acc}")
    for f in sorted((HERE.parent / "results").glob("*.jsonl")):
        R = [json.loads(l) for l in open(f)]; reparse(R, KEYS["pseudo"])
        for v in ("wt", variant):
            for r in R:
                if r.get("accession") == acc and r.get("variant") == v and r.get("ans"):
                    a = r["ans"]; cat = sorted(f"{d.get('residue')}{d.get('position')}" for d in a.get("catalytic_residues") or [] if isinstance(d, dict))
                    lost = sorted(f"{d.get('expected')}>{d.get('found')}@{d.get('position')}" for d in a.get("substituted_or_missing") or [] if isinstance(d, dict))
                    print(f"    {f.stem:22s} {v:11s} active={str(a.get('catalytically_active')):9s} catalytic {' '.join(cat)}" + (f"  substituted {' '.join(lost)}" if lost else ""))

print("== Case 1: YrfG (P64636), nucleophile Asp9 (UniProt) or Asp16 (models)?")
S = json.loads((HERE / "snapshot" / "P64636.json").read_text()); uniprot(S, ("Active site", "Binding site"))
seq = S["entries"][0]["sequence"]; print(f"  residues 1-24: {seq[:24]}   (Asp at {[i + 1 for i, c in enumerate(seq[:24]) if c == 'D']})")
alignment(S)
for label, at in MODELS("P64636"):
    het = sorted({a["res"] for a in at if a["het"]}); K = sel(at, 149, {"NZ"}); T = sel(at, 116, {"OG1"}); MG = [a for a in at if a["het"] and a["res"] == "MG"]
    print(f"  {label}; hetero groups {het}")
    for n in (9, 11, 16, 18):
        A = sel(at, n, {"OD1", "OD2"}); assert A, n
        print(f"    Asp{n:<3d} carboxylate oxygen to: Lys149 NZ {dmin(A, K):5.1f}   Asp173 carboxylate {dmin(A, sel(at, 173, {'OD1', 'OD2'})):5.1f}   Asp174 carboxylate {dmin(A, sel(at, 174, {'OD1', 'OD2'})):5.1f}   Thr116 OG1 {dmin(A, T):5.1f}   Mg {dmin(A, MG):5.1f}   (angstrom)")
answers("P64636", 9, "site_to_ala")

print("\n== Case 2: ENV9 (Q08651), catalytic serine Ser172 (UniProt) or Ser173 (models)?")
S = json.loads((HERE / "snapshot" / "Q08651.json").read_text()); uniprot(S)
seq = S["entries"][0]["sequence"]; print(f"  residues 166-178: {seq[165:178]}")
alignment(S)
pw = S["pairwise"]; t = S["extra"][0]
for e in S["entries"][1:2]:
    for f in e["features"]:
        if f["type"] == "Active site": print(f"    pairwise alignment with {t} alone (MAFFT L-INS-i): {e['sequence'][f['start'] - 1]}{f['start']} {f['description']} -> query {at_col(pw, 'Q08651', col(pw, t, f['start']))}")
for label, at in MODELS("Q08651"):
    Y = sel(at, 202, {"OH"}); K = sel(at, 206, {"NZ"}); NIC = [a for a in at if a["het"] and a["res"] in ("NAP", "NDP", "NAD", "NAI") and a["atom"] == "C4N"]
    print(f"  {label}; cofactor copies with a nicotinamide C4: {len(NIC)}")
    for n in (172, 173):
        A = sel(at, n, {"OG"}); ca = sel(at, n, {"CA"})[0]["xyz"]; cb = sel(at, n, {"CB"})[0]["xyz"]; y = Y[0]["xyz"]
        cos = sum((b - a) * (c - a) for a, b, c in zip(ca, cb, y)) / (math.dist(ca, cb) * math.dist(ca, y))
        print(f"    Ser{n} OG to: Tyr202 OH {dmin(A, Y):4.1f}   Lys206 NZ {dmin(A, K):4.1f}   nearest nicotinamide C4 {dmin(A, NIC):4.1f}   (angstrom); side chain points {'towards' if cos > 0 else 'away from'} Tyr202 OH (cosine {cos:+.2f})")
answers("Q08651", 172, "site_to_ala")
