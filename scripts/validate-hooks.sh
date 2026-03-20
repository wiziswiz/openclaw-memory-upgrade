#!/usr/bin/env bash
# validate-hooks.sh — Pre-gateway hook validation
# Checks that all hook entries in openclaw.json point to resolvable paths.
# Run before 'openclaw gateway start' to prevent cryptic MODULE_NOT_FOUND crashes.
#
# Usage:
#   bash scripts/validate-hooks.sh              # check only
#   bash scripts/validate-hooks.sh --fix        # check + remove bad entries
#   bash scripts/validate-hooks.sh /path/to/openclaw.json  # custom path

set -euo pipefail

command -v jq >/dev/null 2>&1 || { echo "❌ jq required. Install: brew install jq (macOS) or apt install jq (Linux)"; exit 1; }

FIX_MODE=false
CONFIG="${HOME}/.openclaw/openclaw.json"

for arg in "$@"; do
  case "$arg" in
    --fix) FIX_MODE=true ;;
    *) [ -f "$arg" ] && CONFIG="$arg" ;;
  esac
done

if [ ! -f "$CONFIG" ]; then
  echo "❌ Config not found: $CONFIG"
  exit 1
fi

ERRORS=0
BAD_ENTRIES=()
BAD_TOP_KEYS=()

echo "🔍 Validating hooks in: $CONFIG"

# 1. Check for hook-like entries at the wrong JSON level
VALID_TOP_KEYS="meta wizard browser auth acp agents tools messages commands hooks channels gateway skills plugins _template_version _notes"

while IFS= read -r key; do
  is_valid=false
  for valid in $VALID_TOP_KEYS; do
    [ "$key" = "$valid" ] && is_valid=true && break
  done
  if ! $is_valid; then
    # Check if it looks like a hook entry (has a path-like value)
    val=$(jq -r ".[\"$key\"]" "$CONFIG" 2>/dev/null)
    if [[ "$val" == ./* ]] || [[ "$val" == /* ]] || [[ "$val" == *".js"* ]]; then
      echo "❌ \"$key\" is at root level with path value \"$val\" — this is not a valid config key"
      echo "   Hook entries belong under hooks.internal.entries, not at the top level"
      BAD_TOP_KEYS+=("$key")
      ERRORS=$((ERRORS + 1))
    fi
  fi
done < <(jq -r 'keys[]' "$CONFIG" 2>/dev/null)

# 2. Validate hook entries under hooks.internal.entries
if jq -e '.hooks.internal.entries // empty' "$CONFIG" >/dev/null 2>&1; then
  while IFS= read -r entry_name; do
    # Get the entry — check if it has a path field
    entry_path=$(jq -r ".hooks.internal.entries[\"$entry_name\"].path // empty" "$CONFIG" 2>/dev/null)

    if [ -n "$entry_path" ]; then
      config_dir="$(dirname "$CONFIG")"
      
      # Try multiple resolution strategies
      resolved=false
      
      # 1. Relative to config dir
      [ -e "$config_dir/$entry_path" ] && resolved=true
      
      # 2. Absolute path
      [ -e "$entry_path" ] && resolved=true
      
      # 3. Node module resolution
      if ! $resolved; then
        node -e "require.resolve('$entry_path')" 2>/dev/null && resolved=true
      fi
      
      if ! $resolved; then
        echo "❌ Hook \"$entry_name\" → \"$entry_path\" does not resolve"
        BAD_ENTRIES+=("$entry_name")
        ERRORS=$((ERRORS + 1))
      fi
    fi
  done < <(jq -r '.hooks.internal.entries // {} | keys[]' "$CONFIG" 2>/dev/null)
fi

# 3. Check for known-bad hook key patterns at hooks level
for suspect in "session:compact:after" "tool_result_persist"; do
  if jq -e ".hooks[\"$suspect\"] // empty" "$CONFIG" >/dev/null 2>&1; then
    echo "❌ hooks.\"$suspect\" is not a valid hook slot — should be under hooks.internal.entries or removed"
    ERRORS=$((ERRORS + 1))
  fi
done

if [ "$ERRORS" -eq 0 ]; then
  echo "✅ All hooks valid"
  exit 0
fi

echo ""
echo "Found $ERRORS error(s)"

if $FIX_MODE; then
  echo "🔧 Fixing..."
  cp "$CONFIG" "${CONFIG}.bak"
  echo "   Backup: ${CONFIG}.bak"
  
  TEMP=$(mktemp)
  cp "$CONFIG" "$TEMP"
  
  for key in "${BAD_TOP_KEYS[@]}"; do
    jq "del(.[\"$key\"])" "$TEMP" > "${TEMP}.new" && mv "${TEMP}.new" "$TEMP"
    echo "   Removed root key: \"$key\""
  done
  
  for entry in "${BAD_ENTRIES[@]}"; do
    jq "del(.hooks.internal.entries[\"$entry\"])" "$TEMP" > "${TEMP}.new" && mv "${TEMP}.new" "$TEMP"
    echo "   Removed hook entry: \"$entry\""
  done
  
  for suspect in "session:compact:after" "tool_result_persist"; do
    if jq -e ".hooks[\"$suspect\"] // empty" "$TEMP" >/dev/null 2>&1; then
      jq "del(.hooks[\"$suspect\"])" "$TEMP" > "${TEMP}.new" && mv "${TEMP}.new" "$TEMP"
      echo "   Removed hooks.\"$suspect\""
    fi
  done
  
  cp "$TEMP" "$CONFIG"
  rm -f "$TEMP"
  
  echo ""
  echo "✅ Fixed. Run 'openclaw gateway restart' to apply."
  exit 0
else
  echo ""
  echo "Run with --fix to auto-repair:"
  echo "  bash scripts/validate-hooks.sh --fix"
  exit 1
fi
