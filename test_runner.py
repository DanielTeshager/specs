#!/usr/bin/env python3
"""
Test Runner

Reads YAML specs, executes tests, reports results.
The spec defines the test. This runs it.
"""

import yaml
import sys
import os
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass

sys.path.insert(0, 'runtime')

from primitives import T, F, B, P, run, NONE
from io_adapter import use_mock, MockAdapter, Ok, Err


@dataclass
class TestResult:
    name: str
    passed: bool
    expected: Any
    actual: Any
    error: str = None


def load_yaml(path: str) -> Dict:
    """Load YAML file"""
    with open(path) as f:
        return yaml.safe_load(f)


def run_spec_tests(spec_path: str) -> List[TestResult]:
    """Run all tests defined in a spec file"""
    results = []

    try:
        spec = load_yaml(spec_path)
    except Exception as e:
        return [TestResult(
            name=f"load:{spec_path}",
            passed=False,
            expected="valid YAML",
            actual=None,
            error=str(e)
        )]

    # Handle both single primitive and multiple primitives format
    primitives = spec.get('primitives', {spec.get('primitive', 'unknown'): spec})

    for prim_name, prim_spec in primitives.items():
        tests = prim_spec.get('tests', [])

        for test in tests:
            result = run_single_test(prim_name, prim_spec, test)
            results.append(result)

    return results


def run_single_test(prim_name: str, prim_spec: Dict, test: Dict) -> TestResult:
    """Run a single test case"""
    test_name = f"{prim_name}::{test.get('name', 'unnamed')}"

    try:
        # Setup mock environment
        setup = test.get('setup', {})
        mock = setup_mock(setup)

        # Get input
        input_data = test.get('input', {})

        # Build and run the primitive
        block = build_primitive(prim_name, prim_spec, input_data)

        # Extract actual input value (might be nested)
        actual_input = input_data.get('data', input_data)
        if isinstance(actual_input, dict) and len(actual_input) == 1:
            # Single value like {host: "x"} - just for display
            pass

        # Run it
        actual = run(block, actual_input)

        # Check expectation
        expected = test.get('expect')
        passed, error = check_expectation(actual, expected, mock)

        return TestResult(
            name=test_name,
            passed=passed,
            expected=expected,
            actual=simplify_result(actual),
            error=error
        )

    except Exception as e:
        return TestResult(
            name=test_name,
            passed=False,
            expected=test.get('expect'),
            actual=None,
            error=str(e)
        )


def setup_mock(setup: Dict) -> MockAdapter:
    """Setup mock environment from test setup"""
    mock = use_mock()

    # File system mocks
    if 'mock_fs' in setup:
        mock.fs = dict(setup['mock_fs'])

    # HTTP mocks
    if 'mock_http' in setup:
        mock.http_responses = dict(setup['mock_http'])

    # Environment mocks
    if 'mock_env' in setup:
        mock.env = dict(setup['mock_env'])

    # Time mock
    if 'mock_time' in setup:
        mock.time = setup['mock_time']

    # Random mock
    if 'mock_random' in setup:
        mock.random_values = list(setup['mock_random'])

    # Network mocks (for network primitives)
    if 'mock_tcp' in setup:
        mock._tcp_mocks = setup['mock_tcp']
    if 'mock_ping' in setup:
        mock._ping_mocks = setup['mock_ping']
    if 'mock_dns' in setup:
        mock._dns_mocks = setup['mock_dns']
    if 'mock_port_scan' in setup:
        mock._port_scan_mocks = setup['mock_port_scan']

    return mock


