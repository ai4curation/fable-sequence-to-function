"""Draw the manuscript figures from the committed model outputs. Usage: make_figures.py [--values-only] [PROBE_DIR]

PROBE_DIR is the folder that holds pseudo/ and structure/. It defaults to experiments/ in this repository.
A checkout of projects/LLM_SEQUENCE_PROBE from ai4curation/ai-gene-review (commit 119ac18676) holds the same data.
The plotted values come from the scoring code in experiments/pseudo/score.py and experiments/structure/score.py and
are printed at the end. With --values-only nothing is drawn or written; `just check` compares that output with
expected/figures.txt.
"""
import collections, importlib.util, json, pathlib, statistics, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ARGS = [a for a in sys.argv[1:] if a != "--values-only"]; DRAW = "--values-only" not in sys.argv[1:]
if len(ARGS) > 1: sys.exit(__doc__)
HERE = pathlib.Path(__file__).parent; ROOT = pathlib.Path(ARGS[0]) if ARGS else HERE.parent / "experiments"
# The four models run on all four tests. Each entry: key, legend label, colour, results file for the PSEUDO test, results file for the STRFN test.
# Claude models at high effort; Gemini 4 Neon at the settings it was run at (low in the PSEUDO test, medium in the STRFN test).
GEM = HERE.parent / "gemini_experiment" / "results_vertex"
MODELS = [("claude-fable-5-2", "Fable 5.2", "#2a78d6", ROOT / "pseudo/results/claude-fable-5-2.jsonl", ROOT / "structure/results/claude-fable-5-2.jsonl"),
          ("claude-opus-5-5", "Opus 5.5", "#eb6834", ROOT / "pseudo/results/claude-opus-5-5.jsonl", ROOT / "structure/results/claude-opus-5-5.jsonl"),
          ("claude-opus-4-6-high", "Opus 4.6", "#1baf7a", ROOT / "pseudo/results/claude-opus-4-6-high.jsonl", ROOT / "structure/results/claude-opus-4-6-high.jsonl"),
          ("gemini-4-neon", "Gemini 4 Neon", "#eda100", GEM / "pseudo/gemini-4-neon-low.jsonl", GEM / "structure/gemini-4-neon-medium.jsonl")]
NEED = [ROOT / d / "truth.json" for d in ("pseudo", "structure")] + [f for m in MODELS for f in m[3:]]
MISSING = [str(f) for f in NEED if not f.exists()]
if MISSING: sys.exit("Missing input files:\n  " + "\n  ".join(MISSING) + "\n\n" + __doc__)   # stop before any figure is overwritten
def scorer(test):   # the scoring module of one test, loaded from this repository
    spec = importlib.util.spec_from_file_location(f"{test}_score", HERE.parent / "experiments" / test / "score.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
PSEUDO, STRUCT = scorer("pseudo"), scorer("structure")
INK, MUTED, GRID = "#1a1a19", "#6b6a63", "#e4e3dd"
plt.rcParams.update({"font.size": 8.5, "font.family": "DejaVu Sans", "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
def bars(ax, groups, values, ymax, fmt="{:.0f}"):
    w = 0.8 / len(MODELS)
    for k, (mid, label, col, *_) in enumerate(MODELS):
        xs = [i + (k - (len(MODELS) - 1) / 2) * w for i in range(len(groups))]
        ax.bar(xs, values[mid], w - 0.03, color=col, label=label, zorder=3)
        for x, v in zip(xs, values[mid]): ax.text(x, v + ymax * 0.015, fmt.format(v), ha="center", va="bottom", fontsize=6.5, color=INK, zorder=6,
                                                    bbox=dict(facecolor="white", edgecolor="none", pad=0.3, alpha=0.85))
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups); ax.set_ylim(0, ymax); ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0); ax.spines["left"].set_visible(False)

# Figure 2: share of sequences called catalytically active, by sequence class
T = {t["accession"]: t for t in json.loads((ROOT / "pseudo/truth.json").read_text())}
classes = [("kinase", "wt", "Kinase\nwild type"), ("kinase", "asp_to_asn", "Kinase\nAsp→Asn"), ("kinase", "lys_to_met", "Kinase\nLys→Met"),
           ("pseudo", "wt", "Named inactive\nin Swiss-Prot"), ("enzyme", "wt", "Other enzyme\nwild type"), ("enzyme", "site_to_ala", "Other enzyme\nsite→Ala")]
vals = {}
for mid, _, _, f3, _ in MODELS:
    c = collections.Counter(); n = collections.Counter()
    for r in PSEUDO.load(f3)[0]:
        if not r["ans"]: continue   # as in the scorer, an unparsed reply is not counted
        key = (T[r["accession"]]["group"], r["variant"]); n[key] += 1
        c[key] += str(r["ans"].get("catalytically_active")).lower() == "yes"
    vals[mid] = [100 * c[(g, v)] / n[(g, v)] for g, v, _ in classes]
fig, ax = plt.subplots(figsize=(6.9, 2.8))
bars(ax, [c[2] for c in classes], vals, 112); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_ylabel("Called catalytically active (%)")
ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.16))
fig.tight_layout()
if DRAW: fig.savefig(HERE / "fig1_pseudoenzyme.pdf")
plt.close(fig)

