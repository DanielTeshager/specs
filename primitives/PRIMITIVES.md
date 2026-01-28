# The Primitives

A complete catalog of computational building blocks.

## IO Primitives (Platform-Agnostic)

| Primitive | Type | Description |
|-----------|------|-------------|
| **source.file.read** | Source | Read file contents |
| **source.file.exists** | Source | Check if file exists |
| **source.file.list** | Source | List directory contents |
| **source.http.request** | Source | HTTP request |
| **source.env.get** | Source | Environment variable |
| **source.time.now** | Source | Current timestamp |
| **source.random.number** | Source | Random number |
| **source.random.uuid** | Source | Random UUID |
| **source.stdin** | Source | User input |
| **source.args** | Source | Command-line arguments |
| **sink.file.write** | Sink | Write to file |
| **sink.file.delete** | Sink | Delete file |
| **sink.stdout** | Sink | Console output |
| **sink.stderr** | Sink | Error output |
| **sink.log** | Sink | Structured logging |
| **sink.exit** | Sink | Exit process |

All IO primitives use the **Adapter Pattern** for platform independence:
- Same spec works on Python, Node, Rust, Go, Browser
- Mock adapter for deterministic testing
- Real adapter for production

## Data Flow

| Primitive | Input | Output | Description |
|-----------|-------|--------|-------------|
| **transform** | `(data, fn)` | `data'` | Apply pure function to data |
| **filter** | `(data, predicate)` | `Option<data>` | Pass data if predicate true |
| **split** | `(data, fn)` | `[data, ...]` | Route one input to many outputs |
| **merge** | `[data, ...]` | `data` | Combine many inputs to one |
| **source** | `trigger` | `data` | Produce data (IO boundary) |
| **sink** | `data` | `effect` | Consume data (IO boundary) |

## State

| Primitive | Input | Output | Description |
|-----------|-------|--------|-------------|
| **store** | `(key, value)` | `Result<>` | Persist a value |
| **retrieve** | `key` | `Option<value>` | Get stored value |
| **update** | `(key, fn)` | `Result<>` | Modify stored value atomically |
| **watch** | `(key, predicate)` | `Stream<event>` | Emit when state changes |

## Control

| Primitive | Input | Output | Description |
|-----------|-------|--------|-------------|
| **sequence** | `[A, B, ...]` | `last output` | Execute in order |
| **branch** | `(cond, data, then, else)` | `output` | Conditional execution |
| **repeat** | `(cond, block)` | `accumulated` | Loop until condition |
| **parallel** | `[A, B, ...]` | `[outputs]` | Concurrent execution |
| **wait** | `condition` | `signal` | Block until condition |
| **race** | `[A, B, ...]` | `first output` | Return first to complete |

## Composition

| Primitive | Input | Output | Description |
|-----------|-------|--------|-------------|
| **pipe** | `(A, B)` | `Block<A.in, B.out>` | Chain blocks |
| **group** | `{name: Block, ...}` | `Block` | Bundle into component |
| **wrap** | `(block, behavior)` | `Block` | Add cross-cutting concern |
| **fanout** | `(data, [blocks])` | `[outputs]` | Send same input to many |
| **fanin** | `([data], block)` | `output` | Collect many for one block |

## Error Handling

| Primitive | Input | Output | Description |
|-----------|-------|--------|-------------|
| **try** | `block` | `Result<out, err>` | Catch errors |
| **recover** | `(block, handler)` | `output` | Handle errors with fallback |
| **retry** | `(block, policy)` | `output` | Retry on failure |
| **timeout** | `(block, duration)` | `Result<out, timeout>` | Fail if too slow |

## Communication

| Primitive | Input | Output | Description |
|-----------|-------|--------|-------------|
| **send** | `(channel, data)` | `Result<>` | Push to channel |
| **receive** | `channel` | `data` | Pull from channel |
| **publish** | `(topic, data)` | `Result<>` | Broadcast to subscribers |
| **subscribe** | `topic` | `Stream<data>` | Receive broadcasts |
| **request** | `(endpoint, data)` | `Result<response>` | Sync request-response |

---

## Completeness Argument

These primitives are sufficient because:

1. **Turing complete**: `branch` + `repeat` + `store` = any computation
2. **IO covered**: `source` + `sink` = all external interaction
3. **Composition**: `pipe` + `group` = arbitrary complexity
4. **Concurrency**: `parallel` + `race` + `wait` = async patterns
5. **Errors**: `try` + `recover` = fault tolerance
6. **Communication**: `send` + `receive` + `publish` = any messaging pattern

Any program can be expressed as a composition of these primitives.

---

## Design Principles

### 1. Orthogonality
Each primitive does one thing. No overlap. `transform` doesn't filter. `filter` doesn't branch.

### 2. Composability
Output types match input types. Any primitive can connect to any other (when types align).

### 3. Testability
Every primitive has:
- Concrete test cases (input → expected output)
- Algebraic properties (laws that must hold)
- Edge case coverage

### 4. Language Agnosticism
Specs are semantic, not syntactic. "Transform applies a function" means the same thing in any language.

### 5. Minimality
If it can be built from other primitives, it's not a primitive. It's a component.

---

## What's NOT a Primitive

These are **compositions**, not primitives:

| Concept | Composition |
|---------|-------------|
| Map over list | `transform` with list-aware fn |
| Reduce/fold | `repeat` + `update` |
| HTTP request | `source` (network) + `transform` (parse) |
| Database query | `request` + `transform` |
| Validation | `pipe` of `filter` blocks |
| State machine | `group` of `branch` + `store` |
| Event loop | `repeat` + `receive` + `branch` |
| Middleware | `wrap` |
| Pipeline | Chain of `pipe` |
| Saga/workflow | `sequence` of `try` + `recover` |
