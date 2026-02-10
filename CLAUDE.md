# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace Structure

This is a workspace with two sub-projects:

- **`starting-ragchatbot-codebase/`** — The main project: a RAG chatbot for querying course materials
- **`sc-claude-code-files/`** — Course materials, reading notes, Jupyter notebooks, and ecommerce data for a Claude Code course

## RAG Chatbot (`starting-ragchatbot-codebase/`)

### Commands

```bash
# Install dependencies
uv sync

# Run the server (from repo root)
./run.sh
# Or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app serves at http://localhost:8000 (web UI) and http://localhost:8000/docs (API docs).

### Environment Setup

Requires Python 3.13+ and `uv`. Always use `uv` for running commands and managing all dependencies — never use `pip` directly. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.

### Architecture

FastAPI backend with a vanilla HTML/JS/CSS frontend, no build step.

**Query flow:** User question → `app.py` POST `/api/query` → `RAGSystem.query()` → Claude API with tool use → `CourseSearchTool` executes vector search → Claude generates final answer from search results.

Key backend modules (all in `backend/`):

- **`app.py`** — FastAPI app, mounts frontend as static files from `../frontend`, defines `/api/query` and `/api/courses` endpoints
- **`rag_system.py`** — Orchestrator that wires together all components; the `query()` method drives the full RAG pipeline
- **`ai_generator.py`** — Anthropic Claude API client using tool use; handles the tool execution loop (initial response → tool call → final response)
- **`vector_store.py`** — ChromaDB wrapper with two collections: `course_catalog` (course metadata for name resolution) and `course_content` (chunked text for semantic search). Uses `all-MiniLM-L6-v2` embeddings via sentence-transformers
- **`document_processor.py`** — Parses course text files with expected format (Course Title/Link/Instructor header, then `Lesson N:` markers), chunks text with sentence-aware splitting and configurable overlap
- **`search_tools.py`** — Tool abstraction layer for Claude's tool use: `Tool` ABC, `CourseSearchTool` (wraps VectorStore.search), `ToolManager` (registry + execution). Source tracking for UI display
- **`session_manager.py`** — In-memory conversation history per session, capped at `MAX_HISTORY` exchanges
- **`config.py`** — Dataclass holding all settings (chunk size, overlap, model names, paths), loaded from env vars
- **`models.py`** — Pydantic models: `Course`, `Lesson`, `CourseChunk`

**Frontend** (`frontend/`): Single-page chat UI. `script.js` manages sessions, sends queries to `/api/query`, renders markdown responses with `marked.js`, displays sources in collapsible sections.

### Course Document Format

Documents in `docs/` follow a specific format the parser expects:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<content>

Lesson 1: <title>
...
```

### Key Configuration (in `config.py`)

- Model: `claude-sonnet-4-20250514`
- Embedding: `all-MiniLM-L6-v2`
- Chunk size: 800 chars, overlap: 100 chars
- Max search results: 5, max conversation history: 2 exchanges
- ChromaDB path: `./chroma_db` (relative to backend/)