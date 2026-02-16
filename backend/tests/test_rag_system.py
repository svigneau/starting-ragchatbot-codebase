"""Tests for RAGSystem.query() — the full pipeline from question to answer"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from vector_store import SearchResults


class TestRAGSystemQuery:
    """Test the RAG query pipeline end-to-end (with mocked external services)"""

    def _build_rag_system(self, max_results=5):
        """Build a RAGSystem with mocked dependencies"""
        from config import Config

        config = Config()
        config.ANTHROPIC_API_KEY = "test-key"
        config.MAX_RESULTS = max_results
        config.CHROMA_PATH = "/tmp/claude/test_chroma_db"

        with (
            patch("rag_system.VectorStore") as MockVS,
            patch("rag_system.AIGenerator") as MockAI,
            patch("rag_system.DocumentProcessor"),
        ):
            from rag_system import RAGSystem

            rag = RAGSystem(config)
            return rag, MockVS, MockAI

    def test_query_calls_ai_with_tools(self):
        """RAGSystem.query() should pass tool definitions to the AI generator"""
        rag, _, _ = self._build_rag_system()

        rag.ai_generator.generate_response.return_value = "Test answer"

        answer, sources = rag.query("What is Python?", session_id=None)

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] is not None
        assert len(call_kwargs["tools"]) > 0
        assert call_kwargs["tool_manager"] is not None

    def test_query_returns_response_and_sources(self):
        """query() should return (answer_string, sources_list)"""
        rag, _, _ = self._build_rag_system()

        rag.ai_generator.generate_response.return_value = "The answer is 42"
        # Simulate the search tool having found sources
        rag.search_tool.last_sources = [
            {"name": "Course A - Lesson 1", "url": "https://example.com"}
        ]

        answer, sources = rag.query("question")

        assert answer == "The answer is 42"
        assert len(sources) == 1
        assert sources[0]["name"] == "Course A - Lesson 1"

    def test_query_resets_sources_after_retrieval(self):
        """Sources should be reset after each query to avoid leaking into next query"""
        rag, _, _ = self._build_rag_system()

        rag.ai_generator.generate_response.return_value = "answer"
        rag.search_tool.last_sources = [{"name": "Source", "url": None}]

        rag.query("question")

        # After query, sources should be reset
        assert rag.search_tool.last_sources == []

    def test_query_with_session_adds_history(self):
        """query() should record the exchange in session history"""
        rag, _, _ = self._build_rag_system()

        rag.ai_generator.generate_response.return_value = "response"
        session_id = rag.session_manager.create_session()

        rag.query("my question", session_id=session_id)

        history = rag.session_manager.get_conversation_history(session_id)
        assert "my question" in history
        assert "response" in history

    def test_query_without_session_skips_history(self):
        """query() with no session_id should still work (no history)"""
        rag, _, _ = self._build_rag_system()
        rag.ai_generator.generate_response.return_value = "answer"

        answer, sources = rag.query("question", session_id=None)

        assert answer == "answer"

    def test_both_tools_registered(self):
        """Both search and outline tools should be registered"""
        rag, _, _ = self._build_rag_system()

        tool_defs = rag.tool_manager.get_tool_definitions()
        tool_names = [t["name"] for t in tool_defs]

        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


class TestConfigMaxResults:
    """Test that config MAX_RESULTS is correctly propagated"""

    def test_default_config_max_results_is_positive(self):
        """MAX_RESULTS must be > 0 for ChromaDB to return results"""
        from config import Config

        config = Config()
        assert config.MAX_RESULTS > 0, (
            f"MAX_RESULTS is {config.MAX_RESULTS} — ChromaDB requires n_results > 0. "
            "This will cause all searches to fail."
        )

    def test_max_results_passed_to_vector_store(self):
        """VectorStore should receive the configured MAX_RESULTS"""
        with (
            patch("rag_system.VectorStore") as MockVS,
            patch("rag_system.AIGenerator"),
            patch("rag_system.DocumentProcessor"),
        ):
            from config import Config
            from rag_system import RAGSystem

            config = Config()
            config.ANTHROPIC_API_KEY = "test"
            config.CHROMA_PATH = "/tmp/claude/test_chroma"
            rag = RAGSystem(config)

            # Check VectorStore was instantiated with max_results from config
            MockVS.assert_called_once_with(
                config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
            )


class TestVectorStoreSearch:
    """Test VectorStore.search with real ChromaDB (in-memory) to catch n_results=0"""

    def test_search_with_zero_max_results_fails(self):
        """Searching with n_results=0 should produce an error — this is the bug"""
        import chromadb

        client = chromadb.Client()
        collection = client.create_collection("test_content")
        collection.add(
            documents=["Python is great for data science"],
            metadatas=[{"course_title": "Python 101", "lesson_number": 1}],
            ids=["chunk_1"],
        )

        # Simulate what happens with MAX_RESULTS=0
        with pytest.raises(Exception) as exc_info:
            collection.query(query_texts=["Python"], n_results=0)

        # ChromaDB raises an error for n_results <= 0
        assert (
            "Number of requested results" in str(exc_info.value)
            or "n_results" in str(exc_info.value).lower()
            or exc_info.value is not None
        )

    def test_search_with_positive_max_results_succeeds(self):
        """Searching with n_results=5 should return results"""
        import chromadb

        client = chromadb.Client()
        collection = client.create_collection("test_content_ok")
        collection.add(
            documents=["Python is great for data science"],
            metadatas=[{"course_title": "Python 101", "lesson_number": 1}],
            ids=["chunk_1"],
        )

        results = collection.query(query_texts=["Python"], n_results=5)
        assert len(results["documents"][0]) == 1
        assert "Python" in results["documents"][0][0]
