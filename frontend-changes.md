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

---

# Testing Infrastructure - Changes

No frontend files were modified. All changes were to the backend testing infrastructure.

## Changes Made

### New Files

**`backend/tests/conftest.py`** — Shared pytest fixtures:
- `mock_rag_system` — Creates a RAGSystem with VectorStore, AIGenerator, and DocumentProcessor all mocked out
- `mock_vector_store` — Standalone mock VectorStore for tool-level tests
- `sample_query_payload` / `sample_query_with_session` — Reusable request payloads for API tests

**`backend/tests/test_api.py`** — 16 API endpoint tests across 3 test classes:
- `TestQueryEndpoint` (8 tests) — POST `/api/query`: success response, session creation/reuse, validation errors, 500 on RAG failure, response shape and source structure
- `TestCoursesEndpoint` (4 tests) — GET `/api/courses`: success response, response shape, 500 on error, empty catalog
- `TestMiscRoutes` (4 tests) — 404 on unknown routes, 405 on wrong HTTP methods, 422 on malformed JSON

The test app is built inline via `create_test_app()` to avoid importing `backend/app.py` which mounts static files from `../frontend` (unavailable in the test environment).

### Modified Files

**`pyproject.toml`** — Added:
- `httpx` dev dependency (required by FastAPI's `TestClient`)
- `[tool.pytest.ini_options]` section with `testpaths`, `pythonpath`, and `addopts` for cleaner test execution (`uv run pytest` from repo root now works without extra flags)
