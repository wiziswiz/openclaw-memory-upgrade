# Compaction Auto-Logger

**Hook:** `session:compact:after`

Automatically logs compaction events to `memory/LIVE.md` so your agent has a breadcrumb trail of what happened before context was compressed. Solves "agent amnesia" after compaction — mechanical, doesn't rely on the agent remembering to write.

## What it does

After each compaction event, appends a timestamped entry with:
- Messages compacted
- Token count before/after (and savings %)
- Summary length

Maintains a rolling window of the last 5 entries (oldest auto-pruned).

## Setup

Add to your `openclaw.json` hooks:

```json
{
  "hooks": {
    "session:compact:after": "./extensions/compaction-logger/index.js"
  }
}
```

## Behavior

- **Zero-risk:** Any error is caught and logged to stderr. The hook never throws.
- **Graceful fallback:** If `memory/LIVE.md` doesn't exist, it creates it. If the directory doesn't exist, it skips silently.
- **Rolling window:** Keeps only the 5 most recent entries to prevent unbounded growth.
