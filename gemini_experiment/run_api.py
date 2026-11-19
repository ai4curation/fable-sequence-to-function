"""Run the four sequence-to-function tests on Gemini models via the direct Gemini REST API.

Uses the exact same test sets, sampling seeds, prompts, and reply-parsing rules
as `experiments/`, with zero tools and zero system prompt. Writes results into
`gemini_experiment/results/<test>/` separately from the original Claude results. Saved outputs are covered by `just check`.

Usage:
    uv run python gemini_experiment/run_api.py <test> <model> [--effort medium|high|low] [--workers 8] [--limit N] [--ncond 2]
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
EXP = ROOT / "experiments"
OUT_ROOT = HERE / "results"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(HERE))
from common import KEYS, answer, has_tool_call, sha  # noqa: E402
from run_agy import build_questions  # noqa: E402


def thinking_config(model: str, effort: str) -> dict:
    if model.startswith("gemini-2.5"):
        budgets = {"low": 0, "medium": 2048, "high": 8192}
        return {"thinkingConfig": {"thinkingBudget": budgets[effort]}}
    return {"thinkingConfig": {"thinkingLevel": effort.upper()}}


def api_unusable(row: dict) -> bool:
    return "error" in row or row.get("status") != "SUCCESS"


def call_gemini_api(model: str, effort: str, prompt: str, tries: int = 5, timeout: int = 240):
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": thinking_config(model, effort),
    }
    body = json.dumps(payload).encode()
    rec = dict(
        model=model,
        effort=effort,
        prompt_sha256=sha(prompt),
        cli_version="gemini-rest-v1beta",
    )
    d = None
    why = ""
    t0 = time.time()
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")[:400]
            why = f"HTTP {e.code}: {err_body}"
            d = None
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(5 * (2 ** (attempt - 1)), 45))
                continue
            break
        except Exception as e:
            why = str(e)[:400]
            d = None
            time.sleep(2)
            continue

    rec.update(
        attempts=attempt,
        duration_seconds=round(time.time() - t0, 3),
        asked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    if d is None:
        return None, dict(rec, error=why or "no response")

    cands = d.get("candidates") or []
    if not cands:
        fb = d.get("promptFeedback")
        return None, dict(rec, error=f"no candidates: {fb}")

    cand = cands[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    u = d.get("usageMetadata") or {}
    rec.update(
        status="SUCCESS",
        num_turns=1,
        finish_reason=cand.get("finishReason"),
        model_version=d.get("modelVersion"),
        input_tokens=u.get("promptTokenCount"),
        output_tokens=u.get("candidatesTokenCount"),
        thinking_tokens=u.get("thoughtsTokenCount"),
        thinking=u.get("thoughtsTokenCount"),
        total_tokens=u.get("totalTokenCount"),
        served=[d.get("modelVersion") or model],
    )
    return text, rec


def load_done(path: pathlib.Path, key_fn) -> set:
    if not path.exists():
        return set()
    rows = [json.loads(line) for line in path.open() if line.strip()]
    return {key_fn(r) for r in rows if not api_unusable(r)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["next_residue", "features", "pseudo", "structure"])
    ap.add_argument("model")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default="high")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ncond", type=int, default=2)
    args = ap.parse_args()

    out_dir = OUT_ROOT / args.test
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}-{args.effort}"
    out_path = out_dir / f"{tag}.jsonl"

    qs, key_fn = build_questions(args.test, tag, args.ncond)
    done = load_done(out_path, key_fn)
    todo = [q for q in qs if q[0] not in done][: args.limit]
    print(f"[{args.test}] {tag}: {len(qs)} total, {len(done)} done, {len(todo)} to run", flush=True)
    if not todo:
        return

    def ask_one(item):
        _, prompt, meta = item
        text, rec = call_gemini_api(args.model, args.effort, prompt)
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
                print(f"  [{args.test}] {tag}: {i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
