#!/usr/bin/env python3
"""Cloudflare API helper - reads credentials from Hermes .env"""
import os
import sys
import json
import subprocess

ENV_FILE = os.path.expanduser("~/.hermes/.env")

def get_creds():
    token = None
    account = None
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                token = line.split("=", 1)[1]
            elif line.startswith("CLOUDFLARE_ACCOUNT_ID="):
                account = line.split("=", 1)[1]
    if not token or not account:
        print("ERROR: Missing Cloudflare credentials in ~/.hermes/.env")
        sys.exit(1)
    return token, account

def api_get(path):
    token, account = get_creds()
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}{path}"
    r = subprocess.run(
        ["curl", "-s", url, "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True
    )
    return json.loads(r.stdout)

def api_post(path, data):
    token, account = get_creds()
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}{path}"
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", url,
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(data)],
        capture_output=True, text=True
    )
    return json.loads(r.stdout)

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    
    if action == "add-domain":
        domain = sys.argv[2]
        result = api_post("/pages/projects/toknet-affiliate/domains", {"domain": domain})
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif action == "list-domains":
        result = api_get("/pages/projects/toknet-affiliate/domains")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif action == "list-projects":
        token, account = get_creds()
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects"
        r = subprocess.run(
            ["curl", "-s", url, "-H", f"Authorization: Bearer {token}"],
            capture_output=True, text=True
        )
        print(json.dumps(json.loads(r.stdout), indent=2, ensure_ascii=False))
    
    else:
        print("Usage: cf_api.py [add-domain|list-domains|list-projects] [args]")
