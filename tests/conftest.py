"""Pytest configuration."""

import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def test_db():
    """Create a test database fixture."""
    # Use in-memory SQLite for tests
    os.environ["DATABASE_URL"] = "sqlite:///./tests/test_database.db"
    yield
    # Cleanup
    if os.path.exists("./tests/test_database.db"):
        os.remove("./tests/test_database.db")
