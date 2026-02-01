---
name: reflect
description: Update documents based on implementation results
metadata:
  short-description: Code → Design
---

# reflect

Update documents based on implementation results.

## Usage

- `$reflect` - Check entire project alignment
- `$reflect <path>` - Check specific file/directory

## Behavior

1. Read DESIGN.md principles
2. Analyze code for adherence
3. Report divergences:
   - **Code drifted** — implementation violates principle
   - **Philosophy outdated** — code shows better approach
4. Propose: update docs, fix code, or discuss

Can reflect on DESIGN.md itself (meta-reflection).

## Example

```
Human: $reflect

Codex: Found 2 divergences:

1. DESIGN.md: "fail fast" / Code: silent retry
   → Update principle or remove retry?

2. DESIGN.md: 900 lines (violates "lightweight")
   → Split into Core/Extended?
```
