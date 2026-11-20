"""Run the four sequence-to-function tests on Gemini models via `agy -p`.

Uses the exact same test sets, sampling seeds, prompts, and reply-parsing rules
as `experiments/`, writing results into `gemini_experiment/results/<test>/` separately
from the original Claude results. Saved outputs are covered by `just check`.

Usage:
    uv run python gemini_experiment/run_agy.py <test> <model> [--workers 6] [--limit N] [--ncond 2]
"""
import argparse
import collections
import csv
import datetime
import functools
import json
import pathlib
import random
import re
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments"
OUT_ROOT = pathlib.Path(__file__).resolve().parent / "results"
sys.path.insert(0, str(EXP))
from common import KEYS, answer, has_tool_call, sha  # noqa: E402

PROMPTS = {
    "features": (
        "Below is a protein sequence in one-letter amino acid codes. Annotate it using only the sequence. "
        "Reply with a single JSON object and nothing else, with these keys: "
        '"pfam_domains": list of {"accession": "PFxxxxx", "name": Pfam short name, "start": int, "end": int} '
        "(1-based residue positions; empty list if none recognised); "
        '"transmembrane_helices": list of [start, end]; "signal_peptide": true or false; '
        '"protein_name": string; "ec_number": string or null; "function": one sentence. '
        "Do not guess identifiers you are not confident of: leave a field empty or null instead.\n\n>sequence\n"
    ),
    "pseudo": (
        "Below is a protein sequence in one-letter amino acid codes. Using only the sequence, decide whether the protein is "
        "likely to be catalytically active. Reply with a single JSON object and nothing else, with these keys: "
        '"protein_name": string; "enzyme_family": string; '
        '"catalytic_residues": list of {"role": string, "residue": one-letter code actually present in this sequence, "position": int (1-based)}; '
        '"substituted_or_missing": list of {"role": string, "expected": string, "found": string, "position": int or null} for any canonical catalytic or '
        "cofactor-binding residue that this sequence lacks (empty list if none); "
        '"catalytically_active": "yes", "no" or "uncertain"; "ec_number": string or null; "reason": one or two sentences.\n\n>sequence\n'
    ),
    "structure": (
        "Below is a protein sequence in one-letter amino acid codes (it may be a recombinant construct). Using only the sequence, predict its "
        "three-dimensional structure and then its function. Reply with a single JSON object and nothing else, with these keys: "
        '"helices": list of [start, end] residue ranges predicted to be helix (1-based positions in this sequence); '
        '"strands": list of [start, end] ranges predicted to be beta strand; '
        '"fold": short name of the predicted fold or structural superfamily; '
        '"contacts": list of exactly 20 [i, j] residue pairs with j - i >= 24 that you predict are in contact in the folded structure '
        "(C-alpha atoms within 8 angstroms), most confident first; "
        '"protein_name": string; "function": one sentence on the molecular function; '
        '"functional_residues": list of {"position": int, "residue": one-letter code, "role": string}; '
        '"recognised": true if you recognise this as a specific known protein, else false.\n\n>sequence\n'
    ),
}


def fasta(seq: str, width: int = 60) -> str:
    return "\n".join(seq[i : i + width] for i in range(0, len(seq), width))


def shuffled(seq: str, acc: str) -> str:
    chars = list(seq)
    random.Random(zlib.crc32(acc.encode())).shuffle(chars)
    return "".join(chars)


@functools.cache
def agy_version() -> str:
    return subprocess.run(["agy", "--version"], capture_output=True, text=True).stdout.strip()


def agy_unusable(row: dict) -> bool:
    """True if a row failed, returned non-SUCCESS, did not record exactly one turn (possible tool use),
    or finished for a reason other than STOP. This one rule decides both which questions the
    runners ask again on resume and which rows score_gemini.py and audit.py count (#144)."""
    return (
        "error" in row
        or row.get("status") != "SUCCESS"
        or row.get("num_turns") != 1
        or ("finish_reason" in row and row["finish_reason"] != "STOP")
    )


