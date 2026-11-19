"""Recompute the draft's reported numbers from the raw model outputs, and add checks the draft omits.

Purpose: independent recomputation for the review of fable-sequence-to-function.pdf (draft of 2026-11-18).
         Reads the committed truth.json and results/*.jsonl files; does NOT import or run the authors' scripts.
Inputs:  the raw outputs as they stood at ai4curation/ai-gene-review PR #6527, head 119ac18676. They are copied,
         unchanged, to review/pr6527_snapshot/ in this repository, and that folder is read by default. Another folder
         with the same layout can be given as argv[1].
Outputs: plain text on stdout. Nothing is written to disk.
Serves:  review/critique_content_v1.md.
Date:    2026-11-18
Run:     python3 -I review/scripts/recompute_from_pr6527.py
"""
import collections
import json
import math
import pathlib
import random
import re
import statistics
import sys

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent / "pr6527_snapshot"
MODELS = ["claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"]


def rows(p):
    return [json.loads(line) for line in open(p)] if p.exists() else []


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else f"{a}/{b}"


def boot(vals, n=10000, seed=0):
    rng = random.Random(seed)
    bs = sorted(sum(rng.choices(vals, k=len(vals))) / len(vals) for _ in range(n))
    return bs[int(0.025 * n)], bs[int(0.975 * n)]


# ---------------------------------------------------------------- Test 1
print("=" * 30, "TEST 1: next residue")
for eff in ("low", "high"):
    for m in MODELS:
        R = rows(ROOT / "next_residue" / "results" / eff / f"{m}.jsonl")
        if not R:
            continue
        err = [r for r in R if "error" in r or r.get("is_error")]
        R = [r for r in R if r not in err]
        served = collections.Counter(tuple(sorted(r.get("served") or [])) for r in R)
        print(f"\n-- {m} effort={eff}: {len(R)} answered, {len(err)} errors; served-model sets: {dict(served)}")
        for c in ("real", "shuffled", "reversed"):
            x = [r for r in R if r["condition"] == c]
            if not x:
                continue
            inv = sum(not r["valid"] for r in x)
            ok = sum(r["first_correct"] for r in x)
            th = [r for r in x if r.get("thinking")]
            nt = [r for r in x if not r.get("thinking")]
            print(f"   {c:9s} n={len(x)} correct {pct(ok, len(x))} invalid={inv} | "
                  f"thinking: {pct(sum(r['first_correct'] for r in th), len(th))} invalid={sum(not r['valid'] for r in th)} | "
                  f"no thinking: {pct(sum(r['first_correct'] for r in nt), len(nt))} invalid={sum(not r['valid'] for r in nt)}")
        fam = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in R:
            fam[r["pfam"]][r["condition"]].append(r["first_correct"])
        g = [sum(d["real"]) / len(d["real"]) - sum(d["shuffled"]) / len(d["shuffled"]) for d in fam.values() if d["real"] and d["shuffled"]]
        lo, hi = boot(g)
        print(f"   gap real-shuffled {100 * sum(g) / len(g):+.1f} (95% {100 * lo:+.1f} to {100 * hi:+.1f}), {len(g)} families")
        # is "thinking" a property of the question? same real question, thinking in real vs shuffled
        real = [r for r in R if r["condition"] == "real"]
        lens = [len(r.get("text") or "") for r in real]
        multi = sum(len(re.findall(r"[ACDEFGHIKLMNPQRSTVWY]{5,}", (r.get("text") or "").replace(" ", ""))) > 1 for r in real)
        print(f"   real answers: median reply length {statistics.median(lens):.0f} chars, max {max(lens)}; "
              f"replies with more than one residue run (parser takes the last): {multi}")
        # thinking by family size bin
        by = collections.defaultdict(lambda: [0, 0, 0])
        for r in real:
            b = by[r["size_bin"]]
            b[0] += 1
            b[1] += bool(r.get("thinking"))
            b[2] += r["first_correct"]
        print("   real, by family-size bin (n, thinking, correct):", {k: tuple(v) for k, v in sorted(by.items())})

