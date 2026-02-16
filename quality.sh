#!/bin/bash

# Code quality check script
# Usage:
#   ./quality.sh         - Check formatting (no changes)
#   ./quality.sh format  - Auto-format code with black

set -e

if [ "$1" = "format" ]; then
    echo "Formatting code with black..."
    uv run black backend/ main.py
else
    echo "Checking code formatting with black..."
    uv run black --check backend/ main.py
fi

echo "All quality checks passed!"
