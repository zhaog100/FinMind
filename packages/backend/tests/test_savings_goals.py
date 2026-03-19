from datetime import date, timedelta


def test_savings_goal_crud(client, auth_header):
    # Empty list
    r = client.get("/savings-goals", headers=auth_header)
    assert r.status_code == 200
    assert r.get_json() == []

    # Create goal
    payload = {
        "name": "Emergency Fund",
        "description": "6-month emergency fund",
        "target_amount": 5000.0,
        "currency": "USD",
        "deadline": (date.today() + timedelta(days=365)).isoformat(),
    }
    r = client.post("/savings-goals", json=payload, headers=auth_header)
    assert r.status_code == 201
    g = r.get_json()
    assert g["name"] == "Emergency Fund"
    assert g["target_amount"] == 5000.0
    assert g["current_amount"] == 0.0
    assert g["progress_percent"] == 0.0
    assert g["status"] == "ACTIVE"
    assert len(g["milestones"]) == 4  # pre-created placeholders
    goal_id = g["id"]

    # Get single goal
    r = client.get(f"/savings-goals/{goal_id}", headers=auth_header)
    assert r.status_code == 200
    assert r.get_json()["id"] == goal_id

    # List now has 1
    r = client.get("/savings-goals", headers=auth_header)
    assert len(r.get_json()) == 1

    # Update
    r = client.put(
        f"/savings-goals/{goal_id}",
        json={"name": "Bigger Emergency Fund", "target_amount": 10000.0},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.get_json()["name"] == "Bigger Emergency Fund"

    # Delete (abandon)
    r = client.delete(f"/savings-goals/{goal_id}", headers=auth_header)
    assert r.status_code == 200
    r = client.get(f"/savings-goals/{goal_id}", headers=auth_header)
    assert r.get_json()["status"] == "ABANDONED"


def test_contribute_milestones(client, auth_header):
    # Create goal with target 1000
    payload = {
        "name": "Vacation",
        "target_amount": 1000.0,
        "currency": "USD",
    }
    r = client.post("/savings-goals", json=payload, headers=auth_header)
    assert r.status_code == 201
    goal_id = r.get_json()["id"]

    # Contribute 300 -> crosses 25%
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 300.0},
        headers=auth_header,
    )
    assert r.status_code == 200
    g = r.get_json()
    assert g["current_amount"] == 300.0
    assert g["progress_percent"] == 30.0
    assert "new_milestones" in g
    assert "PERCENT_25" in g["new_milestones"]

    # Contribute 200 more -> crosses 50%
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 200.0},
        headers=auth_header,
    )
    g = r.get_json()
    assert g["current_amount"] == 500.0
    assert "PERCENT_50" in g.get("new_milestones", [])

    # Contribute 300 more -> crosses 75%
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 300.0},
        headers=auth_header,
    )
    g = r.get_json()
    assert g["current_amount"] == 800.0
    assert "PERCENT_75" in g.get("new_milestones", [])

    # Contribute 200 more -> crosses 100%, auto-completes
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 200.0},
        headers=auth_header,
    )
    g = r.get_json()
    assert g["current_amount"] == 1000.0
    assert g["status"] == "COMPLETED"
    assert "PERCENT_100" in g.get("new_milestones", [])

    # Cannot contribute to completed goal
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 100.0},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_contribute_validation(client, auth_header):
    payload = {"name": "Gadget", "target_amount": 500.0}
    r = client.post("/savings-goals", json=payload, headers=auth_header)
    goal_id = r.get_json()["id"]

    # Negative amount
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": -10.0},
        headers=auth_header,
    )
    assert r.status_code == 400

    # Missing amount
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_goal_not_found(client, auth_header):
    r = client.get("/savings-goals/99999", headers=auth_header)
    assert r.status_code == 404

    r = client.put("/savings-goals/99999", json={"name": "x"}, headers=auth_header)
    assert r.status_code == 404


def test_savings_summary(client, auth_header):
    # No goals -> zero summary
    r = client.get("/savings-goals/summary", headers=auth_header)
    assert r.status_code == 200
    s = r.get_json()
    assert s["active_goals"] == 0
    assert s["total_target"] == 0
    assert s["total_saved"] == 0

    # Create two goals and contribute
    for name, target in [("Goal A", 1000), ("Goal B", 2000)]:
        client.post(
            "/savings-goals",
            json={"name": name, "target_amount": target},
            headers=auth_header,
        )
    r = client.get("/savings-goals", headers=auth_header)
    goals = r.get_json()
    ga_id = next(g["id"] for g in goals if g["name"] == "Goal A")
    gb_id = next(g["id"] for g in goals if g["name"] == "Goal B")

    client.post(
        f"/savings-goals/{ga_id}/contribute",
        json={"amount": 500},
        headers=auth_header,
    )
    client.post(
        f"/savings-goals/{gb_id}/contribute",
        json={"amount": 600},
        headers=auth_header,
    )

    r = client.get("/savings-goals/summary", headers=auth_header)
    s = r.get_json()
    assert s["active_goals"] == 2
    assert s["total_target"] == 3000.0
    assert s["total_saved"] == 1100.0
    assert s["overall_progress_percent"] == 36.7
    assert s["next_milestone"] is not None


def test_goal_defaults_to_user_currency(client, auth_header):
    r = client.patch(
        "/auth/me", json={"preferred_currency": "INR"}, headers=auth_header
    )
    assert r.status_code == 200

    payload = {"name": "Phone", "target_amount": 30000.0}
    r = client.post("/savings-goals", json=payload, headers=auth_header)
    assert r.status_code == 201
    assert r.get_json()["currency"] == "INR"
