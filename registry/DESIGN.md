# Registry & Wiring System Design

## Core Principle

> **Nothing is created from scratch. The optimal block always exists or is composed from existing blocks.**

## The Problem We're Solving

```
Developer thinks: "I need to validate an email"

TODAY (wasteful):
  → Writes regex from scratch
  → Gets it wrong
  → 10,000 developers do the same thing
  → 10,000 slightly different, mostly broken implementations

WITH REGISTRY (optimal):
  → Search: "validate email"
  → Find: email.validate (used 50,000 times, 99.9% test pass rate)
  → Use it
  → Done
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DEVELOPER                                │
│                            │                                     │
│                    "I need X"                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DISCOVERY ENGINE                            │
│                                                                  │
│  • Semantic search ("validate email" → email.validate)          │
│  • Type matching (need Text→Bool? here are options...)          │
│  • Usage ranking (most used, best tested)                       │
│  • Composition suggestion (no exact match? combine these...)    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         REGISTRY                                 │
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │    CORE     │ │  COMMUNITY  │ │   PRIVATE   │               │
│  │  Primitives │ │   Blocks    │ │   Blocks    │               │
│  │  (builtin)  │ │  (shared)   │ │ (your org)  │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│                                                                  │
│  Each block has:                                                 │
│  • Unique ID (namespace/name@version)                           │
│  • Type signature (Input → Output)                              │
│  • Test suite & pass rate                                       │
│  • Usage count & dependents                                     │
│  • Quality score                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WIRING ENGINE                               │
│                                                                  │
│  • Type-checks all connections                                  │
│  • Auto-completes compatible blocks                             │
│  • Validates flow completeness                                  │
│  • Optimizes block selection                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Registry Schema

### Block Manifest

```yaml
# Every block has this metadata
manifest:
  # Identity
  namespace: "stdlib"           # Who owns it
  name: "email.validate"        # What it's called
  version: "1.2.0"              # Semver
  id: "stdlib/email.validate@1.2.0"  # Unique global ID

  # Type Signature (THE KEY TO WIRING)
  signature:
    input: Text                 # What it accepts
    output: Result<Bool, ValidationError>  # What it produces

  # Categorization
  tags: ["validation", "email", "text", "security"]
  category: "validation/text"

  # Quality Metrics (auto-computed)
  metrics:
    test_count: 47
    test_pass_rate: 0.998
    usage_count: 52341
    dependent_count: 1203       # Other blocks that use this
    avg_response_time_ms: 0.3
    last_updated: "2024-01-15"
    maintainer_score: 0.95      # Based on response time, updates

  # Dependencies
  depends:
    - stdlib/regex.match@^2.0.0

  # Alternatives (blocks that do similar things)
  similar:
    - community/email.check@1.0.0
    - acme/mail.validate@3.0.0
```

### Type System for Wiring

```yaml
# Types enable automatic wiring

primitive_types:
  - None
  - Bool
  - Num
  - Text
  - Bytes

compound_types:
  - List<T>
  - Map<K, V>
  - Option<T>          # T or None
  - Result<T, E>       # T or Error

# Wiring rule: Output type must match Input type
#
# VALID:   [Text → Text] ──► [Text → Bool]
# INVALID: [Text → Text] ──► [Num → Bool]
```

## Discovery Engine

### Search Modes

```yaml
# 1. Semantic Search
query: "check if email is valid"
results:
  - stdlib/email.validate (score: 0.95)
  - community/email.check (score: 0.87)
  - stdlib/text.matches_pattern (score: 0.62)

# 2. Type Search
query:
  input: Text
  output: Bool
results:
  - stdlib/text.is_empty
  - stdlib/email.validate
  - stdlib/url.is_valid
  - community/phone.validate

# 3. Composition Search (no exact match exists)
query: "validate email and check if domain is in whitelist"
results:
  suggestion: "No exact match. Compose from:"
  composition:
    - stdlib/email.validate
    - stdlib/email.extract_domain
    - stdlib/list.contains
  wiring: |
    email.validate → branch(valid?)
      → email.extract_domain
      → list.contains(whitelist)
