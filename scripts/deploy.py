#!/usr/bin/env python3
"""Deploy to Cloudflare Pages with better error handling"""
import os, subprocess, sys

ENV_FILE = os.path.expanduser("~/.hermes/.env")
PROJECT_DIR = os.path.expanduser("~/Projects/toknet-affiliate/astro")

def load_credentials():
    """Load Cloudflare credentials from .env file (Python-based, safe parsing)"""
    token = account = None
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("CLOUDFLARE_API_TOKEN=") and "ACCOUNT" not in line:
                    token = line.split("=", 1)[1]
                elif line.startswith("CLOUDFLARE_ACCOUNT_ID="):
                    account = line.split("=", 1)[1]
    except FileNotFoundError:
        print(f"ERROR: {ENV_FILE} not found")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read {ENV_FILE}: {e}")
        sys.exit(1)

    if not token:
        print("ERROR: CLOUDFLARE_API_TOKEN not found in ~/.hermes/.env")
        sys.exit(1)
    if not account:
        print("ERROR: CLOUDFLARE_ACCOUNT_ID not found in ~/.hermes/.env")
        sys.exit(1)

    return token, account

def main():
    print("🚀 Cloudflare Pages deploy start")

    token, account = load_credentials()
    print(f"  ✅ Credentials loaded (account: {account[:8]}...)")

    os.environ["CLOUDFLARE_API_TOKEN"] = token
    os.environ["CLOUDFLARE_ACCOUNT_ID"] = account

    # Check if astro build exists
    dist_dir = os.path.join(PROJECT_DIR, "dist")
    if not os.path.isdir(dist_dir):
        print(f"  ⚠️ dist/ not found. Building first...")
        build_result = subprocess.run(
            ["npm", "run", "build"],
            cwd=PROJECT_DIR,
            capture_output=True, text=True, timeout=300
        )
        if build_result.returncode != 0:
            print(f"❌ Build failed:\n{build_result.stderr[:500]}")
            sys.exit(1)
        print("  ✅ Build complete")

    print(f"  📦 Deploying {dist_dir}...")
    result = subprocess.run(
        ["npx", "wrangler", "pages", "deploy", "dist", "--project-name=toknet-affiliate"],
        cwd=PROJECT_DIR,
        capture_output=True, text=True, timeout=180
    )

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Deploy failed (exit code: {result.returncode})")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        sys.exit(1)

    print("✅ Deploy complete!")

if __name__ == '__main__':
    main()
