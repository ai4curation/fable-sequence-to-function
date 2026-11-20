"""Model-side measurements and weight writes. Needs torch and qwen2obo."""

import numpy as np
import torch
from qwen2obo.knowledge_update import LAYERS, ridge_right

from tasks import AA, HEADER, shuffled

HEAD_BOOST = 4.0


class SeqLM:
    """Reads a protein as one token per residue: the header, then " M", " K", ..."""

    def __init__(self, runner):
        self.runner = runner
        tok = runner.tokenizer
        self.header = tok.encode(HEADER, add_special_tokens=False)
        self.newline = tok.encode("\n", add_special_tokens=False)
        encoded = [tok.encode(" " + a, add_special_tokens=False) for a in AA]
        assert all(len(e) == 1 for e in encoded)
        self.aa = [e[0] for e in encoded]
        self.aa_tensor = torch.tensor(self.aa, device=runner.device)
        assert runner.model.lm_head.bias is None

    def ids(self, seq, context=None):
        """Token ids, and the index of the token that predicts residue 0."""
        own = self.header + [self.aa[AA.index(c)] for c in seq]
        if context is None:
            return own, len(self.header) - 1
        before = self.header + [self.aa[AA.index(c)] for c in context] + self.newline
        return before + own, len(before) + len(self.header) - 1

    @torch.inference_mode()
    def hidden(self, seq, context=None):
        """Final hidden states at the positions that predict residues 0..L-1."""
        ids, first = self.ids(seq, context)
        tokens = torch.tensor([ids], device=self.runner.device)
        h = self.runner.model.model(input_ids=tokens, use_cache=False).last_hidden_state[0]
        return h[first : first + len(seq)]

    @torch.inference_mode()
    def logp(self, seq, context=None, mass_at=()):
        """Log-probabilities over the 20 residues at every position, renormalised to sum to one.

        Also returns, for the positions in ``mass_at``, the share of the model's whole
        next-token distribution that falls on those 20 tokens.
        """
        h = self.hidden(seq, context)
        head = self.runner.model.lm_head.weight
        logp = (h @ head[self.aa_tensor].T).float().log_softmax(-1).cpu().numpy()
        mass = []
        if len(mass_at):
            full = self.runner.model.lm_head(h[list(mass_at)]).float().softmax(-1)
            mass = full[:, self.aa_tensor].sum(-1).cpu().tolist()
        assert np.isfinite(logp).all()
        return logp, mass


def evaluate(lm, rows, conditions=("real", "shuffled"), homologs=None):
    """Next-residue scores at the five cut points and over all positions after the first.

    With ``homologs`` (accession -> row), that family member is placed in context first.
    A shuffled sequence gets the unshuffled homolog, so only its own order is destroyed.
    """
    result = []
    for r in rows:
        for condition in conditions:
            seq = r["sequence"] if condition == "real" else shuffled(r["sequence"], r["accession"])
            context = homologs[r["accession"]]["sequence"] if homologs else None
            logp, mass = lm.logp(seq, context, mass_at=r["cuts"])
            truth = np.array([AA.index(c) for c in seq])
            pred = logp.argmax(-1)
            own = logp[np.arange(len(seq)), truth]
            result.append(
                {
                    "accession": r["accession"],
                    "pfam": r["pfam"],
                    "condition": condition,
                    "cuts": r["cuts"],
                    "target": "".join(seq[c] for c in r["cuts"]),
                    "pred": "".join(AA[pred[c]] for c in r["cuts"]),
                    "logp": [round(float(own[c]), 4) for c in r["cuts"]],
                    "aa_mass": [round(m, 4) for m in mass],
                    "all_n": len(seq) - 1,
                    "all_correct": int((pred[1:] == truth[1:]).sum()),
                    "all_logp": round(float(own[1:].sum()), 3),
                }
            )
    return result


def evaluate_raw(runner, rows, conditions=("real", "shuffled")):
    """The same cut points with the sequence written without spaces.

    The tokenizer then merges residues into multi-letter tokens, so the probability of
    the next residue is the summed probability of every token that starts with it.
    """
    tok = runner.tokenizer
    vocabulary = runner.model.lm_head.weight.shape[0]
    group = torch.full((vocabulary,), 20, dtype=torch.long)
    for i in range(min(vocabulary, len(tok))):
        text = tok.decode([i])
        if text and text[0] in AA:
            group[i] = AA.index(text[0])
    group = group.numpy()
    result = []
    with torch.inference_mode():
        for r in rows:
            for condition in conditions:
                seq = r["sequence"] if condition == "real" else shuffled(r["sequence"], r["accession"])
                pred, own, mass = "", [], []
                for c in r["cuts"]:
                    ids = tok.encode(HEADER + "\n" + seq[:c], add_special_tokens=False)
                    h = runner.model.model(
                        input_ids=torch.tensor([ids], device=runner.device), use_cache=False
                    ).last_hidden_state[0, -1]
                    p = runner.model.lm_head(h).float().softmax(-1).cpu().numpy()
                    by_letter = np.bincount(group, weights=p, minlength=21)[:20]
                    share = float(by_letter.sum())
                    by_letter = by_letter / by_letter.sum()
                    pred += AA[int(by_letter.argmax())]
                    own.append(round(float(np.log(by_letter[AA.index(seq[c])])), 4))
                    mass.append(round(share, 4))
                result.append(
                    {
                        "accession": r["accession"],
                        "pfam": r["pfam"],
                        "condition": condition,
                        "cuts": r["cuts"],
                        "target": "".join(seq[c] for c in r["cuts"]),
                        "pred": pred,
                        "logp": own,
                        "aa_mass": mass,
                    }
                )
    return result


