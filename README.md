# ✨ Design-Doc Loop (DDL)

> Human and LLM share design across sessions.

![DDL Overview](./assets/main.webp)

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

### 📄 Scribe Plugin

Document writing workflow for [Claude Cowork](https://claude.com/product/cowork) and [Claude Code](https://code.claude.com/).

```bash
# Add marketplace
claude plugin marketplace add SnowLightPath/snow-light-place

# Install plugin
claude plugin install scribe@snow-light-place
```

**🔄 Document Loop:**

| Command | Action |
|---------|--------|
| 📝 `/scribe:draft` | Design the document outline |
| ⚡ `/scribe:realize` | Write and export the document |
| 🪞 `/scribe:reflect` | Review and improve |

> Supports PDF, DOCX, HTML, XLSX, PPTX, Pencil (.pen), and Confluence output. Parallel section writing with [Agent Teams](https://code.claude.com/docs/en/agent-teams). Works in both Claude Cowork (Web) and Claude Code (CLI).

---

## 📄 License

[CC BY 4.0](./LICENSE) with publishing restriction
