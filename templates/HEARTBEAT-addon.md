# Time-aware Heartbeat Routing (Memory Upgrade Addon)

This section enhances HEARTBEAT.md with time-aware context switching for optimal memory system performance.

## Time-based Context Routing

### Morning Focus (6-10 AM)
**Priority**: Daily planning + memory consolidation
- Run salience decay update: `./scripts/salience-decay.py sweep`
- Check stale threads: `./scripts/auto-followup.py report`
- Review yesterday's cross-refs: `./scripts/cross-ref.py stats`
- Memory dedup scan: `./scripts/memory-dedup.py scan`

### Pre-meeting/Call (scheduled events)
**Priority**: Context loading + research prep
- Entity lookup: `./scripts/cross-ref.py show people/[name]`
- Recent interactions: Check salience scores for attendees
- Tool performance check: `./scripts/tool-perf.py stats`

### Deep Work Hours (10 AM - 4 PM)
**Priority**: Minimize interruptions, efficient memory
- Use pre-retrieval filtering: Let `pre-retrieval.sh` skip simple queries
- Track tool performance: Log all API calls via `tool-perf.py`
- Correction learning: Monitor for user feedback patterns

### Evening Wrap-up (6-9 PM)
**Priority**: Thread cleanup + follow-up preparation
- Auto follow-up generation: `./scripts/auto-followup.py report`
- Cross-reference update: `./scripts/cross-ref.py scan`
- Correction pattern review: `./scripts/correction-tracker.py stats`
- Memory typing migration: `./scripts/memory-typing.py migrate`

### Late Night/Maintenance (10 PM+)
**Priority**: System optimization + batch processing
- Full memory deduplication: `./scripts/memory-dedup.py rebuild`
- Salience score recalculation: `./scripts/salience-decay.py entity [recent_entities]`
- Relationship graph rebuild: `./scripts/cross-ref.py rebuild`
- Tool performance cleanup: `./scripts/tool-perf.py clean --days 30`

## Context-aware Memory Loading

Before each session, determine context needs:

```bash
# Quick context check
QUERY_TYPE=$(./scripts/pre-retrieval.sh "$1")

if [[ "$QUERY_TYPE" == "search" ]]; then
    # Load relevant entity context
    ENTITY=$(echo "$1" | grep -oE '\b[A-Z][a-z]+\b' | head -1)
    if [[ -n "$ENTITY" ]]; then
        ./scripts/cross-ref.py show "people/$ENTITY" --depth 1
        ./scripts/salience-decay.py entity "$ENTITY" --limit 5
    fi
fi
```

## Proactive Pattern Recognition

### Auto-correction Integration
```bash
# Check for known patterns before taking action
CORRECTIONS=$(./scripts/correction-tracker.py check "$ACTION_DESCRIPTION")
if [[ -n "$CORRECTIONS" ]]; then
    echo "⚠️  Similar situations have corrections: $CORRECTIONS"
fi
```

### Intent Prediction (Phase 3)
- Morning crypto check → Pre-fetch portfolio data
- Pre-call research → Auto-load entity relationships
- Thread follow-ups → Draft messages in advance

## Memory System Health Monitoring

### Daily Checks
- Deduplication efficiency: `./scripts/memory-dedup.py stats`
- Cross-reference coverage: `./scripts/cross-ref.py list | wc -l`
- Correction learning rate: `./scripts/correction-tracker.py stats`

### Weekly Maintenance
- Salience decay sweep: `./scripts/salience-decay.py sweep`
- Relationship graph rebuild: `./scripts/cross-ref.py rebuild`
- Tool performance analysis: `./scripts/tool-perf.py summary`

---

**Note**: Append this section to your existing HEARTBEAT.md file. These patterns will become automatic as the memory system learns your workflows.