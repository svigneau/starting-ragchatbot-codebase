import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
1. **search_course_content** — Search within course lesson content for specific topics or details.
2. **get_course_outline** — Retrieve a course's title, course link, and full lesson list (number and title for each lesson). Use this for questions about what a course covers, its structure, table of contents, or lesson listing.

Tool Usage:
- **Up to 2 tool calls per query** — you may call a tool, review its results, then call another tool if needed
- Use multiple tool calls for multi-step lookups (e.g., get a course outline first, then search for specific content based on what you found)
- For course outline, structure, or "what lessons" questions: use **get_course_outline**
- For specific topic or content questions: use **search_course_content**
- When returning an outline, include the course title, course link, and every lesson with its number and title
- Synthesize tool results into accurate, fact-based responses
- **Only reference courses and lessons that appear in tool results** — never invent or suggest courses that were not returned by a tool
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Use the appropriate tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the tool results"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool calls.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]

        for _ in range(self.MAX_TOOL_ROUNDS):
            # Build API params with tools included
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content
            }
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            response = self.client.messages.create(**api_params)

            # If no tool use or no tool_manager, return text directly
            if response.stop_reason != "tool_use" or not tool_manager:
                return response.content[0].text

            # Append assistant's tool_use response
            messages.append({"role": "assistant", "content": response.content})

            # Execute tools and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool execution error: {e}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                        break
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

        # Max rounds exhausted — final call without tools to force text response
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text