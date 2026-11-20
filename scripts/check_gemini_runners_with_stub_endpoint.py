"""Run the Gemini API runners against a stub endpoint and check what they record. Calls no model.

Purpose: show that call_vertex (run_vertex.py) and call_gemini_api (run_api.py) store Google's
response ID, create time, model version and the full response metadata (minus reply text) with
each row, for an answer, a safety block with no candidates, and an HTTP error (#155); and that
audit.py's metadata checks pass on such a row and fail when it is altered.
Inputs: none (the stub replaces urllib.request.urlopen and the gcloud token).
Outputs: one "ok"/"FAIL" line per check; exit 1 on any failure.
PR: #155 follow-up on the #115 branch, 2026-11-19.
"""
import copy
import email.message
import io
import json
import pathlib
import sys
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "gemini_experiment"))
import run_api  # noqa: E402
import run_vertex  # noqa: E402

FAILS = 0


def check(cond, what):
    global FAILS
    print(("ok   " if cond else "FAIL ") + what)
    FAILS += not cond


class Resp:
    def __init__(self, body, headers):
        self._b = json.dumps(body).encode()
        self.headers = headers

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


ANSWER = {
    "candidates": [{
        "content": {"role": "model", "parts": [
            {"text": "thinking about it", "thought": True, "thoughtSignature": "c2lnbmF0dXJl"},
            {"text": "MKVLAAGIVG"},
        ]},
        "finishReason": "STOP",
        "safetyRatings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "probability": "NEGLIGIBLE"}],
        "avgLogprobs": -0.5,
    }],
    "usageMetadata": {"promptTokenCount": 150, "candidatesTokenCount": 10, "thoughtsTokenCount": 40,
                      "totalTokenCount": 200, "trafficType": "ON_DEMAND"},
    "modelVersion": "gemini-4-neon",
    "createTime": "2026-11-19T16:27:29.123456Z",
    "responseId": "stub-response-id-1",
}
BLOCKED = {"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": {"promptTokenCount": 150},
           "modelVersion": "gemini-4-neon", "createTime": "2026-11-19T16:30:00Z", "responseId": "stub-response-id-2"}
HEADERS = email.message.Message()  # what urllib's resp.headers is; repeated names are possible
for k, v in (("Content-Type", "application/json; charset=UTF-8"), ("Vary", "Origin"), ("Vary", "X-Origin"),
             ("Server-Timing", "gfet4t7; dur=812"), ("Set-Cookie", "should-not-be-kept")):
    HEADERS[k] = v


def run(call, body=None, http_error=None):
    def urlopen(req, timeout=None):
        if http_error:
            raise urllib.error.HTTPError(req.full_url, http_error, "stub", {}, io.BytesIO(b'{"error": "stub"}'))
        return Resp(body, HEADERS)
    run_api.urllib.request.urlopen = urlopen
    run_vertex.urllib.request.urlopen = urlopen
    run_api.time.sleep = run_vertex.time.sleep = lambda s: None
    return call()


