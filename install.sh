#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# OpenClaw Memory Upgrade — Installer
# Adds 10-component memory system to any OpenClaw workspace
# ============================================================================

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; PURPLE='\033[0;35m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

ok() { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
info() { echo -e "  ${BLUE}ℹ${NC}  $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }
step() { echo -e "\n${PURPLE}${BOLD}[$1/8]${NC} ${BOLD}$2${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default workspace = OpenClaw workspace or current dir
WORKSPACE="${OPENCLAW_WORKSPACE:-${WORKSPACE_DIR:-$(pwd)}}"

usage() {
    echo -e "${BOLD}OpenClaw Memory Upgrade Installer${NC}"
    echo ""
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --workspace DIR    Target workspace directory (default: current dir)"
    echo "  --dry-run          Show what would be done without making changes"
    echo "  --skip-claude-mem  Skip claude-mem plugin setup"
    echo "  --help             Show this help"
    echo ""
    echo "Environment:"
    echo "  WORKSPACE_DIR      Alternative to --workspace flag"
}

DRY_RUN=false
SKIP_CLAUDE_MEM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --workspace) WORKSPACE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --skip-claude-mem) SKIP_CLAUDE_MEM=true; shift ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   🧠 OpenClaw Memory Upgrade Installer   ║"
echo "  ║   10 components • 3-layer architecture   ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  Workspace: ${BOLD}$WORKSPACE${NC}"
echo -e "  Mode: ${DRY_RUN:+${YELLOW}DRY RUN${NC}}${DRY_RUN:-${GREEN}INSTALL${NC}}"

# ── Pre-flight checks ──────────────────────────────────────────────────────
step "1" "Pre-flight checks"

if ! command -v python3 &>/dev/null; then
    fail "Python 3 required but not found"; exit 1
fi
ok "Python 3 found ($(python3 --version 2>&1 | awk '{print $2}'))"

if [ ! -d "$WORKSPACE" ]; then
    if $DRY_RUN; then
        warn "Workspace $WORKSPACE doesn't exist (would create)"
    else
        mkdir -p "$WORKSPACE"
        ok "Created workspace: $WORKSPACE"
    fi
else
    ok "Workspace exists: $WORKSPACE"
fi

# Check for existing AGENTS.md (indicates OpenClaw workspace)
if [ -f "$WORKSPACE/AGENTS.md" ]; then
    ok "OpenClaw workspace detected (AGENTS.md found)"
else
    warn "No AGENTS.md found — creating a minimal workspace"
fi

# ── Create directory structure ─────────────────────────────────────────────
step "2" "Creating directory structure"

dirs=("scripts" "memory" "life/areas/people" "life/areas/companies" "life/areas/projects" "drafts")
for dir in "${dirs[@]}"; do
    target="$WORKSPACE/$dir"
    if [ ! -d "$target" ]; then
        if ! $DRY_RUN; then mkdir -p "$target"; fi
        ok "Created $dir/"
    else
        info "$dir/ already exists"
    fi
done

# ── Copy scripts ───────────────────────────────────────────────────────────
step "3" "Installing memory scripts"

scripts=(
    "memory-typing.py:Memory Typing (profile/event/knowledge/behavior/skill/tool)"
    "memory-dedup.py:Deduplication Engine (SHA-256 content hashing)"
    "pre-retrieval.sh:Pre-retrieval Decision Filter"
    "tool-perf.py:Tool Performance Tracker"
    "salience-decay.py:Salience Decay (recency × frequency scoring)"
    "cross-ref.py:Cross-referencing / Backlinks Graph"
    "auto-followup.py:Autonomous Follow-up Drafter"
    "correction-tracker.py:Correction Learning System"
)

for entry in "${scripts[@]}"; do
    file="${entry%%:*}"
    desc="${entry#*:}"
    src="$SCRIPT_DIR/scripts/$file"
    dst="$WORKSPACE/scripts/$file"

    if [ ! -f "$src" ]; then
        fail "Source not found: $src"
        continue
    fi

    if ! $DRY_RUN; then
        cp "$src" "$dst"
        chmod +x "$dst"
    fi
    ok "$desc"
done

# ── Initialize state files ─────────────────────────────────────────────────
step "4" "Initializing state files"

create_state_file() {
    local file="$1" content="$2" target="$WORKSPACE/$file"
    if [ ! -f "$target" ]; then
        if ! $DRY_RUN; then echo "$content" > "$target"; fi
        ok "Created $file"
    else
        info "$file already exists (preserved)"
    fi
}

create_state_file ".memory-hashes.json" "{}"
create_state_file ".tool-perf.json" '{"version":1,"calls":[]}'
create_state_file ".corrections.json" '{"version":1,"corrections":[]}'
create_state_file "pending-threads.json" '{"version":1,"threads":[]}'

# Patterns file (larger template)
if [ ! -f "$WORKSPACE/patterns.json" ]; then
    if [ -f "$SCRIPT_DIR/templates/patterns-template.json" ]; then
        if ! $DRY_RUN; then
            cp "$SCRIPT_DIR/templates/patterns-template.json" "$WORKSPACE/patterns.json"
        fi
        ok "Created patterns.json from template"
    else
        if ! $DRY_RUN; then
            echo '{"version":1,"relationships":[],"behavioral_sequences":[]}' > "$WORKSPACE/patterns.json"
        fi
        ok "Created patterns.json (empty)"
    fi
else
    info "patterns.json already exists (preserved)"
fi

# ── Apply HEARTBEAT routing ────────────────────────────────────────────────
step "5" "Configuring time-aware heartbeat routing"

if [ -f "$SCRIPT_DIR/templates/HEARTBEAT-addon.md" ]; then
    if [ -f "$WORKSPACE/HEARTBEAT.md" ]; then
        if grep -q "Time-Aware Routing" "$WORKSPACE/HEARTBEAT.md" 2>/dev/null; then
            info "HEARTBEAT.md already has time-aware routing"
        else
            if ! $DRY_RUN; then
                echo "" >> "$WORKSPACE/HEARTBEAT.md"
                cat "$SCRIPT_DIR/templates/HEARTBEAT-addon.md" >> "$WORKSPACE/HEARTBEAT.md"
            fi
            ok "Appended time-aware routing to HEARTBEAT.md"
        fi
    else
        if ! $DRY_RUN; then
            echo "# HEARTBEAT.md" > "$WORKSPACE/HEARTBEAT.md"
            echo "" >> "$WORKSPACE/HEARTBEAT.md"
            cat "$SCRIPT_DIR/templates/HEARTBEAT-addon.md" >> "$WORKSPACE/HEARTBEAT.md"
        fi
        ok "Created HEARTBEAT.md with time-aware routing"
    fi
else
    warn "HEARTBEAT template not found — skipping"
fi

# ── Apply AGENTS memory docs ──────────────────────────────────────────────
step "6" "Adding memory system documentation"

if [ -f "$SCRIPT_DIR/templates/AGENTS-memory.md" ]; then
    if [ -f "$WORKSPACE/AGENTS.md" ]; then
        if grep -q "Three-Layer Memory" "$WORKSPACE/AGENTS.md" 2>/dev/null; then
            info "AGENTS.md already has memory system docs"
        else
            if ! $DRY_RUN; then
                echo "" >> "$WORKSPACE/AGENTS.md"
                cat "$SCRIPT_DIR/templates/AGENTS-memory.md" >> "$WORKSPACE/AGENTS.md"
            fi
            ok "Appended memory system docs to AGENTS.md"
        fi
    else
        if ! $DRY_RUN; then
            echo "# AGENTS.md" > "$WORKSPACE/AGENTS.md"
            echo "" >> "$WORKSPACE/AGENTS.md"
            cat "$SCRIPT_DIR/templates/AGENTS-memory.md" >> "$WORKSPACE/AGENTS.md"
        fi
        ok "Created AGENTS.md with memory system docs"
    fi
else
    warn "AGENTS template not found — skipping"
fi

# ── Run initial indexing ───────────────────────────────────────────────────
step "7" "Running initial indexing"

if ! $DRY_RUN; then
    # Dedup scan
    cd "$WORKSPACE"
    result=$(python3 scripts/memory-dedup.py scan 2>&1 | tail -1)
    ok "Dedup scan: $result"

    # Cross-ref build (if entities exist)
    entity_count=$(find life/areas -name "items.json" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$entity_count" -gt 0 ]; then
        python3 scripts/cross-ref.py build 2>&1 | tail -1
        ok "Cross-references built from $entity_count entity files"
    else
        info "No entities yet — cross-refs will build as you add data"
    fi

    # Salience migration
    python3 scripts/salience-decay.py migrate 2>&1 | tail -1
    ok "Salience fields initialized"
else
    info "Would run: dedup scan, cross-ref build, salience migrate"
fi

# ── claude-mem (optional) ──────────────────────────────────────────────────
step "8" "claude-mem integration (optional)"

if $SKIP_CLAUDE_MEM; then
    info "Skipped (--skip-claude-mem flag)"
elif [ -d "$HOME/.openclaw/extensions/claude-mem" ]; then
    # Check for the index.js shim
    if [ -f "$HOME/.openclaw/extensions/claude-mem/index.js" ]; then
        ok "claude-mem already installed and shimmed"
    else
        if ! $DRY_RUN; then
            echo 'export { default } from "./dist/index.js";' > "$HOME/.openclaw/extensions/claude-mem/index.js"
            echo 'export * from "./dist/index.js";' >> "$HOME/.openclaw/extensions/claude-mem/index.js"
            ok "Created index.js shim for claude-mem plugin"
            warn "Restart OpenClaw gateway to load: openclaw gateway restart"
        else
            info "Would create index.js shim for claude-mem"
        fi
    fi
elif command -v claude-mem &>/dev/null; then
    info "claude-mem CLI found but OpenClaw plugin not installed"
    info "Run: curl -fsSL https://install.cmem.ai/openclaw.sh | bash"
else
    info "claude-mem not installed — memory system works without it"
    info "Optional: curl -fsSL https://install.cmem.ai/openclaw.sh | bash"
fi

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ╔══════════════════════════════════════════╗"
echo "  ║   🧠 Memory Upgrade Complete!             ║"
echo "  ╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Installed components:${NC}"
echo -e "    ${CYAN}Phase 2:${NC} typing · dedup · pre-retrieval · tool-perf · salience · cross-refs"
echo -e "    ${CYAN}Phase 3:${NC} time-aware heartbeats · auto follow-ups · corrections · intent prediction"
echo ""
echo -e "  ${BOLD}Quick test:${NC}"
echo -e "    ${DIM}cd $WORKSPACE${NC}"
echo -e "    ${DIM}python3 scripts/memory-typing.py classify \"Claude is an AI assistant\"${NC}"
echo -e "    ${DIM}python3 scripts/memory-dedup.py scan${NC}"
echo -e "    ${DIM}./scripts/pre-retrieval.sh \"what time is it\"${NC}"
echo ""
echo -e "  ${BOLD}Docs:${NC} See README.md for full usage guide"
echo ""
