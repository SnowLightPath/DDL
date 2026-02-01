---
name: realize
description: Write code based on design principles in DESIGN.md
metadata:
  short-description: Design → Code
---

# realize

Write code based on design principles.

## Usage

- `$realize` - Read DESIGN.md, await instruction
- `$realize <feature>` - Implement specific feature

## Behavior

1. Read DESIGN.md (required)
2. Generate code honoring the principles
3. If implementation would violate principles—stop and discuss

## Example

```
Human: $realize retry logic

Codex: Reading DESIGN.md...
Principles: Transparency, Exception-based Errors

Implementing:
- Transparent retry (user doesn't see)
- Throws after max (consistent with exceptions)

[code]
```
