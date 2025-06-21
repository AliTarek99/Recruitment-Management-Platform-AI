#!/usr/bin/env bash
set -euo pipefail

log() {
  local emoji="$1"; shift
  echo -e "${emoji} $*"
}

# 1. Parsing Service
log "🔍" "Stopping Parsing service..."
(
  cd "./Parsing" \
    && docker compose stop \
    && log "✅ Parsing service containers stopped."
) || log "❌ Failed to stop Parsing service"

# 2. Embedding Service
log "🧠" "Stopping Embedding service..."
(
  cd "./Embedding" \
    && docker compose stop \
    && log "✅ Embedding service containers stopped."
) || log "❌ Failed to stop Embedding service"

log "🎉" "All AI services have been stopped successfully!"
