#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m compileall frontend services

echo "Start services with Docker Compose: docker compose up --build"
echo "Open: http://localhost:8080"
