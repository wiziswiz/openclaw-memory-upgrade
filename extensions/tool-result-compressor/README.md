# Tool Result Compressor

**Hook:** `tool_result_persist`

Strips noise from tool results before they persist to the conversation transcript. Reduces ~5-10% context waste from verbose CLI output.

## What it cleans

- ANSI escape sequences (colors, cursor control)
- npm WARN / notice lines
- pip WARNING / deprecation lines
- Node.js ExperimentalWarning lines
- Box-drawing characters (└─┌ etc.)
- Excessive blank lines (3+ consecutive → 2)
- Truncates results over 8,192 characters with a marker

## Setup

> ⚠️ **Do NOT paste this path directly into `openclaw.json`** — the gateway will crash if the path doesn't resolve from the config directory. This extension must be registered under `hooks.internal.entries` with the correct absolute or resolvable path. See [SETUP.md](../../SETUP.md) for proper installation.

**Hook key:** `tool_result_persist`
**Entry path:** Must resolve to this extension's `index.js` from your OpenClaw config directory.

## Behavior

- **Non-destructive:** Only modifies the persisted transcript, not the live tool output you see.
- **Zero-risk:** Returns `undefined` (no-op) on any error — never breaks your session.
- **Smart:** Handles both string content and array-of-parts `{type, text}` format. Only returns cleaned content when changes were actually made.
