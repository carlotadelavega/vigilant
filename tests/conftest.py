"""Shared pytest fixtures for the VIGILANT test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from vigilant.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide a FastAPI TestClient bound to the real application instance."""
    with TestClient(app) as test_client:
        yield test_client
