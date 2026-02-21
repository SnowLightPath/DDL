<!-- Template: Copy this file to your project's .claude/CLAUDE.md and adapt as needed.
     This file is NOT auto-loaded by the plugin system. It serves as a starting point
     for projects that use the Scribe plugin. -->

# Project Name

## Protocol

→ Scribe Document Writing
→ The `document-writing` skill is loaded automatically when any Scribe command is invoked

## Commands

| Command | Intent |
|---------|--------|
| `/scribe:draft` | Design the document outline and structure |
| `/scribe:realize` | Write and export the document |
| `/scribe:reflect` | Review quality and improve |

## Structure

- `scribe.md` - Document Design File (outline, meta, sources)

## Detection Targets

Every command defines its own D1–D7. Cross-cutting targets below apply globally.

+++DETECT:
  G1: Vague Intent — Document purpose or audience not defined
  G2: Scope Creep — Writing touches sections outside the outline
  G3: Tone Violation — Content doesn't match the meta tone setting
  G4: Missing Validation — No review step after writing
  G5: Format Mismatch — Output format doesn't match what was requested
  G6: Silent Failure — Format conversion error swallowed without notification
  G7: Unreviewed Mutation — Document changed without +++STOP approval

## Behavior

### On session start

1. Read `CLAUDE.md` (this file)
2. Read `scribe.md` if it exists — extract outline, meta, sources

### On any task

1. Identify which sections (from `scribe.md`) are affected
2. Run the command's Phase sequence
3. Scan for Detection Targets at each phase boundary

### On completion

1. Summarize what changed (sections, word count, format)
2. List any Detection Targets that fired
3. Suggest next command if applicable (`/scribe:draft` → `/scribe:realize` → `/scribe:reflect`)

## Constraints

+++NEVER: Hardcode sections — they come from scribe.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Spawn agents for single-section documents — swarm is optional
+++NEVER: Output a format different from what the user requested
