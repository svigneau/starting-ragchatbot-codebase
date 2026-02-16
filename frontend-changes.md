# Code Quality Tools - Changes

## Summary
Added black as an automatic code formatter and created a development script for running quality checks.

## Changes Made

### `pyproject.toml`
- Added `black>=25.1.0` to the `dev` dependency group
- Added `[tool.black]` configuration section with `line-length = 88` and `target-version = ["py313"]`

### `quality.sh` (new file)
- Created a development script for running code quality checks
- `./quality.sh` — checks formatting without making changes (useful for CI)
- `./quality.sh format` — auto-formats code with black

### Formatted Python files (12 files)
All Python files in `backend/` and `main.py` were formatted with black for consistency:
- `backend/ai_generator.py`
- `backend/app.py`
- `backend/config.py`
- `backend/document_processor.py`
- `backend/models.py`
- `backend/rag_system.py`
- `backend/search_tools.py`
- `backend/session_manager.py`
- `backend/vector_store.py`
- `backend/tests/test_ai_generator.py`
- `backend/tests/test_course_search_tool.py`
- `backend/tests/test_rag_system.py`

Formatting changes were minimal — mostly trailing whitespace cleanup, consistent blank lines between classes/functions, and alignment comment spacing to match black's style.
