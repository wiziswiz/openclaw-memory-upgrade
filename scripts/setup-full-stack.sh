#!/usr/bin/env bash
# setup-full-stack.sh — Install the full recommended memory stack
# Run after initial SME setup to add LCM + hooks
# Usage: ./scripts/setup-full-stack.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "Memory Stack Setup"
echo "==================="
echo ""
echo "This will set up the full recommended memory stack:"
echo "  Layer 1: SME (already included)"
echo "  Layer 2: LCM (lossless-claw — within-session context preservation)"
echo "  Layer 3: Hooks (compaction logger + tool result compressor)"
echo ""

# Check if LCM is already installed
if npm ls -g @martian-engineering/lossless-claw --depth=0 >/dev/null 2>&1; then
  printf "${GREEN}✅ LCM already installed${NC}\n"
  INSTALL_LCM="skip"
else
  printf "${YELLOW}LCM (lossless-claw) is not installed.${NC}\n"
  echo "It provides within-session context preservation via DAG-based summaries."
  echo "SME handles between sessions; LCM handles within a session."
  echo ""
  read -p "Install lossless-claw? [y/N] " -n 1 -r
  echo ""
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    INSTALL_LCM="yes"
  else
    INSTALL_LCM="no"
  fi
fi

if [ "$INSTALL_LCM" = "yes" ]; then
  echo ""
  echo "Installing @martian-engineering/lossless-claw..."
  npm install -g @martian-engineering/lossless-claw
  printf "${GREEN}✅ LCM installed${NC}\n"
  echo ""
  echo "Add to your openclaw.json plugins:"
  echo '  "plugins": { "@martian-engineering/lossless-claw": {} }'
fi

# Hooks are already in the repo — just remind about config
echo ""
echo "Hooks are included in extensions/. To enable them, add to openclaw.json:"
echo ""
echo '  "hooks": {'
echo '    "session:compact:after": "./extensions/compaction-logger/index.js",'
echo '    "tool_result_persist": "./extensions/tool-result-compressor/index.js"'
echo '  }'
echo ""

# Run health check
echo "Running stack health check..."
echo ""
bash "$SCRIPT_DIR/check-stack.sh"
