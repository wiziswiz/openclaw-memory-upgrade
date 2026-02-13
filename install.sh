#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# OpenClaw Memory Upgrade — Interactive Installer v2
# Modular: pick components you want, skip what you don't
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; PURPLE='\033[0;35m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

ok() { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
info() { echo -e "  ${BLUE}ℹ${NC}  $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${OPENCLAW_WORKSPACE:-${WORKSPACE_DIR:-$(pwd)}}"

# ── Defaults ──
DRY_RUN=false
INTERACTIVE=true
INSTALL_ALL=false
SKIP_CLAUDE_MEM=false
SKIP_AGENTS_APPEND=false
SKIP_HEARTBEAT_APPEND=false
SKIP_CRONS=false
SELECTED_COMPONENTS=()

usage() {
    echo -e "${BOLD}OpenClaw Memory Upgrade Installer v2${NC}"
    echo ""
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Modes:"
    echo "  (default)           Interactive — choose components one by one"
    echo "  --all               Install everything (original behavior)"
    echo "  --pick COMPONENTS   Comma-separated list of components to install"
    echo ""
    echo "Options:"
    echo "  --workspace DIR         Target workspace directory (default: cwd)"
    echo "  --dry-run               Show what would be done without making changes"
    echo "  --skip-claude-mem       Skip claude-mem plugin setup"
    echo "  --skip-agents-append    Don't modify AGENTS.md"
    echo "  --skip-heartbeat-append Don't modify HEARTBEAT.md"
    echo "  --skip-crons            Don't suggest cron jobs"
    echo "  --help                  Show this help"
    echo ""
    echo "Components (for --pick):"
    echo "  core         Directories, state files, example entity (always included)"
    echo "  typing       Memory typing classifier"
    echo "  dedup        Deduplication engine (SHA-256 hashing)"
    echo "  preretrieval Pre-retrieval decision filter"
    echo "  toolperf     Tool performance tracker"
    echo "  salience     Salience decay scoring"
    echo "  crossref     Cross-referencing / backlinks"
    echo "  followup     Autonomous follow-up drafter"
    echo "  corrections  Correction learning system"
    echo "  search       Hybrid search (vector + keyword)"
    echo "  extraction   Extraction pipeline (auto-fact extraction)"
    echo "  writer       Memory writer (read/write separation)"
    echo "  heartbeat    Time-aware heartbeat routing (appends to HEARTBEAT.md)"
    echo "  agents       Memory docs (appends to AGENTS.md)"
    echo ""
    echo "Examples:"
    echo "  ./install.sh                          # Interactive mode"
    echo "  ./install.sh --all                    # Full install"
    echo "  ./install.sh --pick dedup,extraction  # Just dedup + extraction"
    echo "  ./install.sh --pick core,typing,dedup --skip-agents-append"
}

# ── Component definitions ──
declare -A COMPONENT_SCRIPTS=(
    [typing]="memory-typing.py"
    [dedup]="memory-dedup.py"
    [preretrieval]="pre-retrieval.sh"
    [toolperf]="tool-perf.py"
    [salience]="salience-decay.py"
    [crossref]="cross-ref.py"
    [followup]="auto-followup.py"
    [corrections]="correction-tracker.py"
    [search]="hybrid-search.py"
    [extraction]="extraction-pipeline.py"
    [writer]="memory-writer.py"
)

declare -A COMPONENT_DESCS=(
    [typing]="Memory Typing — classifies facts as profile/event/knowledge/behavior/skill/tool"
    [dedup]="Dedup Engine — SHA-256 content hashing to prevent duplicate facts"
    [preretrieval]="Pre-retrieval Filter — decides if a query needs memory lookup"
    [toolperf]="Tool Performance — tracks which tools succeed/fail and how long they take"
    [salience]="Salience Decay — scores facts by recency × frequency"
    [crossref]="Cross-references — builds backlinks between entities"
    [followup]="Auto Follow-up — drafts follow-up messages for pending threads"
    [corrections]="Correction Learning — tracks when the user corrects the assistant"
    [search]="Hybrid Search — vector 60% + keyword 40% retrieval"
    [extraction]="Extraction Pipeline — auto-extracts facts from conversations"
    [writer]="Memory Writer — separates read/write paths for better concurrency"
)

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case $1 in
        --workspace) WORKSPACE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --all) INSTALL_ALL=true; INTERACTIVE=false; shift ;;
        --pick) IFS=',' read -ra SELECTED_COMPONENTS <<< "$2"; INTERACTIVE=false; shift 2 ;;
        --skip-claude-mem) SKIP_CLAUDE_MEM=true; shift ;;
        --skip-agents-append) SKIP_AGENTS_APPEND=true; shift ;;
        --skip-heartbeat-append) SKIP_HEARTBEAT_APPEND=true; shift ;;
        --skip-crons) SKIP_CRONS=true; shift ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# ── Header ──
echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   🧠 OpenClaw Memory Upgrade v2          ║"
echo "  ║   Modular • Pick what you need           ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  Workspace: ${BOLD}$WORKSPACE${NC}"
if $DRY_RUN; then echo -e "  Mode: ${YELLOW}DRY RUN${NC}"; fi

# ── Pre-flight ──
echo -e "\n${PURPLE}${BOLD}[1]${NC} ${BOLD}Pre-flight checks${NC}"
if ! command -v python3 &>/dev/null; then
    fail "Python 3 required but not found"; exit 1
fi
ok "Python 3 found ($(python3 --version 2>&1 | awk '{print $2}'))"
[ -d "$WORKSPACE" ] || { $DRY_RUN || mkdir -p "$WORKSPACE"; }
ok "Workspace: $WORKSPACE"

# ── Interactive component selection ──
if $INTERACTIVE; then
    echo ""
    echo -e "${BOLD}Select components to install:${NC}"
    echo -e "${DIM}(Enter y/n for each, or 'a' to install all remaining)${NC}"
    echo ""
    
    ALL_COMPONENTS=(typing dedup preretrieval toolperf salience crossref followup corrections search extraction writer)
    install_all_remaining=false
    
    for comp in "${ALL_COMPONENTS[@]}"; do
        if $install_all_remaining; then
            SELECTED_COMPONENTS+=("$comp")
            ok "${COMPONENT_DESCS[$comp]}"
            continue
        fi
        
        echo -ne "  ${CYAN}${COMPONENT_DESCS[$comp]}${NC} [y/n/a] "
        read -r answer
        case "$answer" in
            y|Y) SELECTED_COMPONENTS+=("$comp") ;;
            a|A) SELECTED_COMPONENTS+=("$comp"); install_all_remaining=true ;;
            *) info "Skipped $comp" ;;
        esac
    done
    
    # Ask about AGENTS.md / HEARTBEAT.md modifications
    echo ""
    if [ -f "$WORKSPACE/AGENTS.md" ]; then
        echo -ne "  ${CYAN}Append memory docs to AGENTS.md?${NC} [y/n] "
        read -r answer
        [[ "$answer" != "y" && "$answer" != "Y" ]] && SKIP_AGENTS_APPEND=true
    fi
    
    if [ -f "$WORKSPACE/HEARTBEAT.md" ]; then
        echo -ne "  ${CYAN}Append time-aware routing to HEARTBEAT.md?${NC} [y/n] "
        read -r answer
        [[ "$answer" != "y" && "$answer" != "Y" ]] && SKIP_HEARTBEAT_APPEND=true
    fi
fi

if $INSTALL_ALL; then
    SELECTED_COMPONENTS=(typing dedup preretrieval toolperf salience crossref followup corrections search extraction writer)
fi

echo ""
echo -e "${BOLD}Installing ${#SELECTED_COMPONENTS[@]} components:${NC} ${SELECTED_COMPONENTS[*]}"

# ── Core setup (always runs) ──
echo -e "\n${PURPLE}${BOLD}[2]${NC} ${BOLD}Core directory structure${NC}"

dirs=("scripts" "memory" "life/areas/people" "life/areas/companies" "life/areas/projects" "drafts")
for dir in "${dirs[@]}"; do
    target="$WORKSPACE/$dir"
    if [ ! -d "$target" ]; then
        $DRY_RUN || mkdir -p "$target"
        ok "Created $dir/"
    else
        info "$dir/ exists"
    fi
done

# Example entity
example_entity_dir="$WORKSPACE/life/areas/people/example-user"
if [ ! -d "$example_entity_dir" ] && [ -f "$SCRIPT_DIR/templates/example-entity/summary.md" ]; then
    $DRY_RUN || { mkdir -p "$example_entity_dir"; cp "$SCRIPT_DIR/templates/example-entity/summary.md" "$example_entity_dir/"; cp "$SCRIPT_DIR/templates/example-entity/items.json" "$example_entity_dir/"; }
    ok "Created example entity (shows JSON format)"
