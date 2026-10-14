import { createHmac } from "node:crypto";
import type { FastifyBaseLogger } from "fastify";
import type { Config } from "./config.js";
import type { FeedbackFlowEvent } from "./events.js";
import { render } from "./format.js";

export type Fetch = typeof fetch;
export type Sleep = (ms: number) => Promise<void>;

export interface DeliveryStats {
  accepted: number;
  duplicates: number;
  delivered: number;
  failed: number;
  inFlight: number;
}

const SEEN_LIMIT = 5000;

export function sign(secret: string, timestamp: string, body: string): string {
  return "sha256=" + createHmac("sha256", secret).update(`${timestamp}.${body}`).digest("hex");
}

function retryable(status: number): boolean {
  return status === 408 || status === 429 || status >= 500;
}

/**
 * Delivers each accepted event to every configured webhook, retrying transient failures with
 * exponential backoff. Event ids are remembered so a retried publish from the API is not re-sent.
 */
export class Dispatcher {
  readonly stats: DeliveryStats = { accepted: 0, duplicates: 0, delivered: 0, failed: 0, inFlight: 0 };
  private readonly seen = new Set<string>();
  private readonly pending = new Set<Promise<void>>();

  constructor(
    private readonly config: Config,
    private readonly log: FastifyBaseLogger,
    private readonly fetchImpl: Fetch = fetch,
    private readonly sleep: Sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  ) {}

  /** Queue an event. Returns false when the id was already accepted. */
  enqueue(event: FeedbackFlowEvent): boolean {
    if (this.seen.has(event.id)) {
      this.stats.duplicates++;
      return false;
    }
    this.seen.add(event.id);
    if (this.seen.size > SEEN_LIMIT) this.seen.delete(this.seen.values().next().value!);
    this.stats.accepted++;

    for (const url of this.config.webhookUrls) {
      this.stats.inFlight++;
      const job = this.deliver(url, event).finally(() => {
        this.stats.inFlight--;
        this.pending.delete(job);
      });
      this.pending.add(job);
    }
    return true;
  }

  /** Resolves once every queued delivery has finished (used on shutdown and in tests). */
  async idle(): Promise<void> {
    while (this.pending.size) await Promise.allSettled([...this.pending]);
  }

  private async deliver(url: string, event: FeedbackFlowEvent): Promise<void> {
    const { deliveryAttempts, deliveryTimeoutMs, retryBaseDelayMs, webhookFormat, webhookSecret } = this.config;
    const body = JSON.stringify(render(event, webhookFormat));
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": "FeedbackFlow-Notifier/0.1",
      "X-FeedbackFlow-Event": event.type,
      "X-FeedbackFlow-Delivery": event.id,
    };
    if (webhookSecret && webhookFormat === "json") {
      const timestamp = Math.floor(Date.now() / 1000).toString();
      headers["X-FeedbackFlow-Timestamp"] = timestamp;
      headers["X-FeedbackFlow-Signature"] = sign(webhookSecret, timestamp, body);
    }
    const target = new URL(url).host; // never log full URLs: Slack webhook paths are secrets

    for (let attempt = 1; attempt <= deliveryAttempts; attempt++) {
      let reason: string;
      try {
        const response = await this.fetchImpl(url, {
          method: "POST",
          headers,
          body,
          signal: AbortSignal.timeout(deliveryTimeoutMs),
        });
        await response.body?.cancel();
        if (response.ok) {
          this.stats.delivered++;
          this.log.info({ event: event.id, type: event.type, target, attempt }, "webhook delivered");
          return;
        }
        reason = `HTTP ${response.status}`;
        if (!retryable(response.status)) {
          attempt = deliveryAttempts; // permanent failure: stop retrying
        }
      } catch (error) {
        reason = error instanceof Error ? error.message : String(error);
      }
      if (attempt < deliveryAttempts) {
        this.log.warn({ event: event.id, target, attempt, reason }, "webhook delivery failed, retrying");
        await this.sleep(retryBaseDelayMs * 2 ** (attempt - 1));
      } else {
        this.stats.failed++;
        this.log.error({ event: event.id, type: event.type, target, attempt, reason }, "webhook delivery gave up");
      }
    }
  }
}
