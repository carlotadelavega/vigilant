from fastapi.testclient import TestClient

from vigilant.config import settings
from vigilant.main import app


def test_app_title_matches_settings() -> None:
    """The FastAPI app should be titled after settings.project_name."""
    assert app.title == settings.project_name


def test_health_endpoint(client: TestClient) -> None:
    """GET /health should report a healthy status without touching any dependency."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_router_is_mounted(client: TestClient) -> None:
    """The chat router should be reachable under /v1 once mounted on app."""
    response = client.get("/v1/models")

    assert response.status_code == 200


def test_mcp_server_is_mounted(client: TestClient) -> None:
    """The MCP streamable-http app should be reachable under /mcp once mounted on app."""
    response = client.get("/mcp")

    assert response.status_code != 404
