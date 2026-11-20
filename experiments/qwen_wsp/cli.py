"""Sequence tests of Qwen3-1.7B-Base and closed-form weight writes. Run `cli.py --help`."""

import hashlib
import json
import pathlib
import time

import typer

import tasks

HERE = pathlib.Path(__file__).parent
app = typer.Typer(no_args_is_help=True, help=__doc__)
Out = typer.Option(None, help="Folder for result files. Default: results/MODEL-NAME.")
Model = typer.Option("Qwen/Qwen3-1.7B-Base", help="A model listed in data/model_revisions.json.")
Limit = typer.Option(0, help="Use only this many proteins per split (a canary run; never for reported numbers).")

PROTOCOL = {
    "question": "Does Qwen3-1.7B-Base read protein sequences at all, and do qwen2obo's closed-form weight writes improve next-residue prediction on held-out proteins?",
    "model": "Qwen/Qwen3-1.7B-Base at the revision in data/model_revisions.json, float16 on MPS, no sampling.",
    "code": "qwen2obo at c4eb160 supplies the model runner, ridge solution, weight application and restoration, random edits and control scoring.",
    "input": f"Header '{tasks.HEADER}' followed by one token per residue (' M', ' K', ...). Scores are the 20 residue tokens renormalised to sum to one; the share of the full distribution on those tokens is recorded at cut points.",
    "baseline": {
        "next_residue": "All 668 proteins and their shuffled copies (upstream seed), top-ranked residue at the 3,340 cut points; also every position after the first. Secondary: the same cut points with the sequence written without spaces, residue probability summed over tokens starting with that letter.",
        "substitutions": "60 catalytic-residue substitutions of test 3 and the 58 decoy substitutions: log-probability of the wild-type residue minus the substituted residue at the site (left context only), and whole-sequence log-likelihood difference.",
        "features": "60 proteins of test 2 and shuffled copies, unspaced sequence: rank of the true Pfam name among the 66 names in the set (summed and per-token log-probability), yes-minus-no margin for signal peptide and for transmembrane helices.",
    },
    "splits": f"Seed {tasks.SEED}. 100 seen families: two fitting members, one validation, one test. 67 unseen families: all four members test only.",
    "fitting": f"{tasks.MAX_KEYS} evenly spaced positions inside the Pfam domain of the 200 fitting proteins. MLP write at zero-based layer 16 or 24: keys are the gated MLP activations, written values are block output with the other fitting member of the family in context minus block output without it. Output write: +4 logits for the true next residue on the 20 residue rows of a cloned output matrix. Ridge 0.001 times mean squared key norm; 256 locality keys from the calibration controls, weighted sqrt(10), with zero requested change. No gradients.",
    "grid": {"mlp_layers": [16, 24], "strengths": [0.25, 0.5, 1.0, 2.0, 4.0]},
    "selection": "Validation proteins and calibration controls only. Eligible: no calibration-control answer changes and mean absolute per-token correct-answer log-probability drift at most 0.5. Per write kind choose the highest validation cut-point accuracy on real sequences, then the smallest strength, then the highest mean log-probability of the true residue. If nothing eligible beats the unedited model, select no edit. The selection file is written before any test protein is scored with an edit.",
    "test": "Test members of seen families (100) and all members of unseen families (268), real and shuffled; the substitution items; qwen2obo's held-out controls with greedy completions. Conditions: unedited, homolog in context, each selected write, its reverse, and three matched-norm random writes (seeds 42 to 44).",
    "reading": "A gain on real sequences that also appears on shuffled sequences is residue composition, not sequence reading. A gain limited to seen families is family memorisation. Only a gain on unseen families beyond the shuffled gain would count as improved sequence reading. All conditions are reported, including failures.",
    "controls": "Calibration and held-out controls are the questions of qwen2obo's knowledge-update experiment (controls.json).",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def frozen():
    """Splits, homologs, fitting positions and controls, as written by `prepare`."""
    rows = tasks.load_sequences()
    splits = json.loads((HERE / "splits.json").read_text())
    assert splits["splits"] == tasks.assign_splits(rows)
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["splits_sha256"] == digest(HERE / "splits.json")
    assert protocol["controls_sha256"] == digest(HERE / "controls.json")
    return rows, splits, json.loads((HERE / "controls.json").read_text())


def load_model(model):
    import qwen2obo.model
    import torch

    import lm

    qwen2obo.model.MODEL = model  # the runner reads its model name, and that model's pinned revision, from here
    runner = qwen2obo.model.Runner(HERE)
    tied = runner.model.lm_head.weight.data_ptr() == runner.model.model.embed_tokens.weight.data_ptr()
    if tied:  # as in qwen2obo: an identical copy, so output writes leave the input embeddings alone
        runner.model.lm_head.weight = torch.nn.Parameter(
            runner.model.lm_head.weight.detach().clone(), requires_grad=False
        )
    return runner, lm.SeqLM(runner), {"model": model, "model_revision": runner.revision, "device": runner.device, "head_was_tied": tied}


@app.command()
def prepare(folder: pathlib.Path = typer.Option(HERE, help="Where to write the protocol files.")):
    """Write the protocol, splits and controls. Run once, before any model call."""
    from qwen2obo.knowledge_data import CASES, records

    rows = tasks.load_sequences()
    splits = tasks.assign_splits(rows)
    controls = {}
    for case in CASES:
        for r in records(case):
            if r["split"] in ("calibration_control", "test_control"):
                controls.setdefault(r["prompt"], {**r, "id": f"control-{len(controls)}"})
    (folder / "splits.json").write_text(
        json.dumps({"splits": splits, "homologs": tasks.assign_homologs(rows, splits)}, indent=1) + "\n"
    )
    (folder / "controls.json").write_text(json.dumps(list(controls.values()), indent=1) + "\n")
    protocol = {
        **PROTOCOL,
        "splits_sha256": digest(folder / "splits.json"),
        "controls_sha256": digest(folder / "controls.json"),
    }
    (folder / "protocol.json").write_text(json.dumps(protocol, indent=1) + "\n")
    typer.echo(f"Prepared {len(splits)} proteins and {len(controls)} controls in {folder}")


@app.command()
def baseline(model: str = Model, out: pathlib.Path = Out, limit: int = Limit):
    """Score the unedited model on every sequence test."""
    import lm

    rows, _, _ = frozen()
    out = out or HERE / "results" / model.split("/")[-1]
    started = time.perf_counter()
    runner, seqlm, manifest = load_model(model)
    out.mkdir(parents=True, exist_ok=True)
    subs = tasks.substitutions()
    items, names = tasks.feature_items()
    if limit:
        rows, subs, items = rows[:limit], subs[:limit], items[:limit]
    write_jsonl(out / "baseline_next_residue.jsonl", lm.evaluate(seqlm, rows))
    typer.echo(f"next residue done {time.perf_counter() - started:.0f}s")
    write_jsonl(out / "baseline_substitutions.jsonl", lm.evaluate_substitutions(seqlm, subs))
    typer.echo(f"substitutions done {time.perf_counter() - started:.0f}s")
    write_jsonl(out / "baseline_raw.jsonl", lm.evaluate_raw(runner, rows))
    typer.echo(f"unspaced next residue done {time.perf_counter() - started:.0f}s")
    features = {"names": names, "items": lm.evaluate_features(runner, items, names)}
    (out / "baseline_features.json").write_text(json.dumps(features) + "\n")
    manifest.update(protocol_sha256=digest(HERE / "protocol.json"), seconds=round(time.perf_counter() - started), limit=limit)
    (out / "baseline_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")


def choose(calibration, kind, baseline_accuracy):
    """Pick one write of a kind by the frozen rule, or no edit.

    >>> c = [{"kind": "head", "eligible": True, "strength": s, "validation_accuracy": a, "validation_logp": -2.0, "patch_index": 2}
    ...      for s, a in [(0.5, 0.2), (1.0, 0.3), (2.0, 0.3)]]
    >>> choose(c, "head", 0.1)["strength"], choose(c, "head", 0.3)["strength"], choose(c, "mlp", 0.1)["strength"]
    (1.0, 0.0, 0.0)
    """
    better = [c for c in calibration if c["kind"] == kind and c["eligible"] and c["validation_accuracy"] > baseline_accuracy]
    if not better:
        return {"kind": kind, "strength": 0.0, "reason": "No eligible write beat the unedited model on validation."}
    best = min(better, key=lambda c: (-c["validation_accuracy"], c["strength"], -c["validation_logp"]))
    return {"kind": kind, "strength": best["strength"], "patch_index": best["patch_index"], "layer": best.get("layer")}


@app.command()
def edit(model: str = Model, out: pathlib.Path = Out, limit: int = Limit):
    """Fit the weight writes, select on validation, then score the test proteins."""
    import numpy as np
    from qwen2obo.knowledge_update import apply, randomize
    from qwen2obo.knowledge_update import capture as capture_controls
    from qwen2obo.knowledge_update import score as score_controls
    from qwen2obo.knowledge_update import summarize

    import lm

    rows, frozen_splits, controls = frozen()
    out = out or HERE / "results" / model.split("/")[-1]
    splits = frozen_splits["splits"]
    by_accession = {r["accession"]: r for r in rows}
    homologs = {a: by_accession[h] for a, h in frozen_splits["homologs"].items()}
    picks = tasks.fit_positions(rows, splits)
    validation = [r for r in rows if splits[r["accession"]] == "validation"]
    test = [r for r in rows if splits[r["accession"]].startswith("test")]
    subs = tasks.substitutions()
    if limit:
        validation, test, subs, picks = validation[:limit], test[:limit] + test[-limit:], subs[:limit], picks[: 20 * limit]
    calibration_controls = [c for c in controls if c["split"] == "calibration_control"]
    test_controls = [c for c in controls if c["split"] == "test_control"]
    started = time.perf_counter()
    runner, seqlm, manifest = load_model(model)
    out.mkdir(parents=True, exist_ok=True)
    local = out / "local"  # weight patches: large, kept out of git
    local.mkdir(exist_ok=True)

    base_validation = lm.evaluate(seqlm, validation, conditions=("real",))
    base_controls = score_controls(runner, calibration_controls)
    base_accuracy = lm.accuracy(base_validation)
    patches = lm.fit_patches(
        seqlm,
        lm.capture(seqlm, picks, by_accession),
        lm.capture(seqlm, picks, by_accession, homologs),
        capture_controls(runner, calibration_controls, all_positions=True),
    )
    typer.echo(f"fitted {len(picks)} keys {time.perf_counter() - started:.0f}s")
    calibration = []
    for i, patch in enumerate(patches):
        for strength in PROTOCOL["grid"]["strengths"]:
            with apply(runner, patch, strength) as metadata:
                scores = lm.evaluate(seqlm, validation, conditions=("real",))
                control = summarize(score_controls(runner, calibration_controls), base_controls)["calibration_control"]
            calibration.append(
                {
                    **metadata,
                    "patch_index": i,
                    "validation_accuracy": lm.accuracy(scores),
                    "validation_logp": lm.mean_logp(scores),
                    "control": control,
                    "eligible": control["prediction_flips"] == 0 and control["mean_abs_target_logp_drift"] <= 0.5,
                }
            )
            typer.echo(f"{patch['kind']} {patch.get('layer')} x{strength}: validation {calibration[-1]['validation_accuracy']:.3f} eligible {calibration[-1]['eligible']}")
    selected = [choose(calibration, kind, base_accuracy) for kind in ("mlp", "head")]
    # Written before any test protein is scored with an edit.
    selection = {
        "baseline_validation_accuracy": base_accuracy,
        "baseline_validation_logp": lm.mean_logp(base_validation),
        "fit_keys": len(picks),
        "calibration": calibration,
        "selected": selected,
    }
    (out / "edit_selection.json").write_text(json.dumps(selection, indent=1) + "\n")

    base_test_controls = score_controls(runner, test_controls)

    def measure(name, context=None, generate=False, edit=None):
        record = {
            "name": name,
            "edit": edit,
            "next_residue": lm.evaluate(seqlm, test, homologs=context),
            "substitutions": [] if context else lm.evaluate_substitutions(seqlm, subs),
            "controls": summarize(score_controls(runner, test_controls), base_test_controls)["test_control"],
            "generations": [
                {"prompt": c["prompt"], "expected": c["answers"][0], "completion": runner.generate(c["prompt"], max_new_tokens=32)}
                for c in (test_controls if generate else [])
            ],
        }
        typer.echo(f"{name} done {time.perf_counter() - started:.0f}s")
        return record

    conditions = [measure("baseline", generate=True), measure("homolog_in_context", context=homologs)]
    for choice in selected:
        if choice["strength"] == 0:
            continue
        patch, kind, strength = patches[choice["patch_index"]], choice["kind"], choice["strength"]
        np.savez_compressed(
            local / f"{kind}-patch.npz",
            **{k: v for k, v in patch.items() if isinstance(v, np.ndarray)},
            strength=np.array(strength),
            layer=np.array(patch.get("layer", -1)),
        )
        variants = [(kind, patch, strength), (f"{kind}-reverse", patch, -strength)]
        variants += [(f"{kind}-random-{seed}", randomize(patch, seed), strength) for seed in (42, 43, 44)]
        for name, variant, amount in variants:
            with apply(runner, variant, amount) as metadata:
                conditions.append(measure(name, generate=name == kind, edit=metadata))
    write_jsonl(out / "edit_results.jsonl", conditions)
    manifest.update(protocol_sha256=digest(HERE / "protocol.json"), seconds=round(time.perf_counter() - started), limit=limit)
    (out / "edit_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    app()
