#!/usr/bin/env bash
set -euo pipefail

log() {
  local emoji="$1"; shift
  echo -e "${emoji} $*"
}

# 🚧 1. Parsing Service
log "🔍" "Starting Parsing service..."
(
  cd "./Parsing" \
    && docker compose up -d --build \
    && log "✅ Parsing service is up."
) || { log "❌ Parsing service failed."; exit 1; }

# 🧠 2. Embedding Service
log "🤖" "Starting Embedding service..."
(
  cd "./Embedding" \
    && docker compose up -d --build \
    && log "✅ Embedding service is up."
) || { log "❌ Embedding service failed."; exit 1; }

log "🎉" "All AI services have been started successfully!"