# ---------------------------------------------------------------- Test 2
print("\n" + "=" * 30, "TEST 2: domains / membrane features")
T2 = {t["accession"]: t for t in json.loads((ROOT / "features" / "truth.json").read_text())}
norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())


def ov(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)


print("truth: set sizes", dict(collections.Counter(t["set"] for t in T2.values())),
      "| proteins with TM", sum(bool(t["tm"]) for t in T2.values()),
      "| with signal", sum(t["signal"] for t in T2.values()),
      "| reference Pfam matches (set B)", sum(len(t["pfam"]) for t in T2.values() if t["set"] == "B"),
      "| distinct reference families (set B)", sum(len({p["accession"] for p in t["pfam"]}) for t in T2.values() if t["set"] == "B"))
for m in MODELS:
    R = rows(ROOT / "features" / "results" / f"{m}.jsonl")
    ok = [r for r in R if r.get("ans")]
    print(f"\n-- {m}: {len(R)} calls, {len(R) - len(ok)} unparsed; served sets {dict(collections.Counter(tuple(sorted(r.get('served') or [])) for r in R))}")
    for st in ("B", "A"):
        x = [r for r in ok if r["condition"] == "real" and T2[r["accession"]]["set"] == st]
        prot_hit = prot_hit_id = npred = tp_id = tp_nm = fam_true = fam_found = 0
        iou = []
        helix_hit = helix_true = helix_pred = 0
        sp = collections.Counter()
        for r in x:
            t, a = T2[r["accession"]], r["ans"]
            pd = [d for d in (a.get("pfam_domains") or []) if isinstance(d, dict)]
            true_acc = {p["accession"] for p in t["pfam"]}
            true_nm = {norm(p["short"]) for p in t["pfam"]} | {norm(p["name"]) for p in t["pfam"]}
            npred += len(pd)
            fam_true += len(true_acc)
            hit = hit_id = False
            found = set()
            for d in pd:
                acc = str(d.get("accession") or "").split(".")[0]
                ia = acc in true_acc
                im = norm(d.get("name")) in true_nm
                tp_id += ia
                tp_nm += (ia or im)
                hit |= (ia or im)
                hit_id |= ia
                if ia:
                    found.add(acc)
                if (ia or im) and isinstance(d.get("start"), int) and isinstance(d.get("end"), int):
                    best = max((ov((d["start"], d["end"]), (p["start"], p["end"])) / (max(d["end"], p["end"]) - min(d["start"], p["start"]) + 1)
                                for p in t["pfam"] if p["accession"] == acc or norm(d.get("name")) in (norm(p["short"]), norm(p["name"]))), default=None)
                    if best is not None:
                        iou.append(best)
            fam_found += len(found)
            prot_hit += hit
            prot_hit_id += hit_id
            ph = [h for h in (a.get("transmembrane_helices") or []) if isinstance(h, list) and len(h) == 2 and all(isinstance(v, int) for v in h)]
            helix_true += len(t["tm"])
            helix_pred += len(ph)
            helix_hit += sum(any(ov(h, u) >= 10 for h in ph) for u in t["tm"])
            sp[(bool(a.get("signal_peptide")), t["signal"])] += 1
        print(f"   set {st} real n={len(x)}: proteins with >=1 correct family (id or name) {prot_hit}, by accession only {prot_hit_id}; "
              f"predicted domains {npred}, right accession {tp_id}, right id-or-name {tp_nm}; "
              f"reference families recovered by accession {pct(fam_found, fam_true)}; IoU {statistics.mean(iou) if iou else float('nan'):.2f} (n={len(iou)})")
        print(f"       TM helices recovered {helix_hit}/{helix_true}, predicted {helix_pred}; signal TP {sp[(True, True)]} FN {sp[(False, True)]} FP {sp[(True, False)]} TN {sp[(False, False)]}")
    sh = [r for r in ok if r["condition"] == "shuffled"]
    anyd = sum(bool([d for d in (r["ans"].get("pfam_domains") or []) if isinstance(d, dict)]) for r in sh)
    print(f"   shuffled: given any Pfam domain {anyd}/{len(sh)}")

