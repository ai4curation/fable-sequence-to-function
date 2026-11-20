"""Test items for the Qwen sequence tests. Standard library only, so the scorer can import it.

Positions named ``t`` are zero-based indices of the residue being predicted: the
model sees ``sequence[:t]`` and is scored on ``sequence[t]``.
"""

import csv
import json
import pathlib
import random
import zlib

AA = "ACDEFGHIKLMNPQRSTVWY"
HEADER = "Protein sequence in one-letter amino acid codes:"
SEED = 20261119
SEEN_FAMILIES = 100
MAX_KEYS = 4096
HERE = pathlib.Path(__file__).parent
EXPERIMENTS = HERE.parent


def shuffled(seq: str, accession: str) -> str:
    """Shuffle residues with the upstream seed, the CRC32 of the accession.

    >>> shuffled("MKKEIAIKIR", "A0A4D4KTH5")
    'IIMKKKAEIR'
    >>> sorted(shuffled("MKKEIAIKIR", "A0A4D4KTH5")) == sorted("MKKEIAIKIR")
    True
    """
    residues = list(seq)
    random.Random(zlib.crc32(accession.encode())).shuffle(residues)
    return "".join(residues)


def load_sequences() -> list[dict]:
    """The 668 next-residue proteins: 167 Pfam families of four members, five cuts each.

    >>> rows = load_sequences()
    >>> len(rows), len({r["pfam"] for r in rows}), rows[0]["cuts"]
    (668, 167, [202, 203, 230, 234, 239])
    """
    path = EXPERIMENTS / "next_residue" / "upstream" / "confirm_sequences.tsv"
    rows = []
    for r in csv.DictReader(path.open(), delimiter="\t"):
        start, end = (int(x) for x in r["domain"].split("-"))
        rows.append(
            {
                "accession": r["accession"],
                "pfam": r["pfam"],
                "size_bin": r["size_bin"],
                "sequence": r["sequence"],
                "cuts": [int(c) for c in r["cuts"].split(",")],
                "domain": [start - 1, end - 1],  # zero-based, inclusive
            }
        )
    return rows


def assign_splits(rows: list[dict], seed: int = SEED) -> dict[str, str]:
    """Split by family, then by member. Returns accession -> split.

    100 "seen" families give two fitting members, one validation member and one
    test member; all four members of the other 67 families are test only.

    >>> s = assign_splits(load_sequences())
    >>> sorted((k, list(s.values()).count(k)) for k in set(s.values()))
    [('fit', 200), ('test_seen', 100), ('test_unseen', 268), ('validation', 100)]
    """
    rng = random.Random(seed)
    families = sorted({r["pfam"] for r in rows})
    rng.shuffle(families)
    seen = set(families[:SEEN_FAMILIES])
    result = {}
    for family in sorted(set(families)):
        members = sorted(r["accession"] for r in rows if r["pfam"] == family)
        if family not in seen:
            result.update({m: "test_unseen" for m in members})
            continue
        rng.shuffle(members)
        for member, split in zip(members, ["fit", "fit", "validation", "test_seen"]):
            result[member] = split
    return result


def assign_homologs(rows: list[dict], splits: dict[str, str]) -> dict[str, str]:
    """The family member shown in context for the "homolog in context" condition.

    In seen families it is always a fitting member (for a fitting member, the other
    one). In unseen families it is the next member in accession order.

    >>> rows = load_sequences(); s = assign_splits(rows); h = assign_homologs(rows, s)
    >>> all(h[a] != a for a in h), {s[h[a]] for a in h if s[a] != "test_unseen"}
    (True, {'fit'})
    """
    result = {}
    for family in sorted({r["pfam"] for r in rows}):
        members = sorted(r["accession"] for r in rows if r["pfam"] == family)
        fit = [m for m in members if splits[m] == "fit"]
        for i, member in enumerate(members):
            if fit:
                result[member] = next(f for f in fit if f != member)
            else:
                result[member] = members[(i + 1) % len(members)]
    return result


def fit_positions(rows: list[dict], splits: dict[str, str], max_keys: int = MAX_KEYS):
    """Evenly spaced (accession, t) pairs inside the Pfam domain of fitting members.

    >>> rows = load_sequences(); picks = fit_positions(rows, assign_splits(rows))
    >>> len(picks), len({a for a, _ in picks})
    (4096, 200)
    """
    pairs = [
        (r["accession"], t)
        for r in rows
        if splits[r["accession"]] == "fit"
        for t in range(max(r["domain"][0], 1), r["domain"][1] + 1)
    ]
    n = min(max_keys, len(pairs))
    return [pairs[round(i * (len(pairs) - 1) / (n - 1))] for i in range(n)]


def substitutions() -> list[dict]:
    """Single substitutions at catalytic residues (test 3) and at decoy positions.

    Each decoy makes the same residue change as its paired catalytic substitution,
    at a non-catalytic position of the same protein.

    >>> subs = substitutions()
    >>> sorted((k, sum(s["kind"] == k for s in subs)) for k in {"catalytic", "decoy"})
    [('catalytic', 60), ('decoy', 58)]
    >>> all(s["sequence"][s["t"]] == s["wt"] for s in subs)
    True
    """
    truth = json.loads((EXPERIMENTS / "pseudo" / "truth.json").read_text())
    wild = {r["accession"]: r["variants"]["wt"] for r in truth}
    result = []
    for r in truth:
        sites = {"kinase": [("asp_to_asn", "asp"), ("lys_to_met", "lys")], "enzyme": [("site_to_ala", "site")]}
        for variant, key in sites.get(r["group"], []):
            t = r[key] - 1
            result.append(
                {
                    "id": f"{r['accession']}:{variant}",
                    "accession": r["accession"],
                    "group": r["group"],
                    "kind": "catalytic",
                    "variant": variant,
                    "t": t,
                    "wt": wild[r["accession"]][t],
                    "new": r["variants"][variant][t],
                    "sequence": wild[r["accession"]],
                }
            )
    decoys = json.loads((EXPERIMENTS / "decoy_control" / "decoys.json").read_text())
    for d in decoys:
        result.append(
            {
                "id": f"{d['accession']}:{d['variant']}",
                "accession": d["accession"],
                "group": d["group"],
                "kind": "decoy",
                "variant": d["paired_original_variant"],
                "t": d["position"] - 1,
                "wt": d["wild_type_residue"],
                "new": d["new_residue"],
                "sequence": wild[d["accession"]],
            }
        )
    return result


def feature_items() -> list[dict]:
    """The 60 proteins of test 2 with their Pfam names, and the candidate name list.

    >>> items, names = feature_items()
    >>> len(items), len(names), sum(i["signal"] for i in items), sum(i["tm"] for i in items)
    (60, 66, 9, 18)
    """
    truth = json.loads((EXPERIMENTS / "features" / "truth.json").read_text())
    names = sorted({p["name"] for r in truth for p in r["pfam"]})
    items = [
        {
            "accession": r["accession"],
            "sequence": r["sequence"],
            "pfam": sorted({p["name"] for p in r["pfam"]}),
            "signal": bool(r["signal"]),
            "tm": bool(r["tm"]),
        }
        for r in truth
    ]
    return items, names
