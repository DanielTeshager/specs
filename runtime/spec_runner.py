#!/usr/bin/env python3
"""
Spec Runner: Execute primitive specs directly

The spec IS the program.
"""

from typing import Any, Dict, List
from primitives import T, F, B, P, R, Primitives, Store, run, NONE


def build_block(spec: Dict[str, Any], components: Dict[str, Any] = None):
    """Build a block from a spec"""
    components = components or {}

    # Reference to existing component
    if "use" in spec:
        ref = spec["use"]
        parts = ref.split(".")
        target = components
        for part in parts:
            target = target[part]
        return build_block(target["spec"], components)

    primitive = spec.get("primitive")

    if primitive == "transform":
        return T(spec["fn"])

    elif primitive == "filter":
        return F(spec["predicate"])

    elif primitive == "branch":
        then_block = spec["then"]
        else_block = spec["else"]
        # then/else can be strings or nested specs
        if isinstance(then_block, dict):
            then_block = build_block(then_block, components)
        if isinstance(else_block, dict):
            else_block = build_block(else_block, components)
        return B(spec["condition"], then_block, else_block)

    elif primitive == "pipe":
        blocks = [build_block(b, components) for b in spec["blocks"]]
        return P(*blocks)

    elif primitive == "repeat":
        block = build_block(spec["block"], components)
        return R(spec["condition"], block, spec.get("max", 1000))

    elif primitive == "parallel":
        blocks = [build_block(b, components) for b in spec["blocks"]]
        return Primitives.parallel(*blocks)

    elif primitive == "group":
        # Groups are more complex - for now just build the exposed output
        # In a full implementation, we'd wire internal blocks together
        blocks = {}
        for name, block_spec in spec.get("blocks", {}).items():
            blocks[name] = build_block(block_spec, components)
        # Return the first block for now (simplified)
        if blocks:
            return list(blocks.values())[0]
        return T("x => x")

    else:
        raise ValueError(f"Unknown primitive: {primitive}")


def run_spec(spec: Dict[str, Any], input_data: Any = NONE) -> Any:
    """Run a spec with input data"""
    block = build_block(spec)
    return run(block, input_data)


def run_tests(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run all tests in a spec, return results"""
    results = []
    block = build_block(spec)

    for test in spec.get("tests", []):
        name = test.get("name", "unnamed")
        input_data = test.get("input", {})
        expected = test.get("expect")

        # Handle input format - might be nested
        if isinstance(input_data, dict):
            if "data" in input_data:
                actual_input = input_data["data"]
            else:
                actual_input = input_data
        else:
            actual_input = input_data

        try:
            actual = run(block, actual_input)
            passed = actual == expected
            results.append({
                "name": name,
                "passed": passed,
                "expected": expected,
                "actual": actual,
            })
        except Exception as e:
            results.append({
                "name": name,
                "passed": False,
                "expected": expected,
                "actual": f"ERROR: {e}",
            })

    return results


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    # Example: Define a price calculator as a spec (pure data structure)
    price_calculator_spec = {
        "primitive": "pipe",
        "blocks": [
            {
                "primitive": "branch",
                "condition": "order => order.total > 100",
                "then": "order => {total: order.total * 0.9, discount: true}",
                "else": "order => {total: order.total, discount: false}"
            },
            {
                "primitive": "transform",
                "fn": "order => {total: order.total * 1.08, tax: order.total * 0.08, discount: order.discount}"
            },
            {
                "primitive": "branch",
                "condition": "order => order.total > 50",
                "then": "order => {total: order.total, shipping: 0, discount: order.discount}",
                "else": "order => {total: order.total + 10, shipping: 10, discount: order.discount}"
            }
        ],
        "tests": [
            {
                "name": "large_order_gets_discount",
                "input": {"data": {"total": 150}},
                "expect": {"total": 145.8, "shipping": 0, "discount": True}
            },
            {
                "name": "small_order_pays_shipping",
                "input": {"data": {"total": 40}},
                "expect": {"total": 53.2, "shipping": 10, "discount": False}
            }
        ]
    }

    print("=" * 60)
    print("  SPEC RUNNER: The spec IS the program")
    print("=" * 60)

    spec = price_calculator_spec

    print("\n1. LOADED SPEC:")
    print(f"   Primitive: {spec['primitive']}")
    print(f"   Pipeline stages: {len(spec['blocks'])}")

    print("\n2. RUNNING TESTS:")
    results = run_tests(spec)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"   [{status}] {r['name']}")
        if not r["passed"]:
            print(f"      Expected: {r['expected']}")
            print(f"      Actual:   {r['actual']}")

    print("\n3. INTERACTIVE:")
    block = build_block(spec)
    test_orders = [
        {"total": 200},
        {"total": 75},
        {"total": 30},
    ]
    for order in test_orders:
        result = run(block, order)
        print(f"   ${order['total']:>3} order -> ${result['total']:.2f} "
              f"(discount: {result['discount']}, shipping: ${result['shipping']})")

    # Example 2: FizzBuzz as a spec
    print("\n" + "=" * 60)
    print("  EXAMPLE 2: FIZZBUZZ")
    print("=" * 60)

    fizzbuzz_spec = {
        "primitive": "branch",
        "condition": "n => n % 15 == 0",
        "then": "n => 'fizzbuzz'",
        "else": {
            "primitive": "branch",
            "condition": "n => n % 3 == 0",
            "then": "n => 'fizz'",
            "else": {
                "primitive": "branch",
                "condition": "n => n % 5 == 0",
                "then": "n => 'buzz'",
                "else": "n => n"
            }
        }
    }

    fizzbuzz = build_block(fizzbuzz_spec)
    print("\nFizzBuzz 1-20:")
    for i in range(1, 21):
        print(f"  {i:2} -> {run(fizzbuzz, i)}")
