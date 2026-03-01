# Upgrading SME: v5.3 → v6.4

## What's New

SME v6.4.0 is a major quality-of-life upgrade. No breaking changes — just pull and go.

### New Modules
| Module | What it does |
|--------|-------------|
| `lib/temporal.js` | Temporal query preprocessing — "last week", "yesterday", "what's coming in March?" now filter by actual date ranges |
| `lib/query-strip.js` | Strips metadata envelopes, code blocks, and system prefixes from search terms before FTS |
| `lib/recall-logger.js` | Logs every recall to `.memory/recall-log.jsonl` — track quality over time |

### Enhanced CIL Pipeline (`lib/context.js`)
- **Query intent detection** — classifies queries as aggregation, reasoning, or action:
  - `aggregation` ("list all my...") → wider net, lower score threshold
  - `reasoning` ("why did I...") → boosts decision + confirmed chunks
  - `action` ("what should I do") → boosts action_item + decision chunks
- **Rule chunk penalty** — policy/rules content deprioritized for factual queries
- **Smart truncation** — cuts at sentence boundaries instead of mid-word
- **Forward-looking temporal** — "what's coming in March?" finds future events
- **`excludeFromRecall`** config — skip noisy files (e.g., JSON trackers)

### New Config Options

```json
{
  "owner": "yourname",
  "excludeFromRecall": ["some-noisy-file.json"],
  "include": ["AGENTS.md", "TOOLS.md"],
  "includeGlobs": ["skills/*.md"],
  "fileTypeDefaults": {
    "MEMORY.md": "confirmed",
    "memory/*.md": "fact"
  }
}
```

### New Scripts
- `npm run test:recall` — regression test harness for recall quality
- `npm run test:all` — full suite + recall tests

## Upgrade Steps

```bash
cd Structured-Memory-Engine
git pull origin main
npm install
npm test        # Expected: 914-915 passed, 0 failed
node lib/index.js index --workspace ~/your-workspace
```

Then optionally update `.memory/config.json` with new options above.

## What Changed Internally

- `context.js` doubled (345 → 738 lines) — all new features live here
- `recall.js` gained `STOP_WORDS` export (+31 lines)
- `store.js` added `getChunksByFile()` export
- 3 new test files, total: 915 tests (up from ~520)

## Compatibility

- No breaking changes to MCP tools, plugin hooks, or config
- All existing configs work unchanged — new options are additive
- SQLite schema unchanged — no migration needed
