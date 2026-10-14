export type WebhookFormat = "json" | "slack";

export interface Config {
  port: number;
  host: string;
  logLevel: string;
  /** Shared bearer token the API presents on POST /events. Required outside development. */
  ingestToken: string | null;
  webhookUrls: string[];
  webhookFormat: WebhookFormat;
  /** HMAC-SHA256 key for the X-FeedbackFlow-Signature header on JSON deliveries. */
  webhookSecret: string | null;
  deliveryAttempts: number;
  deliveryTimeoutMs: number;
  retryBaseDelayMs: number;
}

type Env = Record<string, string | undefined>;

function int(env: Env, key: string, fallback: number, min = 0): number {
  const raw = env[key];
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < min) throw new Error(`${key} must be an integer >= ${min}`);
  return value;
}

function optional(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export function loadConfig(env: Env = process.env): Config {
  const webhookUrls = (env.WEBHOOK_URLS ?? "")
    .split(",")
    .map((url) => url.trim())
    .filter(Boolean);
  for (const url of webhookUrls) {
    const { protocol } = new URL(url); // throws on malformed URLs
    if (protocol !== "https:" && protocol !== "http:") throw new Error(`Unsupported webhook URL: ${url}`);
  }

  const webhookFormat = (env.WEBHOOK_FORMAT ?? "json") as WebhookFormat;
  if (webhookFormat !== "json" && webhookFormat !== "slack") {
    throw new Error("WEBHOOK_FORMAT must be 'json' or 'slack'");
  }

  const ingestToken = optional(env.NOTIFIER_TOKEN);
  const appEnv = env.APP_ENV ?? "development";
  if (!ingestToken && appEnv !== "development" && appEnv !== "test") {
    throw new Error("Set NOTIFIER_TOKEN when APP_ENV is not development");
  }

  return {
    port: int(env, "PORT", 8002),
    host: env.HOST ?? "0.0.0.0",
    logLevel: env.LOG_LEVEL?.toLowerCase() ?? "info",
    ingestToken,
    webhookUrls,
    webhookFormat,
    webhookSecret: optional(env.WEBHOOK_SECRET),
    deliveryAttempts: int(env, "DELIVERY_ATTEMPTS", 4, 1),
    deliveryTimeoutMs: int(env, "DELIVERY_TIMEOUT_MS", 5000, 1),
    retryBaseDelayMs: int(env, "RETRY_BASE_DELAY_MS", 500),
  };
}