def build_primitive(name: str, spec: Dict, input_data: Dict, mock: MockAdapter):
    """Build a primitive block from spec - uses mock if available"""

    # Check for network mocks first
    if hasattr(mock, '_tcp_mocks') and ('tcp_connect' in name or 'tcp' in name):
        host = input_data.get('host', '')
        port = input_data.get('port', 80)
        key = f"{host}:{port}"
        if key in mock._tcp_mocks:
            mock_result = mock._tcp_mocks[key]
            if mock_result.get('timeout'):
                return T(lambda _: Err(IOErr("Timeout")))
            return T(lambda _: Ok(mock_result))

    if hasattr(mock, '_ping_mocks') and 'ping' in name:
        host = input_data.get('host', '')
        if host in mock._ping_mocks:
            return T(lambda _: Ok(mock._ping_mocks[host]))

    if hasattr(mock, '_dns_mocks') and 'dns' in name:
        hostname = input_data.get('hostname', '')
        if hostname in mock._dns_mocks:
            return T(lambda _: Ok(mock._dns_mocks[hostname]))

    if hasattr(mock, '_port_scan_mocks') and 'port_scan' in name:
        host = input_data.get('host', '')
        if host in mock._port_scan_mocks:
            mock_data = mock._port_scan_mocks[host]
            open_ports = [{"port": p, "service": get_service(p)}
                         for p in mock_data.get('open', [])]
            return T(lambda _: Ok({
                "host": host,
                "open_ports": open_ports,
                "scan_time_ms": 10
            }))

    if hasattr(mock, '_service_mocks') and 'service_detect' in name:
        host = input_data.get('host', '')
        port = input_data.get('port', 80)
        key = f"{host}:{port}"
        if hasattr(mock, '_service_mocks') and key in mock._service_mocks:
            return T(lambda _: Ok(mock._service_mocks[key]))

    if hasattr(mock, '_discover_mocks') and 'host_discover' in name:
        range_ = input_data.get('range', '')
        if hasattr(mock, '_discover_mocks') and range_ in mock._discover_mocks:
            return T(lambda _: Ok(mock._discover_mocks[range_]))

    # Map primitive names to real implementations (for integration tests)
    if 'transform' in name:
        fn = spec.get('contract', {}).get('config', {}).get('fn', 'x => x')
        return T(fn)

    if 'filter' in name:
        pred = spec.get('contract', {}).get('config', {}).get('predicate', 'x => true')
        return F(pred)

    if 'file.read' in name:
        from io_primitives import file_read
        path = input_data.get('path', '')
        return file_read(path)

    if 'file.write' in name:
        from io_primitives import file_write
        path = input_data.get('path', '')
        return file_write(path)

    if 'tcp_connect' in name or 'tcp' in name:
        from net_primitives import tcp_connect
        host = input_data.get('host', '')
        port = input_data.get('port', 80)
        timeout = input_data.get('timeout', 1000) / 1000
        # Capture variables in closure properly
        h, p, t = host, port, timeout
        return T(lambda _: tcp_connect(h, p, t))

    if 'ping' in name:
        from net_primitives import ping
        host = input_data.get('host', '')
        timeout = input_data.get('timeout', 1000) / 1000
        h, t = host, timeout
        return T(lambda _: ping(h, t))

    if 'dns' in name:
        from net_primitives import dns_lookup
        hostname = input_data.get('hostname', '')
        record_type = input_data.get('record_type', 'A')
        h, r = hostname, record_type
        return T(lambda _: dns_lookup(h, r))

    if 'port_scan' in name:
        from net_primitives import port_scan
        host = input_data.get('host', '')
        ports = input_data.get('ports', [])
        timeout = input_data.get('timeout', 500) / 1000
        h, p, t = host, ports, timeout
        return T(lambda _: port_scan(h, p, t))

    if 'service_detect' in name:
        from net_primitives import service_detect
        host = input_data.get('host', '')
        port = input_data.get('port', 80)
        h, p = host, port
        return T(lambda _: service_detect(h, p))

    if 'host_discover' in name:
        from net_primitives import host_discover
        range_ = input_data.get('range', '')
        method = input_data.get('method', 'ping')
        r, m = range_, method
        return T(lambda _: host_discover(r, m))

    # Default: identity
    return T('x => x')


def get_service(port: int) -> str:
    """Get service name for port"""
    services = {
        22: "ssh", 80: "http", 443: "https", 21: "ftp",
        25: "smtp", 53: "dns", 3306: "mysql", 5432: "postgres"
    }
    return services.get(port, "unknown")


