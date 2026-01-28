# Primitives

A library of computational building blocks with no code.

## Philosophy

Every program ever written is a composition of a small number of fundamental operations:
- Transform data
- Filter data
- Branch on conditions
- Repeat operations
- Store and retrieve state
- Compose smaller things into bigger things

This library specifies those primitives with rigorous tests. Agents implement them.

## Structure

```
primitives/
├── data_flow/      # transform, filter, split, merge
├── state/          # store, retrieve, watch
├── control/        # sequence, branch, repeat, parallel
└── composition/    # pipe, wrap, group

examples/
└── oven_toaster.yaml   # Real-world composition example
```

## The Contract

**For users:** Describe what you want. Get working software.

**For agents:** Implement primitives. Pass tests. Compose solutions.

**For everyone:** Same primitives, any language, any platform.

## Why No Code?

Code is an implementation detail. The specification is the product.

When you reuse a `timer` component, you don't care if it's written in Rust, Python, or JavaScript. You care that:
- Setting duration to 3 and ticking 3 times produces `{ done: true }`
- The tests pass
- It composes with your other components

## Biological Inspiration

Cells solve universal problems through:
1. **Local rules** - Each cell follows simple instructions
2. **Composition** - Cells combine into tissues, organs, systems
3. **Reuse** - Same cellular machinery, different configurations

This library applies the same principle to computation:
1. **Local rules** - Each primitive has a clear contract
2. **Composition** - Primitives combine via pipe, group, wire
3. **Reuse** - Same primitives, different products

## Getting Started

See [INSTALL.md](INSTALL.md) for how to use this with an AI agent.

See [examples/oven_toaster.yaml](examples/oven_toaster.yaml) for a complete composition example.

## Adding New Primitives

New primitives should only be added when:
1. No existing primitive can express the operation
2. The operation is truly fundamental (not a composition)
3. Full test coverage is provided
4. Algebraic properties are documented

Most "new" requirements are compositions of existing primitives.
