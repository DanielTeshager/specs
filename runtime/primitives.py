"""
Primitive Runtime Interpreter

The spec IS the program. This interpreter executes primitive compositions directly.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import operator
import re


# =============================================================================
# CORE: Values and Blocks
# =============================================================================

class None_:
    """Explicit None value (distinct from Python None)"""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __repr__(self):
        return "None_"
    def __bool__(self):
        return False

NONE = None_()


@dataclass
class Some:
    """Optional value present"""
    value: Any
    def __repr__(self):
        return f"Some({self.value!r})"


@dataclass
class Err:
    """Error value"""
    reason: str
    def __repr__(self):
        return f"Err({self.reason!r})"


@dataclass
class Block:
    """A composable unit of computation"""
    name: str
    fn: Callable[[Any], Any]

    def __call__(self, input_: Any) -> Any:
        return self.fn(input_)

    def __repr__(self):
        return f"Block({self.name})"


# =============================================================================
# EXPRESSION PARSER: Simple expression language for specs
# =============================================================================

def parse_expr(expr: str) -> Callable[[Any], Any]:
    """
    Parse simple expressions like:
    - "x => x + 1"
    - "x => x.name"
    - "x => x > 0"
    - "(a, b) => a + b"
    """
    if "=>" not in expr:
        # Literal value
        return lambda _: eval_literal(expr)

    parts = expr.split("=>", 1)
    params = parts[0].strip()
    body = parts[1].strip()

    # Parse parameters
    if params.startswith("(") and params.endswith(")"):
        param_names = [p.strip() for p in params[1:-1].split(",")]
    else:
        param_names = [params.strip()]

    def evaluate(input_: Any) -> Any:
        # Build context
        ctx = {}
        if len(param_names) == 1:
            ctx[param_names[0]] = input_
        else:
            # Multiple params - expect tuple or list input
            if isinstance(input_, (tuple, list)):
                for i, name in enumerate(param_names):
                    ctx[name] = input_[i] if i < len(input_) else NONE
            else:
                ctx[param_names[0]] = input_

        return eval_expr(body, ctx)

    return evaluate


def eval_literal(s: str) -> Any:
    """Evaluate a literal value"""
    s = s.strip()
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "null":
        return NONE
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def eval_expr(expr: str, ctx: Dict[str, Any]) -> Any:
    """Evaluate an expression in a context"""
    expr = expr.strip()

    # Object literal { key: value, ... }
    if expr.startswith("{") and expr.endswith("}"):
        return eval_object(expr, ctx)

    # Array literal [a, b, c]
    if expr.startswith("[") and expr.endswith("]"):
        return eval_array(expr, ctx)

    # Function call: fn(args) - check early, must be identifier followed by (
    # and the closing ) must match the opening one
    if "(" in expr and expr.endswith(")"):
        paren_idx = expr.index("(")
        fn_name = expr[:paren_idx]
        # Verify it looks like a function name (alphanumeric, no spaces before paren)
        if fn_name.isidentifier() or fn_name in ("filter", "map", "length", "uppercase",
                                                   "lowercase", "toString", "toNumber",
                                                   "abs", "min", "max", "sum", "keys", "values"):
            # Verify balanced parens
            depth = 0
            for i, c in enumerate(expr[paren_idx:]):
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
            if depth == 0:
                return eval_function_call(expr, ctx)

    # Ternary: cond ? then : else (check after parens balanced)
    if "?" in expr and ":" in expr:
        # Only treat as ternary if ? comes before : at same depth
        depth = 0
        q_pos = -1
        for i, c in enumerate(expr):
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "?" and depth == 0 and q_pos == -1:
                q_pos = i
        if q_pos > 0:
            return eval_ternary(expr, ctx)

    # Comparison operators - only at depth 0
    for op, fn in [("==", operator.eq), ("!=", operator.ne),
                   (">=", operator.ge), ("<=", operator.le),
                   (">", operator.gt), ("<", operator.lt)]:
        if op in expr:
            # Find op at depth 0
            idx = find_at_depth_0(expr, op)
            if idx >= 0:
                parts = [expr[:idx], expr[idx+len(op):]]
                left = eval_expr(parts[0], ctx)
                right = eval_expr(parts[1], ctx)
                return fn(left, right)

    # Logical operators
    if " && " in expr:
        idx = find_at_depth_0(expr, " && ")
        if idx >= 0:
            parts = [expr[:idx], expr[idx+4:]]
            return eval_expr(parts[0], ctx) and eval_expr(parts[1], ctx)
    if " || " in expr:
        idx = find_at_depth_0(expr, " || ")
        if idx >= 0:
            parts = [expr[:idx], expr[idx+4:]]
            return eval_expr(parts[0], ctx) or eval_expr(parts[1], ctx)

    # Arithmetic - must have spaces around operator for binary ops, at depth 0
    for op, fn in [("+", operator.add), ("-", operator.sub),
                   ("*", operator.mul), ("/", operator.truediv),
                   ("%", operator.mod)]:
        spaced_op = f" {op} "
        if spaced_op in expr:
            # Find rightmost occurrence at depth 0
            idx = find_at_depth_0(expr, spaced_op, rightmost=True)
            if idx >= 0:
                left_part = expr[:idx].strip()
                right_part = expr[idx+len(spaced_op):].strip()
                if left_part and right_part:
                    left = eval_expr(left_part, ctx)
                    right = eval_expr(right_part, ctx)
                    if isinstance(left, str) and op == "+":
                        return left + str(right)
                    return fn(left, right)

    # Property access: x.foo.bar
    if "." in expr and not expr[0].isdigit():
        return eval_property_access(expr, ctx)

    # Array index: x[0]
    if "[" in expr and expr.endswith("]"):
        return eval_index_access(expr, ctx)

    # Variable lookup
    if expr in ctx:
        return ctx[expr]

    # Literal
    return eval_literal(expr)


def find_at_depth_0(expr: str, target: str, rightmost: bool = False) -> int:
    """Find target string in expr only at depth 0 (outside parens/brackets)"""
    depth = 0
    found = -1
    i = 0
    while i < len(expr) - len(target) + 1:
        c = expr[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and expr[i:i+len(target)] == target:
            if rightmost:
                found = i
            else:
                return i
        i += 1
    return found


def eval_object(expr: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate object literal"""
    inner = expr[1:-1].strip()
    if not inner:
        return {}

    result = {}
    # Simple parsing - doesn't handle nested objects perfectly
    depth = 0
    current = ""
    for char in inner:
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        if char == "," and depth == 0:
            if ":" in current:
                k, v = current.split(":", 1)
                result[k.strip()] = eval_expr(v.strip(), ctx)
            current = ""
        else:
            current += char

    if current.strip() and ":" in current:
        k, v = current.split(":", 1)
        result[k.strip()] = eval_expr(v.strip(), ctx)

    return result


