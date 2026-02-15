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

        # Inspect the second API call
        second_call = self.mock_client.messages.create.call_args_list[1]
        second_kwargs = second_call[1]
        messages = second_kwargs["messages"]

        # Second call should still include tools (loop-based approach)
        assert "tools" in second_kwargs

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

    def test_two_sequential_tool_calls(self):
        """Two tool calls in sequence: 3 API calls, 2 tool executions, correct final text"""
        tool_block_1 = make_tool_use_block("get_course_outline", {"course_name": "AI"}, "id_1")
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block_1]

        tool_block_2 = make_tool_use_block("search_course_content", {"query": "transformers"}, "id_2")
        second_response = MagicMock()
        second_response.stop_reason = "tool_use"
        second_response.content = [tool_block_2]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("Transformers are covered in lesson 3.")]

        self.mock_client.messages.create.side_effect = [
            first_response, second_response, final_response
        ]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.side_effect = [
            "Outline: Lesson 1: Intro, Lesson 3: Transformers",
            "Found: Transformers content in lesson 3",
        ]

        tools = [{"name": "get_course_outline"}, {"name": "search_course_content"}]
        result = self.generator.generate_response(
            query="Find content about transformers in AI course",
            tools=tools,
            tool_manager=mock_tool_manager,
        )

        assert self.mock_client.messages.create.call_count == 3
        assert mock_tool_manager.execute_tool.call_count == 2
        assert result == "Transformers are covered in lesson 3."

    def test_second_round_includes_tools(self):
        """The second API call in the loop should still include tools"""
        tool_block = make_tool_use_block("get_course_outline", {"course_name": "X"}, "id_1")
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("done")]

        self.mock_client.messages.create.side_effect = [first_response, final_response]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.return_value = "outline data"

        tools = [{"name": "get_course_outline"}]
        self.generator.generate_response(
            query="q", tools=tools, tool_manager=mock_tool_manager
        )

        second_call_kwargs = self.mock_client.messages.create.call_args_list[1][1]
        assert "tools" in second_call_kwargs
        assert second_call_kwargs["tools"] == tools

    def test_max_rounds_forces_response_without_tools(self):
        """After MAX_TOOL_ROUNDS tool calls, final call should have no tools"""
        tool_block_1 = make_tool_use_block("get_course_outline", {"course_name": "A"}, "id_1")
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block_1]

        tool_block_2 = make_tool_use_block("search_course_content", {"query": "B"}, "id_2")
        second_response = MagicMock()
        second_response.stop_reason = "tool_use"
        second_response.content = [tool_block_2]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("final answer")]

        self.mock_client.messages.create.side_effect = [
            first_response, second_response, final_response
        ]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.side_effect = ["result1", "result2"]

        tools = [{"name": "get_course_outline"}, {"name": "search_course_content"}]
        self.generator.generate_response(
            query="q", tools=tools, tool_manager=mock_tool_manager
        )

        # Third (final) call should NOT have tools
        third_call_kwargs = self.mock_client.messages.create.call_args_list[2][1]
        assert "tools" not in third_call_kwargs

    def test_second_tool_uses_first_results_context(self):
        """Final call messages should contain both tool rounds' context"""
        tool_block_1 = make_tool_use_block("get_course_outline", {"course_name": "C"}, "id_1")
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block_1]

        tool_block_2 = make_tool_use_block("search_course_content", {"query": "D"}, "id_2")
        second_response = MagicMock()
        second_response.stop_reason = "tool_use"
        second_response.content = [tool_block_2]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("answer")]

        self.mock_client.messages.create.side_effect = [
            first_response, second_response, final_response
        ]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.side_effect = ["outline_data", "search_data"]

        tools = [{"name": "get_course_outline"}, {"name": "search_course_content"}]
        self.generator.generate_response(
            query="q", tools=tools, tool_manager=mock_tool_manager
        )

        # Final (third) API call messages should contain both rounds of context
        final_call_msgs = self.mock_client.messages.create.call_args_list[2][1]["messages"]
        # user query, assistant tool_use #1, user tool_result #1,
        # assistant tool_use #2, user tool_result #2
        assert len(final_call_msgs) == 5
        assert final_call_msgs[1]["role"] == "assistant"
        assert final_call_msgs[1]["content"] == first_response.content
        assert final_call_msgs[2]["content"][0]["tool_use_id"] == "id_1"
        assert final_call_msgs[2]["content"][0]["content"] == "outline_data"
        assert final_call_msgs[3]["content"] == second_response.content
        assert final_call_msgs[4]["content"][0]["tool_use_id"] == "id_2"
        assert final_call_msgs[4]["content"][0]["content"] == "search_data"

    def test_single_tool_round_still_works(self):
        """A single tool_use then end_turn: 2 API calls, 1 tool execution"""
        tool_block = make_tool_use_block("search_course_content", {"query": "ML"}, "id_1")
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("ML answer")]

        self.mock_client.messages.create.side_effect = [first_response, final_response]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.return_value = "ML content"

        result = self.generator.generate_response(
            query="What is ML?",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        assert self.mock_client.messages.create.call_count == 2
        mock_tool_manager.execute_tool.assert_called_once()
        assert result == "ML answer"

    def test_tool_exception_handled_gracefully(self):
        """execute_tool raising an exception sends error as tool_result"""
        tool_block = make_tool_use_block("search_course_content", {"query": "fail"}, "id_err")
        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_block]

        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [make_text_block("Sorry, something went wrong.")]

        self.mock_client.messages.create.side_effect = [first_response, final_response]

        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool.side_effect = RuntimeError("connection failed")

        result = self.generator.generate_response(
            query="fail query",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Error should be sent as tool_result, then loop continues to next API call
        second_call_msgs = self.mock_client.messages.create.call_args_list[1][1]["messages"]
        tool_result = second_call_msgs[2]["content"][0]
        assert "Tool execution error" in tool_result["content"]
        assert "connection failed" in tool_result["content"]
        assert result == "Sorry, something went wrong."