def check_expectation(actual: Any, expected: Any, mock: MockAdapter) -> tuple:
    """Check if actual matches expected"""

    if expected is None:
        return True, None

    # Handle Ok/Err expectations
    if isinstance(expected, dict):
        if 'ok' in expected:
            if isinstance(actual, Ok):
                return match_value(actual.value, expected['ok'])
            return False, f"Expected Ok, got {type(actual).__name__}"

        if 'err' in expected:
            if isinstance(actual, Err):
                return match_value(actual.error, expected['err'])
            return False, f"Expected Err, got {type(actual).__name__}"

        if 'some' in expected:
            return match_value(actual, expected['some'])

        if 'none' in expected:
            return actual is None or actual is NONE, None

        # Direct dict comparison
        return match_value(actual, expected)

    # Direct value comparison
    return match_value(actual, expected)


def match_value(actual: Any, expected: Any) -> tuple:
    """Deep match actual against expected pattern"""

    if expected is None:
        return True, None

    # Handle Result types
    if isinstance(actual, Ok):
        actual = actual.value
    if isinstance(actual, Err):
        actual = {"error": str(actual.error)}

    # Length check
    if isinstance(expected, dict) and 'length' in expected:
        if hasattr(actual, '__len__'):
            if len(actual) != expected['length']:
                return False, f"Expected length {expected['length']}, got {len(actual)}"
        else:
            return False, f"Cannot check length of {type(actual)}"
        # Remove length from further checks
        expected = {k: v for k, v in expected.items() if k != 'length'}
        if not expected:
            return True, None

    # Dict pattern matching
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, exp_val in expected.items():
            if key not in actual:
                return False, f"Missing key: {key}"
            passed, err = match_value(actual[key], exp_val)
            if not passed:
                return False, f"Key '{key}': {err}"
        return True, None

    # List matching
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False, f"List length: expected {len(expected)}, got {len(actual)}"
        for i, (exp, act) in enumerate(zip(expected, actual)):
            passed, err = match_value(act, exp)
            if not passed:
                return False, f"Index {i}: {err}"
        return True, None

    # Direct comparison
    if actual == expected:
        return True, None

    return False, f"Expected {expected}, got {actual}"


def simplify_result(result: Any) -> Any:
    """Simplify result for display"""
    if isinstance(result, Ok):
        return {"Ok": simplify_result(result.value)}
    if isinstance(result, Err):
        return {"Err": str(result.error)}
    if isinstance(result, dict):
        return {k: simplify_result(v) for k, v in result.items()}
    if isinstance(result, list):
        return [simplify_result(v) for v in result[:5]]  # Limit list display
    return result


def print_results(results: List[TestResult], verbose: bool = False):
    """Print test results"""
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print(f"\n{'='*60}")
    print(f"  TEST RESULTS: {passed} passed, {failed} failed")
    print('='*60)

    for r in results:
        status = "✓" if r.passed else "✗"
        print(f"\n  [{status}] {r.name}")

        if not r.passed or verbose:
            print(f"      Expected: {r.expected}")
            print(f"      Actual:   {r.actual}")
            if r.error:
                print(f"      Error:    {r.error}")

    print()
    return failed == 0


def run_all_specs(spec_dir: str = "primitives") -> bool:
    """Run tests from all spec files"""
    all_results = []

    for yaml_file in Path(spec_dir).rglob("*.yaml"):
        print(f"\nRunning: {yaml_file}")
        results = run_spec_tests(str(yaml_file))
        all_results.extend(results)

    return print_results(all_results)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Installing PyYAML...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
        import yaml

    if len(sys.argv) > 1:
        spec_path = sys.argv[1]
        if os.path.isdir(spec_path):
            success = run_all_specs(spec_path)
        else:
            results = run_spec_tests(spec_path)
            success = print_results(results, verbose=True)
    else:
        print("Usage: python test_runner.py <spec.yaml | spec_dir>")
        print("\nRunning all specs in primitives/...")
        success = run_all_specs("primitives")

    sys.exit(0 if success else 1)
