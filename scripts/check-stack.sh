#!/usr/bin/env bash
# check-stack.sh — Verify your memory stack installation
# Run: ./scripts/check-stack.sh

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

ok() { printf "${GREEN}✅ %s${NC}\n" "$1"; }
fail() { printf "${RED}❌ %s${NC}\n" "$1"; }
warn() { printf "${YELLOW}⚠️  %s${NC}\n" "$1"; }

missing=()

echo ""
echo "Memory Stack Health Check"
echo "========================="
echo ""

# Layer 1: SME
if [ -d "$REPO_DIR/extensions/memory-sme" ]; then
  ok "SME extension present"
else
  fail "SME extension missing (expected extensions/memory-sme/)"
  missing+=("SME")
fi

# Layer 2: LCM
if npm ls -g @martian-engineering/lossless-claw --depth=0 >/dev/null 2>&1; then
  lcm_version=$(npm ls -g @martian-engineering/lossless-claw --depth=0 2>/dev/null | grep lossless-claw | sed 's/.*@//' | tr -d '[:space:]')
  ok "LCM installed (v${lcm_version})"
else
  fail "LCM not installed"
  warn "Run: npm install -g @martian-engineering/lossless-claw"
  missing+=("LCM")
fi

# Layer 3: Hooks
if [ -f "$REPO_DIR/extensions/compaction-logger/index.js" ]; then
  ok "Compaction logger hook present"
else
  fail "Compaction logger hook missing"
  missing+=("compaction-logger")
fi

if [ -f "$REPO_DIR/extensions/tool-result-compressor/index.js" ]; then
  ok "Tool result compressor hook present"
else
  fail "Tool result compressor hook missing"
  missing+=("tool-result-compressor")
fi

echo ""

if [ ${#missing[@]} -eq 0 ]; then
  ok "Full stack installed"
else
  echo "Missing: ${missing[*]}"
  echo "See RECOMMENDED-STACK.md for setup instructions."
fi

echo ""
