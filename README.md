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
mkdir -p your-project/.claude/commands
cp examples/claude-commands/CLAUDE.md your-project/.claude/
cp examples/claude-commands/{DDL-PROTOCOL-SKILL.md,draft.md,realize.md,reflect.md,validate.md,docs.md,refactoring.md,commit.md} your-project/.claude/commands/
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

> 🚀 Commands support Phase-based workflows, Detection Targets, STOP gates, and parallel workers per scope through the runtime's own mechanism (subagents in Claude Code).

### 🧬 OpenAI Codex

```bash
cp examples/codex-skills/AGENTS.md your-project/
cp -r examples/codex-skills/.agents your-project/
cp -r examples/codex-skills/.codex your-project/
```

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

> Skills follow the same Phase-based structure with Detection Targets and STOP gates. Codex runs scopes in parallel with its subagents (on by default). Without subagents, the lead runs the assignments itself: read-only work as parallel shell reads, the rest one by one.

---

## 📄 License

[CC BY 4.0](./LICENSE) with publishing restriction
