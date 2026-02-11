# ✨ Design-Doc Loop (DDL)

> Human and LLM share design across sessions.

![DDL Overview](./assets/main.png)

---

## 🎯 The Problem

- Sessions end
- Context is lost
- Previous discussions are forgotten

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
cp examples/claude-commands/CLAUDE.md your-project/.claude/
cp examples/claude-commands/*.md your-project/.claude/commands/
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
| 📦 `/commit` | Verified git commit |
| 📚 `/docs` | Documentation audit |
| 🔧 `/refactoring` | Code quality audit |

> 🚀 Commands support Phase-based workflows, Detection Targets, STOP gates, and [Agent Teams](https://code.claude.com/docs/en/agent-teams) for parallel execution across scopes.

### 🧬 OpenAI Codex

```bash
cp examples/codex-skills/AGENTS.md your-project/
cp -r examples/codex-skills/*/  your-project/.codex/skills/
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
| 📦 `$commit` | Verified git commit |
| 📚 `$docs` | Documentation audit |
| 🔧 `$refactoring` | Code quality audit |

> Skills follow the same Phase-based structure with Detection Targets and STOP gates. Codex processes scopes sequentially.

---

## 📄 License

[CC BY 4.0](./LICENSE) with publishing restriction
