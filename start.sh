#!/usr/bin/env bash
set -euo pipefail

log() {
  local emoji="$1"; shift
  echo -e "${emoji} $*"
}

# 1. Parsing Service
log "🔍" "Starting Parsing service..."
(
  cd "./Parsing" \
    && docker compose start \
    && log "✅ Parsing service containers started."
) || log "❌ Failed to start Parsing service"

# 2. Embedding Service
log "🧠" "Starting Embedding service..."
(
  cd "./Embedding" \
    && docker compose start \
    && log "✅ Embedding service containers started."
) || log "❌ Failed to start Embedding service"

log "🎉 All AI services have been fully started!"
