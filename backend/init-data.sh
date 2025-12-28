#!/bin/sh

# Source script to initialize data on a Fly.io volume if it's empty.
# The Dockerfile copies initial data to /app/data_initial.
# This script checks if the mounted volume at /app/data is empty (by checking posters.json).
# If empty, it copies the initial data from /app/data_initial to /app/data.

MOUNT_PATH="/app/data"
INITIAL_DATA_PATH="/app/data_initial"
POSTERS_JSON="${MOUNT_PATH}/posters.json"

echo "Checking for initial data on volume at ${MOUNT_PATH}..."

if [ ! -f "$POSTERS_JSON" ]; then
  echo "Volume appears empty. Initializing data from ${INITIAL_DATA_PATH}..."
  # Ensure the destination directory exists
  mkdir -p "${MOUNT_PATH}/posters"
  # Copy the initial data, preserving directory structure
  cp -Rv "${INITIAL_DATA_PATH}/." "${MOUNT_PATH}/"
  echo "Data initialization complete."
else
  echo "Volume contains data. Skipping initialization."
fi

# Execute the main application command
exec sh -lc "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
