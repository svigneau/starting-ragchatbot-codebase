"""Shared test fixtures for the RAG system test suite"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_rag_system():
    """Create a RAGSystem with all external dependencies mocked"""
    from config import Config

    config = Config()
    config.ANTHROPIC_API_KEY = "test-key"
    config.MAX_RESULTS = 5
    config.CHROMA_PATH = "/tmp/claude/test_chroma_db"

    with patch("rag_system.VectorStore") as MockVS, \
         patch("rag_system.AIGenerator") as MockAI, \
         patch("rag_system.DocumentProcessor"):
        from rag_system import RAGSystem

        rag = RAGSystem(config)
        yield rag


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore for tool tests"""
    store = MagicMock()
    store.search.return_value = MagicMock(
        documents=[], metadata=[], distances=[], error=None
    )
    store.get_course_count.return_value = 0
    store.get_existing_course_titles.return_value = []
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    return store


@pytest.fixture
def sample_query_payload():
    """Standard query payload for API tests"""
    return {"query": "What is Python?"}


@pytest.fixture
def sample_query_with_session():
    """Query payload with a session ID"""
    return {"query": "Tell me more", "session_id": "session_1"}
