from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import create_app


def make_client(token: str = "test-token") -> TestClient:
    return TestClient(create_app(token))


def local_headers(token: str = "test-token") -> dict[str, str]:
    return {"Host": "127.0.0.1", "X-Ryan-DAM-Token": token}


def test_health_returns_version_for_valid_local_request() -> None:
    with make_client() as client:
        response = client.get("/health", headers=local_headers())
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_api_rejects_missing_token() -> None:
    with make_client() as client:
        response = client.get("/health", headers={"Host": "127.0.0.1"})
    assert response.status_code == 401


def test_api_rejects_non_loopback_host() -> None:
    with make_client() as client:
        response = client.get("/health", headers={"Host": "example.com", "X-Ryan-DAM-Token": "test-token"})
    assert response.status_code == 403


def test_api_rejects_untrusted_origin() -> None:
    headers = {**local_headers(), "Origin": "https://untrusted.example"}
    with make_client() as client:
        response = client.get("/health", headers=headers)
    assert response.status_code == 403


def test_dev_origin_preflight_is_allowed() -> None:
    headers = {
        "Host": "127.0.0.1",
        "Origin": "http://127.0.0.1:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-ryan-dam-token",
    }
    with make_client() as client:
        response = client.options("/health", headers=headers)
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_shutdown_requests_server_exit() -> None:
    application = create_app("test-token")
    application.state.server = SimpleNamespace(should_exit=False)
    with TestClient(application) as client:
        response = client.post("/shutdown", headers=local_headers())
    assert response.status_code == 202
    assert application.state.server.should_exit is True
