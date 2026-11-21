"""Run the #52 comparison on EC2 in bounded, resumable waves; no automatic re-asking.

Usage: uv run python gpt6_experiment/run_full.py --workers 4
Uses the experiment login already prepared on this host. Each model runs one test at a time;
one unusable new row stops both models after their running calls finish. Logs, status and
reports live under <home>/full_analysis. Results remain in the repository's append-only files.
"""
import argparse
import datetime
import fcntl
import json
import pathlib
import signal
import socket
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import run_codex as runner

# Test 1 low includes reversed sequences; high matches the original two-condition run.
# The other tests precede test 1 high so the long high-effort run does not delay their results.
GRID = (("next_residue", "low", 3), ("features", "high", 2), ("pseudo", "high", 2),
        ("decoy_control", "high", 2), ("structure", "high", 2), ("next_residue", "high", 2))
MODELS = ("gpt-6-astra", "gpt-rosalind-astra")


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def usable(test, row):
    return not runner.codex_unusable(row) and (test == "next_residue" or
        runner.answer(row.get("text"), runner.KEYS["pseudo" if test == "decoy_control" else test]) is not None)


def coverage(test, model, effort, ncond, rows):
    questions, key = runner.build_questions(test, f"{model}-{effort}", ncond)
    expected = {q[0] for q in questions}
    asked = {key(r) for r in rows if not r.get("not_asked")}
    accepted = {key(r) for r in rows if usable(test, r)}
    return dict(expected=len(expected), attempted=len(expected & asked), usable=len(expected & accepted),
                remaining=len(expected - asked), unusable_questions=len((expected & asked) - accepted))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    ap.add_argument("--workers", type=int, default=4, help="Concurrent calls per model, also the wave size")
    ap.add_argument("--home", type=pathlib.Path, default=runner.DEFAULT_HOME)
    args = ap.parse_args()
    if args.workers < 1 or len(set(args.models)) != len(args.models):
        ap.error("workers must be positive and models must be distinct")
    if "gpt-rosalind-astra" in args.models and sys.platform != "linux":
        ap.error("Run Rosalind through the paired Orca EC2 environment, not this laptop")
    work = args.home / "full_analysis"
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / "run.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        ap.error(f"another full analysis holds {work / 'run.lock'}")
    stop = threading.Event()
    for sig in runner.STOP_SIGNALS:
        if signal.getsignal(sig) != signal.SIG_IGN:
            signal.signal(sig, lambda *_: stop.set())
    manifest = dict(host=socket.gethostname(), cli=runner.codex_version(), models=args.models,
                    workers_per_model=args.workers, grid=GRID,
                    commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=runner.ROOT, text=True).strip(),
                    started_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def save(model, state):
        state = dict(state, updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        dest = work / f"{model}.json"
        temp = dest.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=2) + "\n")
        temp.replace(dest)
        print(json.dumps(dict(model=model, **state)), flush=True)

    def run_model(model):
        state = dict(status="running", stages=[])
        try:
            for test, effort, ncond in GRID:
                path = runner.OUT_ROOT / test / f"{model}-{effort}.jsonl"
                stage = dict(test=test, effort=effort, ncond=ncond)
                state["stages"].append(stage)
                while True:
                    rows = read_rows(path)
                    stage.update(coverage(test, model, effort, ncond, rows))
                    save(model, state)
                    if stage["unusable_questions"]:
                        raise RuntimeError(f"{test}/{effort}: attempted questions lack usable replies; inspect evidence before re-asking")
                    if stage["usable"] == stage["expected"]:
                        break
                    if stop.is_set():
                        raise RuntimeError("stopped; running wave drained")
                    cmd = [sys.executable, "-u", str(runner.HERE / "run_codex.py"), test, model,
                           "--effort", effort, "--ncond", str(ncond), "--workers", str(args.workers),
                           "--limit", str(args.workers), "--home", str(args.home)]
                    with (work / f"{model}-{test}-{effort}.log").open("a") as log:
                        proc = subprocess.Popen(cmd, cwd=runner.ROOT, stdout=log, stderr=subprocess.STDOUT,
                                                stdin=subprocess.DEVNULL, start_new_session=True)
                        signalled = False
                        while True:
                            try:
                                code = proc.wait(timeout=1)
                                break
                            except subprocess.TimeoutExpired:
                                if stop.is_set() and not signalled:
                                    proc.send_signal(signal.SIGTERM)
                                    signalled = True
                    after = read_rows(path)
                    stage.update(coverage(test, model, effort, ncond, after))
                    if code or len(after) <= len(rows) or any(not usable(test, r) for r in after[len(rows):]):
                        raise RuntimeError(f"{test}/{effort}: wave stopped (exit {code}); inspect {work} and launch journal")
            state["status"] = "complete"
        except Exception as exc:
            stop.set()
            state.update(status="stopped", error=str(exc))
        save(model, state)
        return state["status"] == "complete"

    with ThreadPoolExecutor(len(args.models)) as pool:
        complete = list(pool.map(run_model, args.models))
    reports = [(["gemini_experiment/score_gemini.py", "gpt6_experiment/results"], "scores.txt"),
               (["gemini_experiment/audit.py", "gpt6_experiment/results"], "audit.txt"),
               (["experiments/decoy_control/score_decoys.py", "--results", "gpt6_experiment/results/decoy_control",
                 "--pseudo-results", "gpt6_experiment/results/pseudo"], "decoys.txt")]
    for cmd, name in reports:
        with (work / name).open("w") as output:
            result = subprocess.run([sys.executable, *cmd], cwd=runner.ROOT, stdout=output, stderr=subprocess.STDOUT)
        complete.append(result.returncode == 0)
    lock.close()
    raise SystemExit(0 if all(complete) else 1)


if __name__ == "__main__":
    main()
