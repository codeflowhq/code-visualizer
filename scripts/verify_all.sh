#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="/Users/bbnb/sg/code_visualizer_web/web_app"

cd "$ROOT_DIR"
uv run pytest tests -q
uv run mypy src/code_visualizer/builders src/code_visualizer/views src/code_visualizer/tracing src/code_visualizer/graph_builder.py src/code_visualizer/graph_view_builder.py src/code_visualizer/browser_api.py
uv run ruff check src/code_visualizer/builders src/code_visualizer/views src/code_visualizer/tracing src/code_visualizer/graph_builder.py src/code_visualizer/graph_view_builder.py src/code_visualizer/browser_api.py src/code_visualizer/view_utils.py tests
python3 "$WEB_DIR/scripts/sync_python_runtime.py"
cd "$WEB_DIR"
npm run build