fi

# ── Install selected scripts ──
echo -e "\n${PURPLE}${BOLD}[3]${NC} ${BOLD}Installing selected scripts${NC}"

installed_count=0
for comp in "${SELECTED_COMPONENTS[@]}"; do
    file="${COMPONENT_SCRIPTS[$comp]:-}"
    if [ -z "$file" ]; then
        warn "Unknown component: $comp"
        continue
    fi
    
    src="$SCRIPT_DIR/scripts/$file"
    dst="$WORKSPACE/scripts/$file"
    
    if [ ! -f "$src" ]; then
        fail "Source not found: $src"
        continue
    fi
    
    $DRY_RUN || { cp "$src" "$dst"; chmod +x "$dst"; }
    ok "${COMPONENT_DESCS[$comp]}"
    ((installed_count++))
done

# ── State files (only for installed components) ──
echo -e "\n${PURPLE}${BOLD}[4]${NC} ${BOLD}State files${NC}"

create_if_missing() {
    local file="$1" content="$2" target="$WORKSPACE/$file"
    if [ ! -f "$target" ]; then
        $DRY_RUN || echo "$content" > "$target"
        ok "Created $file"
    else
        info "$file exists (preserved)"
    fi
}

# Always create these
create_if_missing "pending-threads.json" '{"version":1,"threads":[]}'
create_if_missing "memory/$(date +%Y-%m-%d).md" "# $(date +%Y-%m-%d) Daily Notes"

# Component-specific state files
for comp in "${SELECTED_COMPONENTS[@]}"; do
    case "$comp" in
        dedup) create_if_missing ".memory-hashes.json" "{}" ;;
        toolperf) create_if_missing ".tool-perf.json" '{"version":1,"calls":[]}' ;;
        corrections) create_if_missing ".corrections.json" '{"version":1,"corrections":[]}' ;;
        writer) create_if_missing ".memory-write-queue.json" "[]" ;;
        extraction) create_if_missing ".last-extraction.json" '{"last_processed":"1970-01-01T00:00:00","last_run":"1970-01-01T00:00:00"}' ;;
        crossref|salience)
            if [ -f "$SCRIPT_DIR/templates/patterns-template.json" ] && [ ! -f "$WORKSPACE/patterns.json" ]; then
                $DRY_RUN || cp "$SCRIPT_DIR/templates/patterns-template.json" "$WORKSPACE/patterns.json"
                ok "Created patterns.json"
            fi
            ;;
    esac
done

# ── HEARTBEAT.md (optional) ──
if ! $SKIP_HEARTBEAT_APPEND; then
    echo -e "\n${PURPLE}${BOLD}[5]${NC} ${BOLD}Heartbeat routing${NC}"
    if [ -f "$SCRIPT_DIR/templates/HEARTBEAT-addon.md" ]; then
        if [ -f "$WORKSPACE/HEARTBEAT.md" ] && grep -q "Time-Aware Routing" "$WORKSPACE/HEARTBEAT.md" 2>/dev/null; then
            info "HEARTBEAT.md already has time-aware routing"
        elif [ -f "$WORKSPACE/HEARTBEAT.md" ]; then
            $DRY_RUN || { echo "" >> "$WORKSPACE/HEARTBEAT.md"; cat "$SCRIPT_DIR/templates/HEARTBEAT-addon.md" >> "$WORKSPACE/HEARTBEAT.md"; }
            ok "Appended time-aware routing"
        else
            $DRY_RUN || { echo "# HEARTBEAT.md" > "$WORKSPACE/HEARTBEAT.md"; echo "" >> "$WORKSPACE/HEARTBEAT.md"; cat "$SCRIPT_DIR/templates/HEARTBEAT-addon.md" >> "$WORKSPACE/HEARTBEAT.md"; }
            ok "Created HEARTBEAT.md with time-aware routing"
        fi
    fi
else
    info "Skipped HEARTBEAT.md modification"
fi

