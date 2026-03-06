"""Tests for the Holdsworth request_cook tool.

Covers:
- Tool polls for result via _submit_and_poll
- Handler returns summary/message/error fields correctly
- Tool registry includes request_cook
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestRequestCookHandler:
    """Test handle_request_cook routes to _submit_and_poll and formats results."""

    async def test_returns_summary_when_present(self):
        from holdsworth.consciousness.tools.cook import handle_request_cook

        with patch(
            "holdsworth.consciousness.tools.cook._submit_and_poll",
            new_callable=AsyncMock,
            return_value={
                "summary": "Recipe suggestions for Dave:\n  1. Chicken Tikka (score 115)"
            },
        ):
            result = await handle_request_cook(
                request_type="suggest_recipes",
                payload={"diners": ["Dave"]},
            )

        assert "Chicken Tikka" in result
        assert "score 115" in result

    async def test_returns_message_when_no_summary(self):
        from holdsworth.consciousness.tools.cook import handle_request_cook

        with patch(
            "holdsworth.consciousness.tools.cook._submit_and_poll",
            new_callable=AsyncMock,
            return_value={"success": True, "message": "Rating recorded: Dave rated Pasta 4/5."},
        ):
            result = await handle_request_cook(
                request_type="rate_recipe",
                payload={"recipe_name": "Pasta", "member_name": "Dave", "rating": 4},
            )

        assert "Rating recorded" in result
        assert "4/5" in result

    async def test_returns_error_when_present(self):
        from holdsworth.consciousness.tools.cook import handle_request_cook

        with patch(
            "holdsworth.consciousness.tools.cook._submit_and_poll",
            new_callable=AsyncMock,
            return_value={"error": "Recipe not found: Nonexistent"},
        ):
            result = await handle_request_cook(
                request_type="check_dietary",
                payload={"recipe_name": "Nonexistent"},
            )

        assert "Recipe not found" in result

    async def test_returns_string_result_directly(self):
        from holdsworth.consciousness.tools.cook import handle_request_cook

        with patch(
            "holdsworth.consciousness.tools.cook._submit_and_poll",
            new_callable=AsyncMock,
            return_value="Cook didn't respond in time — please try again.",
        ):
            result = await handle_request_cook(request_type="suggest_recipes")

        assert "didn't respond" in result

    async def test_empty_payload_defaults_to_empty_dict(self):
        from holdsworth.consciousness.tools.cook import handle_request_cook

        with patch(
            "holdsworth.consciousness.tools.cook._submit_and_poll",
            new_callable=AsyncMock,
            return_value={"message": "OK"},
        ) as mock_poll:
            await handle_request_cook(request_type="get_dietary_profile")

        # payload should default to {}
        mock_poll.assert_called_once_with("cook", "get_dietary_profile", {})


class TestCookToolRegistry:
    """Test that request_cook is properly registered."""

    def test_request_cook_in_all_tools(self):
        from holdsworth.consciousness.tools.cook import ALL_TOOLS

        names = {t["name"] for t in ALL_TOOLS}
        assert "request_cook" in names

    def test_request_cook_has_handler(self):
        from holdsworth.consciousness.tools.cook import HANDLERS

        assert "request_cook" in HANDLERS
        assert callable(HANDLERS["request_cook"])

    def test_request_cook_in_cooking_intent(self):
        from holdsworth.consciousness.tools import get_tools_for_intent

        tools = get_tools_for_intent("cooking")
        names = {t["name"] for t in tools}
        assert "request_cook" in names

    def test_tool_schema_has_required_fields(self):
        from holdsworth.consciousness.tools.cook import REQUEST_COOK

        assert REQUEST_COOK["name"] == "request_cook"
        assert "description" in REQUEST_COOK
        assert "input_schema" in REQUEST_COOK
        schema = REQUEST_COOK["input_schema"]
        assert "request_type" in schema["properties"]
        assert "payload" in schema["properties"]
        assert schema["required"] == ["request_type"]
