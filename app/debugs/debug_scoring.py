# app/debug_scoring.py
import sys
import os
sys.path.append('.')

from app.scoring import _parse_ip

print("🔍 Testing IP parsing in scoring.py...")

test_cases = [
    "IP65",
    "IP65.0",
    "65",
    65,
    65.0,
    "IP 65",
    "IP-65",
    "IP65/IP66",
    "IP65/IP67",
    "IP65, IP66",
    "IP65/IP66/IP67",
]

print("Testing _parse_ip function:")
for test in test_cases:
    try:
        result = _parse_ip(test)
        print(f"  '{test}' ({type(test).__name__}) -> {result}")
    except Exception as e:
        print(f"  '{test}' -> ERROR: {e}")

# Test the match_value function
from app.scoring import _match_value

print("\nTesting _match_value for IP:")
test_pairs = [
    ("IP65", "IP65"),
    ("IP65", ">=IP65"),
    ("IP66", ">=IP65"),
    ("IP64", ">=IP65"),
    ("IP65.0", ">=IP65"),
    ("65", ">=IP65"),
]

for got, wanted in test_pairs:
    ok, why = _match_value("ip_rating", got, wanted)
    print(f"  got='{got}', want='{wanted}' -> {'✅' if ok else '❌'} {why}")