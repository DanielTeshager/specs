#!/usr/bin/env python3
"""
Examples: Primitives in action

Run with: python examples.py
"""

from primitives import T, F, B, P, R, run, Primitives, Store, NONE, Some


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# =============================================================================
# EXAMPLE 1: Basic transforms
# =============================================================================

separator("1. BASIC TRANSFORMS")

# Single transform
increment = T("x => x + 1")
print(f"increment(5) = {run(increment, 5)}")

double = T("x => x * 2")
print(f"double(5) = {run(double, 5)}")

# Chained transforms (pipe)
inc_then_double = P(increment, double)
print(f"inc_then_double(5) = {run(inc_then_double, 5)}")  # (5+1)*2 = 12

double_then_inc = P(double, increment)
print(f"double_then_inc(5) = {run(double_then_inc, 5)}")  # (5*2)+1 = 11


# =============================================================================
# EXAMPLE 2: Filtering
# =============================================================================

separator("2. FILTERING")

positive = F("x => x > 0")
print(f"positive(5) = {run(positive, 5)}")
print(f"positive(-3) = {run(positive, -3)}")

# Filter list
even = F("x => x % 2 == 0")
print(f"even([1,2,3,4,5,6]) = {run(even, [1,2,3,4,5,6])}")


# =============================================================================
# EXAMPLE 3: Branching
# =============================================================================

separator("3. BRANCHING")

sign = B(
    "x => x >= 0",
    "x => 'positive'",
    "x => 'negative'"
)
print(f"sign(5) = {run(sign, 5)}")
print(f"sign(-3) = {run(sign, -3)}")

# Fizzbuzz single number - using nested branches instead of complex ternary
fizzbuzz = B(
    "x => x % 15 == 0",
    "x => 'fizzbuzz'",
    "x => x % 3 == 0 ? 'fizz' : x"
)
fizzbuzz_full = P(
    B("x => x % 15 == 0", "x => 'fizzbuzz'",
      B("x => x % 3 == 0", "x => 'fizz'",
        B("x => x % 5 == 0", "x => 'buzz'", "x => x")))
)
print(f"fizzbuzz(15) = {run(fizzbuzz_full, 15)}")
print(f"fizzbuzz(9) = {run(fizzbuzz_full, 9)}")
print(f"fizzbuzz(10) = {run(fizzbuzz_full, 10)}")
print(f"fizzbuzz(7) = {run(fizzbuzz_full, 7)}")


# =============================================================================
# EXAMPLE 4: Object manipulation
# =============================================================================

separator("4. OBJECT MANIPULATION")

get_name = T("user => user.name")
user = {"name": "Alice", "age": 30}
print(f"get_name({user}) = {run(get_name, user)}")

add_fullname = T("u => {name: u.first + ' ' + u.last, age: u.age}")
user2 = {"first": "Bob", "last": "Smith", "age": 25}
print(f"add_fullname({user2}) = {run(add_fullname, user2)}")


# =============================================================================
# EXAMPLE 5: Pipelines (composition)
# =============================================================================

separator("5. DATA PIPELINES")

# Process list: filter evens, double them
filter_evens = F("x => x % 2 == 0")
double_each = T("xs => map(xs, n => n * 2)")  # map applies fn to each element
process_numbers = P(filter_evens, double_each)
print(f"filter_evens([1,2,3,4,5,6]) = {run(filter_evens, [1,2,3,4,5,6])}")
print(f"double_each([2,4,6]) = {run(double_each, [2,4,6])}")
print(f"process_numbers([1,2,3,4,5,6]) = {run(process_numbers, [1,2,3,4,5,6])}")

# User validation pipeline
check_age = B("u => u.age >= 18", "u => u", "u => {error: 'too young'}")
check_name = B("u => u.name != null", "u => u", "u => {error: 'no name'}")

print(f"check_age(Alice, 25) = {run(check_age, {'name': 'Alice', 'age': 25})}")
print(f"check_age(Bob, 16) = {run(check_age, {'name': 'Bob', 'age': 16})}")


# =============================================================================
# EXAMPLE 6: State
# =============================================================================

separator("6. STATE")

store = Store()
store.set("count", 0)
print(f"Initial: {store.get('count')}")

store.update("count", lambda x: x + 1)
print(f"After increment: {store.get('count')}")

store.update("count", lambda x: x + 1)
store.update("count", lambda x: x + 1)
print(f"After 2 more: {store.get('count')}")


# =============================================================================
# EXAMPLE 7: Repeat (loops)
# =============================================================================

separator("7. REPEAT (LOOPS)")

# Count up to 10
count_up = R(
    "x => x < 10",
    T("x => x + 1")
)
print(f"count_up(0) = {run(count_up, 0)}")
print(f"count_up(7) = {run(count_up, 7)}")

# Collatz sequence step
collatz_step = B(
    "n => n % 2 == 0",
    "n => n / 2",
    "n => n * 3 + 1"  # spaces around operators
)

# Run until we hit 1
collatz = R(
    "n => n > 1",
    collatz_step
)
print(f"collatz(27) = {run(collatz, 27)}")  # Should be 1


# =============================================================================
# EXAMPLE 8: Real-world - Price calculator
# =============================================================================

separator("8. REAL-WORLD: PRICE CALCULATOR")

# Pricing rules as primitives
apply_discount = B(
    "order => order.total > 100",
    "order => {total: order.total * 0.9, discount: true}",
    "order => {total: order.total, discount: false}"
)

add_tax = T("order => {total: order.total * 1.08, tax: order.total * 0.08, discount: order.discount}")

add_shipping = B(
    "order => order.total > 50",
    "order => {total: order.total, shipping: 0, discount: order.discount}",
    "order => {total: order.total + 10, shipping: 10, discount: order.discount}"
)

calculate_price = P(apply_discount, add_tax, add_shipping)

order1 = {"total": 150}
order2 = {"total": 40}

print(f"$150 order: {run(calculate_price, order1)}")
print(f"$40 order: {run(calculate_price, order2)}")


# =============================================================================
# EXAMPLE 9: Parallel processing
# =============================================================================

separator("9. PARALLEL (FANOUT)")

# Run multiple validations in parallel
validations = Primitives.parallel(
    T("x => x.name != null"),   # has name?
    T("x => x.age >= 18"),       # adult?
    T("x => x.email != null")   # has email?
)

user3 = {"name": "Carol", "age": 25, "email": "carol@example.com"}
user4 = {"name": "Dan", "age": 16, "email": None}

print(f"validate Carol: {run(validations, user3)}")
print(f"validate Dan: {run(validations, user4)}")


# =============================================================================
# SUMMARY
# =============================================================================

separator("SUMMARY: THE PRIMITIVES")

print("""
T(fn)           - Transform: apply function to data
F(pred)         - Filter: pass if predicate true
B(cond, t, e)   - Branch: if/else
P(*blocks)      - Pipe: chain blocks
R(cond, block)  - Repeat: loop while condition true
Parallel        - Fanout: same input to multiple blocks
Store           - Mutable state

These compose into anything.
""")
