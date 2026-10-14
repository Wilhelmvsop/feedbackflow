import { afterEach, describe, expect, it } from "vitest";
import { sign } from "../src/dispatcher.js";
import { app, config, feedbackEvent, fetchReturning, post } from "./helpers.js";

const open: { close: () => Promise<unknown> }[] = [];
afterEach(async () => {
  await Promise.all(open.splice(0).map((instance) => instance.close()));
});

function setup(...args: Parameters<typeof app>) {
  const result = app(...args);
  open.push(result.instance);
  return result;
}

describe("health endpoints", () => {
  it("reports liveness and readiness with delivery stats", async () => {
    const { instance } = setup();
    expect((await instance.inject("/healthz")).json()).toEqual({ ok: true });
    const ready = await instance.inject("/readyz");
    expect(ready.statusCode).toBe(200);
    expect(ready.json()).toMatchObject({ ok: true, webhooks: 1, accepted: 0, inFlight: 0 });
  });
});

describe("POST /events", () => {
  it("rejects missing or wrong tokens", async () => {
    const { instance, fetch } = setup();
    expect((await post(instance, feedbackEvent(), null)).statusCode).toBe(401);
    expect((await post(instance, feedbackEvent(), "nope")).statusCode).toBe(401);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("allows unauthenticated events when no token is configured (development)", async () => {
    const { instance } = setup({ config: config({ ingestToken: null }) });
    expect((await post(instance, feedbackEvent(), null)).statusCode).toBe(202);
  });

  it("validates the event body", async () => {
    const { instance } = setup();
    expect((await post(instance, { ...feedbackEvent(), type: "unknown.event" })).statusCode).toBe(400);
    expect((await post(instance, { ...feedbackEvent(), occurred_at: "yesterday" })).statusCode).toBe(400);
    expect((await post(instance, { ...feedbackEvent(), data: { id: 1 } })).statusCode).toBe(400);
  });

  it("delivers a signed JSON payload to every webhook", async () => {
    const urls = ["https://hooks.example.com/a", "https://hooks.example.com/b"];
    const { instance, fetch } = setup({ config: config({ webhookUrls: urls, webhookSecret: "s3cret" }) });

    const response = await post(instance, feedbackEvent());
    expect(response.statusCode).toBe(202);
    expect(response.json()).toEqual({ accepted: true, duplicate: false, targets: 2 });
    await instance.dispatcher.idle();

    expect(fetch.mock.calls.map(([url]) => url)).toEqual(urls);
    const init = fetch.mock.calls[0]![1]!;
    const headers = init.headers as Record<string, string>;
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({ id: "evt-1", type: "feedback.created", data: { id: 7 } });
    expect(body.summary).toBe('New bug feedback in Demo Workspace on /reports: "Export to CSV times out"');
    expect(headers["X-FeedbackFlow-Event"]).toBe("feedback.created");
    expect(headers["X-FeedbackFlow-Signature"]).toBe(
      sign("s3cret", headers["X-FeedbackFlow-Timestamp"]!, init.body as string),
    );
    expect(instance.dispatcher.stats).toMatchObject({ accepted: 1, delivered: 2, failed: 0, inFlight: 0 });
  });

  it("formats Slack messages and escapes user-supplied markup", async () => {
    const { instance, fetch } = setup({ config: config({ webhookFormat: "slack", webhookSecret: "s3cret" }) });
    await post(instance, feedbackEvent({ data: { id: 1, message: "<!channel> help & <b>", category: "general", page_path: null } }));
    await instance.dispatcher.idle();

    const init = fetch.mock.calls[0]![1]!;
    expect(JSON.parse(init.body as string)).toEqual({
      text: 'New general feedback in Demo Workspace: "&lt;!channel&gt; help &amp; &lt;b&gt;"',
    });
    // Slack does not verify our signature, so none is sent.
    expect(init.headers).not.toHaveProperty("X-FeedbackFlow-Signature");
  });

  it("summarizes requirement status changes", async () => {
    const { instance, fetch } = setup({ config: config({ webhookFormat: "slack" }) });
    await post(instance, {
      ...feedbackEvent(),
      type: "requirement.status_changed",
      data: { id: 3, title: "Faster exports", from: "draft", to: "confirmed" },
    });
    await instance.dispatcher.idle();
    expect(JSON.parse(fetch.mock.calls[0]![1]!.body as string).text).toBe(
      'Requirement #3 "Faster exports" moved draft → confirmed in Demo Workspace',
    );
  });

  it("ignores a repeated event id", async () => {
    const { instance, fetch } = setup();
    await post(instance, feedbackEvent());
    const again = await post(instance, feedbackEvent());
    expect(again.json()).toMatchObject({ accepted: false, duplicate: true });
    await instance.dispatcher.idle();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(instance.dispatcher.stats.duplicates).toBe(1);
  });

  it("truncates long messages in the summary", async () => {
    const { instance, fetch } = setup();
    const message = "word ".repeat(200);
    await post(instance, feedbackEvent({ data: { id: 1, message, category: "bug", page_path: null } }));
    await instance.dispatcher.idle();
    const { summary } = JSON.parse(fetch.mock.calls[0]![1]!.body as string);
    expect(summary.length).toBeLessThan(340);
    expect(summary).toMatch(/…"$/);
  });
});

describe("delivery retries", () => {
  it("retries transient failures with exponential backoff", async () => {
    const fetch = fetchReturning(503, new Error("ECONNRESET"), 200);
    const { instance, sleep } = setup({ fetch, config: config({ retryBaseDelayMs: 100 }) });
    await post(instance, feedbackEvent());
    await instance.dispatcher.idle();

    expect(fetch).toHaveBeenCalledTimes(3);
    expect(sleep.mock.calls.map(([ms]) => ms)).toEqual([100, 200]);
    expect(instance.dispatcher.stats).toMatchObject({ delivered: 1, failed: 0 });
  });

  it("gives up after the configured number of attempts", async () => {
    const fetch = fetchReturning(500);
    const { instance } = setup({ fetch, config: config({ deliveryAttempts: 3 }) });
    await post(instance, feedbackEvent());
    await instance.dispatcher.idle();
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(instance.dispatcher.stats).toMatchObject({ delivered: 0, failed: 1 });
  });

  it("does not retry permanent client errors", async () => {
    const fetch = fetchReturning(404);
    const { instance, sleep } = setup({ fetch });
    await post(instance, feedbackEvent());
    await instance.dispatcher.idle();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(sleep).not.toHaveBeenCalled();
    expect(instance.dispatcher.stats.failed).toBe(1);
  });

  it("finishes in-flight deliveries before closing", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const fetch = fetchReturning(200);
    fetch.mockImplementationOnce(async () => {
      await gate;
      return new Response(null, { status: 200 });
    });
    const { instance } = app({ fetch });
    await post(instance, feedbackEvent());
    expect(instance.dispatcher.stats.inFlight).toBe(1);

    const closed = instance.close();
    release();
    await closed;
    expect(instance.dispatcher.stats).toMatchObject({ delivered: 1, inFlight: 0 });
  });
});