NO_TOOL_PREFIX = "Do not call or invoke any tools. "


def response_metadata(d: dict, headers=None) -> dict:
    """Everything the Gemini endpoint returned except the reply text itself (#155).

    Keeps responseId, createTime, modelVersion, usageMetadata, promptFeedback and every candidate
    field (finishReason, safetyRatings, citationMetadata, ...). Each content part is kept without
    its text and thought signature, whose lengths are recorded instead; the visible reply text is
    already stored in the row's `text`. `headers` are the HTTP response headers, minus cookies.
    """
    meta = {k: v for k, v in d.items() if k != "candidates"}
    meta["candidates"] = []
    for c in d.get("candidates") or []:
        c2 = {k: v for k, v in c.items() if k != "content"}
        parts = []
        for part in (c.get("content") or {}).get("parts") or []:
            q = {k: v for k, v in part.items() if k not in ("text", "thoughtSignature")}
            if "text" in part:
                q["text_chars"] = len(part["text"])
            if "thoughtSignature" in part:
                q["thought_signature_chars"] = len(part["thoughtSignature"])
            parts.append(q)
        c2["content"] = {k: v for k, v in (c.get("content") or {}).items() if k != "parts"}
        c2["content"]["parts"] = parts
        meta["candidates"].append(c2)
    if headers is not None:
        meta["http_headers"] = {k: v for k, v in headers.items() if k.lower() not in ("set-cookie", "cookie")}
    return meta


