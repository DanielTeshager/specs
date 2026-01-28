#!/usr/bin/env python3
"""
Registry & Wiring Demo

Demonstrates:
1. Searching for blocks
2. Preventing reinvention
3. Type-safe wiring
4. Auto-completion
"""

from registry import (
    get_registry, Registry, Block, BlockMetrics, TypeSignature,
    WiringEngine, FlowStep
)


def separator(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)


def main():
    registry = get_registry()
    wiring = WiringEngine(registry)

    # =========================================================================
    # 1. REGISTRY STATS
    # =========================================================================
    separator("1. REGISTRY OVERVIEW")

    stats = registry.stats()
    print(f"Total blocks: {stats['total_blocks']}")
    print(f"Namespaces: {stats['namespaces']}")
    print(f"Tags: {stats['tags']}")
    print(f"Avg quality: {stats['avg_quality']:.2f}")

    # =========================================================================
    # 2. SEMANTIC SEARCH
    # =========================================================================
    separator("2. SEMANTIC SEARCH")

    print("\n> Search: 'validate email'")
    results = registry.search("validate email")
    for block, score in results[:5]:
        print(f"  [{score:.2f}] {block.id}")
        print(f"         {block.description}")
        print(f"         Quality: {block.metrics.quality_score:.2f}, "
              f"Uses: {block.metrics.usage_count:,}")

    print("\n> Search: 'parse json'")
    results = registry.search("parse json")
    for block, score in results[:3]:
        print(f"  [{score:.2f}] {block.id}")

    print("\n> Search: 'read file'")
    results = registry.search("read file")
    for block, score in results[:3]:
        print(f"  [{score:.2f}] {block.id}")

    # =========================================================================
    # 3. TYPE-BASED SEARCH
    # =========================================================================
    separator("3. TYPE-BASED SEARCH")

    print("\n> Find blocks: Text → Bool")
    results = registry.search_by_type(input_type="Text", output_type="Bool")
    for block in results[:5]:
        print(f"  {block.id}: {block.signature}")

    print("\n> Find blocks that accept: Result<Text, IOError>")
    results = registry.find_compatible("Result<Text, IOError>")
    for block in results[:5]:
        print(f"  {block.id}: {block.signature}")

    # =========================================================================
    # 4. PREVENT REINVENTION
    # =========================================================================
    separator("4. PREVENT REINVENTION")

    print("\n> Developer tries to create: 'email.checker'")
    print("  Type: Text → Bool")
    print("  Tags: ['email', 'validation']")

    duplicates = registry.check_duplicate(
        name="email.checker",
        signature=TypeSignature("Text", "Bool"),
        tags=["email", "validation"]
    )

    if duplicates:
        print("\n⚠️  SIMILAR BLOCKS EXIST:\n")
        for block, similarity in duplicates[:3]:
            print(f"  [{similarity:.0%} match] {block.id}")
            print(f"     {block.description}")
            print(f"     Uses: {block.metrics.usage_count:,}, "
                  f"Test pass: {block.metrics.test_pass_rate:.1%}")
        print("\n  Recommendation: Use existing block instead of creating new one")

    # =========================================================================
    # 5. WIRING VALIDATION
    # =========================================================================
    separator("5. WIRING VALIDATION")

    print("\n> Valid flow: read file → parse json → transform")
    valid_flow = [
        FlowStep("read", "io/file.read"),
        FlowStep("parse", "stdlib/json.parse", input_from="read.output"),
        FlowStep("process", "core/transform", input_from="parse.output"),
    ]
    result = wiring.validate_flow(valid_flow)
    print(f"  Valid: {result.valid}")
    if result.warnings:
        print(f"  Warnings: {result.warnings}")

    print("\n> Invalid flow: read file → (missing step) → validate email")
    invalid_flow = [
        FlowStep("read", "io/file.read"),
        FlowStep("validate", "stdlib/email.validate", input_from="missing.output"),
    ]
    result = wiring.validate_flow(invalid_flow)
    print(f"  Valid: {result.valid}")
    for error in result.errors:
        print(f"  Error: {error}")

    print("\n> Flow with type mismatch: List<Text> → email.validate (expects Text)")
    mismatch_flow = [
        FlowStep("split", "stdlib/text.split"),
        FlowStep("validate", "stdlib/email.validate", input_from="split.output"),
    ]
    result = wiring.validate_flow(mismatch_flow)
    print(f"  Valid: {result.valid}")
    for error in result.errors:
        print(f"  Error: {error}")

    # =========================================================================
    # 6. AUTO-COMPLETION
    # =========================================================================
    separator("6. AUTO-COMPLETION")

    print("\n> After file.read (outputs Result<Text, IOError>), suggest next blocks:")
    suggestions = wiring.suggest_next("Result<Text, IOError>")
    for block in suggestions:
        print(f"  → {block.name}: {block.signature}")
        print(f"     {block.description[:60]}...")

    print("\n> After json.parse (outputs Result<Any, ParseError>), suggest next blocks:")
    suggestions = wiring.suggest_next("Result<Any, ParseError>")
    for block in suggestions:
        print(f"  → {block.name}: {block.signature}")

    # =========================================================================
    # 7. AUTO-WIRING
    # =========================================================================
    separator("7. AUTO-WIRING")

    print("\n> Auto-wire this flow (no manual connections):")
    unwired = [
        FlowStep("read", "io/file.read"),
        FlowStep("unwrap", "core/unwrap"),
        FlowStep("parse", "stdlib/json.parse"),
        FlowStep("print", "io/stdout"),
    ]
    for step in unwired:
        print(f"  {step.name}: {step.block_id} (input: {step.input_from or 'none'})")

    print("\n> After auto-wiring:")
    wired = wiring.auto_wire(unwired)
    for step in wired:
        print(f"  {step.name}: {step.block_id} (input: {step.input_from or 'START'})")

    # =========================================================================
    # 8. FIND SIMILAR BLOCKS
    # =========================================================================
    separator("8. FIND SIMILAR BLOCKS")

    print("\n> Blocks similar to stdlib/email.validate:")
    similar = registry.find_similar("stdlib/email.validate@1.0.0")
    if similar:
        for block in similar[:5]:
            print(f"  {block.id}: {block.signature}")
    else:
        print("  (none found in this demo registry)")

    # Let's add a similar block to demonstrate
    registry.register(Block(
        namespace="community",
        name="email.check",
        version="1.0.0",
        description="Alternative email validator",
        signature=TypeSignature("Text", "Result<Bool, ValidationError>"),
        tags=["email", "validate", "validation"],
        metrics=BlockMetrics(test_count=20, test_pass_rate=0.95, usage_count=1000)
    ))

    print("\n> After adding community/email.check:")
    similar = registry.find_similar("stdlib/email.validate@1.0.0")
    for block in similar[:5]:
        print(f"  {block.id}")
        print(f"     Quality: {block.metrics.quality_score:.2f}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    separator("SUMMARY")

    print("""
The registry system provides:

  1. SEMANTIC SEARCH
     "validate email" → finds stdlib/email.validate

  2. TYPE SEARCH
     "Text → Bool" → finds all matching blocks

  3. DUPLICATE PREVENTION
     Creating "email.checker"? → "Similar blocks exist!"

  4. WIRING VALIDATION
     Catches type mismatches before runtime

  5. AUTO-COMPLETION
     "After file.read, you can use: unwrap, json.parse, ..."

  6. AUTO-WIRING
     Connects blocks automatically based on types

  7. QUALITY RANKING
     Most used + best tested → appears first

NOTHING IS CREATED FROM SCRATCH.
THE OPTIMAL BLOCK ALWAYS SURFACES.
""")


if __name__ == "__main__":
    main()
