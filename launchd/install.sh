#!/bin/bash
# Install launchd plist for anki-pipeline

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_SRC="$SCRIPT_DIR/com.user.anki-pipeline.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/com.user.anki-pipeline.plist"

if [ ! -f "$PLIST_SRC" ]; then
    echo "Error: Template not found at $PLIST_SRC"
    exit 1
fi

# Substitute {{HOME}}
sed "s|{{HOME}}|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"

# Unload if already loaded
launchctl bootout gui/$(id -u) "$PLIST_DST" 2>/dev/null || true

# Load
launchctl bootstrap gui/$(id -u) "$PLIST_DST"

echo "Installed and loaded: $PLIST_DST"
