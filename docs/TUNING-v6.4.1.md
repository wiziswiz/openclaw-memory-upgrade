# SME v6.4.1 Tuning Guide — Post-Audit Fixes

**Date:** 2026-03-01  
**Context:** After running parallel Codex + Opus audits on the full memory stack, we identified and fixed 8 issues. This guide documents what changed and why.

## What Changed

### 1. autoCapture: OFF (default changed to `false`)

**Problem:** autoCapture was triggering on keywords inside quoted reply context and conversation metadata. In a real-world Telegram session, **84% of auto-captured entries were noise** — raw JSON blobs, reply context, forwarded message headers.

**Root cause:** `shouldCapture()` checked the full message text including quoted blocks. A keyword like "decided" inside a quoted reply would trigger capture of the entire message.

**Fix (plugin code):**
- Added filters for conversation metadata, reply context, forwarded messages, sender labels
- Trigger patterns now run against stripped text (quoted blocks removed)
- Default changed from `true` to `false` in plugin schema

**Recommendation:** If your agent writes facts manually per AGENTS.md rules, leave autoCapture off. If your agent doesn't have manual write discipline, enable it but expect ~15-20% noise rate (down from 84% with the filter fixes).

### 2. Disable built-in memorySearch sessionMemory

**Problem:** OpenClaw's built-in `memorySearch` and SME's auto-recall both inject context before each turn. They search overlapping data with different ranking, potentially injecting contradictory or duplicate context.

**Fix:**
```json
{
  "agents": {
    "defaults": {
      "memorySearch": {
        "experimental": {
          "sessionMemory": false
        }
      }
    }
  }
}
```

**Note:** We kept `memorySearch.enabled: true` to avoid breaking compaction/memory-flush. Only `sessionMemory` (the duplicate injection vector) was disabled.

### 3. items.json Indexing for Knowledge Graph Entities

**Problem:** The entire Layer 1 knowledge graph (63 entities across people, companies, projects) was invisible to SME recall. SME only indexed `.md` files.

**Fix (indexer.js):**
- New `chunkJson()` function that flattens atomic facts into searchable text chunks
- Only `active` facts indexed (superseded facts filtered out)
- Entity name and category extracted from file path
- Proper noun extraction for relationship linking
- Facts batched into groups of 5 for optimal chunk sizes
- All chunks typed as `confirmed` with 0.9 confidence

**Config (.memory/config.json):**
```json
{
  "includeGlobs": ["skills/*.md", "life/areas/**/*.md", "life/areas/**/*.json"],
  "fileTypeDefaults": {
    "life/areas/**/*.json": "confirmed"
  },
  "excludeFromRecall": ["life/areas/credentials/*/items.json"]
}
```

**Results:** Index grew from ~200 chunks to 648 chunks. Entity searches now return facts directly instead of requiring manual file reads.

### 4. Context Pruning TTL: 1h → 4h

**Problem:** OpenClaw's `cache-ttl` pruning clears old tool outputs (file reads, exec results, search results) after the TTL expires. At 1h, the agent loses access to data it read earlier in the session, leading to "fuzzy memory" errors — asserting things about files without having the actual content in context.

**Fix:**
```json
{
  "agents": {
    "defaults": {
      "contextPruning": {
        "mode": "cache-ttl",
        "ttl": "4h"
      }
    }
  }
}
```

**Note:** This only affects tool result trimming, NOT user/assistant messages. The 200K context window has ~140K of unused headroom — 4h is conservative.

### 5. AGENTS.md Documentation Fixes

- Fixed inconsistency: "Use MEMORY.md for durable patterns" → "Use PATTERNS.md for durable patterns"
- Added SME Plugin section documenting its role as recall-only (not truth source)
- Clarified: autoCapture is DISABLED, all memory writes are intentional

### 6. Behavioral Rules (PATTERNS.md)

New rules added based on audit findings:
- **Verification Before Assertion:** Never claim filesystem state without running ls/cat/git show
- **Tool Output ≠ User Delivery:** Reading a file in a tool call is NOT sending it to the user
- **Benchmark Before Implementing:** Don't skip evaluation when user explicitly requests it

## Audit Methodology

All fixes were validated by parallel Codex + Opus audits:
1. **Conflict analysis** — both models independently analyzed SME vs existing memory system
2. **Benchmark** — both models independently evaluated each proposed fix (APPLY/SKIP/MODIFY)
3. **Post-fix audit** — both models verified all 8 fixes applied correctly + regression tested

This dual-model approach catches biases and ensures fixes are robust.

## Upgrade Path

If upgrading from v6.4.0:
1. Pull latest from repo
2. Update `.memory/config.json` with items.json glob (see above)
3. Set `autoCapture: false` in OpenClaw config
4. Set `sessionMemory: false` in OpenClaw config
5. Bump contextPruning TTL to at least 4h
6. Force reindex: `npm run reindex -- --force`
