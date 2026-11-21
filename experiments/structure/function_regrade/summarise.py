"""Unblind the two blinded gradings of the STRFN function calls and report counts and agreement."""
import collections
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FIELDS = ["family", "specific_function", "identity_claim", "true_abstention", "overall"]
OVERALL = ["correct", "partly_correct", "wrong", "abstained"]


def load(name):
    return {x["item"]: x for x in json.loads((HERE / name).read_text())}


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca) / n**2
    return (po - pe) / (1 - pe)


def main():
    key = json.loads((HERE / "key.json").read_text())
    G = {"A": load("grader_A.json"), "B": load("grader_B.json")}
    items = sorted(key)
    print("== blinded regrading of function calls, 12 distinct proteins x 3 models, two graders")
    for m in sorted(set(key.values())):
        for g in "AB":
            c = collections.Counter(G[g][i]["overall"] for i in items if key[i] == m)
            ident = collections.Counter(G[g][i]["identity_claim"] for i in items if key[i] == m)
            print(f"  {m:18s} grader {g}: " + ", ".join(f"{k} {c[k]}" for k in OVERALL) + f"; wrong identity or origin claims {ident['wrong']}")
    print("  agreement between graders (36 items):")
    for f in FIELDS:
        a, b = [G["A"][i][f] for i in items], [G["B"][i][f] for i in items]
        print(f"    {f:18s} {sum(x == y for x, y in zip(a, b))}/36, kappa {kappa(a, b):.2f}")
    print("  items where the overall grades differ:")
    for i in items:
        if G["A"][i]["overall"] != G["B"][i]["overall"]:
            print(f"    {i.split('-')[0]} {key[i]}: A {G['A'][i]['overall']}, B {G['B'][i]['overall']}")
    print("  per protein, overall grade (A/B where they differ):")
    for pdb in sorted({i.split("-")[0] for i in items}):
        row = []
        for m in sorted(set(key.values())):
            i = next(i for i in items if i.startswith(pdb) and key[i] == m)
            a, b = G["A"][i]["overall"], G["B"][i]["overall"]
            row.append(f"{m} {a if a == b else a + '/' + b}")
        print(f"    {pdb}: " + "; ".join(row))


if __name__ == "__main__":
    main()
