import json

from sqlalchemy import select

from app import services
from app.models import Analysis


def test_analysis_is_idempotent_and_requirement_stays_source_linked(client):
    fid = client.ids.feedback_id
    first = client.post(f"/api/feedback/{fid}/analysis").json()
    second = client.post(f"/api/feedback/{fid}/analysis").json()
    assert first["analysis_id"] == second["analysis_id"]
    assert first["version"] == second["version"] == 1
    assert client.get(f"/api/feedback/{fid}").json()["analysis"]["status"] == "succeeded"

    draft = client.post(f"/api/feedback/{fid}/requirement")
    assert draft.status_code == 201
    req = draft.json()
    assert req["source_feedback_ids"] == [fid]
    assert req["status"] == "draft"
    again = client.post(f"/api/feedback/{fid}/requirement")
    assert again.status_code == 200 and again.json()["id"] == req["id"]
    assert client.get(f"/api/feedback/{fid}").json()["requirement_id"] == req["id"]


def test_requirement_requires_successful_analysis(client):
    assert client.post(f"/api/feedback/{client.ids.feedback_id}/requirement").status_code == 409


def test_requirement_lifecycle_and_tasks(client):
    fid = client.ids.feedback_id
    client.post(f"/api/feedback/{fid}/analysis")
    req = client.post(f"/api/feedback/{fid}/requirement").json()
    base = f"/api/requirements/{req['id']}"

    created = client.post(f"{base}/tasks", json={"title": "  Show progress states in the import panel "})
    assert created.status_code == 201
    task = created.json()["tasks"][0]
    assert task["title"] == "Show progress states in the import panel"
    assert client.post(f"{base}/tasks", json={"title": "   "}).status_code == 422
    assert client.patch(f"{base}/tasks/{task['id']}", json={"done": True}).json()["tasks"][0]["done"] is True
    # Setting the same value twice is idempotent (no toggling).
    assert client.patch(f"{base}/tasks/{task['id']}", json={"done": True}).json()["tasks"][0]["done"] is True
    assert client.delete(f"{base}/tasks/{task['id']}").json()["tasks"] == []
    assert client.patch(f"{base}/tasks/{task['id']}", json={"done": False}).status_code == 404

    assert client.patch(base, json={"title": "Show import progress"}).json()["title"] == "Show import progress"
    assert client.patch(base, json={"status": "delivered"}).status_code == 409
    assert client.patch(base, json={"status": "confirmed"}).json()["status"] == "confirmed"
    assert client.patch(base, json={"status": "draft"}).status_code == 409
    assert client.patch(base, json={"status": "delivered"}).status_code == 200
    assert client.get(f"/api/feedback/{fid}").json()["status"] == "resolved"


def test_failed_analysis_retries_with_a_new_version(client, db):
    fid = client.ids.feedback_id
    db.add(Analysis(feedback_id=fid, version=1, status="failed", error="temporary provider failure"))
    db.commit()
    assert client.post(f"/api/feedback/{fid}/analysis/retry").json()["version"] == 2
    assert client.get(f"/api/feedback/{fid}").json()["analysis"]["status"] == "succeeded"
    rows = db.scalars(select(Analysis).where(Analysis.feedback_id == fid).order_by(Analysis.version)).all()
    assert [(row.version, row.status) for row in rows] == [(1, "failed"), (2, "succeeded")]
    assert json.loads(rows[1].result_json)["problem"] == "Uploading files is slow and the progress is unclear."
    assert client.post(f"/api/feedback/{fid}/analysis/retry").status_code == 409


def test_provider_errors_become_retryable_failures(client, monkeypatch):
    def broken(*_, **__):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(services, "analyze", broken)
    fid = client.ids.feedback_id
    client.post(f"/api/feedback/{fid}/analysis")
    analysis = client.get(f"/api/feedback/{fid}").json()["analysis"]
    assert analysis["status"] == "failed"
    assert analysis["error"] == "provider unavailable"


def test_interrupted_analyses_are_recovered_as_failed(db, seeded):
    db.add_all([Analysis(feedback_id=seeded.feedback_id, version=1, status="running")])
    db.commit()
    assert services.recover_interrupted_analyses(db) == 1
    assert db.scalar(select(Analysis.status)) == "failed"
