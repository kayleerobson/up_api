"""Applies the category and tag changes queued on the 2Up Money page to Up.

The page stores one document per transaction in its database collections
`changes` ({txId, to, status}) and `tagChanges` ({txId, add, status}).
Save both collections as JSON files (ArtifactData list with out_dir), then:

usage: python3 -I tools/up_money/apply_changes.py CHANGES_DIR TAGCHANGES_DIR RESULTS_JSON

Only documents with status "pending" are applied. RESULTS_JSON maps each
transaction id to {ok, error} under "categories" and "tags"; use it to set
each document's status to "applied" or "failed" (with the error).
Needs UP_API_TOKEN in the environment.
"""
import glob
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ["UP_API_TOKEN"]
BASE = "https://api.up.com.au/api/v1/transactions/"


def call(method, url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method=method,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status == 204, None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = "; ".join(x.get("detail", "") for x in json.loads(detail).get("errors", [])) or detail
        except Exception:
            pass
        return False, f"HTTP {e.code}: {detail}"[:300]


def pending(folder):
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        doc = json.load(open(path))
        data = doc.get("data", doc) if isinstance(doc.get("data"), dict) else doc
        if data.get("status") == "pending":
            yield data


results = {"categories": {}, "tags": {}}
for d in pending(sys.argv[1]):
    to = d.get("to")
    ok, err = call("PATCH", BASE + d["txId"] + "/relationships/category",
                   {"data": {"type": "categories", "id": to} if to else None})
    results["categories"][d["txId"]] = {"ok": ok, "error": err}
for d in pending(sys.argv[2]):
    tags = [{"type": "tags", "id": t} for t in d.get("add", [])]
    ok, err = call("POST", BASE + d["txId"] + "/relationships/tags", {"data": tags}) if tags else (True, None)
    results["tags"][d["txId"]] = {"ok": ok, "error": err}

json.dump(results, open(sys.argv[3], "w"), indent=1)
for kind, res in results.items():
    print(kind, sum(r["ok"] for r in res.values()), "applied,", sum(not r["ok"] for r in res.values()), "failed")
