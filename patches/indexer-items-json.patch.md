# items.json Indexing Patch for SME v6.5+

This patch adds knowledge graph entity indexing to SME. Apply to `lib/indexer.js` in your SME installation.

## What it does
- Indexes `life/areas/**/items.json` files (people, companies, projects, etc.)
- Only indexes active facts (superseded facts filtered out)
- Extracts entity names and categories from file paths
- Batches facts into groups of 5 for optimal FTS5 chunk sizes
- Types all chunks as `confirmed` with 0.9 confidence

## How to apply

### Option 1: Copy the patched indexer
Copy `lib/indexer.js` from this repo's `patches/` directory into your SME `lib/` folder.

### Option 2: Manual patch
Add `chunkJson()` function and areas walker to your `lib/indexer.js`. See the full function in `patches/indexer.js`.

### Config (.memory/config.json)
Add to your workspace config:
```json
{
  "includeGlobs": ["life/areas/**/*.json"],
  "fileTypeDefaults": { "life/areas/**/*.json": "confirmed" },
  "excludeFromRecall": ["life/areas/credentials/*/items.json"]
}
```