def eval_array(expr: str, ctx: Dict[str, Any]) -> List[Any]:
    """Evaluate array literal"""
    inner = expr[1:-1].strip()
    if not inner:
        return []

    result = []
    depth = 0
    current = ""
    for char in inner:
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        if char == "," and depth == 0:
            result.append(eval_expr(current.strip(), ctx))
            current = ""
        else:
            current += char

    if current.strip():
        result.append(eval_expr(current.strip(), ctx))

    return result


def eval_ternary(expr: str, ctx: Dict[str, Any]) -> Any:
    """Evaluate ternary expression"""
    q_idx = expr.index("?")
    c_idx = expr.rindex(":")

    cond = eval_expr(expr[:q_idx], ctx)
    then_val = eval_expr(expr[q_idx+1:c_idx], ctx)
    else_val = eval_expr(expr[c_idx+1:], ctx)

    return then_val if cond else else_val


def eval_property_access(expr: str, ctx: Dict[str, Any]) -> Any:
    """Evaluate property access like x.foo.bar"""
    parts = expr.split(".")
    value = ctx.get(parts[0], eval_literal(parts[0]))

    for part in parts[1:]:
        if isinstance(value, dict):
            value = value.get(part, NONE)
        elif hasattr(value, part):
            value = getattr(value, part)
        else:
            return NONE

    return value


def eval_index_access(expr: str, ctx: Dict[str, Any]) -> Any:
    """Evaluate array access like x[0]"""
    bracket_idx = expr.index("[")
    base = eval_expr(expr[:bracket_idx], ctx)
    index = eval_expr(expr[bracket_idx+1:-1], ctx)

    if isinstance(base, (list, tuple)):
        return base[int(index)] if int(index) < len(base) else NONE
    if isinstance(base, dict):
        return base.get(index, NONE)
    return NONE


