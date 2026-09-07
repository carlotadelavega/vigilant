"""Shared pytest fixtures for the VIGILANT test suite."""

from collections.abc import AsyncGenerator, Iterator

import pytest
from fastapi.testclient import TestClient

from vigilant.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide a FastAPI TestClient bound to the real application instance."""
    with TestClient(app) as test_client:
        yield test_client


async def fake_token_stream(tokens: list[str]) -> AsyncGenerator[str, None]:
    """Yield a predefined sequence of tokens, mimicking LLMService.generate_stream."""
    for token in tokens:
        yield token