def evaluate_substitutions(lm, items):
    """Does the model prefer the wild-type residue to the substituted one?

    ``site_margin`` uses only the residues before the site. ``sequence_margin`` is the
    log-likelihood of the whole wild-type sequence minus that of the substituted one.
    """
    result = []
    for s in items:
        t, wt, new = s["t"], AA.index(s["wt"]), AA.index(s["new"])
        mutant = s["sequence"][:t] + s["new"] + s["sequence"][t + 1 :]
        a, _ = lm.logp(s["sequence"])
        b, _ = lm.logp(mutant)
        index = np.arange(len(mutant))
        total_a = a[index, [AA.index(c) for c in s["sequence"]]][1:].sum()
        total_b = b[index, [AA.index(c) for c in mutant]][1:].sum()
        result.append(
            {
                **{k: s[k] for k in ["id", "accession", "group", "kind", "variant", "t", "wt", "new"]},
                "site_margin": round(float(a[t, wt] - a[t, new]), 4),
                "site_rank_wt": int((a[t] > a[t, wt]).sum()) + 1,
                "sequence_margin": round(float(total_a - total_b), 4),
            }
        )
    return result


def evaluate_features(runner, items, names):
    """Restricted-choice questions on the test 2 proteins: Pfam name, signal peptide, membrane."""
    result = []
    for item in items:
        for condition in ("real", "shuffled"):
            seq = item["sequence"] if condition == "real" else shuffled(item["sequence"], item["accession"])
            start = f"Protein sequence:\n{seq}\n"
            pfam = runner.score([start + "Pfam domain family:"], names)[0]
            lengths = [len(runner.tokenizer.encode(" " + n, add_special_tokens=False)) for n in names]
            signal = runner.score([start + "Signal peptide (yes or no):"], ["yes", "no"])[0]
            tm = runner.score([start + "Transmembrane helices (yes or no):"], ["yes", "no"])[0]
            result.append(
                {
                    "accession": item["accession"],
                    "condition": condition,
                    "pfam_logp": [round(float(x), 3) for x in pfam],
                    "pfam_tokens": lengths,
                    "signal_margin": round(float(signal[0] - signal[1]), 4),
                    "tm_margin": round(float(tm[0] - tm[1]), 4),
                }
            )
    return result


@torch.inference_mode()
def capture(lm, picks, by_accession, homologs=None):
    """MLP inputs, block outputs and final hidden states at the picked (accession, t) pairs."""
    runner = lm.runner
    wanted = {}
    for accession, t in picks:
        wanted.setdefault(accession, []).append(t)
    gathered = {f"{kind}-{layer}": [] for kind in ("key", "value") for layer in LAYERS}
    gathered["head"] = []
    current, handles = {}, []
    for layer in LAYERS:

        def pre(module, args, layer=layer):
            current[f"key-{layer}"] = args[0][0]

        def post(module, args, output, layer=layer):
            current[f"value-{layer}"] = (output[0] if isinstance(output, tuple) else output)[0]

        handles.append(runner.layers[layer].mlp.down_proj.register_forward_pre_hook(pre))
        handles.append(runner.layers[layer].register_forward_hook(post))
    try:
        for accession, positions in wanted.items():
            seq = by_accession[accession]["sequence"]
            context = homologs[accession]["sequence"] if homologs else None
            ids, first = lm.ids(seq, context)
            tokens = torch.tensor([ids], device=runner.device)
            final = runner.model.model(input_ids=tokens, use_cache=False).last_hidden_state[0]
            at = [first + t for t in positions]
            for name in current:
                gathered[name].append(current[name][at].float().cpu().numpy())
            gathered["head"].append(final[at].float().cpu().numpy())
    finally:
        for handle in handles:
            handle.remove()
    result = {name: np.concatenate(values) for name, values in gathered.items()}
    result["target"] = np.array(
        [AA.index(by_accession[a]["sequence"][t]) for a, ts in wanted.items() for t in ts]
    )
    return result


def fit_patches(lm, bare, donor, locality):
    """qwen2obo's two closed-form writes, fitted on protein positions.

    MLP write (layers 16 and 24): move the block output at each fitting position towards
    what it was with a family member in context. Output write: raise the logit of the true
    next residue by HEAD_BOOST on the 20 residue rows of the output matrix.
    """
    patches = []
    for layer in LAYERS:
        right = ridge_right(bare[f"key-{layer}"], locality[f"key-{layer}"])
        left = (donor[f"value-{layer}"] - bare[f"value-{layer}"]).T
        patches.append({"kind": "mlp", "layer": layer, "left": left, "right": right})
    desired = HEAD_BOOST * (bare["target"][:, None] == np.arange(20)[None, :]).astype(np.float32)
    right = ridge_right(bare["head"], locality["head"])
    patches.append({"kind": "head", "indices": np.array(lm.aa), "delta": desired.T @ right})
    return patches


def accuracy(scores, condition="real"):
    """Share of cut points whose top-ranked residue is the true one.

    >>> accuracy([{"condition": "real", "pred": "AC", "target": "AD"}])
    0.5
    """
    pairs = [(p, t) for s in scores if s["condition"] == condition for p, t in zip(s["pred"], s["target"])]
    return sum(p == t for p, t in pairs) / len(pairs)


def mean_logp(scores, condition="real"):
    values = [x for s in scores if s["condition"] == condition for x in s["logp"]]
    return float(np.mean(values))
