"""Shared fixtures for Cook tests.

All external dependencies (database) are mocked.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock database session
# ---------------------------------------------------------------------------


class MockResult:
    """Mimics SQLAlchemy result objects."""

    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self


class MockSession:
    """Async mock of a SQLAlchemy session."""

    def __init__(self, execute_side_effect=None):
        if execute_side_effect:
            self.execute = AsyncMock(side_effect=execute_side_effect)
        else:
            self.execute = AsyncMock(return_value=MockResult())
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_session():
    """Return a MockSession that can be customised per test."""
    return MockSession()


@pytest.fixture
def patch_cook_db(mock_session):
    """Patch cook.db.get_session to return mock_session."""

    @asynccontextmanager
    async def _get_session():
        yield mock_session

    with patch("cook.db.get_session", _get_session):
        yield mock_session
