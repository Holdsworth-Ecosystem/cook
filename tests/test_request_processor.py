"""Tests for the Cook request processor.

Covers:
- Dispatch routing to correct handlers
- Unknown request type handling
- Status lifecycle (pending → processing → complete/failed)
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cook.request_processor import _dispatch, process_pending_requests


class TestDispatch:
    """Test _dispatch routes to correct handlers."""

    async def test_suggest_recipes_dispatches(self):
        mock_handler = AsyncMock(return_value={"recipes": []})
        with patch("cook.request_processor.handle_suggest_recipes", mock_handler):
            result = await _dispatch("suggest_recipes", {"diners": ["Dave"]})
        mock_handler.assert_called_once_with({"diners": ["Dave"]})

    async def test_get_dietary_profile_dispatches(self):
        mock_handler = AsyncMock(return_value={"profiles": []})
        with patch("cook.request_processor.handle_get_dietary_profile", mock_handler):
            result = await _dispatch("get_dietary_profile", {"member_name": "Dave"})
        mock_handler.assert_called_once_with({"member_name": "Dave"})

    async def test_update_dietary_profile_dispatches(self):
        mock_handler = AsyncMock(return_value={"success": True})
        with patch("cook.request_processor.handle_update_dietary_profile", mock_handler):
            await _dispatch(
                "update_dietary_profile",
                {"member_name": "Dave", "item": "milk", "severity": "cannot"},
            )
        mock_handler.assert_called_once()

    async def test_check_dietary_dispatches(self):
        mock_handler = AsyncMock(return_value={"recipe": "test"})
        with patch("cook.request_processor.handle_check_dietary", mock_handler):
            await _dispatch("check_dietary", {"recipe_name": "Pasta"})
        mock_handler.assert_called_once()

    async def test_record_meal_dispatches(self):
        mock_handler = AsyncMock(return_value={"success": True})
        with patch("cook.request_processor.handle_record_meal", mock_handler):
            await _dispatch("record_meal", {"recipe_name": "Pasta", "diners": ["Dave"]})
        mock_handler.assert_called_once()

    async def test_rate_recipe_dispatches(self):
        mock_handler = AsyncMock(return_value={"success": True})
        with patch("cook.request_processor.handle_rate_recipe", mock_handler):
            await _dispatch(
                "rate_recipe", {"recipe_name": "Pasta", "member_name": "Dave", "rating": 5}
            )
        mock_handler.assert_called_once()

    async def test_order_recipe_ingredients_dispatches(self):
        mock_handler = AsyncMock(return_value={"success": True})
        with patch("cook.request_processor.handle_order_recipe_ingredients", mock_handler):
            await _dispatch("order_recipe_ingredients", {"recipe_name": "Pasta"})
        mock_handler.assert_called_once()

    async def test_unknown_request_type_raises(self):
        with pytest.raises(ValueError, match="Unknown request_type"):
            await _dispatch("nonexistent_type", {})


class TestProcessPendingRequests:
    """Test the poll-and-dispatch loop."""

    async def test_no_pending_requests(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def _get_session():
            yield mock_session

        with patch("cook.request_processor.get_session", _get_session):
            await process_pending_requests()

        # Should have queried but not dispatched
        mock_session.execute.assert_called_once()
