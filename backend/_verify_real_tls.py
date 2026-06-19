"""Drive a sweep against the running server (real TLS mode) and show that the
tls-lb-01 assessment carries the LIVE cert expiry, not the simulated value."""
import json
import time
import urllib.request

API = "http://localhost:8000"


def post(path):
    req = urllib.request.Request(API + path, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=10))


def get(path):
    return json.load(urllib.request.urlopen(API + path, timeout=10))


run_id = post("/api/runs")["run_id"]
print("run_id:", run_id)

for _ in range(20):
    events = get(f"/api/runs/{run_id}/audit")["events"]
    disc = [e for e in events if e["type"] == "node_update" and e.get("node") == "discover"]
    a = [e for e in events if e["type"] == "assessment_item" and e.get("cred_id") == "tls-lb-01"]
    if a:
        print("\n-- discover messages --")
        for e in disc:
            print("  ", e["message"])
        print("\n-- tls-lb-01 assessment --")
        ev = a[0]
        print("   expiry_source:", ev.get("expiry_source"))
        print("   not_after:    ", ev.get("not_after"))
        print("   days_to_expiry:", ev.get("days_to_expiry"), "| expired:", ev.get("expired"))
        break
    time.sleep(1)
else:
    print("assessment not seen in time")
