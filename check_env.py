import os
from pathlib import Path

# Check environment
print("MSTODON_CLIENT_ID:", bool(os.environ.get('MSTODON_CLIENT_ID')))
print("MSTODON_CLIENT_SECRET:", bool(os.environ.get('MSTODON_CLIENT_SECRET')))
print("MSTODON_ACCESS_TOKEN:", bool(os.environ.get('MSTODON_ACCESS_TOKEN')))

# Check .env file
env_path = Path.home() / '.hermes' / '.env'
print(f"\n.env file exists: {env_path.exists()}")
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if 'MSTODON' in line:
                key = line.split('=')[0].strip()
                print(f"  Found: {key}=...")
