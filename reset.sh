#!/bin/bash
# Reset Orion — wipes all data and rebuilds from scratch
set -e

echo "⚠️  This will delete all Galaxy data and Docker volumes."
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "→ Stopping containers..."
docker compose down -v

echo "→ Rebuilding images (no cache)..."
docker compose build --no-cache

echo "→ Removing local data..."
rm -rf ./data

echo "→ Starting Orion..."
orion start
