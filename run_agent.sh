#!/bin/bash
# Wrapper to run the ACP server with dependencies from this project directory,
# while preserving the caller's current working directory.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run --project "$SCRIPT_DIR" python -m acp_server
