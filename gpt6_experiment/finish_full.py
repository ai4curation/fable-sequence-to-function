"""Wait for an existing EC2 full-analysis controller, then verify and optionally publish its results.

Usage on EC2: uv run python gpt6_experiment/finish_full.py PID --publish
Does not start model calls or retry failed questions. --publish commits only this experiment's
results, reports and data checksums, then pushes the current branch without forcing.
"""
import argparse
import fcntl
import hashlib
import json
import pathlib
import subprocess
import sys
import time

import run_full as full


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pid", type=int)
    ap.add_argument("--home", type=pathlib.Path, default=full.runner.DEFAULT_HOME)
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()
    root = full.runner.ROOT
    work = args.home / "full_analysis"
    manifest = (work / "manifest.json").read_bytes()
    lock = (work / "finish.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def identity():
        try:
            # Field 22, after the parenthesised command: avoid following a reused PID.
            return pathlib.Path(f"/proc/{args.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        except FileNotFoundError:
            return None

    def run(cmd, output=None):
        return subprocess.run(cmd, cwd=root, check=True, stdout=output)

    result = dict(status="waiting", pid=args.pid)
    status_path = work / "completion.json"

    def save():
        temp = status_path.with_suffix(".tmp")
        temp.write_text(json.dumps(result, indent=2) + "\n")
        temp.replace(status_path)

    save()
    try:
        initial = identity()
        while initial is not None and identity() == initial:
            time.sleep(30)
        if (work / "manifest.json").read_bytes() != manifest:
            raise RuntimeError("the run manifest changed; refusing to finalize another run")
        for model in full.MODELS:
            state = json.loads((work / f"{model}.json").read_text())
            if state["status"] != "complete":
                raise RuntimeError(f"{model} is {state['status']}: {state.get('error')}")
        reports = (("gpt6.txt", ["gemini_experiment/score_gemini.py", "gpt6_experiment/results"]),
                   ("gpt6_audit.txt", ["gemini_experiment/audit.py", "gpt6_experiment/results"]),
                   ("gpt6_decoys.txt", ["experiments/decoy_control/score_decoys.py", "--results",
                     "gpt6_experiment/results/decoy_control", "--pseudo-results", "gpt6_experiment/results/pseudo"]))
        # A full report requires every planned call and a fresh audit; unparsed replies are counted.
        (root / "gpt6_experiment/run_manifest.json").write_bytes(manifest)
        run([sys.executable, "gpt6_experiment/report_full.py"])
        for name, cmd in reports:
            temp = work / name
            with temp.open("w") as output:
                run([sys.executable, *cmd], output)
            (root / "expected" / name).write_bytes(temp.read_bytes())
        sums = root / "SHA256SUMS"
        hashes = {p: digest for line in sums.read_text().splitlines() if line.strip()
                  for digest, p in [line.split(None, 1)]}
        for p, digest in hashes.items():
            if not p.startswith("gpt6_experiment/") and hashlib.sha256((root / p).read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"unrelated frozen data changed: {p}")
        for path in (root / "gpt6_experiment/results").rglob("*.jsonl"):
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes["gpt6_experiment/run_manifest.json"] = hashlib.sha256(manifest).hexdigest()
        sums.write_text("".join(f"{hashes[p]}  {p}\n" for p in sorted(hashes)))
        run(["git", "diff", "--check"])
        if args.publish:
            branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=root, text=True).strip()
            if branch != "gpt6/codex-runner-on-115" or staged:
                raise RuntimeError("unexpected branch or pre-existing staged changes; results remain on disk")
            run(["git", "fetch", "origin", "gpt6/codex-runner-on-115"])
            run(["git", "merge-base", "--is-ancestor", "origin/gpt6/codex-runner-on-115", "HEAD"])
            run(["git", "add", "gpt6_experiment/results", "gpt6_experiment/RESULTS.md", "gpt6_experiment/run_manifest.json", "expected/gpt6.txt",
                 "expected/gpt6_audit.txt", "expected/gpt6_decoys.txt", "SHA256SUMS"])
            run(["git", "commit", "-m", "Record the full GPT-6 Astra and Rosalind comparison"])
            run(["git", "push", "origin", "HEAD:gpt6/codex-runner-on-115"])
        result.update(status="published" if args.publish else "verified",
                      commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip())
    except Exception as exc:
        result.update(status="stopped", error=str(exc))
        raise
    finally:
        save()
        lock.close()


if __name__ == "__main__":
    main()
