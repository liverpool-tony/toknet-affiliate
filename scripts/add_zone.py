#!/usr/bin/env python3
"""Add toknet.info as a Cloudflare zone via API"""
import os, json, subprocess

ENV_FILE = os.path.expanduser("~/.hermes/.env")
token = None
account = None
with open(ENV_FILE) as f:
    for line in f:
        line = line.strip()
        if line.startswith("CLOUDFLARE_API_TOKEN="):
            token = line.split("=", 1)[1]
        elif line.startswith("CLOUDFLARE_ACCOUNT_ID="):
            account = line.split("=", 1)[1]

print(f"Token: {token[:15]}...")
print(f"Account: {account}")

# Step 1: Create zone
url = "https://api.cloudflare.com/client/v4/zones"
data = {
    "name": "toknet.info",
    "account": {"id": account},
    "type": "full"
}
r = subprocess.run(
    ["curl", "-s", "-X", "POST", url,
     "-H", f"Authorization: Bearer {token}",
     "-H", "Content-Type: application/json",
     "-d", json.dumps(data)],
    capture_output=True, text=True
)
result = json.loads(r.stdout)
print("Zone create:", json.dumps(result, indent=2, ensure_ascii=False)[:1500])
