#!/bin/bash

###############################################################################
# Starts the prediction app at http://127.0.0.1:8000
# Builds the frontend the first time, or after its source changes.
###############################################################################

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR/frontend"

if [ ! -d node_modules ]; then
    npm install
fi

if [ ! -f dist/index.html ] || [ -n "$(find src index.html -newer dist/index.html)" ]; then
    npm run build
fi

cd "$PROJECT_DIR"
exec pred/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
