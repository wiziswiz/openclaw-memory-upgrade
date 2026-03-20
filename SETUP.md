# Setup Guide

## Prerequisites

- **Node.js 22+** — `node --version`
- **OpenClaw** — `npm install -g openclaw`
- **jq** — `brew install jq` (macOS) or `apt install jq` (Linux)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_ORG/openclaw-memory-upgrade.git
cd openclaw-memory-upgrade
npm install
```

### 2. Install SME (Structured Memory Engine)

```bash
npm install -g structured-memory-engine
```

### 3. Start OpenClaw gateway

```bash
openclaw gateway start
```

### 4. Verify

```bash
openclaw status
```

You should see `session-memory` in hooks. If you installed lossless-claw, it should show as the active context engine.

---

## Optional: Lossless Context Management (LCM)

LCM preserves full conversation history within a session via a summary DAG. Recommended for long-running sessions.

```bash
openclaw plugins install @martian-engineering/lossless-claw
```

Set recommended environment variables:
```bash
export LCM_FRESH_TAIL_COUNT=32
export LCM_INCREMENTAL_MAX_DEPTH=-1
```

Restart the gateway after installing.

---

## Claude Code / Cursor (no OpenClaw needed)

If you're using Claude Code or Cursor, you only need the SME npm package — not OpenClaw or lossless-claw.

```bash
npm install -g structured-memory-engine
```

Add to `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "sme": {
      "command": "npx",
      "args": ["sme-mcp"],
      "env": { "SME_WORKSPACE": "/absolute/path/to/your/workspace" }
    }
  }
}
```

Then initialize SME in your workspace:
```bash
cd /path/to/workspace
sme init
```

Optional session hooks (auto-index on start, auto-reflect on stop):
```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "npx sme index" }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "npx sme reflect" }]
    }]
  }
}
```

---

## ⚠️ Important: Do NOT manually edit hooks

**Do NOT manually add hook entries to `~/.openclaw/openclaw.json`.**

Plugins register their own hooks automatically via `openclaw plugins install`. Manually adding entries — especially with relative paths — will crash the gateway on startup with `MODULE_NOT_FOUND`.

Common mistake (❌ **don't do this**):
```json
{
  "session:compact:after": "./extensions/compaction-logger/index.js",
  "tool_result_persist": "./extensions/tool-result-compressor/index.js"
}
```

These are OpenClaw extension modules that register through the plugin system, not manual hook entries.

### If your gateway won't start

Run the repair script:
```bash
bash scripts/fix-openclaw-config.sh
```

Or validate before starting:
```bash
bash scripts/validate-hooks.sh         # check only
bash scripts/validate-hooks.sh --fix   # check + auto-repair
```

---

## Workspace Structure

| File/Dir | Purpose |
|----------|---------|
| `AGENTS.md` | Agent behavior rules |
| `SOUL.md` | Persona and tone |
| `IDENTITY.md` | Agent identity |
| `USER.md` | User profile |
| `HEARTBEAT.md` | Proactive analysis tasks |
| `TOOLS.md` | External tool notes |
| `memory/` | Daily event logs |
| `PATTERNS.md` | Learned behavioral patterns |
| `extensions/` | OpenClaw extensions (compaction-logger, tool-result-compressor) |
| `config/` | Config templates |
| `scripts/` | Utility scripts |

## Customization

1. Edit `USER.md` with your name and preferences
2. Edit `SOUL.md` to adjust persona/tone
3. Edit `IDENTITY.md` to name your agent
4. Edit `HEARTBEAT.md` to define proactive tasks

---

## Recommended Stack

See [RECOMMENDED-STACK.md](RECOMMENDED-STACK.md) for the full 3-layer memory architecture:
- **Layer 1:** SME — cross-session recall
- **Layer 2:** LCM — within-session context preservation
- **Layer 3:** Bridge extensions — connects them
