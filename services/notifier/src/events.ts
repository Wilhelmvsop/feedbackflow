/** Events published by the FeedbackFlow API. Keep in sync with backend/app/notify.py. */

interface BaseEvent<T extends string, D> {
  id: string;
  type: T;
  occurred_at: string;
  workspace: { slug: string; name: string };
  data: D;
}

export type FeedbackCreated = BaseEvent<
  "feedback.created",
  { id: number; message: string; category: string; page_path: string | null }
>;

export type RequirementStatusChanged = BaseEvent<
  "requirement.status_changed",
  { id: number; title: string; from: string; to: string }
>;

export type FeedbackFlowEvent = FeedbackCreated | RequirementStatusChanged;

const workspace = {
  type: "object",
  required: ["slug", "name"],
  properties: { slug: { type: "string", minLength: 1 }, name: { type: "string" } },
} as const;

const envelope = (type: string, data: object) =>
  ({
    type: "object",
    required: ["id", "type", "occurred_at", "workspace", "data"],
    properties: {
      id: { type: "string", minLength: 1, maxLength: 100 },
      type: { const: type },
      occurred_at: { type: "string", format: "date-time" },
      workspace,
      data,
    },
  }) as const;

/** JSON schema for POST /events; Fastify validates the body with it before the handler runs. */
export const eventSchema = {
  oneOf: [
    envelope("feedback.created", {
      type: "object",
      required: ["id", "message", "category"],
      properties: {
        id: { type: "integer" },
        message: { type: "string", maxLength: 5000 },
        category: { type: "string" },
        page_path: { type: ["string", "null"] },
      },
    }),
    envelope("requirement.status_changed", {
      type: "object",
      required: ["id", "title", "from", "to"],
      properties: {
        id: { type: "integer" },
        title: { type: "string" },
        from: { type: "string" },
        to: { type: "string" },
      },
    }),
  ],
} as const;
