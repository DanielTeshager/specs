#!/usr/bin/env python3
"""
Real Tests - No Mocks

Tests run against actual hosts. If it works, it works.
"""

import sys
sys.path.insert(0, 'runtime')

from primitives import run
from net_primitives import (
    tcp_connect, ping, dns_lookup, port_scan, service_detect
)
from io_adapter import Ok, Err

def test(name: str, result, check):
    """Run a test and print result"""
    try:
        passed = check(result)
        status = "✓" if passed else "✗"
        print(f"  [{status}] {name}")
        if not passed:
            print(f"      Got: {result}")
        return passed
    except Exception as e:
        print(f"  [✗] {name}")
        print(f"      Error: {e}")
        return False


print("="*60)
print("  REAL TESTS - Network Primitives")
print("="*60)

passed = 0
failed = 0

# DNS
print("\n[dns_lookup]")
result = dns_lookup("google.com")
if test("google.com resolves", result, lambda r: isinstance(r, Ok) and len(r.value) > 0):
    passed += 1
else:
    failed += 1

result = dns_lookup("this-domain-does-not-exist-12345.com")
if test("invalid domain fails", result, lambda r: isinstance(r, Err)):
    passed += 1
else:
    failed += 1

# Ping
print("\n[ping]")
result = ping("8.8.8.8", timeout=2.0)
if test("8.8.8.8 reachable", result, lambda r: isinstance(r, Ok) and r.value.get('reachable') == True):
    passed += 1
else:
    failed += 1

# TCP Connect
print("\n[tcp_connect]")
result = tcp_connect("google.com", 443, timeout=2.0)
if test("google.com:443 open", result, lambda r: isinstance(r, Ok) and r.value.get('status') == 'open'):
    passed += 1
else:
    failed += 1

result = tcp_connect("google.com", 12345, timeout=1.0)
if test("google.com:12345 closed", result, lambda r: isinstance(r, Ok) and r.value.get('status') in ('closed', 'filtered')):
    passed += 1
else:
    failed += 1

# Port Scan
print("\n[port_scan]")
result = port_scan("scanme.nmap.org", [22, 80, 443], timeout=2.0)
if test("scanme.nmap.org has open ports", result, lambda r: isinstance(r, Ok) and len(r.value.get('open_ports', [])) > 0):
    passed += 1
else:
    failed += 1

# Check specific ports
if isinstance(result, Ok):
    ports = [p['port'] for p in result.value.get('open_ports', [])]
    if test("port 22 or 80 found", True, lambda _: 22 in ports or 80 in ports):
        passed += 1
    else:
        failed += 1
else:
    failed += 1

# Service Detect
print("\n[service_detect]")
result = service_detect("scanme.nmap.org", 22, timeout=3.0)
if test("detect SSH on port 22", result, lambda r: isinstance(r, Ok) and r.value.get('service') == 'ssh'):
    passed += 1
else:
    failed += 1

# Summary
print("\n" + "="*60)
print(f"  RESULTS: {passed} passed, {failed} failed")
print("="*60)

if failed > 0:
    print("\n  Some tests failed - could be network issues")

sys.exit(0 if failed == 0 else 1)
