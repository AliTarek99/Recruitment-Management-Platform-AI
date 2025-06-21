#!/usr/bin/env bash
set -euo pipefail

log() {
  local emoji="$1"; shift
  echo -e "${emoji} $*"
}

# 1. Parsing Service
log "🔍" "Removing Parsing service..."
(
  cd "./Parsing" \
    && docker compose down \
    && log "✅ Parsing service containers removed."
) || log "❌ Failed to remove Parsing service"

# 2. Embedding Service
log "🧠" "Removing Embedding service..."
(
  cd "./Embedding" \
    && docker compose down \
    && log "✅ Embedding service containers removed."
) || log "❌ Failed to remove Embedding service"

log "🎉 All AI services have been fully removed!"
