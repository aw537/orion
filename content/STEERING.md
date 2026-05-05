## Workflow Orchestration

### Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately
- Write detailed specs upfront to reduce ambiguity

### Memory Strategy
- Use `stardust.save` to persist decisions, learnings, and context
- Use `sun.working_context` to track current focus and blockers
- Use `orion_context` at session start to load active Biome state
- At session end, write new knowledge to the active Biome via `stardust.save`

### Verification Before Done
- Never mark a task complete without proving it works
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- Skip this for simple, obvious fixes — don't over-engineer

### Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them

## Task Management

1. **Plan**: Use `sun.working_context` to set current_focus and add blockers
2. **Track**: Save architectural decisions as Analytical Stardust with reasoning
3. **Progress**: Mark items complete as you go, explain changes at each step
4. **Capture**: Save corrections and learnings as Stardust in the active Biome
5. **Close**: Update working_context to reflect completion

## Core Principles

**Simplicity First**: Make every change as simple as possible. Impact minimal code.
**No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
**Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
