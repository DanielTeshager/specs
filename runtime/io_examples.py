#!/usr/bin/env python3
"""
IO Primitives Examples

Demonstrates IO primitives with both mock (testing) and real (production) adapters.
"""

from primitives import T, F, B, P, run
from io_adapter import use_mock, use_real, MockAdapter
from io_primitives import (
    file_read, file_write, file_exists, file_list,
    http_get, env, time_now, random, uuid, stdin, stdout, log,
    unwrap, unwrap_or, map_ok, is_ok
)


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# =============================================================================
# EXAMPLE 1: File Operations with Mock Adapter
# =============================================================================

separator("1. FILE OPERATIONS (Mock Adapter)")

# Set up mock filesystem
mock = use_mock(
    mock_fs={
        "config.json": '{"debug": true, "port": 8080}',
        "data/users.txt": "alice\nbob\ncharlie",
    }
)

# Read a file
read_config = file_read("config.json")
result = run(read_config, None)
print(f"Read config.json: {result}")

# Chain: read file -> parse -> transform
import json
process_config = P(
    file_read("config.json"),
    unwrap(),
    T("text => text")  # In real code, would parse JSON
)
print(f"Process config: {run(process_config, None)}")

# Check if file exists
check = file_exists("config.json")
print(f"config.json exists: {run(check, None)}")
print(f"missing.txt exists: {run(file_exists('missing.txt'), None)}")

# Write a file
write_result = run(file_write("output.txt"), "Hello, World!")
print(f"Write result: {write_result}")
print(f"Mock filesystem after write: {mock.fs.get('output.txt')}")


# =============================================================================
# EXAMPLE 2: HTTP Requests with Mock Adapter
# =============================================================================

separator("2. HTTP REQUESTS (Mock Adapter)")

use_mock(
    mock_http={
        "https://api.example.com/users": {
            "status": 200,
            "body": '[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]'
        },
        "https://api.example.com/error": {
            "status": 500,
            "body": "Internal Server Error"
        }
    }
)

# Simple GET request
get_users = http_get("https://api.example.com/users")
result = run(get_users, None)
print(f"GET /users: status={result.value['status']}")
print(f"  body: {result.value['body'][:50]}...")

# Handle errors gracefully
get_with_fallback = P(
    http_get("https://api.example.com/error"),
    unwrap_or({"status": 0, "body": "fallback"})
)
result = run(get_with_fallback, None)
print(f"GET /error with fallback: {result}")


# =============================================================================
# EXAMPLE 3: Environment Variables
# =============================================================================

separator("3. ENVIRONMENT VARIABLES (Mock Adapter)")

use_mock(
    mock_env={
        "HOME": "/home/user",
        "DEBUG": "true",
        "PORT": "3000"
    }
)

# Get single var
home = run(env("HOME"), None)
print(f"HOME: {home}")

# Get with default
missing = run(env("UNDEFINED", "default_value"), None)
print(f"UNDEFINED (with default): {missing}")

# Pipeline: get PORT, convert to number, add 1000
port_pipeline = P(
    env("PORT", "8080"),
    T("p => toNumber(p)"),
    T("p => p + 1000")
)
print(f"PORT + 1000: {run(port_pipeline, None)}")


# =============================================================================
# EXAMPLE 4: Time and Random
# =============================================================================

separator("4. TIME AND RANDOM (Mock Adapter)")

use_mock(
    mock_time=1704067200000,  # 2024-01-01T00:00:00Z
    mock_random=[0.25, 0.5, 0.75]
)

# Get time
now = run(time_now(), None)
print(f"Current time: {now} ms")

# Get random numbers
r1 = run(random(0, 100), None)
r2 = run(random(0, 100), None)
r3 = run(random(0, 100), None)
print(f"Random numbers: {r1}, {r2}, {r3}")

# UUID
id = run(uuid(), None)
print(f"UUID: {id}")


# =============================================================================
# EXAMPLE 5: Complete Pipeline - Config Loader
# =============================================================================

separator("5. COMPLETE PIPELINE: Config Loader")

mock = use_mock(
    mock_fs={
        "app.config": "port=8080\ndebug=true\nname=MyApp"
    },
    mock_env={
        "APP_PORT": "9000",  # Override from environment
    }
)

# Pipeline: Read config file, parse it, merge with env overrides
def parse_config(text):
    """Parse key=value config format"""
    config = {}
    for line in text.split("\n"):
        if "=" in line:
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config

# Build the pipeline using primitives
config_loader = P(
    file_read("app.config"),
    unwrap_or(""),
    T("text => text")  # Would use parse_config in real implementation
)

result = run(config_loader, None)
print(f"Loaded config: {result}")

# In a real implementation, we'd compose with env overrides


# =============================================================================
# EXAMPLE 6: Console I/O
# =============================================================================

separator("6. CONSOLE I/O (Mock Adapter)")

mock = use_mock(
    mock_stdin="user_input_here"
)

# Write to stdout
run(stdout(), "Hello from primitives!")
print(f"Captured stdout: {mock.stdout_buffer!r}")

# Log structured data
run(log("info"), {"message": "User logged in", "user_id": 123})
print(f"Captured logs: {mock.log_entries}")


# =============================================================================
# EXAMPLE 7: Real Adapter Demo
# =============================================================================

separator("7. REAL ADAPTER DEMO")

use_real()

# Get actual environment variable
home = run(env("HOME", "/default"), None)
print(f"Real HOME: {home}")

# Get actual time
now = run(time_now(), None)
print(f"Real timestamp: {now}")

# Generate real UUID
real_uuid = run(uuid(), None)
print(f"Real UUID: {real_uuid}")

# Generate real random
real_random = run(random(1, 100), None)
print(f"Real random (1-100): {real_random}")


# =============================================================================
# EXAMPLE 8: Error Handling Pipeline
# =============================================================================

separator("8. ERROR HANDLING PIPELINE")

use_mock(mock_fs={})

# Try to read missing file, handle gracefully
safe_read = P(
    file_read("missing.txt"),
    B("r => r.value != null",  # Check if Ok
      "r => r.value",
      "r => 'FILE NOT FOUND'")
)

# Actually we need to check result type
result = run(file_read("missing.txt"), None)
print(f"Read missing file: {result}")

# With unwrap_or
safe_result = run(P(file_read("missing.txt"), unwrap_or("default content")), None)
print(f"Safe read with fallback: {safe_result}")


# =============================================================================
# SUMMARY
# =============================================================================

separator("SUMMARY: IO PRIMITIVES")

print("""
SOURCES (data flows IN):
  file_read(path)      - Read file contents
  file_exists(path)    - Check if file exists
  file_list(path)      - List directory
  http_get(url)        - HTTP GET request
  http_post(url)       - HTTP POST request
  env(name, default)   - Environment variable
  time_now()           - Current timestamp
  random(min, max)     - Random number
  uuid()               - Random UUID
  stdin(prompt)        - Read user input
  args()               - Command-line arguments

SINKS (data flows OUT):
  file_write(path)     - Write to file
  file_append(path)    - Append to file
  file_delete(path)    - Delete file
  stdout()             - Write to console
  stderr()             - Write to error stream
  log(level)           - Structured logging

RESULT HANDLING:
  unwrap()             - Extract Ok value, raise on Err
  unwrap_or(default)   - Extract Ok value, use default on Err
  map_ok(fn)           - Transform Ok value
  is_ok()              - Check if Ok

ADAPTERS:
  use_mock(**setup)    - Switch to mock adapter (testing)
  use_real()           - Switch to real adapter (production)
""")
