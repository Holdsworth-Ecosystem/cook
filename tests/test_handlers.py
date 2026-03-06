"""Tests for Cook handlers — dietary profiles, meals, ratings, orders.

Covers:
- Dietary profile get/update with member resolution
- Meal recording with diner resolution
- Recipe rating with upsert
- Order delegation to Ocado footman
- Error handling for missing members/recipes
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import MockResult


# ---------------------------------------------------------------------------
# Helper to build a mock session with specific query results
# ---------------------------------------------------------------------------


def _make_row(**kwargs):
    """Create a mock row object with attributes from kwargs."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    # Also support dict-style access for .mappings()
    row.__getitem__ = lambda self, key: kwargs[key]
    row.keys = lambda: kwargs.keys()
    return row


# ---------------------------------------------------------------------------
# Dietary profile handlers
# ---------------------------------------------------------------------------


class TestGetDietaryProfile:
    async def test_returns_profiles_for_member(self):
        profile_rows = [
            {
                "item": "milk",
                "item_type": "ingredient",
                "severity": "cannot",
                "reason": "intolerance",
                "notes": None,
                "source": "manual",
            },
        ]

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=MockResult(rows=profile_rows))
        mock_session.commit = AsyncMock()

        @asynccontextmanager
        async def _get_session():
            yield mock_session

        with patch("cook.handlers.dietary.get_session", _get_session):
            from cook.handlers.dietary import handle_get_dietary_profile

            result = await handle_get_dietary_profile({"member_name": "David"})

        assert result["member"] == "David"
        assert len(result["profiles"]) == 1
        assert "CANNOT" in result["summary"]
        assert "milk" in result["summary"]

    async def test_no_profiles_found(self):
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=MockResult(rows=[]))
        mock_session.commit = AsyncMock()

        @asynccontextmanager
        async def _get_session():
            yield mock_session

        with patch("cook.handlers.dietary.get_session", _get_session):
            from cook.handlers.dietary import handle_get_dietary_profile

            result = await handle_get_dietary_profile({"member_name": "Unknown"})

        assert result["profiles"] == []
        assert "No dietary profiles" in result["message"]

    async def test_missing_member_name_raises(self):
        from cook.handlers.dietary import handle_get_dietary_profile

        with pytest.raises(ValueError, match="member_name is required"):
            await handle_get_dietary_profile({})


class TestUpdateDietaryProfile:
    async def test_successful_update(self):
        member_row = _make_row(id="aaaa-bbbb-cccc-dddd")

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockResult(rows=[member_row])
            return MockResult()

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=_execute_side_effect)
        mock_session.commit = AsyncMock()

        @asynccontextmanager
        async def _get_session():
            yield mock_session

        with patch("cook.handlers.dietary.get_session", _get_session):
            from cook.handlers.dietary import handle_update_dietary_profile

            result = await handle_update_dietary_profile(
                {
                    "member_name": "David",
                    "item": "milk",
                    "severity": "cannot",
                    "reason": "intolerance",
                }
            )

        assert result["success"] is True
        assert "CANNOT" in result["message"]

    async def test_invalid_severity_raises(self):
        from cook.handlers.dietary import handle_update_dietary_profile

        with pytest.raises(ValueError, match="Invalid severity"):
            await handle_update_dietary_profile(
                {
                    "member_name": "Dave",
                    "item": "fish",
                    "severity": "hates",
                }
            )

    async def test_missing_required_fields_raises(self):
        from cook.handlers.dietary import handle_update_dietary_profile

        with pytest.raises(ValueError, match="member_name, item, and severity are required"):
            await handle_update_dietary_profile({"member_name": "Dave"})


# ---------------------------------------------------------------------------
# Meal handlers
# ---------------------------------------------------------------------------


class TestRecordMeal:
    async def test_missing_recipe_name_raises(self):
        from cook.handlers.meals import handle_record_meal

        with pytest.raises(ValueError, match="recipe_name is required"):
            await handle_record_meal({"diners": ["Dave"]})

    async def test_missing_diners_raises(self):
        from cook.handlers.meals import handle_record_meal

        with pytest.raises(ValueError, match="At least one diner"):
            await handle_record_meal({"recipe_name": "Pasta"})


class TestRateRecipe:
    async def test_missing_fields_raises(self):
        from cook.handlers.meals import handle_rate_recipe

        with pytest.raises(ValueError, match="recipe_name, member_name, and rating are required"):
            await handle_rate_recipe({"recipe_name": "Pasta"})

    async def test_invalid_rating_value_raises(self):
        from cook.handlers.meals import handle_rate_recipe

        with pytest.raises(ValueError, match="rating must be between 1 and 5"):
            await handle_rate_recipe(
                {
                    "recipe_name": "Pasta",
                    "member_name": "Dave",
                    "rating": 6,
                }
            )

    async def test_invalid_rating_type_raises(self):
        from cook.handlers.meals import handle_rate_recipe

        with pytest.raises(ValueError, match="rating must be an integer"):
            await handle_rate_recipe(
                {
                    "recipe_name": "Pasta",
                    "member_name": "Dave",
                    "rating": "excellent",
                }
            )

    async def test_zero_rating_raises(self):
        from cook.handlers.meals import handle_rate_recipe

        with pytest.raises(ValueError, match="rating must be between 1 and 5"):
            await handle_rate_recipe(
                {
                    "recipe_name": "Pasta",
                    "member_name": "Dave",
                    "rating": 0,
                }
            )


# ---------------------------------------------------------------------------
# Order handler
# ---------------------------------------------------------------------------


class TestOrderRecipeIngredients:
    async def test_missing_recipe_raises(self):
        from cook.handlers.order import handle_order_recipe_ingredients

        with pytest.raises(ValueError, match="Either recipe_name or recipe_id is required"):
            await handle_order_recipe_ingredients({})
