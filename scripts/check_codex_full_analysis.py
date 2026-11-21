"""Offline checks for the full comparison: grid, prompt identity, wave stopping and resume."""
import ast
import contextlib
import io
import json
import pathlib
import signal
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gpt6_experiment"))
import run_full as full
from run_agy import fasta


class FullAnalysisTests(unittest.TestCase):
    def test_grid_and_decoy_prompt_identity(self):
        self.assertEqual(sum(len(full.runner.build_questions(t, "audit", n)[0]) for t, e, n in full.GRID), 1008)
        tree = ast.parse((ROOT / "experiments/pseudo/ask.py").read_text())
        prompt = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(getattr(t, "id", "") == "P" for t in n.targets))
        decoys = json.loads((ROOT / "experiments/decoy_control/decoys.json").read_text())
        questions, key = full.runner.build_questions("decoy_control", "audit", 2)
        self.assertEqual(len(questions), 58)
        for (identity, question, meta), decoy in zip(questions, decoys):
            self.assertEqual(question, prompt + fasta(decoy["sequence"]))
            self.assertEqual(identity, key(decoy))
            self.assertEqual(meta["group"], decoy["group"])

    def exercise(self, fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            calls = []
            build = full.runner.build_questions

            def short_questions(test, model, ncond):
                questions, key = build(test, model, ncond)
                return questions[:3], key

            class FakeProcess:
                def __init__(self, cmd, **kwargs):
                    test, model = cmd[3:5]
                    effort = cmd[cmd.index("--effort") + 1]
                    ncond = int(cmd[cmd.index("--ncond") + 1])
                    limit = int(cmd[cmd.index("--limit") + 1])
                    calls.append((test, model, effort, limit))
                    dest = home / "results" / test / f"{model}-{effort}.jsonl"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    old = full.read_rows(dest)
                    qs, key = short_questions(test, model, ncond)
                    done = {key(r) for r in old}
                    with dest.open("a") as output:
                        for identity, prompt, meta in [q for q in qs if q[0] not in done][:limit]:
                            # Two requested keys suffice for the canonical JSON parser.
                            keys = full.runner.KEYS["pseudo" if test == "decoy_control" else test] if test != "next_residue" else []
                            text = json.dumps({k: [] for k in list(keys)[:2]}) if keys else "MKVLAAGIVG"
                            row = dict(meta, text=text, model=model, effort=effort, num_turns=1,
                                       status="UNUSABLE" if fail else "SUCCESS", codex_row_format=2,
                                       cli_version="codex-exec stub", prompt_sha256=full.runner.sha(prompt))
                            output.write(json.dumps(row) + "\n")

                def wait(self, timeout=None):
                    return 0

            handlers = {sig: signal.getsignal(sig) for sig in full.runner.STOP_SIGNALS}
            try:
                with patch.object(full.runner, "OUT_ROOT", home / "results"), \
                     patch.object(full.runner, "build_questions", short_questions), \
                     patch.object(full.runner, "codex_version", lambda: "stub"), \
                     patch.object(full.sys, "platform", "linux"), \
                     patch.object(full.sys, "argv", ["run_full.py", "--home", str(home), "--workers", "2"]), \
                     patch.object(full.subprocess, "check_output", lambda *a, **k: "stubcommit\n"), \
                     patch.object(full.subprocess, "Popen", FakeProcess), \
                     patch.object(full.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0)), \
                     contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as exit:
                        full.main()
                    self.assertEqual(exit.exception.code, int(fail))
                    before = len(calls)
                    # Neither completed nor failed questions may be automatically re-asked.
                    with self.assertRaises(SystemExit) as exit:
                        full.main()
                    self.assertEqual(exit.exception.code, int(fail))
                    self.assertEqual(len(calls), before)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
            states = [json.loads((home / "full_analysis" / f"{m}.json").read_text()) for m in full.MODELS]
            if fail:
                self.assertTrue(all(s["status"] == "stopped" for s in states))
                self.assertLessEqual(len(calls), 2)  # at most the already-running wave for each model
            else:
                self.assertTrue(all(s["status"] == "complete" for s in states))
                self.assertEqual(len(calls), 24)  # two waves per stage, six stages, two models
                self.assertTrue(all(stage["usable"] == 3 for s in states for stage in s["stages"]))

    def test_bounded_waves_and_completed_resume(self):
        self.exercise()

    def test_failure_stops_batch_and_is_not_retried(self):
        self.exercise(fail=True)


if __name__ == "__main__":
    unittest.main()
