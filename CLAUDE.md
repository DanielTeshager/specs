# Using Claude Code with Primitives

Claude Code is the LLM layer. No external API needed.

## The Loop

```
USER: "I need X"
         │
         ▼
┌─────────────────────────────────────────┐
│            CLAUDE CODE                   │
│                                          │
│  1. Understand intent                    │
│  2. Search registry (python3 -c "...")   │
│  3. Compose spec                         │
│  4. Run tests                            │
│  5. If fail → fix → goto 4              │
│  6. Return working spec                  │
└─────────────────────────────────────────┘
         │
         ▼
USER: Gets working, tested solution
```

## How Claude Code Works With This

### 1. Search Registry

```bash
cd /Users/hcare/Documents/whenwords+
python3 -c "
from registry.registry import get_registry
r = get_registry()
for block, score in r.search('validate email')[:5]:
    print(f'{block.id}: {block.signature}')
"
```

### 2. Check Types Match

```bash
python3 -c "
from registry.registry import get_registry
r = get_registry()
for b in r.search_by_type('Text', 'Bool')[:5]:
    print(f'{b.id}: {b.signature}')
"
```

### 3. Compose & Test

```bash
python3 -c "
from runtime.primitives import T, F, B, P, run

# Compose
pipeline = P(
    T('x => x + 1'),
    T('x => x * 2')
)

# Test
assert run(pipeline, 5) == 12, 'Expected 12'
print('✓ Tests pass')
"
```

### 4. Full Example with IO

```bash
python3 -c "
from runtime.primitives import T, F, B, P, run
from runtime.io_adapter import use_mock
from runtime.io_primitives import file_read, unwrap

# Setup mock
use_mock(mock_fs={'data.txt': 'hello'})

# Compose
pipeline = P(file_read('data.txt'), unwrap())

# Test
result = run(pipeline, None)
assert result == 'hello', f'Expected hello, got {result}'
print('✓ Tests pass')
"
```

## Spec Format

When Claude Code composes a solution, output this format:

```yaml
# SPEC: <name>
# Intent: <what user asked for>

blocks:
  - id: io/file.read
    config:
      path: "input.csv"

  - id: stdlib/csv.parse
    input: step1.output

  - id: core/filter
    config:
      predicate: "row => row.age > 18"
    input: step2.output

tests:
  - name: filters_adults
    mock:
      fs:
        "input.csv": "name,age\nalice,25\nbob,17"
    expect:
      length: 1
      first_name: "alice"
```

## The Contract

1. **User says what they want** in natural language
2. **Claude Code searches** the registry for blocks
3. **Claude Code composes** them into a spec
4. **Claude Code tests** until passing
5. **User gets** working solution

No external LLM API. Claude Code is the intelligence.
