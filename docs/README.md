# Read about Design-Doc Loop

Start with the short explanation of DDL. Read the extended version for the reasoning, examples, and related ideas.

| Read | English | 日本語 |
|---|---|---|
| **The core idea** | [Start here](./en/design_philosophy.md) | [ここから読む](./ja/design_philosophy.md) |
| **The deeper explanation** | [Rationale and examples](./en/design_philosophy_extended.md) | [背景と実践例](./ja/design_philosophy_extended.md) |

## Put it to work

At a required STOP, review the current numbered recommendations together and approve the displayed set in one native interaction. Choosing a subset or requesting changes is optional; approval does not trigger another question for every item. Work ends with one Git review of the final diff; no command chain follows a commit.

Choose the setup guide for your tool:

- [Codex](../codex/README.md): use the GUI with native choices; the guide explains the known CLI limit.
- [Claude Code](../claude-code/README.md): install DDL and start with `/draft`.

For a quick overview and command mapping, return to the [project README](../README.md).

<details>
<summary>Maintaining DDL?</summary>

The [maintainer reference](./maintainers/README.md) covers adapters, generation, validation, and translation references.

</details>
