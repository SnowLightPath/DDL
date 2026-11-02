# Design-Doc Loop

**Keep the design you agree on across sessions.**

Design-Doc Loop (DDL) gives people and coding agents a shared `design.md`: the experience to build, the decisions that bind it, and the checks that show it works. Use the loop wherever it helps; the commands are optional.

![Design-Doc Loop overview](./assets/main.webp)

[Read in English](./docs/en/design_philosophy.md) · [日本語で読む](./docs/ja/design_philosophy.md) · [All documentation](./docs/README.md)

## Quick start

Install once for the Claude Code or Codex environment already on your machine. Python 3 is required.

```bash
git clone https://github.com/SnowLightPath/DDL.git
bash DDL/bin/install.sh
```

Then follow the short project setup for [Codex](./codex/README.md#quick-start) or [Claude Code](./claude-code/README.md#quick-start). The installer keeps existing settings and installs for each runtime whose home directory exists; `--codex` or `--claude` selects one explicitly.

Open your project in the **Codex GUI** or Claude Code and describe the experience you want with `$draft` or `/draft`. A typical loop is:

| Step | What you do | What you get |
|---|---|---|
| **Draft** | Describe how the result should feel and behave | A design to review before saving |
| **Realize** | Review the proposed implementation plan | Working code and verification results |
| **Reflect** | Compare the implementation with the design | Proposed updates to keep them aligned |
| **Close** | Approve one Git review of the final diff | design.md and documents reflected, one commit, nothing left to do |

> [!NOTE]
> **Codex GUI is the primary experience.** Codex CLI 0.166.0 Default cannot collect approval through its asynchronous selector after the turn ends.
>
> DDL stops unapproved on that route; see the [CLI notice and host limits](./codex/README.md#host-limits).

## Choose a command

| Use it to… | Claude Code | Codex |
|---|---|---|
| Draft the desired experience | `/draft` | `$draft` |
| Implement an approved plan | `/realize` | `$realize` |
| Align the design with what was built | `/reflect` | `$reflect` |
| Run the project's checks | `/validate` | `$validate` |
| Reconcile language versions | `/resonate` | `$resonate` |
| Review documentation | `/docs` | `$docs` |
| Review code quality | `/refactoring` | `$refactoring` |
| Commit verified changes | `/commit` | `$commit` |

`/commit remote` and `$commit remote` also propose a push. Approval names the files, message, and any remote action it covers. The final diff, exact message, and destination form one clickable Git review. Ordinary commit/push calls without that matching review are refused by the hook, even after another approval has opened STOP. If implementation had not yet produced the final diff, this adds one review at the point the contents are ready. `/commit` and `$commit` run the Close scan first, so `design.md` and the documents are current when the review appears; after the commit, no further command is suggested.

## Review the recommendations together

At a required STOP, one concise report gives the overall recommendation and lists the compatible actions ready for approval with stable numbered IDs. Material impacts, risks, and unknowns stay visible; detailed evidence is available separately. Multiple proposals form one current review set.

One native approval interaction covers that set, with optional free text: **approve all current recommendations**, **choose a subset or request changes**, or **hold**. Approve-all authorizes exactly the displayed ready actions and recommended resolutions, without another approval per file, item, or section. It does not cover undisplayed or future work, later STOPs, unconfirmed outward actions, or silent changes to Binding Decisions.

Subset editing is optional and starts only when requested, using a supported native checklist or grouped form rather than an automatic item-by-item question loop or a forced typed ID list. A request receipt, cancellation, dismissal, unanswered question, or timeout approves nothing. If a permitted, answerable native interface is unavailable, DDL explains the limitation and stops instead of silently substituting typed choices.

The protocol defines the workflow. Runtime hooks provide guardrails for the calls they receive; they do not establish complete STOP enforcement. See the [runtime limits and verification notes](./docs/maintainers/README.md#runtime-boundaries) for the distinction.

## Learn more

- [The idea behind DDL](./docs/README.md): short and extended explanations in English and Japanese.
- [Codex setup and use](./codex/README.md): GUI first, with host limits explained.
- [Claude Code setup and use](./claude-code/README.md): install, start a project, and review decisions.
- [Maintainer reference](./docs/maintainers/README.md): installation details, adapters, source files, and validation.

## License

[CC BY 4.0 with a publishing restriction](./LICENSE).
