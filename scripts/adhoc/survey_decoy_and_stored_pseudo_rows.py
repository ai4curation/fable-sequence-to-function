"""Survey the decoy-control rows and the stored test 3 rows before adapting PR 10 to experiments/common.py.

Purpose: (1) size and cost of the rerun of the original mutants asked for in issue 11; (2) whether the decoy rows,
         read by common.answer, give the same answers as the `ans` stored at run time; (3) whether any decoy row
         passes common.context_limit; (4) how many decoy replies mention the decoy position (issue 12).
Inputs:  experiments/decoy_control/{decoys.json,results/*.jsonl}, experiments/pseudo/{truth.json,ask.py,results/*.jsonl}.
Outputs: text on standard output. Nothing is written.     Serves: pull request 10, issues 11 and 12.     2026-11-19
"""
import ast, collections, json, pathlib, re, sys
EXP = pathlib.Path(__file__).resolve().parents[2] / "experiments"; sys.path.insert(0, str(EXP)); import common
K = common.KEYS["pseudo"]
P = next(ast.literal_eval(n.value) for n in ast.parse((EXP / "pseudo/ask.py").read_text()).body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "P" for t in n.targets))
def fasta(s, w=60): return "\n".join(s[i:i+w] for i in range(0, len(s), w))
T = json.loads((EXP / "pseudo/truth.json").read_text()); D = json.loads((EXP / "decoy_control/decoys.json").read_text())
print("truth groups:", dict(collections.Counter(t["group"] for t in T)), "; variants per group:", {g: sorted({v for t in T if t["group"] == g for v in t["variants"]}) for g in {t["group"] for t in T}})
orig = [(t["accession"], v) for t in T if t["group"] in ("kinase", "enzyme") for v in t["variants"]]
print("questions in --set original:", len(orig), "; decoys:", len(D))
seqs = {(d["accession"], d["variant"]): d["sequence"] for d in D}
for m in ("claude-fable-5-2", "claude-opus-5-5", "claude-opus-4-6"):
    S = [json.loads(l) for l in open(EXP / "pseudo/results" / f"{m}.jsonl")]
    so = [r for r in S if (r["accession"], r["variant"]) in set(orig)]
    R = [json.loads(l) for l in open(EXP / "decoy_control/results" / f"{m}.jsonl")]
    same = sum(common.answer(r.get("text"), K) == r.get("ans") for r in R)
    over = sum((r["input_tokens"] or 0) + (r["cache_creation_input_tokens"] or 0) + (r["cache_read_input_tokens"] or 0) > common.context_limit(P + fasta(seqs[(r["accession"], r["variant"])])) for r in R)
    pos = {(d["accession"], d["variant"]): d["position"] for d in D}
    mention = [f"{r['accession']} {pos[(r['accession'], r['variant'])]}" for r in R if re.search(rf"(?<!\d){pos[(r['accession'], r['variant'])]}(?!\d)", r.get("text") or "")]
    print(f"{m}: stored rows {len(S)} (efforts {common.efforts(S)}), of them in --set original {len(so)}, their cost ${sum(r.get('cost') or 0 for r in so):.2f}; "
          f"decoy rows {len(R)} (efforts {common.efforts(R)}), common.answer equals stored ans in {same}, tool calls {len(common.tool_calls(R))}, "
          f"multi-object {sum(len(common.json_objects(r.get('text'), K)) > 1 for r in R)}, over common limit {over}, max context {max((r['input_tokens'] or 0) + (r['cache_creation_input_tokens'] or 0) + (r['cache_read_input_tokens'] or 0) for r in R)}")
    print("   reply text mentions the decoy position number:", len(mention), mention)
for f in sorted((EXP / "decoy_control/results").glob("*.jsonl")): print(f.name, sum(1 for _ in open(f)))
