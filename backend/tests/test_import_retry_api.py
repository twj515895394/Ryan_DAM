from __future__ import annotations

import time

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def wait_terminal(client, headers, job_id: int, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def test_retry_failed_items_only(client, headers, app, tmp_path) -> None:
    folder = client.post("/api/v1/folders", json={"name": "重试", "scope": "general"}, headers=headers).json()
    good = tmp_path / "good.txt"
    good.write_bytes(b"good")
    missing = tmp_path / "later.txt"

    first = client.post(
        "/api/v1/imports", json={"paths": [str(missing), str(good)], "folder_id": folder["id"]}, headers=headers
    )
    job_id = first.json()["id"]
    final = wait_terminal(client, headers, job_id)
    assert final["status"] == "completed_with_errors"
    assert final["success_count"] == 1
    assert final["failed_count"] == 1

    # fix the missing source, then retry
    missing.write_bytes(b"fixed-content")
    retry = client.post(f"/api/v1/imports/{job_id}/retry-failed", headers=headers)
    assert retry.status_code == 200, retry.text
    retried = wait_terminal(client, headers, job_id)
    assert retried["status"] == "completed"
    assert retried["success_count"] == 2
    assert retried["failed_count"] == 0

    with app.state.session_factory() as session:
        from backend.app.models.asset import Asset

        assets = session.query(Asset).all()
        assert len(assets) == 2
        assert {a.name for a in assets} == {"good.txt", "later.txt"}


def test_retry_without_failures_rejected(client, headers, tmp_path) -> None:
    folder = client.post("/api/v1/folders", json={"name": "无失败", "scope": "general"}, headers=headers).json()
    source = tmp_path / "ok.png"
    source.write_bytes(b"ok")
    job = client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers
    ).json()
    final = wait_terminal(client, headers, job["id"])
    assert final["status"] == "completed"

    response = client.post(f"/api/v1/imports/{job['id']}/retry-failed", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "nothing_to_retry"


def test_retry_unknown_job_rejected(client, headers) -> None:
    response = client.post("/api/v1/imports/999/retry-failed", headers=headers)
    assert response.status_code == 404
