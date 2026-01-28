#!/usr/bin/env python3
"""
Interactive Primitives REPL

Try:
  > T("x => x * 2")(5)
  > P(T("x => x + 1"), T("x => x * 2"))(5)
  > F("x => x > 0")([-1, 2, -3, 4])
  > B("x => x > 0", "x => 'positive'", "x => 'negative'")(-5)
"""

import sys
from primitives import (
    T, F, B, P, R, run,
    Primitives, Store, Runtime,
    NONE, Some, Err, Block
)

def main():
    print("=" * 60)
    print("  PRIMITIVES REPL")
    print("=" * 60)
    print("""
Available:
  T(fn)              Transform
  F(pred)            Filter
  B(cond, then, else) Branch
  P(*blocks)         Pipe
  R(cond, block)     Repeat
  Store()            Mutable state

Examples:
  T("x => x * 2")(5)
  P(T("x => x + 1"), T("x => x * 2"))(5)
  F("x => x % 2 == 0")([1,2,3,4,5,6])

Type 'quit' to exit.
""")

    # Create a shared store for the session
    store = Store()

    # Execution context
    ctx = {
        "T": T, "F": F, "B": B, "P": P, "R": R,
        "run": run,
        "Primitives": Primitives,
        "Store": Store,
        "store": store,
        "NONE": NONE,
        "Some": Some,
        "Err": Err,
        "Block": Block,
    }

    while True:
        try:
            line = input("\n> ").strip()
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                print("Bye!")
                break

            # Evaluate the expression
            result = eval(line, ctx)
            print(f"=> {result}")

        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
