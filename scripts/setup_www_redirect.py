#!/usr/bin/env python3
import json, os, subprocess, sys

ENV = os.path.expanduser("~/.hermes/.env")
token = None
with open(ENV) as f:
    for line in f:
        line = line.strip()
        if line.startswith("CLOUDFLARE_API_TOKEN=") and "ACCOUNT" not in line:
            token = line.split("=", 1)[1]

def cf(path, method="GET", body=None):
    cmd = [
        "curl", "-s", "-X", method,
        f"https://api.cloudflare.com/client/v4{path}",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
    ]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout or "{}")

if not token:
    print("NO_TOKEN")
    sys.exit(1)

zones = cf("/zones?name=toknet.info").get("result", [])
if not zones:
    print("NO_ZONE")
    sys.exit(1)
zid = zones[0]["id"]
print("zone_id", zid)

# Check existing dynamic redirect ruleset
rulesets = cf(f"/zones/{zid}/rulesets").get("result", [])
redirect_rs = None
for rs in rulesets:
    if rs.get("phase") == "http_request_dynamic_redirect":
        redirect_rs = rs
        break

rule_body = {
    "description": "www to apex toknet.info",
    "rules": [
        {
            "description": "Redirect www.toknet.info to toknet.info",
            "expression": '(http.host eq "www.toknet.info")',
            "action": "redirect",
            "action_parameters": {
                "from_value": {
                    "status_code": 301,
                    "target_url": {
                        "expression": 'concat("https://toknet.info", http.request.uri.path)',
                    },
                    "preserve_query_string": True,
                }
            },
        }
    ],
}

if redirect_rs:
    rs_id = redirect_rs["id"]
    detail = cf(f"/zones/{zid}/rulesets/{rs_id}")
    existing = detail.get("result", {}).get("rules", [])
    for rule in existing:
        if rule.get("description") == "Redirect www.toknet.info to toknet.info":
            print("RULE_EXISTS")
            sys.exit(0)
    # append rule via ruleset update - need full rules list
    new_rules = existing + rule_body["rules"]
    payload = {"rules": new_rules}
    out = cf(f"/zones/{zid}/rulesets/{rs_id}", "PUT", payload)
else:
    payload = {
        "name": "www to apex redirect",
        "kind": "zone",
        "phase": "http_request_dynamic_redirect",
        **rule_body,
    }
    out = cf(f"/zones/{zid}/rulesets", "POST", payload)

if out.get("success"):
    print("REDIRECT_OK")
else:
    print("REDIRECT_FAIL", json.dumps(out, ensure_ascii=False)[:2000])
    sys.exit(1)