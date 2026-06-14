"""
Generate a realistic sample Apache access log for testing the MapReduce engine.
Usage: python generate_sample_log.py
Output: sample_access.log (~5000 lines)
"""

import random
from datetime import datetime, timedelta

IPS = [
    "192.168.1.10", "10.0.0.5", "172.16.0.2", "203.0.113.44", "198.51.100.8",
    "192.0.2.15", "185.234.21.9", "104.26.4.98", "141.101.72.3", "8.8.8.8",
]
METHODS   = ["GET"] * 70 + ["POST"] * 20 + ["PUT"] * 5 + ["DELETE"] * 5
PATHS     = ["/", "/api/users", "/login", "/logout", "/dashboard", "/upload",
             "/static/app.js", "/favicon.ico", "/api/logs", "/missing-page",
             "/admin", "/api/status", "/health", "/api/v1/data"]
STATUSES  = [200]*60 + [201]*5 + [301]*3 + [302]*2 + [400]*4 + [401]*5 + \
             [403]*3 + [404]*10 + [500]*5 + [502]*2 + [503]*1
SIZES     = [256, 512, 1024, 2048, 4096, 8192, 16384]

start = datetime(2025, 6, 1, 0, 0, 0)

lines = []
for i in range(5000):
    ts = start + timedelta(seconds=random.randint(0, 86400 * 14))
    ip     = random.choice(IPS)
    method = random.choice(METHODS)
    path   = random.choice(PATHS)
    status = random.choice(STATUSES)
    size   = random.choice(SIZES)
    ts_str = ts.strftime("%d/%b/%Y:%H:%M:%S +0000")
    lines.append(f'{ip} - - [{ts_str}] "{method} {path} HTTP/1.1" {status} {size}')

with open("sample_access.log", "w") as f:
    f.write("\n".join(lines))

print(f"Generated sample_access.log with {len(lines)} lines.")
