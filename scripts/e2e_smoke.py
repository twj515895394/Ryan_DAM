"""One-shot HTTP smoke test against a running backend (dev verification only)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
TOKEN = f"e2e-token-{int(time.time())}"
DATA_DIR = REPO / ".e2e-data"
OUT = DATA_DIR / "stdout.log"
ERR = DATA_DIR / "stderr.log"

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


def start_backend() -> tuple[subprocess.Popen, int]:
    OUT.parent.mkdir(exist_ok=True)
    start_offset = OUT.stat().st_size if OUT.exists() else 0
    env = {**os.environ, "RYAN_DAM_API_TOKEN": TOKEN, "RYAN_DAM_DATA_DIR": str(DATA_DIR), "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [str(REPO / ".venv" / "Scripts" / "python.exe"), "-m", "backend.app.main"],
        cwd=REPO, env=env, stdout=open(OUT, "ab"), stderr=open(ERR, "ab"),
    )
    import json

    for _ in range(80):
        time.sleep(0.25)
        if OUT.exists():
            new_bytes = OUT.read_bytes()[start_offset:]
            for line in new_bytes.decode("utf-8", errors="ignore").splitlines():
                if line.startswith("RYAN_DAM_READY "):
                    port = json.loads(line.split(" ", 1)[1])["port"]
                    return proc, port
    proc.kill()
    tail = OUT.read_bytes()[start_offset:].decode("utf-8", errors="ignore") if OUT.exists() else "<no log>"
    raise RuntimeError(f"backend did not become ready; new stdout:\n{tail}")


def main() -> None:
    headers = {"X-Ryan-DAM-Token": TOKEN}
    proc, port = start_backend()
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=base, headers=headers, timeout=10) as client:
            health = client.get("/health").json()
            check("health", health == {"status": "ok", "version": "0.1.0"}, str(health))

            settings = client.get("/api/v1/settings").json()
            check("default managed root", settings["managed_root"] == "D:\\Ryan_DAM\\assets", str(settings))

            project = client.post("/api/v1/projects", json={"name": "E2E 项目"}).json()
            check("create project", project.get("name") == "E2E 项目", str(project))

            folder = client.post(
                "/api/v1/folders", json={"name": "场景图", "scope": "project", "project_id": project["id"]}
            )
            check("create project folder", folder.status_code == 201, folder.text)

            general = client.post("/api/v1/folders", json={"name": "角色图", "scope": "general"})
            check("create general folder", general.status_code == 201, general.text)
            general_id = general.json()["id"]
            child = client.post("/api/v1/folders", json={"name": "主角", "scope": "general", "parent_id": general_id})
            check("create nested folder", child.status_code == 201, child.text)

            tree = client.get("/api/v1/folders/tree", params={"scope": "general"}).json()
            check("tree nesting", len(tree) == 1 and tree[0]["children"][0]["name"] == "主角", str(tree))

            dup = client.post("/api/v1/folders", json={"name": "主角", "scope": "general", "parent_id": general_id})
            check("duplicate sibling 409", dup.status_code == 409 and dup.json()["error"]["code"] == "duplicate_name", dup.text)

            cycle = client.patch(f"/api/v1/folders/{general_id}", json={"parent_id": child.json()["id"]})
            check("cycle move 400", cycle.status_code == 400 and cycle.json()["error"]["code"] == "invalid_move", cycle.text)

            cross = client.post("/api/v1/folders", json={"name": "混入项目", "scope": "project", "project_id": project["id"], "parent_id": general_id})
            check("cross-scope 400", cross.status_code == 400 and cross.json()["error"]["code"] == "invalid_parent", cross.text)

            no_token = httpx.get(f"{base}/api/v1/projects")
            check("api requires token", no_token.status_code == 401, str(no_token.status_code))

            new_root = str(DATA_DIR / "e2e-assets")
            patched = client.patch("/api/v1/settings", json={"managed_root": new_root})
            check("patch settings", patched.status_code == 200 and patched.json()["managed_root"] == new_root, patched.text)

            # end-to-end managed import into the general folder
            source = DATA_DIR / "e2e-source.png"
            source.write_bytes(b"e2e-import-payload")
            imported = client.post(
                "/api/v1/imports", json={"paths": [str(source)], "folder_id": general_id}
            )
            check("create import", imported.status_code == 202, imported.text)
            import_job_id = imported.json()["id"]
            import_final: dict = {}
            for _ in range(100):
                import_final = client.get(f"/api/v1/imports/{import_job_id}").json()
                if import_final["status"] in {"completed", "completed_with_errors", "failed"}:
                    break
                time.sleep(0.2)
            check(
                "import completes",
                import_final.get("status") == "completed" and import_final.get("success_count") == 1,
                str(import_final),
            )
            import_item = (import_final.get("items") or [{}])[0]
            check("import produced asset", bool(import_item.get("asset_id")), str(import_item))

        # restart the backend to prove persistence
        httpx.post(f"{base}/shutdown", headers=headers, timeout=5)
        proc.wait(timeout=10)
        proc, port = start_backend()
        base = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=base, headers=headers, timeout=10) as client:
            projects = client.get("/api/v1/projects").json()
            check("projects persist", [p["name"] for p in projects] == ["E2E 项目"], str(projects))
            settings = client.get("/api/v1/settings").json()
            check("settings persist", settings["managed_root"] == new_root, str(settings))
            tree = client.get("/api/v1/folders/tree", params={"scope": "general"}).json()
            check("folders persist", len(tree) == 1 and tree[0]["name"] == "角色图", str(tree))
    finally:
        try:
            httpx.post(f"{base}/shutdown", headers=headers, timeout=5)
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        print(f"\nRESULT: {passed} passed, {failed} failed")
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
