"""Run the four sequence-to-function tests on Gemini models via Vertex AI (global endpoint).

Uses `gcloud auth print-access-token` (headless; never opens a browser) and the exact
prompts, test sets, sampling seeds, and reply-parsing rules from `experiments/`, with
zero tools and zero system prompt. Writes to `gemini_experiment/results_vertex/<test>/`.

Usage:
    uv run python gemini_experiment/run_vertex.py <test> <model> [--effort high|medium|low] [--workers 8] [--limit N] [--ncond 2]
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
EXP = ROOT / "experiments"
OUT_ROOT = HERE / "results_vertex"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(HERE))
from common import KEYS, answer, has_tool_call, sha  # noqa: E402
from run_agy import agy_unusable, build_questions  # noqa: E402

DEFAULT_PROJECT = "test-project-covid-19-277821"

_token_lock = threading.Lock()
_token_cache = {"token": None, "fetched_at": 0.0}


def get_token(force: bool = False) -> str:
    with _token_lock:
        now = time.time()
        if not force and _token_cache["token"] and (now - _token_cache["fetched_at"]) < 1800:
            return _token_cache["token"]
        proc = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"gcloud auth print-access-token failed: {proc.stderr.strip()}")
        _token_cache["token"] = proc.stdout.strip()
        _token_cache["fetched_at"] = now
        return _token_cache["token"]


vertex_unusable = agy_unusable  # one rule for resume and scoring (#144)


def call_vertex(project: str, model: str, effort: str, prompt: str, tries: int = 3, timeout: int = 480):
    url = f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"thinkingConfig": {"thinkingLevel": effort.upper()}},
    }
    body = json.dumps(payload).encode()
    rec = dict(
        model=model,
        effort=effort,
        prompt_sha256=sha(prompt),
        cli_version="vertex-ai-v1-global",
    )
    d = None
    why = ""
    t0 = time.time()
    for attempt in range(1, tries + 1):
        tok = get_token(force=(attempt > 1 and "401" in why))
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")[:400]
            why = f"HTTP {e.code}: {err_body}"
            d = None
            if e.code in (401, 429, 500, 502, 503, 504):
                time.sleep(min(3 * (2 ** (attempt - 1)), 30))
                continue
            break
        except Exception as e:
            why = str(e)[:400]
            d = None
            time.sleep(3)
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
        return None, dict(rec, error=f"no candidates: {d.get('promptFeedback')}")

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
    return {key_fn(r) for r in rows if not vertex_unusable(r)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["next_residue", "features", "pseudo", "structure"])
    ap.add_argument("model")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default="high")
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ncond", type=int, default=2)
    args = ap.parse_args()

    # Pre-fetch token once on main thread
    get_token()

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
        text, rec = call_vertex(args.project, args.model, args.effort, prompt)
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
        futs = [ex.submit(ask_one, item) for item in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if i % 5 == 0 or i == len(todo):
                err = " ERR" if vertex_unusable(row) else ""
                print(f"  [{args.test}] {tag}: {i}/{len(todo)}{err}", flush=True)


if __name__ == "__main__":
    main()
