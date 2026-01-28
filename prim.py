#!/usr/bin/env python3
"""
prim - Primitives CLI

Interactive tool to search, wire, and run blocks.

Usage:
  python prim.py

Commands:
  search <query>     - Find blocks by name/description
  type <in> <out>    - Find blocks by type signature
  info <block>       - Show block details
  wire               - Start building a flow
  run <flow>         - Execute a flow
  list               - List all blocks
  help               - Show help
"""

import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'registry'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'runtime'))

from registry import get_registry, WiringEngine, FlowStep, Block, TypeSignature, BlockMetrics
from primitives import T, F, B, P, run, NONE
from io_adapter import use_mock, use_real, get_adapter
from io_primitives import (
    file_read, file_write, file_exists,
    http_get, env, time_now, random, uuid,
    stdout, log, unwrap, unwrap_or
)


class PrimCLI:
    def __init__(self):
        self.registry = get_registry()
        self.wiring = WiringEngine(self.registry)
        self.current_flow = []
        self.variables = {}

    def run(self):
        print("=" * 60)
        print("  PRIM - Primitives CLI")
        print("=" * 60)
        print("\nType 'help' for commands, 'quit' to exit.\n")

        while True:
            try:
                line = input("prim> ").strip()
                if not line:
                    continue
                if line.lower() in ('quit', 'exit', 'q'):
                    print("Bye!")
                    break
                self.execute(line)
            except KeyboardInterrupt:
                print("\nBye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    def execute(self, line: str):
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        commands = {
            'help': self.cmd_help,
            'search': self.cmd_search,
            's': self.cmd_search,
            'type': self.cmd_type,
            't': self.cmd_type,
            'info': self.cmd_info,
            'i': self.cmd_info,
            'list': self.cmd_list,
            'ls': self.cmd_list,
            'wire': self.cmd_wire,
            'w': self.cmd_wire,
            'flow': self.cmd_flow,
            'run': self.cmd_run,
            'r': self.cmd_run,
            'test': self.cmd_test,
            'eval': self.cmd_eval,
            'e': self.cmd_eval,
        }

        if cmd in commands:
            commands[cmd](args)
        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for available commands.")

    def cmd_help(self, args):
        print("""
SEARCH & DISCOVER
  search <query>      Find blocks (alias: s)
                      Example: search validate email

  type <in> → <out>   Find by type signature (alias: t)
                      Example: type Text → Bool

  info <block>        Show block details (alias: i)
                      Example: info stdlib/email.validate

  list [category]     List all blocks (alias: ls)
                      Example: list io

BUILD FLOWS
  wire                Start interactive flow builder (alias: w)
  flow                Show current flow
  run                 Execute current flow (alias: r)

TEST & EVALUATE
  test <block>        Run block's test suite
  eval <expr>         Evaluate a primitive expression (alias: e)
                      Example: eval T("x => x * 2")(5)

OTHER
  help                Show this help
  quit                Exit (alias: q)
""")

    def cmd_search(self, query):
        if not query:
            print("Usage: search <query>")
            print("Example: search validate email")
            return

        results = self.registry.search(query, limit=10)
        if not results:
            print(f"No blocks found for '{query}'")
            return

        print(f"\nResults for '{query}':\n")
        for block, score in results:
            quality = block.metrics.quality_score
            uses = block.metrics.usage_count
            print(f"  {block.full_name}")
            print(f"    {block.description[:60]}")
            print(f"    Type: {block.signature} | Quality: {quality:.0%} | Uses: {uses:,}")
            print()

    def cmd_type(self, args):
        # Parse "Text → Bool" or "Text Bool" or "Text -> Bool"
        args = args.replace('→', '->').replace('->', ' ').strip()
        parts = args.split()

        if len(parts) < 2:
            print("Usage: type <input_type> <output_type>")
            print("Example: type Text Bool")
            return

        input_type = parts[0]
        output_type = parts[1]

        results = self.registry.search_by_type(input_type, output_type, limit=10)
        if not results:
            print(f"No blocks found: {input_type} → {output_type}")
            return

        print(f"\nBlocks: {input_type} → {output_type}\n")
        for block in results:
            print(f"  {block.full_name}: {block.signature}")
            print(f"    {block.description[:50]}")
            print()

    def cmd_info(self, name):
        if not name:
            print("Usage: info <block_name>")
            return

        # Try exact match first
        block = self.registry.get(name)
        if not block:
            block = self.registry.get_latest(name)
        if not block:
            # Search
            results = self.registry.search(name, limit=1)
            if results:
                block = results[0][0]

        if not block:
            print(f"Block not found: {name}")
            return

        print(f"\n{'='*50}")
        print(f"  {block.id}")
        print('='*50)
        print(f"\n  {block.description}\n")
        print(f"  Type:     {block.signature}")
        print(f"  Category: {block.category}")
        print(f"  Tags:     {', '.join(block.tags)}")
        print()
        print(f"  Metrics:")
        print(f"    Tests:     {block.metrics.test_count} ({block.metrics.test_pass_rate:.1%} pass)")
        print(f"    Usage:     {block.metrics.usage_count:,}")
        print(f"    Quality:   {block.metrics.quality_score:.0%}")
        print()

        # Show similar
        similar = self.registry.find_similar(block.id)
        if similar:
            print("  Similar blocks:")
            for s in similar[:3]:
                print(f"    - {s.full_name}")
        print()

    def cmd_list(self, category):
        blocks = list(self.registry.blocks.values())

        if category:
            blocks = [b for b in blocks if category.lower() in b.category.lower()
                     or category.lower() in b.namespace.lower()]

        if not blocks:
            print(f"No blocks found in '{category}'")
            return

        # Group by namespace
        by_ns = {}
        for b in blocks:
            if b.namespace not in by_ns:
                by_ns[b.namespace] = []
            by_ns[b.namespace].append(b)

        print()
        for ns in sorted(by_ns.keys()):
            print(f"  {ns}/")
            for b in sorted(by_ns[ns], key=lambda x: x.name):
                print(f"    {b.name}: {b.signature}")
        print()

    def cmd_wire(self, args):
        print("\n  FLOW BUILDER")
        print("  " + "-"*40)
        print("  Commands: add <block>, connect, done, cancel")
        print("  Example:  add io/file.read")
        print()

        self.current_flow = []

        while True:
            try:
                line = input("  wire> ").strip()
                if not line:
                    continue

                parts = line.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd == 'done':
                    if self.current_flow:
                        print(f"\n  Flow saved ({len(self.current_flow)} steps)")
                    break
                elif cmd == 'cancel':
                    self.current_flow = []
                    print("  Flow cancelled")
                    break
                elif cmd == 'add':
                    self._wire_add(arg)
                elif cmd == 'show':
                    self._wire_show()
                elif cmd == 'suggest':
                    self._wire_suggest()
                elif cmd == 'help':
                    print("  add <block>  - Add block to flow")
                    print("  show         - Show current flow")
                    print("  suggest      - Suggest next blocks")
                    print("  done         - Save and exit")
                    print("  cancel       - Discard and exit")
                else:
                    print(f"  Unknown: {cmd}")

            except KeyboardInterrupt:
                print("\n  Cancelled")
                break

    def _wire_add(self, name):
        if not name:
            print("  Usage: add <block_name>")
            return

        block = self.registry.get_latest(name)
        if not block:
            results = self.registry.search(name, limit=1)
            if results:
                block = results[0][0]

        if not block:
            print(f"  Block not found: {name}")
            return

        step_name = f"step{len(self.current_flow) + 1}"
        step = FlowStep(
            name=step_name,
            block_id=block.id
        )

        # Auto-wire to previous
        if self.current_flow:
            prev = self.current_flow[-1]
            step.input_from = f"{prev.name}.output"

        self.current_flow.append(step)
        print(f"  Added: {step_name} = {block.name}")

        if step.input_from:
            print(f"         input ← {step.input_from}")

    def _wire_show(self):
        if not self.current_flow:
            print("  (empty flow)")
            return

        print()
        for step in self.current_flow:
            block = self.registry.get(step.block_id)
            name = block.name if block else step.block_id
            input_str = f" ← {step.input_from}" if step.input_from else ""
            print(f"  {step.name}: {name}{input_str}")
        print()

    def _wire_suggest(self):
        if not self.current_flow:
            print("  Start with: add <block>")
            # Suggest sources
            print("  Sources (data in):")
            for b in self.registry.search("file read http env", limit=5):
                print(f"    {b[0].full_name}")
            return

        # Get last block's output type
        last = self.current_flow[-1]
        block = self.registry.get(last.block_id)
        if not block:
            return

        output_type = block.signature.output_type
        suggestions = self.wiring.suggest_next(output_type, limit=5)

        print(f"\n  After {block.name} ({output_type}):")
        for s in suggestions:
            print(f"    {s.full_name}: {s.signature}")
        print()

    def cmd_flow(self, args):
        if not self.current_flow:
            print("No flow defined. Use 'wire' to build one.")
            return
        self._wire_show()

        # Validate
        result = self.wiring.validate_flow(self.current_flow)
        if result.valid:
            print("  ✓ Flow is valid")
        else:
            print("  ✗ Flow has errors:")
            for e in result.errors:
                print(f"    {e}")
        if result.warnings:
            print("  Warnings:")
            for w in result.warnings:
                print(f"    {w}")

    def cmd_run(self, args):
        """Run a quick demo or the current flow"""
        if not self.current_flow:
            print("No flow to run. Building a demo...\n")
            self._run_demo()
            return

        print("Running flow...")
        # Would execute the flow here
        print("(Flow execution not yet implemented)")

    def _run_demo(self):
        """Quick demo of primitives"""
        print("DEMO: Primitives in action\n")

        # Transform
        print("1. Transform: double a number")
        double = T("x => x * 2")
        print(f"   T('x => x * 2')(5) = {run(double, 5)}")

        # Filter
        print("\n2. Filter: keep even numbers")
        evens = F("x => x % 2 == 0")
        print(f"   F('x => x % 2 == 0')([1,2,3,4,5,6]) = {run(evens, [1,2,3,4,5,6])}")

        # Pipe
        print("\n3. Pipe: chain operations")
        pipeline = P(
            T("x => x + 1"),
            T("x => x * 2"),
            T("x => x - 3")
        )
        print(f"   P(+1, *2, -3)(5) = {run(pipeline, 5)}")  # (5+1)*2-3 = 9

        # Branch
        print("\n4. Branch: conditional")
        sign = B("x => x >= 0", "x => 'positive'", "x => 'negative'")
        print(f"   B(>=0, 'positive', 'negative')(5) = {run(sign, 5)}")
        print(f"   B(>=0, 'positive', 'negative')(-3) = {run(sign, -3)}")

        # IO with mock
        print("\n5. IO: file operations (mock)")
        use_mock(mock_fs={"data.txt": "hello world"})
        result = run(file_read("data.txt"), None)
        print(f"   file_read('data.txt') = {result}")

        # Real IO
        print("\n6. IO: real operations")
        use_real()
        print(f"   time_now() = {run(time_now(), None)}")
        print(f"   uuid() = {run(uuid(), None)}")
        print(f"   env('HOME') = {run(env('HOME'), None)}")

    def cmd_test(self, name):
        if not name:
            print("Usage: test <block_name>")
            return
        print(f"Testing {name}...")
        print("(Test execution not yet implemented)")

    def cmd_eval(self, expr):
        if not expr:
            print("Usage: eval <expression>")
            print("Example: eval T('x => x * 2')(5)")
            return

        # Make primitives available
        ctx = {
            'T': T, 'F': F, 'B': B, 'P': P, 'run': run,
            'file_read': file_read, 'file_write': file_write,
            'http_get': http_get, 'env': env,
            'time_now': time_now, 'random': random, 'uuid': uuid,
            'stdout': stdout, 'unwrap': unwrap, 'unwrap_or': unwrap_or,
            'use_mock': use_mock, 'use_real': use_real,
        }

        try:
            result = eval(expr, ctx)
            print(f"=> {result}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    cli = PrimCLI()
    cli.run()
