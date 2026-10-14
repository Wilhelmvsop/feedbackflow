import httpx
import pytest

from app import notify
from app.config import settings


@pytest.fixture
def sent(monkeypatch):
    """Enable publishing and capture what would be POSTed to the notifier."""
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append({"url": url, "event": json, "headers": headers})
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "notifier_url", "http://notifier:8002")
    monkeypatch.setattr(settings, "notifier_token", "shared-token")
    monkeypatch.setattr(notify.httpx, "post", fake_post)
    return calls


def test_widget_feedback_publishes_event_once(client, sent):
    body = {"message": "Dark mode please", "category": "feature", "page_path": "/settings", "external_key": "k1"}
    assert client.post("/api/public/alpha/feedback", json=body).status_code == 201
    assert client.post("/api/public/alpha/feedback", json=body).status_code == 200  # duplicate: no event

    assert len(sent) == 1
    call = sent[0]
    assert call["url"] == "http://notifier:8002/events"
    assert call["headers"] == {"Authorization": "Bearer shared-token"}
    event = call["event"]
    assert event["type"] == "feedback.created"
    assert event["workspace"] == {"slug": "alpha", "name": "Alpha"}
    assert event["data"] == {
        "id": event["data"]["id"],
        "message": "Dark mode please",
        "category": "feature",
        "page_path": "/settings",
    }


def test_requirement_status_change_publishes_event(client, sent):
    feedback_id = client.ids.feedback_id
    client.post(f"/api/feedback/{feedback_id}/analysis")
    requirement = client.post(f"/api/feedback/{feedback_id}/requirement").json()

    client.patch(f"/api/requirements/{requirement['id']}", json={"title": "Renamed"})
    assert sent == []  # edits without a status change are not announced

    client.patch(f"/api/requirements/{requirement['id']}", json={"status": "confirmed"})
    assert [call["event"]["type"] for call in sent] == ["requirement.status_changed"]
    assert sent[0]["event"]["data"] == {"id": requirement["id"], "title": "Renamed", "from": "draft", "to": "confirmed"}


def test_publishing_is_disabled_without_url(client, monkeypatch):
    monkeypatch.setattr(settings, "notifier_url", None)
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **k: pytest.fail("should not publish"))
    assert client.post("/api/public/alpha/feedback", json={"message": "Hello there"}).status_code == 201
    assert notify.publish({"type": "x", "id": "1"}) is False


def test_notifier_failures_do_not_break_requests(client, monkeypatch, caplog):
    def failing_post(url, **_):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(settings, "notifier_url", "http://notifier:8002")
    monkeypatch.setattr(notify.httpx, "post", failing_post)
    assert client.post("/api/public/alpha/feedback", json={"message": "Still works"}).status_code == 201
    assert "Could not publish feedback.created" in caplog.text


def test_blank_notifier_url_disables_publishing():
    assert settings.model_validate({"notifier_url": "  "}).notifier_url is None
    assert settings.model_validate({"notifier_url": "http://n:8002/"}).notifier_url == "http://n:8002"


def test_liveness_does_not_touch_database(client):
    assert client.get("/api/health/live").json() == {"ok": True}
