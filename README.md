# ✨ Design-Doc Loop (DDL)

> Human and LLM share design across sessions.

![DDL Overview](./assets/main.webp)

---

## 🎯 The Problem

- Sessions end, and the next session starts without what this one knew
- What the agent remembers, the human never agreed to
- Context is a budget: the more a session holds, the less the model recalls

## 💡 The Solution

Use Design Documents as shared memory.

```
Human ←→ Design Document ←→ LLM
                ↓
              Code
```

## 🔄 The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

| Phase | Flow |
|-------|------|
| 📝 **Draft** | Idea → Design Document |
| ⚡ **Realize** | Design Document → Code |
| 🪞 **Reflect** | Code → Design Document |

Realize and Reflect are inverse functions.

---

## 📚 Documentation

- [English](./docs/en/design_philosophy.md)
- [日本語](./docs/ja/design_philosophy.md)

## 🛠️ Commands (Optional)

### 🤖 Claude Code

```bash
mkdir -p your-project/.claude
cp -R examples/claude-commands/.claude/. your-project/.claude/
```

**🔄 Core Loop:**

| Command | Action |
|---------|--------|
| 📝 `/draft` | Idea → Design Document |
| ⚡ `/realize` | Design Document → Code |
| 🪞 `/reflect` | Code → Design Document |

**🧩 Support Commands:**

| Command | Action |
|---------|--------|
| ✅ `/validate` | Mechanical validation gate |
| 📦 `/commit` | Verified git commit (`/commit remote` also pushes) |
| 📚 `/docs` | Documentation audit |
| 🔧 `/refactoring` | Code quality audit |

> 🚀 Commands support Phase-based workflows, Detection Targets, STOP gates, and parallel workers per scope through the runtime's own mechanism (subagents in Claude Code). The adapter (`settings.json`, `agents/`, `hooks/`, and the import line in `CLAUDE.md`) lets Claude Code itself hold a STOP until you speak, keep workers in their roles, load design.md at session start, and ask before a push; without it the same rules run as instructions.

### 🧬 OpenAI Codex

```bash
cp examples/codex-skills/AGENTS.md your-project/
cp -r examples/codex-skills/.agents your-project/
cp -r examples/codex-skills/.codex your-project/
```

Trust the project in Codex, then run `/hooks` once to review and trust the DDL hooks in `.codex/hooks.json`.

**🔄 Core Loop:**

| Skill | Action |
|-------|--------|
| 📝 `$draft` | Idea → Design Document |
| ⚡ `$realize` | Design Document → Code |
| 🪞 `$reflect` | Code → Design Document |

**🧩 Support Skills:**

| Skill | Action |
|-------|--------|
| ✅ `$validate` | Mechanical validation gate |
| 📦 `$commit` | Verified git commit (`$commit remote` also pushes) |
| 📚 `$docs` | Documentation audit |
| 🔧 `$refactoring` | Code quality audit |

> Skills follow the same Phase-based structure with Detection Targets and STOP gates. Codex runs scopes in parallel with its subagents (on by default). Without subagents, the lead runs the assignments itself: read-only work as parallel shell reads, the rest one by one. The adapter (`.codex/config.toml`, `.codex/agents/`, `.codex/hooks.json`, `.codex/rules/`) lets Codex hold a STOP until you speak, inject design.md at session start, and ask before a push; without it the same rules run as instructions.

---

## 📄 License

[CC BY 4.0](./LICENSE) with publishing restriction
