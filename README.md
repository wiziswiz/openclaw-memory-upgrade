# OpenClaw Memory Upgrade System

**Transform your OpenClaw assistant into a memory-powered intelligence — now with SME integration**

This package implements a comprehensive 3-layer memory architecture inspired by memU research patterns, specifically designed for OpenClaw. Your assistant gains persistent knowledge graphs, intelligent deduplication, proactive follow-ups, and time-aware context management.

## 🔥 NEW: SME Integration (Recommended)

**[Structured Memory Engine](https://github.com/Bryptobricks/Structured-Memory-Engine)** is now the recommended search and recall backend. It replaces 3 of our 11 components with a unified engine that adds auto-recall, confidence scoring, entity graphs, and semantic embeddings — all local, zero API cost.

**What SME replaces:**
- `hybrid-search.py` → SME's 6-signal ranking (FTS + recency + confidence + type + file weight + entity overlap)
- `salience-decay.py` → SME's confidence decay with reinforcement
- `cross-ref.py` → SME's entity graph with co-occurrence tracking

**What stays unique to this repo (8 components):**
- `memory-dedup.py` — SHA-256 deduplication (SME doesn't deduplicate)
- `memory-typing.py` — Fact classification by type (SME uses chunk_type but doesn't classify)
- `extraction-pipeline.py` — Structured fact extraction from conversations
- `pre-retrieval.sh` — Token-saving query filter
- `correction-tracker.py` — Learn from user corrections (SME detects contradictions but doesn't learn)
- `auto-followup.py` — Draft follow-ups for stale threads (SME doesn't handle open loops)
- `tool-perf.py` — Track tool success/failure rates
- `memory-writer.py` — Read/write path separation

**Why both?** SME is an indexing and retrieval engine — it never modifies your source files. This repo provides the structured knowledge management layer (entity graphs, fact schemas, proactive actions) that SME doesn't cover. Together they're the full stack.

### Quick Start with SME (recommended)
```bash
# 1. Clone this repo + install (skips redundant components)
git clone https://github.com/wiziswiz/openclaw-memory-upgrade.git
cd openclaw-memory-upgrade
./install.sh --with-sme

# 2. Clone and install SME
cd .. && git clone https://github.com/Bryptobricks/Structured-Memory-Engine.git
cd Structured-Memory-Engine && npm install

# 3. Install the OpenClaw plugin extension
cd extensions/memory-sme && npm install && npm link structured-memory-engine

# 4. Optional: add semantic embeddings (50MB local model, runs on Apple Silicon GPU)
cd ../.. && npm install @xenova/transformers --save-optional

# 5. Index your workspace
node lib/index.js index --workspace ~/your-workspace

# 6. Optional: generate embeddings for semantic search
node -e "
const store = require('./lib/store');
const embeddings = require('./lib/embeddings');
const db = store.openDb('$HOME/your-workspace');
embeddings.embedAll(db).then(r => console.log('Embedded:', r));
"

# 7. Patch your OpenClaw config (see below)
```

### OpenClaw Plugin Config
Add to your `~/.openclaw/openclaw.json`:
```json
{
  "plugins": {
    "load": {
      "paths": ["/path/to/Structured-Memory-Engine/extensions"]
    },
    "slots": {
      "memory": "memory-sme"
    },
    "entries": {
      "memory-sme": {
        "enabled": true,
        "config": {
          "workspace": "/path/to/your/workspace",
          "autoRecall": true,
          "autoRecallMaxTokens": 2000,
          "autoCapture": true,
          "autoIndex": true
        }
      }
    }
  }
}
```

Then restart: `openclaw gateway restart`

Verify with `openclaw status` — you should see:
```
│ Memory │ enabled (plugin memory-sme) │
```

### What You Get with SME
- **Auto-recall**: Relevant context injected before every agent turn — no manual searching
- **Confidence scoring**: Facts decay over time, frequently-used ones get reinforced
- **Contradiction detection**: Flags when memory contains conflicting facts
- **Entity graph**: Co-occurrence tracking — mention a person, get their projects too
- **6-signal ranking**: FTS + recency + confidence + type + file weight + entity overlap
- **Token budgeting**: Configurable context injection window (default 2000 tokens)
- **Semantic search**: Optional local embeddings via `@xenova/transformers` (no API cost)

## 🚀 Quick Start (Standalone)

### Interactive Install
```bash
git clone https://github.com/wiziswiz/openclaw-memory-upgrade.git
cd openclaw-memory-upgrade
./install.sh
# Walks you through each component — pick what you want, skip what you don't
```

### Full Install
```bash
./install.sh --all    # Everything, original behavior
```

### Cherry-Pick Mode
```bash
# Just want dedup + extraction? Grab only those:
./install.sh --pick dedup,extraction

# Want scripts but don't touch your AGENTS.md or HEARTBEAT.md?
./install.sh --pick typing,dedup,crossref --skip-agents-append --skip-heartbeat-append
```

### Flags
| Flag | What it does |
|------|-------------|
| `--all` | Install everything (no prompts) |
| `--with-sme` | Install only components that complement SME (skips search, salience, crossref) |
| `--pick comp1,comp2` | Install only specific components |
| `--dry-run` | Preview changes without writing |
| `--skip-agents-append` | Don't modify AGENTS.md |
| `--skip-heartbeat-append` | Don't modify HEARTBEAT.md |
| `--skip-claude-mem` | Skip claude-mem plugin setup |
| `--workspace DIR` | Target a specific directory |

## 🍒 Cherry-Picking Components

| Component | Script | Standalone? | SME? | Best for |
|-----------|--------|-------------|------|----------|
| **dedup** | `memory-dedup.py` | ✅ Yes | Keep | Preventing duplicate facts |
| **typing** | `memory-typing.py` | ✅ Yes | Keep | Classifying facts by type |
| **extraction** | `extraction-pipeline.py` | ✅ Yes | Keep | Auto-extracting facts from conversations |
| **preretrieval** | `pre-retrieval.sh` | ✅ Yes | Keep | Deciding if a query needs memory lookup |
| **corrections** | `correction-tracker.py` | ✅ Yes | Keep | Learning from user corrections |
| **salience** | `salience-decay.py` | Needs entities | ⚡ SME replaces | Scoring facts by recency × frequency |
| **crossref** | `cross-ref.py` | Needs entities | ⚡ SME replaces | Building backlinks between entities |
| **toolperf** | `tool-perf.py` | ✅ Yes | Keep | Tracking tool success/failure rates |
| **followup** | `auto-followup.py` | Needs pending-threads.json | Keep | Drafting follow-ups for open threads |
| **search** | `hybrid-search.py` | Needs entities | ⚡ SME replaces | Vector + keyword search |
| **writer** | `memory-writer.py` | ✅ Yes | Keep | Separating read/write memory paths |

**Recommended with SME** (8 complementary scripts):
```bash
./install.sh --with-sme
```

**Recommended standalone** (3 scripts, no dependencies):
```bash
./install.sh --pick dedup,extraction,typing --skip-agents-append --skip-heartbeat-append
```

## 🏗️ Architecture

### With SME (recommended)
```
┌─────────────────────────────────────────────────────┐
│           SME Search & Recall Engine                │
│  Auto-recall • 6-signal ranking • Confidence decay  │
│  Entity graph • Semantic embeddings • FTS5          │
└─────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────┐
│         Structured Memory Layer (this repo)         │
│  ├── MEMORY.md (patterns & preferences)            │
│  ├── memory/YYYY-MM-DD.md (daily events)           │
│  ├── life/areas/ (entity knowledge graph)          │
│  ├── pending-threads.json (open loops)             │
│  └── patterns.json (intent prediction data)        │
└─────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────┐
│          Proactive Action Layer (this repo)         │
│  ├── Time-aware routing (HEARTBEAT.md)             │
│  ├── Auto follow-ups                               │
│  ├── Correction learning                           │
│  ├── Deduplication + typing                        │
│  └── Tool performance tracking                     │
└─────────────────────────────────────────────────────┘
```

### Standalone (without SME)
```
┌─────────────────────────────────────────────────────┐
│                Vector Memory Layer                  │
│  claude-mem: ChromaDB + semantic search            │
└─────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────┐
│              Structured Memory Layer                │
│  ├── MEMORY.md (patterns & preferences)            │
│  ├── memory/YYYY-MM-DD.md (daily events)           │
│  ├── life/areas/ (entity knowledge graph)          │
│  ├── pending-threads.json (open loops)             │
│  └── patterns.json (intent prediction data)        │
└─────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────┐
│               Proactive Action Layer                │
│  ├── Time-aware routing (HEARTBEAT.md)             │
│  ├── Auto follow-ups                               │
│  ├── Correction learning                           │
│  └── Context optimization                          │
└─────────────────────────────────────────────────────┘
```

## 🗃️ Structured Entity Knowledge Graph

**This is NOT a flat file system** - it's a sophisticated entity-based knowledge graph with structured JSON storage and tiered retrieval for performance.

### Directory Structure
```
life/areas/
├── people/
│   ├── john-smith/
│   │   ├── summary.md      # Weekly-rewritten snapshot (cheap to load)
│   │   └── items.json      # Atomic facts with metadata (detailed)
│   └── sarah-chen/
│       ├── summary.md
│       └── items.json
├── companies/
│   ├── movement-labs/
│   │   ├── summary.md
│   │   └── items.json
│   └── openai/
│       ├── summary.md
│       └── items.json
└── projects/
    └── memory-upgrade/
        ├── summary.md
        └── items.json
```

### 3-Tier Retrieval Strategy

1. **summary.md (Cheap)**: Load first for basic context, ~200-500 words
2. **items.json (Detailed)**: Load specific atomic facts when needed
3. **Full Memory Search**: SME auto-recall or vector/semantic search across all conversations

This architecture saves 70%+ on token usage while maintaining comprehensive knowledge access.

## 📊 Performance Impact

| Metric | Standalone | With SME | Notes |
|--------|-----------|----------|-------|
| Context relevance | ~85% | ~95% | SME's 6-signal ranking + auto-recall |
| Token usage | -30% vs baseline | -30% + budgeted recall | Pre-filtering + SME token budgeting |
| Memory retrieval | <1s | <1ms (FTS5) | SME is 1000x faster on keyword queries |
| Duplicate storage | <5% | <5% | Dedup script handles this in both modes |
| Follow-up rate | ~80% | ~80% | Same — SME doesn't cover this |
| Stale fact handling | Manual decay | Automatic | SME confidence decay + reinforcement |

## 🔧 Requirements

- **OpenClaw**: Already installed and configured
- **Python 3.7+**: All memory scripts are Python-based
- **Bash**: Install script and shell wrappers
- **jq**: JSON processing (auto-installed if missing)
- **Node.js 18+**: Required for SME (if using SME integration)

### Operating Systems
- ✅ macOS (tested on arm64 & x86_64)
- ✅ Linux (Ubuntu, Debian, CentOS)
- ⚠️ Windows (requires WSL)

## 📄 Credits

- **SME (Structured Memory Engine)** by [Bryptobricks](https://github.com/Bryptobricks) — The search and recall engine that powers the recommended configuration. Auto-recall, 6-signal ranking, confidence decay, entity graphs, contradiction detection, and semantic embeddings. [github.com/Bryptobricks/Structured-Memory-Engine](https://github.com/Bryptobricks/Structured-Memory-Engine)
- **Pixel** ([@spacecatpixel](https://x.com/spacecatpixel)) — Original 3-tier memory architecture (knowledge graph + daily notes + tacit knowledge) that forms the foundation of this system
- **memU Research**: Original intelligence patterns (https://github.com/NevaMind-AI/memU)
- **claude-mem**: Vector memory foundation (https://github.com/thedotmack/claude-mem)
- **OpenClaw Community**: Testing and feedback

Built with ❤️ for the OpenClaw ecosystem.

---

**Questions?** Open an issue or join the [OpenClaw Discord](https://discord.com/invite/clawd) community.
