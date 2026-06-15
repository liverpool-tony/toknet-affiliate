#!/usr/bin/env python3
from pathlib import Path
import os

env_path = Path.home() / '.hermes' / '.env'
print('exists:', env_path.exists())
if env_path.exists():
    print('size:', env_path.stat().st_size)
    with open(env_path) as f:
        content = f.read()
    lines = [l for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
    print('total non-comment lines:', len(lines))
    for line in lines:
        k = line.split('=')[0].strip()
        print(f'  key: {k}')
else:
    print('.env does NOT exist')
    # List what's in ~/.hermes/
    hermes_dir = Path.home() / '.hermes'
    if hermes_dir.exists():
        for item in hermes_dir.iterdir():
            print(f'  {item.name}')