def eval_function_call(expr: str, ctx: Dict[str, Any]) -> Any:
    """Evaluate built-in function calls"""
    paren_idx = expr.index("(")
    fn_name = expr[:paren_idx]
    args_str = expr[paren_idx+1:-1]

    # Built-in functions
    builtins = {
        "length": lambda x: len(x) if hasattr(x, "__len__") else 0,
        "uppercase": lambda x: str(x).upper(),
        "lowercase": lambda x: str(x).lower(),
        "toString": lambda x: str(x),
        "toNumber": lambda x: float(x) if "." in str(x) else int(x),
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "keys": lambda x: list(x.keys()) if isinstance(x, dict) else [],
        "values": lambda x: list(x.values()) if isinstance(x, dict) else [],
    }

    if fn_name in builtins:
        arg = eval_expr(args_str, ctx)
        return builtins[fn_name](arg)

    # filter(list, predicate)
    if fn_name == "filter":
        parts = split_args(args_str)
        lst = eval_expr(parts[0], ctx)
        pred = parse_expr(parts[1])
        return [x for x in lst if pred(x)]

    # map(list, fn)
    if fn_name == "map":
        parts = split_args(args_str)
        lst = eval_expr(parts[0], ctx)
        fn = parse_expr(parts[1])
        return [fn(x) for x in lst]

    return NONE


def split_args(s: str) -> List[str]:
    """Split function arguments respecting nesting"""
    result = []
    depth = 0
    current = ""
    for char in s:
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        if char == "," and depth == 0:
            result.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        result.append(current.strip())
    return result


# =============================================================================
# PRIMITIVES: The fundamental building blocks
# =============================================================================

class Primitives:
    """Factory for creating primitive blocks"""

    @staticmethod
    def transform(fn: str) -> Block:
        """Apply pure function to input"""
        func = parse_expr(fn)
        return Block(f"transform({fn})", func)

    @staticmethod
    def filter(predicate: str) -> Block:
        """Pass value if predicate true, else NONE"""
        pred = parse_expr(predicate)
        def filter_fn(x):
            if isinstance(x, list):
                return [item for item in x if pred(item)]
            return Some(x) if pred(x) else NONE
        return Block(f"filter({predicate})", filter_fn)

    @staticmethod
    def branch(condition: str, then, else_) -> Block:
        """Route based on condition. then/else can be strings or Blocks."""
        cond = parse_expr(condition)
        then_fn = then if callable(then) else parse_expr(then)
        else_fn = else_ if callable(else_) else parse_expr(else_)
        def branch_fn(x):
            if cond(x):
                return then_fn(x)
            return else_fn(x)
        return Block(f"branch({condition})", branch_fn)

    @staticmethod
    def pipe(*blocks: Block) -> Block:
        """Chain blocks: output of each feeds input of next"""
        def pipe_fn(x):
            result = x
            for block in blocks:
                result = block(result)
            return result
        names = " | ".join(b.name for b in blocks)
        return Block(f"pipe({names})", pipe_fn)

    @staticmethod
    def parallel(*blocks: Block) -> Block:
        """Run blocks in parallel, collect results"""
        def parallel_fn(x):
            return tuple(block(x) for block in blocks)
        return Block(f"parallel({len(blocks)} blocks)", parallel_fn)

    @staticmethod
    def fanout(*blocks: Block) -> Block:
        """Send same input to multiple blocks"""
        return Primitives.parallel(*blocks)

    @staticmethod
    def merge(fn: str) -> Block:
        """Combine multiple inputs into one"""
        func = parse_expr(fn)
        return Block(f"merge({fn})", func)

    @staticmethod
    def repeat(condition: str, block: Block, max_iterations: int = 1000) -> Block:
        """Repeat block while condition true"""
        cond = parse_expr(condition)
        def repeat_fn(x):
            result = x
            for _ in range(max_iterations):
                if not cond(result):
                    break
                result = block(result)
            return result
        return Block(f"repeat({condition})", repeat_fn)


# =============================================================================
# STATE: Mutable storage
# =============================================================================

class Store:
    """Mutable key-value store"""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str) -> Any:
        return self._data.get(key, NONE)

    def update(self, key: str, fn: Callable[[Any], Any]) -> None:
        self._data[key] = fn(self._data.get(key, NONE))

    def __repr__(self):
        return f"Store({self._data})"


# =============================================================================
# RUNTIME: Execute primitive compositions
# =============================================================================

class Runtime:
    """Execute primitive specs"""

    def __init__(self):
        self.store = Store()
        self.blocks: Dict[str, Block] = {}

    def register(self, name: str, block: Block) -> None:
        """Register a named block"""
        self.blocks[name] = block

    def run(self, block: Block, input_: Any = NONE) -> Any:
        """Execute a block with input"""
        return block(input_)

    def pipe(self, *block_names: str) -> Block:
        """Create pipe from registered block names"""
        blocks = [self.blocks[n] for n in block_names]
        return Primitives.pipe(*blocks)


# =============================================================================
# CONVENIENCE: Shorthand constructors
# =============================================================================

# Shortcuts
T = Primitives.transform
F = Primitives.filter
B = Primitives.branch
P = Primitives.pipe
R = Primitives.repeat


def run(block: Block, input_: Any = NONE) -> Any:
    """Quick run a block"""
    return block(input_)