```

### Ranking Algorithm

```python
score = (
    0.3 * semantic_match +      # How well it matches the query
    0.2 * test_pass_rate +      # Quality indicator
    0.2 * log(usage_count) +    # Popularity (log scaled)
    0.1 * maintainer_score +    # Is it maintained?
    0.1 * recency +             # Recent updates
    0.1 * specificity           # Exact match > general match
)
```

## Wiring Engine

### Auto-Completion

```yaml
# You're building a flow and have:
flow:
  read:
    block: file.read
    # output type: Result<Text, IOError>

  next:
    block: ???  # ← What can go here?

# Wiring engine suggests (filtered by type compatibility):
suggestions:
  - unwrap          # Result<Text, E> → Text
  - map_ok          # Result<Text, E> → Result<T, E>
  - json.parse      # Text → Result<Any, ParseError>  (if unwrapped first)
```

### Validation

```yaml
# Wiring engine checks:

errors:
  - "Type mismatch at step 3: json.parse outputs Map, but filter expects List"
  - "Unreachable: step 5 has no input connection"
  - "Cycle detected: step 2 → step 4 → step 2"

warnings:
  - "Result not handled: step 2 outputs Result but step 3 expects unwrapped value"
  - "Deprecated block: stdlib/old.thing@1.0.0 → use stdlib/new.thing@2.0.0"

suggestions:
  - "Insert 'unwrap_or' between step 2 and step 3 to handle errors"
```

## Preventing Reinvention

### Before Creating a New Block

```
Developer: prim create "validate phone number"

Registry: ⚠️  Similar blocks exist:

  1. stdlib/phone.validate (94% match)
     - 12,340 uses, 99.8% tests pass
     - Supports: US, UK, EU formats

  2. community/phone.check (87% match)
     - 3,210 uses, 98.2% tests pass
     - Supports: International format

  3. telecom-corp/number.validate (82% match)
     - 890 uses, 99.9% tests pass
     - Supports: Carrier-specific validation

Options:
  [U] Use existing block
  [E] Extend existing block (add your case)
  [C] Create new (requires justification)
```

### Justification Required

```yaml
# If you insist on creating new:
new_block:
  name: "my.phone.validate"
  justification: "Existing blocks don't support Martian phone numbers"

  # You must specify how it differs
  differs_from:
    - stdlib/phone.validate: "No Mars support"
    - community/phone.check: "No Mars support"

# Registry tracks this for potential future merge
```

## Optimal Block Selection

### Automatic Optimization

```yaml
# When multiple blocks can do the job:

need:
  input: Text
  output: Bool
  semantic: "validate email"

candidates:
  - stdlib/email.validate:
      score: 0.95
      reason: "Highest usage, best test coverage"

  - community/email.check:
      score: 0.82
      reason: "Good but less battle-tested"

  - fast/email.valid:
      score: 0.78
      reason: "Faster but lower test coverage"

recommendation: stdlib/email.validate
auto_select: true  # Use best by default unless overridden
```

### Context-Aware Selection

```yaml
# Selection changes based on context

context: high_performance
  prefer: fast/email.valid
  reason: "10x faster, acceptable accuracy"

context: high_reliability
  prefer: stdlib/email.validate
  reason: "Best test coverage"

context: offline
  prefer: local/email.check
  reason: "No network dependency"
```

## Governance

### Block Lifecycle

```
PROPOSED → TESTING → STABLE → DEPRECATED → ARCHIVED
    │          │         │          │
    │          │         │          └── Still works, not recommended
    │          │         └── Production ready
    │          └── Needs more usage/tests
    └── Under review
```

### Quality Gates

```yaml
# To reach STABLE status:
requirements:
  test_count: ">= 10"
  test_pass_rate: ">= 0.95"
  usage_count: ">= 100"
  no_critical_bugs: true
  documentation: complete
  type_signature: verified
```

## Summary

| Component | Purpose |
|-----------|---------|
| **Registry** | Store all blocks with metadata |
| **Discovery** | Find the right block (semantic + type search) |
| **Wiring** | Connect blocks with type safety |
| **Ranking** | Surface optimal blocks |
| **Governance** | Ensure quality, prevent duplication |

The goal: **Write less, reuse more, never reinvent.**
