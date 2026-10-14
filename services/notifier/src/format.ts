import type { WebhookFormat } from "./config.js";
import type { FeedbackFlowEvent } from "./events.js";

const PREVIEW_LENGTH = 280;

function preview(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > PREVIEW_LENGTH ? `${flat.slice(0, PREVIEW_LENGTH - 1)}…` : flat;
}

/** Escape the characters Slack treats as markup so user text cannot inject links or mentions. */
function slackEscape(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function summarize(event: FeedbackFlowEvent): string {
  switch (event.type) {
    case "feedback.created": {
      const where = event.data.page_path ? ` on ${event.data.page_path}` : "";
      return `New ${event.data.category} feedback in ${event.workspace.name}${where}: "${preview(event.data.message)}"`;
    }
    case "requirement.status_changed":
      return `Requirement #${event.data.id} "${event.data.title}" moved ${event.data.from} → ${event.data.to} in ${event.workspace.name}`;
  }
}

/** Body sent to a webhook: Slack-compatible `{text}` or the event itself plus a summary. */
export function render(event: FeedbackFlowEvent, format: WebhookFormat): object {
  if (format === "slack") return { text: slackEscape(summarize(event)) };
  return { ...event, summary: summarize(event) };
}
