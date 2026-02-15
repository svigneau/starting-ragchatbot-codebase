"""Tests for AIGenerator tool-calling behavior in ai_generator.py"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from ai_generator import AIGenerator


def make_text_block(text):
    """Create a mock text content block"""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(tool_name, tool_input, tool_id="tool_123"):
    """Create a mock tool_use content block"""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    return block


class TestAIGeneratorToolCalling:
    """Test that AIGenerator correctly invokes tools and handles responses"""

    def setup_method(self):
        self.mock_client = MagicMock()
        with patch("ai_generator.anthropic.Anthropic", return_value=self.mock_client):
            self.generator = AIGenerator(api_key="test-key", model="test-model")

    def test_direct_response_no_tools(self):
        """When Claude responds without tool use, return text directly"""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [make_text_block("Hello!")]
        self.mock_client.messages.create.return_value = mock_response

        result = self.generator.generate_response(query="Hi")

        assert result == "Hello!"
        self.mock_client.messages.create.assert_called_once()

    def test_tools_passed_to_api(self):
        """Tools should be included in the API call when provided"""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [make_text_block("answer")]
        self.mock_client.messages.create.return_value = mock_response

        tools = [{"name": "search_course_content", "description": "search", "input_schema": {}}]
        self.generator.generate_response(query="question", tools=tools)

        call_kwargs = self.mock_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == {"type": "auto"}

    def test_tool_execution_flow(self):
        """When Claude requests tool_use, execute the tool and make a follow-up call"""
        # First API call: Claude decides to use a tool
        tool_block = make_tool_use_block(
            "search_course_content",
            {"query": "Python basics"},
        )
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block]

        # Second API call: Claude generates final answer from tool results
        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("Python is a programming language.")]

        self.mock_client.messages.create.side_effect = [first_response, final_response]

        # Mock tool manager
        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.return_value = "Found: Python basics content"

        tools = [{"name": "search_course_content", "description": "search", "input_schema": {}}]

        result = self.generator.generate_response(
            query="What is Python?",
            tools=tools,
            tool_manager=mock_tool_manager,
        )

        # Verify tool was called with correct arguments
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="Python basics"
        )

        # Verify two API calls were made
        assert self.mock_client.messages.create.call_count == 2

        # Verify final answer
        assert result == "Python is a programming language."

    def test_tool_result_sent_back_to_api(self):
        """The tool result should be sent back as a user message with tool_result type"""
        tool_block = make_tool_use_block(
            "search_course_content",
            {"query": "MCP"},
            tool_id="call_abc",
        )
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("MCP answer")]

        self.mock_client.messages.create.side_effect = [first_response, final_response]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.return_value = "MCP search results"

        self.generator.generate_response(
            query="What is MCP?",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Inspect the second API call's messages
        second_call = self.mock_client.messages.create.call_args_list[1]
        messages = second_call[1]["messages"]

        # Should have: user query, assistant tool_use, user tool_result
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

        # The tool_result message
        tool_result_content = messages[2]["content"]
        assert tool_result_content[0]["type"] == "tool_result"
        assert tool_result_content[0]["tool_use_id"] == "call_abc"
        assert tool_result_content[0]["content"] == "MCP search results"

    def test_no_tool_execution_without_tool_manager(self):
        """If tool_manager is None, tool_use responses should be returned as text"""
        tool_block = make_tool_use_block("search_course_content", {"query": "test"})
        text_block = make_text_block("I need to search")
        response = MagicMock()
        response.stop_reason = "tool_use"
        response.content = [text_block, tool_block]

        self.mock_client.messages.create.return_value = response

        # No tool_manager passed — should fall through to return content[0].text
        result = self.generator.generate_response(
            query="test",
            tools=[{"name": "search_course_content"}],
            tool_manager=None,
        )

        assert result == "I need to search"
        assert self.mock_client.messages.create.call_count == 1

    def test_conversation_history_included_in_system(self):
        """Conversation history should be appended to the system prompt"""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [make_text_block("answer")]
        self.mock_client.messages.create.return_value = mock_response

        self.generator.generate_response(
            query="follow up", conversation_history="User: hi\nAssistant: hello"
        )

        call_kwargs = self.mock_client.messages.create.call_args[1]
        assert "Previous conversation" in call_kwargs["system"]
        assert "User: hi" in call_kwargs["system"]

    def test_tool_error_result_propagated(self):
        """If the tool returns an error string, it should still be sent to Claude"""
        tool_block = make_tool_use_block(
            "search_course_content", {"query": "xyz"}
        )
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("Sorry, no results found.")]

        self.mock_client.messages.create.side_effect = [first_response, final_response]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.return_value = "Search error: n_results must be > 0"

        result = self.generator.generate_response(
            query="xyz",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Error string should have been passed to Claude as tool_result
        mock_tool_manager.execute_tool.assert_called_once()
        assert self.mock_client.messages.create.call_count == 2
