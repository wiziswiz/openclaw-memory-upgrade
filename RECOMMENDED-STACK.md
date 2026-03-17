# Recommended Memory Stack

Three layers that work together. Layer 1 is included. Layer 2 is optional (but recommended). Layer 3 bridges them.

---

## Layer 1: SME (included)

**Structured Memory Engine** — cross-session recall.

Your agent remembers things between sessions. SME indexes your workspace markdown files into a local SQLite FTS5 database and automatically injects relevant context into every agent turn.

- Auto-recall with confidence scoring
- Contradiction detection
- Memory lifecycle (decay, reinforcement, pruning)
- Entity tracking
- Zero API calls, runs locally

**Already installed** when you use this repo.

---

## Layer 2: LCM (optional install)

**Lossless Context Management** (`@martian-engineering/lossless-claw`) — within-session context preservation.

When conversations get long, OpenClaw compacts older messages into summaries. LCM builds a DAG (directed acyclic graph) of those summaries so nothing is truly lost — just compressed. You can drill back into any summary to recover the original detail.

SME handles *between* sessions. LCM handles *within* a session.

### Install

```bash
npm install -g @martian-engineering/lossless-claw
```

Then add to your `openclaw.json` plugins:

```json
{
  "plugins": {
    "@martian-engineering/lossless-claw": {}
  }
}
```

---

## Layer 3: Hooks (included)

Two hooks that bridge SME and LCM and reduce context waste:

### Compaction Auto-Logger
**Hook:** `session:compact:after`

After each compaction, writes a breadcrumb to `memory/LIVE.md` with timestamps and stats. Your agent always knows *that* compaction happened and roughly what was compressed — even if it can't recall the details without LCM.

### Tool Result Compressor
**Hook:** `tool_result_persist`

Strips ANSI codes, npm/pip warnings, box-drawing chars, and truncates oversized tool output before it persists to the transcript. Saves ~5-10% context that would otherwise be wasted on noise.

### Enable hooks

Add to your `openclaw.json`:

```json
{
  "hooks": {
    "session:compact:after": "./extensions/compaction-logger/index.js",
    "tool_result_persist": "./extensions/tool-result-compressor/index.js"
  }
}
```

---

## Quick setup (all 3 layers)

```bash
# 1. SME is already included — just run the repo's install

# 2. Install LCM
npm install -g @martian-engineering/lossless-claw

# 3. Add to your openclaw.json:
#    - Plugin: @martian-engineering/lossless-claw
#    - Hooks: compaction-logger + tool-result-compressor
#    (see examples above)

# 4. Verify
./scripts/check-stack.sh
```

---

## Why all three?

| Problem | Without | With |
|---------|---------|------|
| Agent forgets yesterday's decisions | ❌ Blank slate each session | ✅ SME auto-recalls relevant context |
| Long session loses early context | ❌ Compacted away forever | ✅ LCM preserves as expandable summaries |
| Agent doesn't know compaction happened | ❌ Silent context loss | ✅ Compaction logger leaves breadcrumbs |
| Tool output wastes context tokens | ❌ ANSI codes eat your budget | ✅ Compressor strips noise before persist |