# ---------------------------------------------------------------- Test 3
print("\n" + "=" * 30, "TEST 3: pseudoenzymes")
T3 = {t["accession"]: t for t in json.loads((ROOT / "pseudo" / "truth.json").read_text())}
print("truth groups:", dict(collections.Counter(t["group"] for t in T3.values())))
roles = collections.Counter(t.get("site_role") for t in T3.values() if t["group"] == "enzyme")
print("other-enzyme mutated residue types:", dict(collections.Counter(t.get("site_residue") for t in T3.values() if t["group"] == "enzyme")))
for m in MODELS:
    R = rows(ROOT / "pseudo" / "results" / f"{m}.jsonl")
    ok = [r for r in R if r.get("ans")]
    cnt = collections.defaultdict(collections.Counter)
    flagged = collections.Counter()
    for r in ok:
        t, a = T3[r["accession"]], r["ans"]
        key = (t["group"], r["variant"])
        cnt[key][str(a.get("catalytically_active")).lower()] += 1
        site = {"asp_to_asn": t.get("asp"), "lys_to_met": t.get("lys"), "site_to_ala": t.get("site")}.get(r["variant"])
        if site:
            flagged[key] += site in {d.get("position") for d in (a.get("substituted_or_missing") or []) if isinstance(d, dict)}
    print(f"\n-- {m}: {len(R)} calls, {len(R) - len(ok)} unparsed; effort {set(r.get('effort') for r in ok)}; "
          f"served sets {dict(collections.Counter(tuple(sorted(r.get('served') or [])) for r in R))}")
    for key in sorted(cnt):
        c = cnt[key]
        other = {k: v for k, v in c.items() if k not in ("yes", "no", "uncertain")}
        print(f"   {key[0]:7s} {key[1]:11s} n={sum(c.values())}: yes {c['yes']} no {c['no']} uncertain {c['uncertain']} other {other or 0}"
              + (f" | mutated position flagged {flagged[key]}" if key[1] != "wt" else ""))
    # wild-type false alarms: any substituted_or_missing entry reported on an unmutated active enzyme
    for g in ("kinase", "enzyme"):
        wt = [r for r in ok if T3[r["accession"]]["group"] == g and r["variant"] == "wt"]
        fa = sum(bool(r["ans"].get("substituted_or_missing")) for r in wt)
        print(f"   {g} wild type: answers listing any substituted/missing residue {fa}/{len(wt)}")

# ---------------------------------------------------------------- Test 4
print("\n" + "=" * 30, "TEST 4: structure")
T4 = {t["pdb"]: t for t in json.loads((ROOT / "structure" / "truth.json").read_text())}
DUP = {"27JP", "27JO", "27IQ"}
print("strata:", dict(collections.Counter(t["stratum"] for t in T4.values())),
      "| release dates", min(t["released"] for t in T4.values()), "to", max(t["released"] for t in T4.values()))
print("novel entries:")
for t in T4.values():
    if t["stratum"] == "novel":
        print(f"   {t['pdb']} rel {t['released']} len {len(t['sequence'])} resolved {len(t['ca'])} | {t['organism']} | uniprot {t.get('uniprot')} | {t['title'][:80]}")


def ss(n, h, e):
    s = ["C"] * (n + 1)
    for code, segs in (("H", h), ("E", e)):
        for g in segs or []:
            if isinstance(g, list) and len(g) == 2 and all(isinstance(v, int) for v in g):
                for i in range(max(1, g[0]), min(n, g[1]) + 1):
                    s[i] = code
    return s


