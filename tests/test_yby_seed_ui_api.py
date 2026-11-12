from fastapi.testclient import TestClient

from src.yby_seed.main import app


def test_homepage() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "YBY SEED" in response.text
    assert "Vibe Coding" in response.text


def test_forge_dry_run_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/v1/seed/forge/dry-run", json={"mission": "quantize"})
    assert response.status_code == 200
    body = response.json()
    assert body["mission"] == "quantize"
    assert body["dry_run"] is True
