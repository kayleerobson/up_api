"""Turns the raw Up API pull (fetch_all.sh) into the data files the 2Up Money page reads.

usage: python3 -I tools/up_money/export.py WORK_DIR OUT_DIR
writes OUT_DIR/{transactions,categories,balances,tags}.json
"""
import glob
import json
import os
import re
import sys

WORK, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

acc = json.load(open(f"{WORK}/accounts.json"))["data"]
catdata = json.load(open(f"{WORK}/categories.json"))["data"]
cats = {c["id"]: c["attributes"]["name"] for c in catdata}


def clean(name):
    """Strips the leading emoji from saver names ("🎄 Christmas" -> "Christmas")."""
    return re.sub(r"^[^\w$]+", "", name).strip()


names = {a["id"]: clean(a["attributes"]["displayName"]) for a in acc}
joint = {a["id"] for a in acc if a["attributes"]["ownershipType"] == "JOINT"}
# Up names the person who made a 2Up transaction by their Up username.
WHO = {"$jaiwt": "Jai", "$kayleerobson1": "Kaylee"}

rows = []
for a in acc:
    if a["id"] not in joint:
        continue
    path = f"{WORK}/joint/{a['id']}.json"
    if not os.path.exists(path):
        continue
    for t in json.load(open(path)):
        at, r = t["attributes"], t["relationships"]
        ta = (r.get("transferAccount") or {}).get("data")
        tname = ""
        if ta:
            tname = names.get(ta["id"], "Another Up account")
            if ta["id"] not in joint and ta["id"] in names:
                tname += " (personal)"
        cat = (r["category"]["data"] or {}).get("id")
        par = (r["parentCategory"]["data"] or {}).get("id")
        pc = (at.get("performingCustomer") or {}).get("displayName")
        cpm = at.get("cardPurchaseMethod") or {}
        fa = at.get("foreignAmount")
        rows.append({
            "id": t["id"],
            "date": at["createdAt"][:10],
            "time": at["createdAt"][11:16],
            "month": at["createdAt"][:7],
            "account": names[a["id"]],
            "amount": round(at["amount"]["valueInBaseUnits"] / 100, 2),
            "type": at.get("transactionType") or "Pending",
            "description": at["description"].strip(),
            "reference": (at.get("message") or "").replace("\\n", "").strip(),
            "rawText": (at.get("rawText") or "").strip(),
            "status": at["status"].title(),
            "upCategory": cats.get(cat, "") if cat else "",
            "upParent": cats.get(par, "") if par else "",
            "categoryId": cat or "",
            "parentId": par or "",
            "isCategorizable": bool(at.get("isCategorizable")),
            "transferAccount": tname,
            "internal": bool(ta and ta["id"] in joint),
            "spentBy": WHO.get(pc, pc) if pc else "Not recorded",
            "method": "Card" if cpm else "",
            "tags": [x["id"] for x in (r.get("tags") or {}).get("data") or []],
            "cardMethod": (cpm.get("method") or "").replace("_", " ").title(),
            "foreign": f"{fa['value']} {fa['currencyCode']}" if fa else "",
        })
rows.sort(key=lambda x: (x["date"], x["time"], x["id"]), reverse=True)
json.dump(rows, open(f"{OUT}/transactions.json", "w"), ensure_ascii=False)

parents = sorted([c for c in catdata if not c["relationships"]["parent"]["data"]], key=lambda c: c["attributes"]["name"])
tree = []
for p in parents:
    kids = sorted([c for c in catdata if (c["relationships"]["parent"]["data"] or {}).get("id") == p["id"]], key=lambda c: c["attributes"]["name"])
    tree.append({"id": p["id"], "name": p["attributes"]["name"], "children": [{"id": k["id"], "name": k["attributes"]["name"]} for k in kids]})
json.dump(tree, open(f"{OUT}/categories.json", "w"), ensure_ascii=False)

balances = [{
    "account": names[a["id"]],
    "kind": "Saver" if a["attributes"]["accountType"] == "SAVER" else "Spending",
    "balance": float(a["attributes"]["balance"]["value"]),
    "opened": a["attributes"]["createdAt"][:10],
} for a in acc if a["id"] in joint]
json.dump(balances, open(f"{OUT}/balances.json", "w"), ensure_ascii=False)

tags = sorted(t["id"] for t in json.load(open(f"{WORK}/tags.json")))
json.dump(tags, open(f"{OUT}/tags.json", "w"), ensure_ascii=False)

print(f"{len(rows)} transactions, {sum(1 for r in rows if r['isCategorizable'] and not r['categoryId'])} still need a category, {len(tags)} tags")
