"""Tests for FastAPI API endpoints.

Creates a standalone test app to avoid importing backend/app.py which mounts
static files from ../frontend (not available in the test environment).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import Any, Dict, List, Optional


# --- Standalone test app (mirrors backend/app.py without static file mount) ---

def create_test_app(mock_rag_system):
    """Build a FastAPI app with the same endpoints as app.py but no static files"""
    app = FastAPI()

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Any]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def rag_mock():
    """Fully mocked RAGSystem for API tests"""
    mock = MagicMock()
    mock.session_manager.create_session.return_value = "session_42"
    mock.query.return_value = ("The answer is 42", [{"name": "Source A", "url": "https://example.com"}])
    mock.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Course A", "Course B", "Course C"],
    }
    return mock


@pytest.fixture
def client(rag_mock):
    """TestClient wired to the test app"""
    app = create_test_app(rag_mock)
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    """Tests for POST /api/query"""

    def test_query_returns_200(self, client):
        """A valid query should return 200 with answer, sources, session_id"""
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "The answer is 42"
        assert data["session_id"] == "session_42"
        assert len(data["sources"]) == 1

    def test_query_creates_session_when_missing(self, client, rag_mock):
        """When no session_id is provided, the endpoint should create one"""
        client.post("/api/query", json={"query": "hello"})
        rag_mock.session_manager.create_session.assert_called_once()

    def test_query_uses_provided_session_id(self, client, rag_mock):
        """When session_id is provided, it should be used instead of creating a new one"""
        resp = client.post("/api/query", json={"query": "hi", "session_id": "existing_session"})
        rag_mock.session_manager.create_session.assert_not_called()
        rag_mock.query.assert_called_once_with("hi", "existing_session")
        assert resp.json()["session_id"] == "existing_session"

    def test_query_missing_query_field(self, client):
        """Missing 'query' field should return 422 validation error"""
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_query_empty_string(self, client):
        """An empty query string is valid (the model handles it)"""
        resp = client.post("/api/query", json={"query": ""})
        assert resp.status_code == 200

    def test_query_rag_error_returns_500(self, client, rag_mock):
        """If RAGSystem.query() raises, the endpoint should return 500"""
        rag_mock.query.side_effect = RuntimeError("model exploded")
        resp = client.post("/api/query", json={"query": "boom"})
        assert resp.status_code == 500
        assert "model exploded" in resp.json()["detail"]

    def test_query_response_shape(self, client):
        """Response must contain exactly 'answer', 'sources', 'session_id'"""
        resp = client.post("/api/query", json={"query": "test"})
        keys = set(resp.json().keys())
        assert keys == {"answer", "sources", "session_id"}

    def test_query_sources_structure(self, client):
        """Each source should be a dict with at least 'name' and 'url'"""
        resp = client.post("/api/query", json={"query": "test"})
        sources = resp.json()["sources"]
        for source in sources:
            assert "name" in source
            assert "url" in source


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    """Tests for GET /api/courses"""

    def test_courses_returns_200(self, client):
        """GET /api/courses should return 200 with course stats"""
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3

    def test_courses_response_shape(self, client):
        """Response must contain exactly 'total_courses' and 'course_titles'"""
        resp = client.get("/api/courses")
        keys = set(resp.json().keys())
        assert keys == {"total_courses", "course_titles"}

    def test_courses_error_returns_500(self, client, rag_mock):
        """If get_course_analytics() raises, endpoint should return 500"""
        rag_mock.get_course_analytics.side_effect = RuntimeError("db down")
        resp = client.get("/api/courses")
        assert resp.status_code == 500
        assert "db down" in resp.json()["detail"]

    def test_courses_empty_catalog(self, client, rag_mock):
        """An empty catalog should return 0 courses with empty list"""
        rag_mock.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        resp = client.get("/api/courses")
        data = resp.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []


# ---------------------------------------------------------------------------
# Other routes / edge cases
# ---------------------------------------------------------------------------

class TestMiscRoutes:
    """Miscellaneous route tests"""

    def test_unknown_route_returns_404(self, client):
        """Non-existent routes should 404 (no catch-all static mount in test app)"""
        resp = client.get("/api/nonexistent")
        assert resp.status_code in (404, 405)

    def test_query_wrong_method(self, client):
        """GET on /api/query should return 405 Method Not Allowed"""
        resp = client.get("/api/query")
        assert resp.status_code == 405

    def test_courses_wrong_method(self, client):
        """POST on /api/courses should return 405 Method Not Allowed"""
        resp = client.post("/api/courses")
        assert resp.status_code == 405

    def test_query_invalid_json(self, client):
        """Malformed JSON body should return 422"""
        resp = client.post(
            "/api/query",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422
