"""Live end-to-end smoke workflow against the RUNNING stack (backend :8000).

FoodFlow (food delivery — a different domain than the test-suite hospital app):
register -> project -> requirement -> analyze -> plan -> prototype -> feedback ->
revision -> rebuild -> approve -> engineering -> testing -> review -> security ->
docs -> downloads + SSE verification + logout.
"""

import sys
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
REQUIREMENT = (
    "Build a food delivery platform where customers can browse restaurants, "
    "search for food, add items to cart, place orders, track deliveries and "
    "manage their profiles."
)


def wait_for(check, timeout_s, desc):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = check()
        if last:
            return last
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for: {desc} (last={last})")


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    email = f"foodflow_{uuid.uuid4().hex[:8]}@example.com"

    r = c.post("/api/auth/register", json={"email": email, "name": "FoodFlow Tester", "password": "secret123"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    print("1. registered + logged in")

    r = c.post("/api/projects", json={"name": "FoodFlow", "description": REQUIREMENT}, headers=H)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    print(f"2. project created (id={pid})")

    r = c.post(f"/api/projects/{pid}/requirements", json={"description": REQUIREMENT}, headers=H)
    assert r.status_code == 201, r.text

    c.post(f"/api/projects/{pid}/requirements/analyze", headers=H)
    wait_for(lambda: c.get(f"/api/projects/{pid}/workflow", headers=H).json()["status"] == "PLANNING", 180, "analysis")
    analysis = c.get(f"/api/projects/{pid}/analysis", headers=H).json()["analysis"]
    assert "food" in analysis["project_name"].lower(), analysis["project_name"]
    print(f"3-4. analyzed: {analysis['project_name']} ({len(analysis['essential_features'])} features)")

    c.post(f"/api/projects/{pid}/planning", headers=H)
    wait_for(lambda: c.get(f"/api/projects/{pid}/workflow", headers=H).json()["status"] == "PROTOTYPE_BUILDING", 180, "planning")
    plan = c.get(f"/api/projects/{pid}/planning", headers=H).json()["plan"]
    print(f"5. planned: {len(plan['prototype_scope']['screens'])} prototype screens")

    c.post(f"/api/projects/{pid}/prototype/generate", headers=H)
    wait_for(lambda: c.get(f"/api/projects/{pid}/workflow", headers=H).json()["status"] == "AWAITING_REVIEW", 180, "prototype")
    proto = c.get(f"/api/projects/{pid}/prototype", headers=H).json()
    assert proto["version"] == 1 and len(proto["spec"]["screens"]) >= 2
    r = c.get(f"/api/projects/{pid}/prototype/preview?token={token}")
    assert r.status_code == 200 and "<html" in r.text.lower()
    print(f"6. prototype v1 ready ({len(proto['spec']['screens'])} screens, preview HTML ok)")

    c.post(f"/api/projects/{pid}/prototype/feedback", json={"feedback": "Add order tracking with live delivery status."}, headers=H)
    wait_for(lambda: c.get(f"/api/projects/{pid}/prototype", headers=H).json()["version"] == 2, 240, "rebuild")
    print("7-8. feedback -> plan revised -> prototype v2 rebuilt")

    r = c.post(f"/api/projects/{pid}/prototype/approve", json={"comment": "FoodFlow approved"}, headers=H)
    assert r.status_code == 200, r.text
    print("9. prototype approved")

    c.post(f"/api/projects/{pid}/engineering/start", headers=H)
    final = wait_for(
        lambda: (lambda w: w if w["status"] in ("COMPLETED", "FAILED", "CANCELLED") else None)(
            c.get(f"/api/projects/{pid}/workflow", headers=H).json()
        ),
        900, "engineering",
    )
    assert final["status"] == "COMPLETED", final.get("last_error")
    print(f"10-11. engineering COMPLETED ({final['progress']}%)")

    tests = c.get(f"/api/projects/{pid}/testing", headers=H).json()
    assert tests and tests[-1]["status"] == "passed" and tests[-1]["failed"] == 0
    print(f"12-14. tests passed ({tests[-1]['passed']}/{tests[-1]['total']}), review+security recorded")
    assert c.get(f"/api/projects/{pid}/review", headers=H).json()
    assert c.get(f"/api/projects/{pid}/security", headers=H).json()
    assert any("README" in d["name"] for d in c.get(f"/api/projects/{pid}/documentation", headers=H).json())

    downloads = c.get(f"/api/projects/{pid}/downloads", headers=H).json()
    assert {d["kind"] for d in downloads} == {"prototype", "application", "docs", "deployment", "full"}
    assert all(d["size"] > 0 for d in downloads)
    r = c.get(f"/api/projects/{pid}/download?type=full&token={token}")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    print(f"15-18. downloads ready (full ZIP {len(r.content)//1024} KB)")

    # SSE stream check
    frames = []
    with c.stream("GET", f"/api/projects/{pid}/events/stream?token={token}", timeout=20) as s:
        for line in s.iter_lines():
            if line.startswith("data: "):
                frames.append(line[6:])
                if len(frames) >= 3:
                    break
    assert frames and all('"event_type"' in f for f in frames)
    print(f"19. SSE stream verified ({len(frames)} frames with event_type)")

    assert c.post("/api/auth/logout", headers=H).status_code == 200
    assert c.get("/api/auth/me", headers=H).status_code == 401
    print("20. logout revoked the token")

    print(f"\nFOODFLOW E2E: ALL 20 STEPS PASSED (project {pid})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nFOODFLOW E2E FAILED: {exc}")
        sys.exit(1)
