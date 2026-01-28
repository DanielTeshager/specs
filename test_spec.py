#!/usr/bin/env python3
"""
Test harness for specs.

Claude Code composes specs, this runs the tests.
Loop until green.
"""

import sys
import json
from typing import Any, Dict, List

# Add paths
sys.path.insert(0, 'runtime')
sys.path.insert(0, 'registry')

from primitives import T, F, B, P, run, NONE
from io_adapter import use_mock, use_real, MockAdapter
from io_primitives import *
from registry import get_registry


def test_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run tests defined in a spec.
    Returns {passed: bool, results: [...]}
    """
    results = []
    all_passed = True

    for test in spec.get('tests', []):
        name = test.get('name', 'unnamed')

        try:
            # Setup mock if specified
            mock_config = test.get('mock', {})
            if mock_config:
                mock = use_mock(
                    mock_fs=mock_config.get('fs', {}),
                    mock_http=mock_config.get('http', {}),
                    mock_env=mock_config.get('env', {}),
                    mock_time=mock_config.get('time', 0),
                    mock_stdin=mock_config.get('stdin', ''),
                )
            else:
                use_real()

            # Build the pipeline from spec
            pipeline = build_pipeline(spec.get('blocks', []))

            # Run with input
            input_data = test.get('input', NONE)
            result = run(pipeline, input_data)

            # Check expectations
            expect = test.get('expect', {})
            passed, message = check_expect(result, expect)

            results.append({
                'name': name,
                'passed': passed,
                'message': message,
                'result': str(result)[:100]
            })

            if not passed:
                all_passed = False

        except Exception as e:
            results.append({
                'name': name,
                'passed': False,
                'message': f'Error: {e}',
                'result': None
            })
            all_passed = False

    return {
        'passed': all_passed,
        'results': results
    }


def build_pipeline(blocks: List[Dict]) -> Any:
    """Build a pipeline from block specs"""
    if not blocks:
        return T("x => x")

    built = []
    for block in blocks:
        b = build_block(block)
        if b:
            built.append(b)

    if len(built) == 1:
        return built[0]
    return P(*built)


def build_block(spec: Dict) -> Any:
    """Build a single block from spec"""
    block_id = spec.get('id', spec.get('block', ''))
    config = spec.get('config', {})

    # Core primitives
    if block_id in ('core/transform', 'transform'):
        return T(config.get('fn', 'x => x'))

    if block_id in ('core/filter', 'filter'):
        return F(config.get('predicate', 'x => true'))

    if block_id in ('core/branch', 'branch'):
        return B(
            config.get('condition', 'x => true'),
            config.get('then', 'x => x'),
            config.get('else', 'x => x')
        )

    # IO primitives
    if block_id in ('io/file.read', 'file.read'):
        return file_read(config.get('path'))

    if block_id in ('io/file.write', 'file.write'):
        return file_write(config.get('path'))

    if block_id in ('io/stdout', 'stdout'):
        return stdout()

    if block_id in ('io/http.get', 'http.get'):
        return http_get(config.get('url'))

    # Stdlib
    if block_id in ('stdlib/json.parse', 'json.parse'):
        return T("text => __import__('json').loads(text)")

    if block_id in ('stdlib/email.validate', 'email.validate'):
        return T("email => '@' in email and '.' in email.split('@')[1]")

    # Error handling
    if block_id in ('core/unwrap', 'unwrap'):
        return unwrap()

    if block_id in ('core/unwrap_or', 'unwrap_or'):
        return unwrap_or(config.get('default'))

    # Unknown - return identity
    print(f"Warning: Unknown block {block_id}")
    return T("x => x")


def check_expect(result: Any, expect: Dict) -> tuple:
    """Check if result matches expectations"""
    if not expect:
        return True, "No expectations"

    # Direct value match
    if 'value' in expect:
        if result == expect['value']:
            return True, "Value matches"
        return False, f"Expected {expect['value']}, got {result}"

    # Length check
    if 'length' in expect:
        if hasattr(result, '__len__'):
            if len(result) == expect['length']:
                pass  # Continue checking
            else:
                return False, f"Expected length {expect['length']}, got {len(result)}"
        else:
            return False, f"Result has no length"

    # Contains check
    if 'contains' in expect:
        if expect['contains'] in str(result):
            return True, "Contains match"
        return False, f"Expected to contain {expect['contains']}"

    # Type check
    if 'type' in expect:
        type_name = type(result).__name__
        if type_name == expect['type']:
            return True, "Type matches"
        return False, f"Expected type {expect['type']}, got {type_name}"

    # Truthy check
    if 'truthy' in expect:
        if bool(result) == expect['truthy']:
            return True, "Truthy matches"
        return False, f"Expected truthy={expect['truthy']}, got {bool(result)}"

    return True, "Passed"


def run_inline_test(code: str) -> Dict:
    """Run inline Python test code"""
    try:
        exec_globals = {
            'T': T, 'F': F, 'B': B, 'P': P, 'run': run,
            'file_read': file_read, 'file_write': file_write,
            'http_get': http_get, 'env': env,
            'stdout': stdout, 'stderr': stderr,
            'unwrap': unwrap, 'unwrap_or': unwrap_or,
            'time_now': time_now, 'uuid': uuid, 'random': random,
            'use_mock': use_mock, 'use_real': use_real,
            'NONE': NONE,
        }
        exec(code, exec_globals)
        return {'passed': True, 'message': 'All assertions passed'}
    except AssertionError as e:
        return {'passed': False, 'message': f'Assertion failed: {e}'}
    except Exception as e:
        return {'passed': False, 'message': f'Error: {e}'}


# CLI
if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run spec file
        with open(sys.argv[1]) as f:
            spec = json.load(f)
        result = test_spec(spec)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python test_spec.py <spec.json>")
        print("Or import and use test_spec() / run_inline_test()")