# ── AGENTS.md (optional) ──
if ! $SKIP_AGENTS_APPEND; then
    echo -e "\n${PURPLE}${BOLD}[6]${NC} ${BOLD}Memory documentation${NC}"
    if [ -f "$SCRIPT_DIR/templates/AGENTS-memory.md" ]; then
        if [ -f "$WORKSPACE/AGENTS.md" ] && grep -q "Three-Layer Memory" "$WORKSPACE/AGENTS.md" 2>/dev/null; then
            info "AGENTS.md already has memory docs"
        elif [ -f "$WORKSPACE/AGENTS.md" ]; then
            $DRY_RUN || { echo "" >> "$WORKSPACE/AGENTS.md"; cat "$SCRIPT_DIR/templates/AGENTS-memory.md" >> "$WORKSPACE/AGENTS.md"; }
            ok "Appended memory system docs"
        else
            $DRY_RUN || { echo "# AGENTS.md" > "$WORKSPACE/AGENTS.md"; echo "" >> "$WORKSPACE/AGENTS.md"; cat "$SCRIPT_DIR/templates/AGENTS-memory.md" >> "$WORKSPACE/AGENTS.md"; }
            ok "Created AGENTS.md with memory docs"
        fi
    fi
else
    info "Skipped AGENTS.md modification"
fi

# ── Initial indexing (only for installed components) ──
echo -e "\n${PURPLE}${BOLD}[7]${NC} ${BOLD}Initial indexing${NC}"

if ! $DRY_RUN; then
    cd "$WORKSPACE"
    
    # Only run indexing for installed components
    for comp in "${SELECTED_COMPONENTS[@]}"; do
        case "$comp" in
            dedup)
                result=$(python3 scripts/memory-dedup.py scan 2>&1 | tail -1)
                ok "Dedup scan: $result"
                ;;
            crossref)
                entity_count=$(find life/areas -name "items.json" 2>/dev/null | wc -l | tr -d ' ')
                if [ "$entity_count" -gt 0 ]; then
                    python3 scripts/cross-ref.py build 2>&1 | tail -1
                    ok "Cross-refs built ($entity_count entities)"
                else
                    info "No entities yet — cross-refs will build as you add data"
                fi
                ;;
            salience)
                python3 scripts/salience-decay.py migrate 2>&1 | tail -1
                ok "Salience fields initialized"
                ;;
        esac
    done
else
    info "Would run indexing for: ${SELECTED_COMPONENTS[*]}"
fi

# ── claude-mem (optional) ──
if ! $SKIP_CLAUDE_MEM; then
    echo -e "\n${PURPLE}${BOLD}[8]${NC} ${BOLD}claude-mem (optional)${NC}"
    if [ -d "$HOME/.openclaw/extensions/claude-mem" ]; then
        if [ -f "$HOME/.openclaw/extensions/claude-mem/index.js" ]; then
            ok "claude-mem already installed"
        else
            $DRY_RUN || { echo 'export { default } from "./dist/index.js";' > "$HOME/.openclaw/extensions/claude-mem/index.js"; echo 'export * from "./dist/index.js";' >> "$HOME/.openclaw/extensions/claude-mem/index.js"; }
            ok "Created claude-mem shim"
            warn "Restart gateway: openclaw gateway restart"
        fi
    else
        info "claude-mem not installed (optional)"
    fi
fi

# ── Done ──
echo ""
echo -e "${GREEN}${BOLD}  ╔══════════════════════════════════════════╗"
echo "  ║   🧠 Memory Upgrade Complete!             ║"
echo -e "  ║   ${installed_count} components installed               ║"
echo "  ╚══════════════════════════════════════════╝${NC}"
echo ""
if [ ${#SELECTED_COMPONENTS[@]} -gt 0 ]; then
    echo -e "  ${BOLD}Installed:${NC} ${SELECTED_COMPONENTS[*]}"
fi
echo ""
echo -e "  ${BOLD}Quick test:${NC}"
echo -e "    ${DIM}cd $WORKSPACE${NC}"
[[ " ${SELECTED_COMPONENTS[*]} " =~ " typing " ]] && echo -e "    ${DIM}python3 scripts/memory-typing.py classify \"user prefers dark mode\"${NC}"
[[ " ${SELECTED_COMPONENTS[*]} " =~ " dedup " ]] && echo -e "    ${DIM}python3 scripts/memory-dedup.py scan${NC}"
[[ " ${SELECTED_COMPONENTS[*]} " =~ " preretrieval " ]] && echo -e "    ${DIM}./scripts/pre-retrieval.sh \"what time is it\"${NC}"
echo ""
echo -e "  ${BOLD}Cherry-pick guide:${NC} See README.md §Cherry-Picking Components"
echo ""
