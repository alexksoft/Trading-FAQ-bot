#!/bin/bash
# start.sh — Start the bot on Oracle Cloud (or any Linux server)
# Make executable: chmod +x start.sh

set -e

# Activate virtual environment
source .venv/bin/activate

# Start uvicorn
# --workers 1 is fine for Oracle Free Tier (1 OCPU, 1 GB RAM)
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info
