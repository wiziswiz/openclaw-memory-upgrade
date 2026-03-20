#!/usr/bin/env bash
# fix-openclaw-config.sh — Repair corrupted openclaw.json hook entries
# Removes hook entries pointing to paths that don't exist on disk.
# Creates .bak backup before any changes.
#
# Usage: bash scripts/fix-openclaw-config.sh [path-to-openclaw.json]

set -euo pipefail

command -v jq >/dev/null 2>&1 || { echo "❌ jq required. Install: brew install jq (macOS) or apt install jq (Linux)"; exit 1; }

CONFIG="${1:-${HOME}/.openclaw/openclaw.json}"

if [ ! -f "$CONFIG" ]; then
  echo "❌ Config not found: $CONFIG"
  exit 1
fi

echo "🔍 Scanning: $CONFIG"

# Known invalid hook patterns — top-level keys that aren't valid OpenClaw hook config
INVALID_KEYS=()
INVALID_PATHS=()
FIXES_NEEDED=0


# Check for top-level keys that look like hook entries (common mistake)
# Valid top-level keys in openclaw.json
VALID_TOP_KEYS="meta wizard browser auth acp agents tools messages commands hooks channels gateway skills plugins _template_version _notes"

while IFS= read -r key; do
  is_valid=false
  for valid in $VALID_TOP_KEYS; do
    [ "$key" = "$valid" ] && is_valid=true && break
  done
  if ! $is_valid; then
    echo "⚠️  Invalid top-level key: \"$key\" (not a recognized OpenClaw config field)"
    INVALID_KEYS+=("$key")
    FIXES_NEEDED=$((FIXES_NEEDED + 1))
  fi
done < <(jq -r 'keys[]' "$CONFIG" 2>/dev/null)

# Check hook entries for unresolvable paths
if jq -e '.hooks.internal.entries // empty' "$CONFIG" >/dev/null 2>&1; then
  while IFS=$'\t' read -r entry_name entry_path; do
    if [ -n "$entry_path" ] && [ "$entry_path" != "null" ]; then
      # Resolve relative to config dir
      config_dir="$(dirname "$CONFIG")"
      resolved="$config_dir/$entry_path"
      if [ ! -e "$resolved" ] && [ ! -e "$entry_path" ]; then
        # Try node resolution
        if ! node -e "require.resolve('$entry_path')" 2>/dev/null; then
          echo "⚠️  Hook entry \"$entry_name\" points to unresolvable path: $entry_path"
          INVALID_PATHS+=("$entry_name")
          FIXES_NEEDED=$((FIXES_NEEDED + 1))
        fi
      fi
    fi
  done < <(jq -r '.hooks.internal.entries // {} | to_entries[] | select(.value.path? != null) | [.key, .value.path] | @tsv' "$CONFIG" 2>/dev/null)
fi

# Check for hook entries at wrong level (outside hooks.internal.entries)
for suspect in "session:compact:after" "tool_result_persist" "compaction-logger" "tool-result-compressor"; do
  if jq -e ".[\"$suspect\"] // empty" "$CONFIG" >/dev/null 2>&1; then
    echo "⚠️  \"$suspect\" found at top level — this belongs under hooks.internal.entries (if valid) or should be removed"
    INVALID_KEYS+=("$suspect")
    FIXES_NEEDED=$((FIXES_NEEDED + 1))
  fi
  if jq -e ".hooks[\"$suspect\"] // empty" "$CONFIG" >/dev/null 2>&1; then
    echo "⚠️  \"$suspect\" found under hooks — should be under hooks.internal.entries (if valid) or removed"
    FIXES_NEEDED=$((FIXES_NEEDED + 1))
  fi
done

if [ "$FIXES_NEEDED" -eq 0 ]; then
  echo "✅ Config looks clean — no invalid hook entries found"
  exit 0
fi

echo ""
echo "Found $FIXES_NEEDED issue(s). Fixing..."

# Backup
cp "$CONFIG" "${CONFIG}.bak"
echo "📦 Backup: ${CONFIG}.bak"

TEMP=$(mktemp)
cp "$CONFIG" "$TEMP"

# Remove invalid top-level keys (deduplicated)
if [ ${#INVALID_KEYS[@]} -gt 0 ]; then
  # Deduplicate keys
  SEEN=""
  for key in "${INVALID_KEYS[@]}"; do
    if [[ "$SEEN" != *"|$key|"* ]]; then
      SEEN="${SEEN}|$key|"
      jq "del(.[\"$key\"])" "$TEMP" > "${TEMP}.new" && mv "${TEMP}.new" "$TEMP"
      echo "  🗑  Removed top-level key: \"$key\""
    fi
  done
fi

# Remove invalid hook entry paths
if [ ${#INVALID_PATHS[@]} -gt 0 ]; then
  for entry in "${INVALID_PATHS[@]}"; do
    jq "del(.hooks.internal.entries[\"$entry\"])" "$TEMP" > "${TEMP}.new" && mv "${TEMP}.new" "$TEMP"
    echo "  🗑  Removed hook entry: \"$entry\""
  done
fi

# Remove suspect keys from hooks level
for suspect in "session:compact:after" "tool_result_persist" "compaction-logger" "tool-result-compressor"; do
  if jq -e ".hooks[\"$suspect\"] // empty" "$TEMP" >/dev/null 2>&1; then
    jq "del(.hooks[\"$suspect\"])" "$TEMP" > "${TEMP}.new" && mv "${TEMP}.new" "$TEMP"
    echo "  🗑  Removed hooks.\"$suspect\""
  fi
done

cp "$TEMP" "$CONFIG"
rm -f "$TEMP"

echo ""
echo "✅ Config repaired. Original backed up to ${CONFIG}.bak"
echo "   Run 'openclaw gateway restart' to apply."
