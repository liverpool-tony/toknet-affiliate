from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))
now = datetime.now(JST)
cutoff = now - timedelta(hours=24)
print(f'Now: {now}')
print(f'Cutoff (24h ago): {cutoff}')
articles = [
    ('20260613_2300', datetime(2026,6,13,23,0,tzinfo=JST)),
    ('20260614_0700', datetime(2026,6,14,7,0,tzinfo=JST)),
    ('20260614_0800', datetime(2026,6,14,8,0,tzinfo=JST)),
    ('20260614_0839', datetime(2026,6,14,8,39,tzinfo=JST)),
]
for name, dt in articles:
    print(f'{name}: within_24h={dt >= cutoff}')
