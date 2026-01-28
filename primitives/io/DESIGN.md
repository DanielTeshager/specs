# IO Primitives Design

## The Problem

IO is where purity meets reality. Every platform implements IO differently:
- File paths: `/unix/style` vs `C:\windows\style`
- Network: sockets, HTTP libraries, TLS implementations
- Encoding: UTF-8, UTF-16, platform defaults

## The Solution: Semantic Contracts

We define IO by **what it means**, not how it's done.

```
source.http.get(url) → Result<Response, Error>
```

This means: "Fetch data from this URL and return the response or an error."

Every platform must implement this contract. The spec doesn't care if it uses:
- Python's `requests`
- Rust's `reqwest`
- Node's `fetch`
- Go's `net/http`

## Boundary Principle

IO primitives are **boundaries** between:
- Pure world (deterministic, testable, composable)
- Impure world (effects, state, non-determinism)

```
┌─────────────────────────────────────────┐
│           PURE COMPUTATION              │
│  transform, filter, branch, pipe, ...   │
└──────────────────┬──────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   IO BOUNDARY     │
         │  source / sink    │
         └─────────┬─────────┘
                   │
┌──────────────────▼──────────────────────┐
│           EXTERNAL WORLD                │
│   files, network, databases, users      │
└─────────────────────────────────────────┘
```

## IO Primitive Categories

### Sources (data flows IN)
- `source.file.read` - Read file contents
- `source.http.request` - HTTP request
- `source.stdin` - User input
- `source.env` - Environment variables
- `source.time` - Current time
- `source.random` - Random values

### Sinks (data flows OUT)
- `sink.file.write` - Write file contents
- `sink.http.respond` - HTTP response
- `sink.stdout` - Console output
- `sink.stderr` - Error output
- `sink.log` - Structured logging

### Resources (lifecycle managed)
- `resource.file` - File handle
- `resource.connection` - Network connection
- `resource.transaction` - Atomic operation group

## Testing Strategy

IO primitives are tested via **adapters**:

```yaml
adapters:
  mock:
    description: In-memory fake for testing
    deterministic: true

  real:
    description: Actual platform IO
    deterministic: false
```

Tests run against mock adapters. Integration tests use real adapters.

## Error Model

All IO operations return `Result<T, IOError>`:

```yaml
IOError:
  variants:
    - NotFound: Resource doesn't exist
    - PermissionDenied: Access not allowed
    - Timeout: Operation took too long
    - ConnectionFailed: Network unreachable
    - InvalidData: Data format wrong
    - Unknown: Unexpected error
```

## Platform Manifest

Each platform implementation provides a manifest:

```yaml
platform: python-3.11
adapters:
  source.file.read: implemented
  source.http.request: implemented
  sink.stdout: implemented
  source.random: implemented
  # ... etc
```

This allows specs to declare requirements and validate platform compatibility.
