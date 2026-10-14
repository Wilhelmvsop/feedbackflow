import { vi } from "vitest";
import { buildApp } from "../src/app.js";
import { loadConfig, type Config } from "../src/config.js";
import type { FeedbackFlowEvent } from "../src/events.js";

export const TOKEN = "test-token";

export function config(overrides: Partial<Config> = {}): Config {
  return {
    ...loadConfig({ APP_ENV: "test" }),
    ingestToken: TOKEN,
    webhookUrls: ["https://hooks.example.com/a"],
    retryBaseDelayMs: 1,
    ...overrides,
  };
}

export function feedbackEvent(overrides: Partial<FeedbackFlowEvent> = {}): FeedbackFlowEvent {
  return {
    id: "evt-1",
    type: "feedback.created",
    occurred_at: "2026-10-14T12:00:00+00:00",
    workspace: { slug: "demo", name: "Demo Workspace" },
    data: { id: 7, message: "Export to CSV times out", category: "bug", page_path: "/reports" },
    ...overrides,
  } as FeedbackFlowEvent;
}

/** A fetch stub that answers each call with the next status in the list (the last one repeats). */
export function fetchReturning(...statuses: (number | Error)[]) {
  let call = 0;
  return vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => {
    const next = statuses[Math.min(call++, statuses.length - 1)]!;
    if (next instanceof Error) throw next;
    return new Response(null, { status: next });
  });
}

export function app(options: { config?: Config; fetch?: ReturnType<typeof fetchReturning> } = {}) {
  const sleep = vi.fn(async (_ms: number) => {});
  const fetch = options.fetch ?? fetchReturning(200);
  const instance = buildApp({ config: options.config ?? config(), fetch, sleep });
  return { instance, fetch, sleep };
}

export function post(instance: ReturnType<typeof buildApp>, payload: unknown, token: string | null = TOKEN) {
  return instance.inject({
    method: "POST",
    url: "/events",
    payload: payload as object,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  });
}
