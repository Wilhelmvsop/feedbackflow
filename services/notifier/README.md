# FeedbackFlow notifier

A small TypeScript service (Fastify, Node 22) that receives domain events from the FeedbackFlow API and delivers them to webhooks: a Slack incoming webhook, or any endpoint that accepts signed JSON.

```
widget ─▶ API ──POST /events (Bearer NOTIFIER_TOKEN)──▶ notifier ──▶ webhook(s)
```

The API publishes after it has sent its response, so a slow or unavailable notifier never fails a user request. The notifier answers `202` immediately and delivers in the background:

- one attempt per URL in `WEBHOOK_URLS`;
- exponential backoff on network errors, `408`, `429` and `5xx`;
- no retries on other `4xx` responses;
- in-flight deliveries are finished on `SIGTERM`.

## Events

| Type | Published when | `data` |
| --- | --- | --- |
| `feedback.created` | New widget submission (repeats of the same `external_key` are not published) | `id`, `message`, `category`, `page_path` |
| `requirement.status_changed` | A requirement moves draft → confirmed → delivered | `id`, `title`, `from`, `to` |

Every event also has an `id` (UUID, used to drop repeats), a `type`, an `occurred_at` timestamp, and a `workspace` object `{slug, name}`. The schema is in [`src/events.ts`](src/events.ts); the publisher is `backend/app/notify.py`.

## Configuration

| Variable | Default | |
| --- | --- | --- |
| `PORT` / `HOST` | `8002` / `0.0.0.0` | |
| `NOTIFIER_TOKEN` | — | Bearer token required on `POST /events`. Mandatory unless `APP_ENV=development`/`test`. |
| `WEBHOOK_URLS` | empty | Comma-separated. Empty means events are accepted and counted but not sent. |
| `WEBHOOK_FORMAT` | `json` | `json` sends the event plus a `summary`. `slack` sends `{ "text": … }`. |
| `WEBHOOK_SECRET` | — | Signs JSON deliveries (see below). |
| `DELIVERY_ATTEMPTS` | `4` | Attempts per webhook |
| `DELIVERY_TIMEOUT_MS` | `5000` | Timeout per attempt |
| `RETRY_BASE_DELAY_MS` | `500` | Backoff uses `base × 2^(attempt-1)` |

## Verifying signatures

JSON deliveries carry these headers:

- `X-FeedbackFlow-Event`
- `X-FeedbackFlow-Delivery` (the event id)
- `X-FeedbackFlow-Timestamp`
- `X-FeedbackFlow-Signature: sha256=<hex>`, computed as `HMAC_SHA256(WEBHOOK_SECRET, "<timestamp>.<raw body>")`

To verify a delivery:

1. Recompute the HMAC over `"<timestamp>.<raw body>"`.
2. Compare it to the header in constant time.
3. Reject timestamps that are more than a few minutes old.

## Endpoints

- `POST /events`: ingest an event (`202`, or `401` / `400`).
- `GET /healthz`: liveness.
- `GET /readyz`: readiness plus delivery counters (`accepted`, `delivered`, `failed`, `inFlight`, …). Returns `503` while shutting down.

## Development

```sh
npm ci
npm run dev                 # tsx watch on :8002
npm test                    # Vitest
npm test -- --coverage
npm run typecheck && npm run build
```