# Figure 3: secondary structure and contact precision against deposited structures (ASPRV1 counted once)
S = {t["pdb"]: t for t in json.loads((ROOT / "structure/truth.json").read_text())}
q3 = {}; cp = {}; base = collections.defaultdict(list); chance = collections.defaultdict(list)
for mid, _, _, _, f4 in MODELS:
    q = collections.defaultdict(list); p = collections.defaultdict(list)
    for r in STRUCT.load(f4)[0]:
        t = S[r["pdb"]]
        if r["pdb"] in STRUCT.ASPRV1_REPEATS or not r["ans"]: continue
        v = STRUCT.one(t, r["ans"]); q[t["stratum"]].append(100 * v["q3"])
        if v["prec"] is not None: p[t["stratum"]].append(100 * v["prec"])
        if mid == MODELS[0][0]: base[t["stratum"]].append(100 * v["base"]); chance[t["stratum"]].append(100 * v["chance"])
    q3[mid] = [statistics.mean(q[s]) for s in ("novel", "known")]; cp[mid] = [statistics.mean(p[s]) for s in ("novel", "known")]
fig, axs = plt.subplots(1, 2, figsize=(6.9, 2.8))
labels = ["Unmatched\n(no earlier entry\nat 30% identity)", "Matched\n(20 or more\nearlier entries)"]
for ax, v, ymax, ylab, ref, name in ((axs[0], q3, 100, "Secondary structure accuracy, Q3 (%)", base, "best single\nstate"),
                                     (axs[1], cp, 62, "Long-range contact precision (%)", chance, "chance")):
    bars(ax, labels, v, ymax, "{:.0f}"); ax.set_ylabel(ylab); ax.set_xlim(-0.55, 1.95)
    for i, s in enumerate(("novel", "known")):
        y = statistics.mean(ref[s]); ax.plot([i - 0.42, i + 0.42], [y, y], color=INK, linewidth=1, linestyle=(0, (3, 2)), zorder=4)
    ax.text(1.47, statistics.mean(ref["known"]), name, ha="left", va="center", fontsize=7, color=MUTED)
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, frameon=False, ncol=4, loc="upper center")
fig.tight_layout(rect=(0, 0, 1, 0.92))
if DRAW: fig.savefig(HERE / "fig2_structure.pdf")
plt.close(fig)
f1 = lambda v: "  ".join(f"{x:5.1f}" for x in v)
print("Figure 2, called catalytically active (%): " + "; ".join(c[2].replace("\n", " ") for c in classes))
for mid, label, *_ in MODELS: print(f"  {label:13s} {f1(vals[mid])}")
print("Figure 3, unmatched and matched stratum (novel and known in the data files), ASPRV1 counted once")
for mid, label, *_ in MODELS: print(f"  {label:13s} Q3 (%) {f1(q3[mid])}   long-range contact precision (%) {f1(cp[mid])}")
print(f"  reference lines: best single state {f1([statistics.mean(base[s]) for s in ('novel', 'known')])}   chance {f1([statistics.mean(chance[s]) for s in ('novel', 'known')])}")
