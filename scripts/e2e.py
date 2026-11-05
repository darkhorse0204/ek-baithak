"""End-to-end journey through the HTTP API (server must be running on :8000)."""
import json, sys, time, urllib.request
B = "http://localhost:8000"
def call(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(B + path, data=data, method=method or ("POST" if data is not None else "GET"), headers={"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    return out, time.time() - t
lang = sys.argv[1] if len(sys.argv) > 1 else "en"
first = sys.argv[2] if len(sys.argv) > 2 else "I run a dental clinic in Kochi with 12 staff. We want 1 Gbps internet, appointment SMS reminders and data backup."
s, _ = call("/api/advisor/start", {"lang": lang})
sid = s["session"]; print("BOT:", s["reply"][:120])
msgs = [first]
for i in range(8):
    text = msgs.pop(0) if msgs else None
    if text is None:
        break
    r, dt = call("/api/advisor/message", {"session": sid, "text": text})
    print(f"\nYOU: {text}\nBOT ({r.get('model')}, {dt:.1f}s): {r['reply'][:700]}")
    if r.get("ask") == "sites": msgs.append("1 site")
    elif r.get("ask") == "gstin": msgs.append("__no_gstin__" if "no gst" in first.lower() else "27PZSXS1936O1ZH")
    elif r.get("ask") == "needs": msgs.append("__needs__:" + ",".join(o["tag"] for o in r["needs"]["options"] if o["checked"]))
    elif r.get("ask") == "city": msgs.append("Kochi")
    elif r.get("ask") == "employees": msgs.append("12 people")
    elif r.get("ask") == "business_type": msgs.append("Dental clinic")
    if r.get("reco"):
        rc = r["reco"]; print("PLAN ₹", rc["monthly"], [(l["product_id"], l["qty"]) for l in rc["lines"]], "EXCL", [(e["product_id"], e["alternative"]) for e in rc["excluded"]])
        break
q, _ = call("/api/advisor/quote", {"session": sid, "term": 24}); print("24m price ₹", q["reco"]["monthly"])
c, _ = call("/api/consent", {"session": sid, "purposes": {"kyc": True, "registry": True, "updates": True, "partner": True, "marketing": False}}); print("consent", c["ok"], c["consent"]["id"])
k, dt = call(f"/api/kyc/sample/K03?session={sid}", method="POST"); print("KYC K03", k["verdict"], f"{dt:.1f}s")
o, _ = call("/api/order", {"session": sid}); print("order", o["id"], o["status"])
o, _ = call(f"/api/order/{o['id']}/esign", {"signer": "Joseph Singh"}); o, _ = call(f"/api/order/{o['id']}/pay", method="POST")
for d in range(6):
    o, _ = call(f"/api/order/{o['id']}/advance?days=1", method="POST")
print("status", o["status"], "progress", o["eta"]["progress"]); [print("  WA:", n["text"][:110]) for n in o["notifications"]]
m, _ = call(f"/api/mydata/{sid}"); print("mydata keys", list(m), "images_stored", m["kyc"]["images_stored"])
