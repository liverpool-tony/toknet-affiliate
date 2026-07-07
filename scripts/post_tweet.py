#!/usr/bin/env python3
"""
X (Twitter) API v2 - Post tweet using OAuth 1.0a
Reads credentials from ~/.hermes/.env
"""
import os
import sys
import json
import hashlib
import hmac
import base64
import time
import urllib.parse
import urllib.request
import ssl

ENV_FILE = os.path.expanduser("~/.hermes/.env")

def get_x_creds():
    """Read X API credentials from Hermes .env"""
    creds = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("X_API_KEY="):
                creds["api_key"] = line.split("=", 1)[1]
            elif line.startswith("X_API_SECRET="):
                creds["api_secret"] = line.split("=", 1)[1]
            elif line.startswith("X_ACCESS_TOKEN="):
                creds["access_token"] = line.split("=", 1)[1]
            elif line.startswith("X_ACCESS_TOKEN_SECRET="):
                creds["access_token_secret"] = line.split("=", 1)[1]
    return creds

def oauth1_sign(method, url, params, api_key, api_secret, access_token, access_token_secret):
    """Generate OAuth 1.0a signature"""
    # Collect all parameters
    all_params = {}
    all_params["oauth_consumer_key"] = api_key
    all_params["oauth_nonce"] = hashlib.md5(f"{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()
    all_params["oauth_signature_method"] = "HMAC-SHA1"
    all_params["oauth_timestamp"] = str(int(time.time()))
    all_params["oauth_token"] = access_token
    all_params["oauth_version"] = "1.0"
    
    # Add query params from URL
    parsed = urllib.parse.urlparse(url)
    if parsed.query:
        for k, v in urllib.parse.parse_qsl(parsed.query):
            all_params[k] = v
    
    # Add body params
    all_params.update(params)
    
    # Create signature base string
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    
    base_string = f"{method.upper()}&{urllib.parse.quote(url.split('?')[0], safe='')}&{urllib.parse.quote(sorted_params, safe='')}"
    
    # Create signing key
    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_token_secret, safe='')}"
    
    # Generate signature
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    
    all_params["oauth_signature"] = signature
    
    # Build Authorization header
    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(all_params.items())
        if k.startswith("oauth_")
    )
    
    return auth_header

def post_tweet(text):
    """Post a tweet using X API v2 with OAuth 1.0a"""
    creds = get_x_creds()
    
    if not all(k in creds for k in ["api_key", "api_secret", "access_token", "access_token_secret"]):
        print("ERROR: Missing X API credentials in ~/.hermes/.env")
        print("Required: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET")
        sys.exit(1)
    
    url = "https://api.twitter.com/2/tweets"
    method = "POST"
    params = {"text": text}
    
    auth_header = oauth1_sign(
        method, url, params,
        creds["api_key"], creds["api_secret"],
        creds["access_token"], creds["access_token_secret"]
    )
    
    data = json.dumps(params).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth_header)
    req.add_header("Content-Type", "application/json")
    
    ctx = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read())
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"HTTP Error {e.code}: {error_body}")
        return {"error": error_body, "status": e.code}
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}

def whoami():
    """認証中のアカウントを確認（GET /2/users/me、投稿しない読み取り専用）"""
    creds = get_x_creds()
    if not all(k in creds for k in ["api_key", "api_secret", "access_token", "access_token_secret"]):
        print("ERROR: Missing X API credentials in ~/.hermes/.env")
        sys.exit(1)

    url = "https://api.twitter.com/2/users/me"
    auth_header = oauth1_sign(
        "GET", url, {},
        creds["api_key"], creds["api_secret"],
        creds["access_token"], creds["access_token_secret"]
    )
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", auth_header)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read())
            data = result.get("data", {})
            print(f"account: @{data.get('username')} ({data.get('name')}) id={data.get('id')}")
            return result
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:300]}")
        return None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--whoami":
        whoami()
    elif len(sys.argv) > 1:
        tweet_text = " ".join(sys.argv[1:])
        result = post_tweet(tweet_text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # 以前は引数なしで「テスト投稿」を実投稿していた（危険）ため usage 表示に変更
        print("Usage: post_tweet.py --whoami | post_tweet.py <投稿テキスト>")
        sys.exit(1)
