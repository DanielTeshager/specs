# Installation

This is not a traditional library. There is no code to install.

## For Humans

Describe what you want to build. The agent will compose it from primitives.

## For Agents

```
You are implementing a system using composable primitives.

1. Read primitives/SPEC_FORMAT.md for the specification format
2. Read all primitives in primitives/*/*.yaml to understand available blocks
3. When given a requirement:
   a. Decompose it into primitive operations
   b. Wire the primitives together using pipe, group, and other composition blocks
   c. Generate tests from the primitive test specs
   d. Implement in the target language
   e. Validate all tests pass
4. When reusing components:
   a. Check examples/ for existing composed components
   b. Use { use: "path.to.component" } to reference them
   c. Only build new primitives if no existing primitive fits

The goal is maximum reuse. Every problem is a composition of solved problems.
```

## Example Prompt

"Build me a coffee maker with a water heater, timer, and brew cycle."

Agent response:
1. Reuse: `components.timer` (from oven_toaster.yaml)
2. Reuse: `components.thermostat` (for water temperature)
3. Reuse: `components.heating_element` (for water heater)
4. New: `pump` primitive (water flow control)
5. New: `brew_cycle` group (sequences heating → pumping → timing)

## Validation

The agent must run all tests from:
- Each primitive's `tests:` section
- Each composed component's integration tests
- Property-based tests using generated inputs

Tests pass = implementation correct. That's the contract.
