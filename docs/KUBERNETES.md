# Kubernetes

Manifests live in `deploy/k8s` and are assembled with Kustomize (built into `kubectl`).

```
deploy/k8s/
  base/                 environment-independent resources
    namespace.yaml      feedbackflow
    configmap.yaml      non-secret settings (APP_ENV, CORS_ORIGINS, NOTIFIER_URL, …)
    app.yaml            API + dashboard Deployment and Service
    notifier.yaml       notifier Deployment and (cluster-internal) Service
    ingress.yaml        ingress-nginx route to the app
  overlays/local/       kind: in-cluster PostgreSQL, local images, webhook echo receiver
    secrets.env         generated, gitignored → Secret `feedbackflow-secrets`
  kind-config.yaml      single node, ingress on host port 8080
  kind-up.sh            build → load → apply → wait → smoke test
```

## Run it locally

Requirements: Docker, [kind](https://kind.sigs.k8s.io/), kubectl, openssl.

```sh
make kind-up      # or deploy/k8s/kind-up.sh
```

The script creates the `feedbackflow` cluster (if needed), installs ingress-nginx, builds both images and loads them into the node, generates `overlays/local/secrets.env` with random values, applies the overlay, waits for every rollout, and then checks the full path: it submits feedback through the ingress and waits for it to arrive at the `webhook-echo` receiver via the notifier.

Open <http://localhost:8080> and sign in as `demo@feedbackflow.local` with the `DEMO_PASSWORD` from `secrets.env`.

Useful commands:

```sh
kubectl -n feedbackflow get pods,svc,ingress
kubectl -n feedbackflow logs deploy/notifier -f          # delivery log
kubectl -n feedbackflow logs deploy/webhook-echo -f      # what webhooks receive
kubectl -n feedbackflow rollout restart deploy/app       # pick up a rebuilt image
make kind-down                                           # delete the cluster
```

To send events to a real Slack channel instead of the echo receiver, set `WEBHOOK_URLS=<incoming webhook URL>` in `secrets.env`, change `WEBHOOK_FORMAT` to `slack` in the ConfigMap patch, and re-run the script.

## Health checks

| Pod | Startup | Readiness | Liveness |
| --- | --- | --- | --- |
| app | `/api/health` (up to 2 min, covers migrations) | `/api/health` (checks the database) | `/api/health/live` (process only) |
| notifier | — | `/readyz` (503 while draining) | `/healthz` |
| postgres | — | `pg_isready` | `pg_isready` |

Liveness deliberately ignores the database: when PostgreSQL is down, app pods leave the Service but are not restarted in a loop.

On `SIGTERM` the notifier reports not-ready and finishes in-flight webhook deliveries before exiting (within `terminationGracePeriodSeconds`).

## Design notes

- **Secrets** come from a `secretGenerator` (`feedbackflow-secrets`); nothing secret is committed. Optional keys (`AI_API_KEY`, `WEBHOOK_URLS`, `WEBHOOK_SECRET`) are marked `optional: true`.
- **Hardening:** non-root UID 1000, read-only root filesystem, all capabilities dropped, `RuntimeDefault` seccomp, resource requests/limits.
- **Notifier is internal:** it has a ClusterIP Service only, and every event must carry the shared `NOTIFIER_TOKEN`.
- **Replicas:** the notifier is stateless and runs 2 replicas. The app runs 1 because analysis jobs and the rate limiter are in-process (see README "Known limitations"). Migrations take a PostgreSQL advisory lock, so scaling the app will not race on the schema.
- **ingress-nginx** went into retirement in March 2026. It still works and is the simplest controller for kind; a Gateway API controller is the long-term replacement.