def call_agy(model: str, prompt: str, tries: int = 3, timeout: int = 300):
    """Run one single-turn prompt through `agy -p` from /tmp with slash commands disabled."""
    full_prompt = NO_TOOL_PREFIX + prompt
    rec = dict(
        model=model,
        prompt_sha256=sha(prompt),
        no_tool_prefix=True,
        cli_version=f"agy {agy_version()}",
    )
    j = None
    why = ""
    for attempt in range(1, tries + 1):
        try:
            proc = subprocess.run(
                [
                    "agy",
                    "-p",
                    full_prompt,
                    "--model",
                    model,
                    "--disable-slash-commands",
                    "--output-format",
                    "json",
                ],
                capture_output=True,
                text=True,
                cwd="/tmp",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            j = None
            why = f"timeout after {timeout}s"
            continue
        try:
            j = json.loads(proc.stdout)
        except ValueError:
            j = None
            why = (proc.stdout[-300:] + proc.stderr[-300:]).strip()
            continue
        if not isinstance(j, dict) or j.get("status") != "SUCCESS":
            why = json.dumps(j)[:400] if isinstance(j, dict) else proc.stdout[-400:]
            j = None
            if "safety" in why.lower():
                break
            continue
        break

    rec.update(
        attempts=attempt,
        asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    if j is None:
        return None, dict(rec, error=why or "no parseable output")

    u = j.get("usage") if isinstance(j.get("usage"), dict) else {}
    rec.update(
        status=j.get("status"),
        num_turns=j.get("num_turns"),
        duration_seconds=j.get("duration_seconds"),
        conversation_id=j.get("conversation_id"),
        input_tokens=u.get("input_tokens"),
        output_tokens=u.get("output_tokens"),
        thinking_tokens=u.get("thinking_tokens"),
        thinking=u.get("thinking_tokens"),
        cache_read_tokens=u.get("cache_read_tokens"),
        total_tokens=u.get("total_tokens"),
        served=[model],
    )
    text = j.get("response")
    return (text if isinstance(text, str) else ""), rec


def load_done(path: pathlib.Path, key_fn) -> set:
    if not path.exists():
        return set()
    rows = [json.loads(line) for line in path.open() if line.strip()]
    return {key_fn(r) for r in rows if not agy_unusable(r)}


def build_questions(test: str, model: str, ncond: int):
    if test == "next_residue":
        rows = list(csv.DictReader(open(EXP / "next_residue" / "upstream" / "confirm_sequences.tsv"), delimiter="\t"))
        byfam = collections.defaultdict(list)
        for r in rows:
            byfam[(r["size_bin"], r["pfam"])].append(r)
        rng = random.Random(20261118)
        bins = collections.defaultdict(list)
        for b, f in sorted(byfam):
            bins[b].append(f)
        qs = []
        for b in sorted(bins):
            for f in rng.sample(bins[b], 17):
                r = rng.choice(byfam[(b, f)])
                seq, acc = r["sequence"], r["accession"]
                for cut in rng.sample([int(c) for c in r["cuts"].split(",")], 2):
                    variants = {"real": seq, "shuffled": shuffled(seq, acc), "reversed": seq[::-1]}
                    for cond, s in list(variants.items())[:ncond]:
                        prefix = s[:cut]
                        prompt = (
                            "Below is the beginning of a protein sequence in one-letter amino acid codes. "
                            "Predict how it continues. Reply with exactly the next 10 amino acids as one-letter "
                            "codes on one line, and nothing else.\n\n>sequence\n" + fasta(prefix)
                        )
                        meta = dict(
                            model=model,
                            accession=acc,
                            pfam=f,
                            size_bin=b,
                            fam_n=int(r["family_proteins"]),
                            condition=cond,
                            cut=cut,
                            target=s[cut : cut + 10],
                        )
                        qs.append(((acc, cond, cut), prompt, meta))
        return qs, lambda d: (d["accession"], d["condition"], d["cut"])

    truth = json.loads((EXP / test / "truth.json").read_text())
    if test == "features":
        qs = []
        for t in truth:
            for cond in ("real", "shuffled"):
                seq = t["sequence"] if cond == "real" else shuffled(t["sequence"], t["accession"])
                qs.append(((t["accession"], cond), PROMPTS["features"] + fasta(seq), dict(accession=t["accession"], condition=cond)))
        return qs, lambda d: (d["accession"], d["condition"])

    if test == "pseudo":
        qs = []
        for t in truth:
            for v in t["variants"]:
                qs.append(
                    (
                        (t["accession"], v),
                        PROMPTS["pseudo"] + fasta(t["variants"][v]),
                        dict(accession=t["accession"], group=t["group"], variant=v),
                    )
                )
        return qs, lambda d: (d["accession"], d["variant"])

    if test == "structure":
        qs = [
            (t["pdb"], PROMPTS["structure"] + fasta(t["sequence"]), dict(pdb=t["pdb"]))
            for t in truth
        ]
        return qs, lambda d: d["pdb"]

    raise ValueError(f"Unknown test: {test}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["next_residue", "features", "pseudo", "structure"])
    ap.add_argument("model")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ncond", type=int, default=2, help="Conditions for next_residue (2 or 3)")
    args = ap.parse_args()

    out_dir = OUT_ROOT / args.test
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.model}.jsonl"

    qs, key_fn = build_questions(args.test, args.model, args.ncond)
    done = load_done(out_path, key_fn)
    todo = [q for q in qs if q[0] not in done][: args.limit]
    print(f"[{args.test}] {args.model}: {len(qs)} total, {len(done)} done, {len(todo)} to run", flush=True)
    if not todo:
        return

    def ask_one(item):
        _, prompt, meta = item
        text, rec = call_agy(args.model, prompt)
        if text is None:
            return dict(meta, **rec)
        if args.test == "next_residue":
            cands = re.findall(r"[ACDEFGHIKLMNPQRSTVWY]{5,}", text.replace(" ", ""))
            pred = cands[-1] if cands else ""
            valid = bool(pred) and not has_tool_call(text)
            return dict(
                meta,
                text=text,
                pred=pred,
                valid=valid,
                first_correct=valid and pred[0] == meta["target"][0],
                exact10=valid and pred[:10] == meta["target"],
                **rec,
            )
        return dict(meta, text=text, ans=answer(text, KEYS[args.test]), **rec)

    with ThreadPoolExecutor(args.workers) as ex, out_path.open("a") as fh:
        for i, row in enumerate(ex.map(ask_one, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"  [{args.test}] {args.model}: {i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