run_vertex.get_token = lambda force=False: "stub-token"
run_api.os.environ.setdefault("GEMINI_API_KEY", "stub-key")
callers = {
    "run_vertex": lambda: run_vertex.call_vertex("stub-project", "gemini-4-neon", "low", "PROMPT", tries=2),
    "run_api": lambda: run_api.call_gemini_api("gemini-4-neon", "low", "PROMPT", tries=2),
}
for name, call in callers.items():
    text, rec = run(call, ANSWER)
    m = rec.get("response_metadata") or {}
    check(text == "MKVLAAGIVG", f"{name}: reply text is the visible part only")
    check(rec.get("response_id") == "stub-response-id-1", f"{name}: response id recorded")
    check(rec.get("create_time") == "2026-11-19T16:27:29.123456Z", f"{name}: create time recorded")
    check(rec.get("model_version") == "gemini-4-neon", f"{name}: model version recorded")
    check(m.get("usageMetadata", {}).get("trafficType") == "ON_DEMAND", f"{name}: full usage metadata kept")
    c = (m.get("candidates") or [{}])[0]
    check(c.get("safetyRatings") and c.get("avgLogprobs") == -0.5, f"{name}: candidate metadata kept")
    parts = c.get("content", {}).get("parts", [])
    check(all("text" not in q and "thoughtSignature" not in q for q in parts)
          and [q.get("text_chars") for q in parts] == [17, 10] and parts[0].get("thought_signature_chars") == 12,
          f"{name}: part texts and signature dropped, their lengths kept")
    h = m.get("http_headers", [])
    check([v for k, v in h if k == "Vary"] == ["Origin", "X-Origin"] and not any(k.lower() == "set-cookie" for k, _ in h)
          and ["Server-Timing", "gfet4t7; dur=812"] in h, f"{name}: response headers kept, repeats too, without cookies")
    check(json.loads(json.dumps(rec)) == rec, f"{name}: row is JSON-serialisable")

    text, rec = run(call, BLOCKED)
    check(text is None and "SAFETY" in rec.get("error", ""), f"{name}: safety block is an error row")
    check(rec.get("response_id") == "stub-response-id-2" and rec.get("response_metadata", {}).get("promptFeedback"),
          f"{name}: safety block keeps response id and prompt feedback")

    text, rec = run(call, http_error=400)
    check(text is None and rec.get("error", "").startswith("HTTP 400") and "response_metadata" not in rec,
          f"{name}: HTTP error row has the error and no metadata")

# Reply content outside part text is stripped too, and absent fields are not invented (#157).
from run_agy import response_metadata  # noqa: E402

m = response_metadata({"candidates": [
    {"finishReason": "SAFETY"},
    {"content": {"parts": [{"functionCall": {"name": "f", "args": {"q": "SECRET-REPLY"}}},
                           {"functionResponse": {"name": "f", "response": {"r": "SECRET-REPLY"}}},
                           {"executableCode": {"code": "SECRET-REPLY"}},
                           {"codeExecutionResult": {"output": "SECRET-REPLY"}},
                           {"inlineData": {"mimeType": "text/plain", "data": "SECRET-REPLY"}},
                           {"fileData": {"fileUri": "gs://SECRET-REPLY"}}]},
     "groundingMetadata": {"groundingSupports": [{"segment": {"text": "SECRET-REPLY"}}]},
     "groundingAttributions": [{"content": {"parts": [{"text": "SECRET-REPLY"}]}}],
     "logprobsResult": {"chosenCandidates": [{"token": "SECRET-REPLY"}]}},
    {"content": "SECRET-REPLY"},
]})
check("SECRET-REPLY" not in json.dumps(m), "response_metadata: every named content field, and non-object content, stripped")
check(m["candidates"][0] == {"finishReason": "SAFETY"}, "response_metadata: a candidate without content gets none")
check("functionCall_json_chars" in m["candidates"][1]["content"]["parts"][0]
      and "groundingMetadata_json_chars" in m["candidates"][1], "response_metadata: stripped fields leave their size")
check("candidates" not in response_metadata({"promptFeedback": {}}), "response_metadata: no candidates key invented")

# The audit's new checks, on a row like the one run_vertex writes.
import audit  # noqa: E402

text, rec = run(callers["run_vertex"], ANSWER)
row = dict(rec, text=text)


check(audit.metadata_problem(row) is None, "audit.metadata_problem: an unaltered row passes")
for field, value in (("response_id", "other"), ("model_version", "gemini-other"), ("finish_reason", "MAX_TOKENS"), ("text", "MKV")):
    bad = copy.deepcopy(row)
    bad[field] = value
    check(audit.metadata_problem(bad) is not None, f"audit.metadata_problem: altered {field} fails")

empty = copy.deepcopy(row)
empty["response_metadata"]["candidates"] = []
check(audit.metadata_problem(empty) == "stored metadata has no candidate", "audit.metadata_problem: empty candidates is a message, not a crash")

sys.exit(1 if FAILS else 0)
