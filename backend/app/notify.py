"""Publish domain events to the notifier service (services/notifier), which fans them out to webhooks.

Publishing is best-effort and runs after the response is sent: a slow or unavailable notifier never
fails a user request. Event payloads must match services/notifier/src/events.ts.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import settings
from .models import Feedback, Requirement, Workspace

logger = logging.getLogger("feedbackflow.notify")


def enabled() -> bool:
    return bool(settings.notifier_url)


def _event(event_type: str, workspace: Workspace, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "occurred_at": datetime.now(UTC).isoformat(),
        "workspace": {"slug": workspace.slug, "name": workspace.name},
        "data": data,
    }


def feedback_created(workspace: Workspace, feedback: Feedback) -> dict[str, Any]:
    return _event(
        "feedback.created",
        workspace,
        {
            "id": feedback.id,
            "message": feedback.message,
            "category": str(feedback.category),
            "page_path": feedback.page_path,
        },
    )


def requirement_status_changed(workspace: Workspace, requirement: Requirement, previous: str) -> dict[str, Any]:
    return _event(
        "requirement.status_changed",
        workspace,
        {"id": requirement.id, "title": requirement.title, "from": str(previous), "to": str(requirement.status)},
    )


def publish(event: dict[str, Any]) -> bool:
    """POST one event to the notifier. Returns whether it was accepted; never raises."""
    if not settings.notifier_url:
        return False
    headers = {"Authorization": f"Bearer {settings.notifier_token}"} if settings.notifier_token else {}
    try:
        response = httpx.post(
            f"{settings.notifier_url}/events",
            json=event,
            headers=headers,
            timeout=settings.notifier_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Could not publish %s event %s: %s", event["type"], event["id"], exc)
        return False
    return True
