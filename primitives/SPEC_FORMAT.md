# Primitive Specification Format

## Philosophy

Every computational primitive is defined by:
1. **What it does** (semantic contract)
2. **What it accepts** (input schema)
3. **What it produces** (output schema)
4. **How it fails** (error conditions)
5. **How to verify it** (test cases)

Users care about products. Agents care about tests passing.
The spec is the bridge.

## Primitive Definition Structure

```yaml
primitive: <name>
version: <semver>
category: <data_flow|state|control|composition>

description: |
  Plain English description of what this primitive does.
  Must be unambiguous. If an agent can misinterpret it, rewrite it.

contract:
  input:
    - name: <param_name>
      type: <type>
      required: <bool>
      description: <what it is>
  output:
    type: <type>
    description: <what it produces>
  errors:
    - condition: <when this happens>
      produces: <error_type>

properties:
  # Algebraic properties that must hold (for property-based testing)
  - name: <property_name>
    law: <formal statement>
    description: <plain english>

tests:
  # Concrete input/output pairs
  - name: <test_name>
    input: <value>
    expect: <value>

  # Property tests (agent generates cases)
  - name: <property_test_name>
    property: <property_name>
    generate: <how to generate test cases>
```

## Type System

Primitives communicate through a minimal type system:

| Type | Description |
|------|-------------|
| `Any` | Any value |
| `None` | No value / unit |
| `Bool` | true / false |
| `Num` | Numeric value |
| `Text` | String value |
| `List<T>` | Ordered collection of T |
| `Map<K,V>` | Key-value pairs |
| `Option<T>` | T or None |
| `Result<T,E>` | T or Error E |
| `Stream<T>` | Async sequence of T |
| `Block<I,O>` | A composable unit with input I, output O |

## Composition Rules

Blocks compose when output types align with input types:

```
Block<A,B> → Block<B,C> = Block<A,C>  # Pipe
[Block<A,B>, Block<A,C>] = Block<A, (B,C)>  # Parallel
```

## Directory Structure

```
primitives/
├── SPEC_FORMAT.md          # This file
├── TYPE_SYSTEM.md          # Type definitions
├── data_flow/
│   ├── transform.yaml
│   ├── filter.yaml
│   ├── split.yaml
│   └── merge.yaml
├── state/
│   ├── store.yaml
│   ├── retrieve.yaml
│   └── watch.yaml
├── control/
│   ├── sequence.yaml
│   ├── branch.yaml
│   ├── repeat.yaml
│   └── parallel.yaml
└── composition/
    ├── pipe.yaml
    ├── wrap.yaml
    └── group.yaml
```
