"""Tests for CourseSearchTool.execute() in search_tools.py"""

import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Test the execute method of CourseSearchTool"""

    def setup_method(self):
        self.mock_store = MagicMock()
        self.tool = CourseSearchTool(self.mock_store)

    def test_execute_returns_formatted_results(self):
        """execute() should return formatted string when store returns results"""
        self.mock_store.search.return_value = SearchResults(
            documents=["Chunk about Python basics"],
            metadata=[{"course_title": "Intro to Python", "lesson_number": 1}],
            distances=[0.2],
        )
        self.mock_store.get_lesson_link.return_value = "https://example.com/lesson1"
        self.mock_store.get_course_link.return_value = "https://example.com/course"

        result = self.tool.execute(query="Python basics")

        assert "Chunk about Python basics" in result
        assert "Intro to Python" in result
        self.mock_store.search.assert_called_once_with(
            query="Python basics", course_name=None, lesson_number=None
        )

    def test_execute_with_course_filter(self):
        """execute() should pass course_name filter to store.search"""
        self.mock_store.search.return_value = SearchResults(
            documents=["MCP content"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 2}],
            distances=[0.1],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        result = self.tool.execute(query="tools", course_name="MCP")

        self.mock_store.search.assert_called_once_with(
            query="tools", course_name="MCP", lesson_number=None
        )
        assert "MCP Course" in result

    def test_execute_with_lesson_filter(self):
        """execute() should pass lesson_number filter to store.search"""
        self.mock_store.search.return_value = SearchResults(
            documents=["Lesson 3 content"],
            metadata=[{"course_title": "Course A", "lesson_number": 3}],
            distances=[0.15],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="topic", lesson_number=3)

        self.mock_store.search.assert_called_once_with(
            query="topic", course_name=None, lesson_number=3
        )

    def test_execute_empty_results(self):
        """execute() should return 'No relevant content found' for empty results"""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = self.tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_empty_results_with_filters(self):
        """execute() should mention filters in empty result message"""
        self.mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = self.tool.execute(query="topic", course_name="MCP", lesson_number=2)

        assert "No relevant content found" in result
        assert "MCP" in result
        assert "lesson 2" in result

    def test_execute_search_error(self):
        """execute() should return error message when store returns an error"""
        self.mock_store.search.return_value = SearchResults.empty(
            "Search error: something broke"
        )

        result = self.tool.execute(query="anything")

        assert "Search error" in result

    def test_execute_course_not_found_error(self):
        """execute() should return error when course name doesn't match"""
        self.mock_store.search.return_value = SearchResults.empty(
            "No course found matching 'Nonexistent'"
        )

        result = self.tool.execute(query="topic", course_name="Nonexistent")

        assert "No course found" in result

    def test_execute_tracks_sources(self):
        """execute() should populate last_sources for UI source display"""
        self.mock_store.search.return_value = SearchResults(
            documents=["doc1", "doc2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course A", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
        )
        self.mock_store.get_lesson_link.side_effect = [
            "https://example.com/l1",
            "https://example.com/l2",
        ]
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="topic")

        assert len(self.tool.last_sources) == 2
        assert self.tool.last_sources[0]["name"] == "Course A - Lesson 1"

    def test_execute_deduplicates_sources(self):
        """execute() should deduplicate sources by name"""
        self.mock_store.search.return_value = SearchResults(
            documents=["doc1", "doc2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course A", "lesson_number": 1},
            ],
            distances=[0.1, 0.2],
        )
        self.mock_store.get_lesson_link.return_value = None
        self.mock_store.get_course_link.return_value = None

        self.tool.execute(query="topic")

        assert len(self.tool.last_sources) == 1

    def test_tool_definition_has_required_fields(self):
        """Tool definition should have name, description, and input_schema"""
        defn = self.tool.get_tool_definition()

        assert defn["name"] == "search_course_content"
        assert "description" in defn
        assert "input_schema" in defn
        assert "query" in defn["input_schema"]["properties"]
        assert defn["input_schema"]["required"] == ["query"]


class TestToolManager:
    """Test ToolManager registration and execution"""

    def test_register_and_execute(self):
        manager = ToolManager()
        mock_store = MagicMock()
        tool = CourseSearchTool(mock_store)
        manager.register_tool(tool)

        assert "search_course_content" in manager.tools

    def test_execute_unknown_tool(self):
        manager = ToolManager()
        result = manager.execute_tool("nonexistent_tool")
        assert "not found" in result

    def test_get_last_sources_and_reset(self):
        manager = ToolManager()
        mock_store = MagicMock()
        tool = CourseSearchTool(mock_store)
        tool.last_sources = [{"name": "Test", "url": None}]
        manager.register_tool(tool)

        sources = manager.get_last_sources()
        assert len(sources) == 1

        manager.reset_sources()
        assert manager.get_last_sources() == []
