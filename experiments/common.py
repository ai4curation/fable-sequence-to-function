"""Shared rules for reading model replies and resuming runs. Imported by the ask/run and score scripts.

answer(text, keys)  The answer is the last complete JSON object in the reply that has at least one of the requested
                    keys (#50). A reply that contains a tool invocation instead of an answer has none (#49).
reparse(R, keys)    Apply answer() to stored rows, so the scorers read the reply text and not the `ans` stored at
                    run time. Returns the rows whose reply holds more than one such object.
resume(path, key)   Questions already answered. Rows recorded as errors are moved aside and asked again (#26).
"""
import hashlib, json, os, pathlib, re
_dec = json.JSONDecoder()
# The keys each test's prompt asks for; an answer object has at least one of them.
KEYS = {"features": "pfam_domains transmembrane_helices signal_peptide protein_name ec_number function".split(),
        "pseudo": "protein_name enzyme_family catalytic_residues substituted_or_missing catalytically_active ec_number reason".split(),
        "structure": "helices strands fold contacts protein_name function functional_residues recognised".split()}
# A fenced shell block or tool-call markup: the model wrote a tool invocation instead of answering.
TOOL_CALL = re.compile(r"```(?:bash|sh|shell|zsh|console)\b|<function_calls>|<invoke\b|\"type\"\s*:\s*\"tool_use\"")
def has_tool_call(text): return bool(TOOL_CALL.search(text or ""))
def json_objects(text, keys):
    """Complete JSON objects in the text that have at least one of `keys`, in order. Objects nested in one that
    parsed are not listed; the key test keeps the parts of a malformed object from being taken as an answer."""
    out, i, text = [], 0, text or ""
    while (i := text.find("{", i)) >= 0:
        try: obj, n = _dec.raw_decode(text[i:])
        except ValueError: i += 1; continue
        if isinstance(obj, dict) and any(k in obj for k in keys): out.append(obj)
        i += n
    return out
def answer(text, keys):
    if has_tool_call(text): return None
    objs = json_objects(text, keys)
    return objs[-1] if objs else None
def reparse(R, keys):
    multi = []
    for r in R:
        r["ans"] = answer(r.get("text"), keys)
        if len(json_objects(r.get("text"), keys)) > 1: multi.append(r)
    return multi
def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def resume(path, key):
    """Return the keys of the questions already answered in `path`. A row with an `error` field (the CLI gave no
    parseable output after three tries) is not an answer: such rows are appended to the same path under
    retried_errors/ in place of results/, removed from `path`, and the question is asked again."""
    path = pathlib.Path(path)
    if not path.exists(): return set()
    lines = [l for l in path.open() if l.strip()]; rows = [json.loads(l) for l in lines]
    bad = [l for l, r in zip(lines, rows) if "error" in r]
    if bad:
        parts = list(path.parts); parts[len(parts) - 1 - parts[::-1].index("results")] = "retried_errors"   # the last "results" folder
        side = pathlib.Path(*parts); side.parent.mkdir(parents=True, exist_ok=True)
        with side.open("a") as fh: fh.writelines(bad)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w") as fh: fh.writelines(l for l, r in zip(lines, rows) if "error" not in r)   # other rows byte for byte
        os.replace(tmp, path)
    return {key(r) for r in rows if "error" not in r}