for m in MODELS:
    R = rows(ROOT / "structure" / "results" / f"{m}.jsonl")
    ok = [r for r in R if r.get("ans")]
    print(f"\n-- {m}: {len(R)} calls, {len(R) - len(ok)} unparsed; effort {set(r.get('effort') for r in ok)}")
    for stratum in ("novel", "known"):
        q3, base, prec, chance, sepchance, rec, per = [], [], [], [], [], 0, []
        dropped = kept = 0
        for r in ok:
            t = T4[r["pdb"]]
            if t["stratum"] != stratum or r["pdb"] in DUP:
                continue
            a = r["ans"]
            L = len(t["sequence"])
            ca = {int(k): v for k, v in t["ca"].items()}
            obs = sorted(ca)
            tr, pr = ss(L, t["helices"], t["strands"]), ss(L, a.get("helices"), a.get("strands"))
            q = sum(tr[i] == pr[i] for i in obs) / len(obs)
            b = max(sum(tr[i] == c for i in obs) for c in "HEC") / len(obs)
            raw = [p for p in (a.get("contacts") or []) if isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) for v in p)]
            pairs = [p for p in raw if abs(p[0] - p[1]) >= 24 and p[0] in ca and p[1] in ca]
            dropped += len(raw) - len(pairs)
            kept += len(pairs)
            # contact probability as a function of sequence separation, in this structure
            bysep = collections.defaultdict(lambda: [0, 0])
            tot = [0, 0]
            for i in obs:
                for j in obs:
                    if j - i >= 24:
                        hit = math.dist(ca[i], ca[j]) < 8
                        bysep[j - i][0] += hit
                        bysep[j - i][1] += 1
                        tot[0] += hit
                        tot[1] += 1
            pc = sc = None
            if pairs:
                pc = sum(math.dist(ca[i], ca[j]) < 8 for i, j in pairs) / len(pairs)
                sc = statistics.mean(bysep[abs(i - j)][0] / bysep[abs(i - j)][1] for i, j in pairs)
                prec.append(pc)
                sepchance.append(sc)
            q3.append(q)
            base.append(b)
            chance.append(tot[0] / tot[1])
            rec += bool(a.get("recognised"))
            per.append((r["pdb"], q, b, pc, sc, bool(a.get("recognised"))))
        if not q3:
            continue
        d = [x - y for x, y in zip(q3, base)]
        lo, hi = boot(d)
        plo, phi = boot(prec) if prec else (float("nan"), float("nan"))
        print(f"   {stratum} (ASPRV1 once) n={len(q3)}: Q3 {100 * statistics.mean(q3):.1f} vs best-constant {100 * statistics.mean(base):.1f} "
              f"(difference {100 * statistics.mean(d):+.1f}, 95% {100 * lo:+.1f} to {100 * hi:+.1f}; proteins at or below baseline {sum(x <= 0 for x in d)})")
        print(f"       contact precision {100 * statistics.mean(prec):.1f} (95% {100 * plo:.1f} to {100 * phi:.1f}; n={len(prec)}) "
              f"vs all-long-range chance {100 * statistics.mean(chance):.1f} vs separation-matched chance {100 * statistics.mean(sepchance):.1f}; "
              f"scorable pairs {kept}, dropped {dropped}; says recognised {rec}/{len(q3)}")
        if stratum == "novel":
            for p in sorted(per):
                print(f"         {p[0]}: Q3 {100 * p[1]:.0f} base {100 * p[2]:.0f} contacts {('%.0f' % (100 * p[3])) if p[3] is not None else 'NA'} "
                      f"sep-chance {('%.0f' % (100 * p[4])) if p[4] is not None else 'NA'} recognised={p[5]}")
            nr = [p for p in per if not p[5]]
            if nr and len(nr) != len(per):
                print(f"       not-recognised only (n={len(nr)}): Q3 {100 * statistics.mean(p[1] for p in nr):.1f}, "
                      f"contact precision {100 * statistics.mean(p[3] for p in nr if p[3] is not None):.1f}")
