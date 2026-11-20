"""CLI tests that need no model weights."""

import json
import pathlib
import sys

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import cli  # noqa: E402
import tasks  # noqa: E402

runner = CliRunner()


def test_prepare_reproduces_the_committed_protocol(tmp_path):
    result = runner.invoke(cli.app, ["prepare", "--folder", str(tmp_path)])
    assert result.exit_code == 0, result.output
    for name in ("protocol.json", "splits.json", "controls.json"):
        assert (tmp_path / name).read_text() == (cli.HERE / name).read_text()


@pytest.mark.parametrize("command", ["prepare", "baseline", "edit"])
def test_help(command):
    result = runner.invoke(cli.app, [command, "--help"])
    assert result.exit_code == 0


def test_controls_are_split():
    controls = json.loads((cli.HERE / "controls.json").read_text())
    assert {c["split"] for c in controls} == {"calibration_control", "test_control"}
    assert len({c["prompt"] for c in controls}) == len(controls)


def test_fitting_proteins_are_never_scored():
    rows = tasks.load_sequences()
    splits = tasks.assign_splits(rows)
    fit = {a for a, _ in tasks.fit_positions(rows, splits)}
    assert all(splits[a] == "fit" for a in fit)
    families = lambda split: {r["pfam"] for r in rows if splits[r["accession"]] == split}
    assert not families("test_unseen") & families("fit")
    assert families("test_seen") == families("fit") == families("validation")


@pytest.mark.parametrize("kind,expected", [("catalytic", 60), ("decoy", 58)])
def test_substitution_changes_one_residue(kind, expected):
    subs = [s for s in tasks.substitutions() if s["kind"] == kind]
    assert len(subs) == expected
    assert all(s["wt"] != s["new"] and s["sequence"][s["t"]] == s["wt"] for s in subs)
