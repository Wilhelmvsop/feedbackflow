from app.models import Feedback


def test_workspace_scoping_hides_foreign_feedback_and_requirements(client):
    ids = client.ids
    assert client.get(f"/api/feedback/{ids.foreign_id}").status_code == 404
    assert client.patch(f"/api/feedback/{ids.foreign_id}", json={"status": "resolved"}).status_code == 404
    assert client.post(f"/api/feedback/{ids.foreign_id}/analysis").status_code == 404
    assert client.get(f"/api/requirements/{ids.foreign_req_id}").status_code == 404
    assert [item["id"] for item in client.get("/api/feedback").json()["items"]] == [ids.feedback_id]
    assert client.get("/api/requirements").json() == []


def test_list_is_paginated_filtered_and_searchable(client, db):
    alpha = client.ids.alpha.id
    db.add_all(
        [Feedback(workspace_id=alpha, message=f"Export report number {n}", category="feature") for n in range(5)]
    )
    db.add(Feedback(workspace_id=alpha, message="100% of my exports fail", category="bug", status="triaged"))
    db.commit()

    first_page = client.get("/api/feedback", params={"page_size": 4}).json()
    assert first_page["total"] == 7 and len(first_page["items"]) == 4
    second_page = client.get("/api/feedback", params={"page_size": 4, "page": 2}).json()
    assert len(second_page["items"]) == 3
    assert not {i["id"] for i in first_page["items"]} & {i["id"] for i in second_page["items"]}

    assert client.get("/api/feedback", params={"category": "feature"}).json()["total"] == 5
    assert client.get("/api/feedback", params={"status": "triaged"}).json()["total"] == 1
    # LIKE wildcards in the query are matched literally.
    assert client.get("/api/feedback", params={"q": "100%"}).json()["total"] == 1
    assert client.get("/api/feedback", params={"q": "%"}).json()["total"] == 1
    assert client.get("/api/feedback", params={"status": "bogus"}).status_code == 422


def test_stats_count_whole_workspace(client):
    assert client.get("/api/feedback/stats").json() == {
        "total": 1,
        "new": 1,
        "triaged": 0,
        "in_progress": 0,
        "resolved": 0,
    }


def test_update_feedback_validates_status(client):
    url = f"/api/feedback/{client.ids.feedback_id}"
    assert client.patch(url, json={"status": "done"}).status_code == 422
    updated = client.patch(url, json={"status": "triaged", "tags": "upload", "assignee": "sam"}).json()
    assert (updated["status"], updated["tags"], updated["assignee"]) == ("triaged", "upload", "sam")


def test_widget_intake_is_public_scoped_and_idempotent(client):
    client.headers.pop("Authorization")
    payload = {"message": "  The upload status is unclear.  ", "category": "usability", "external_key": "retry-1"}
    first = client.post("/api/public/alpha/feedback", json=payload)
    retry = client.post("/api/public/alpha/feedback", json=payload)
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json() == {**first.json(), "duplicate": True}
    assert client.post("/api/public/missing/feedback", json=payload).status_code == 404
    assert client.post("/api/public/alpha/feedback", json={"message": "  "}).status_code == 422

    client.headers["Authorization"] = "Bearer alpha-token"
    stored = client.get(f"/api/feedback/{first.json()['id']}").json()
    assert stored["message"] == "The upload status is unclear."


def test_bulk_status_update_skips_other_workspaces(client):
    ids = client.ids
    result = client.post("/api/feedback/bulk", json={"ids": [ids.feedback_id, ids.foreign_id], "status": "triaged"})
    assert result.json() == {"updated": 1}
    assert client.get(f"/api/feedback/{ids.feedback_id}").json()["status"] == "triaged"
    assert client.post("/api/feedback/bulk", json={"ids": [], "status": "triaged"}).status_code == 422
