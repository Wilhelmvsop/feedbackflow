# Deploying to Azure

FeedbackFlow runs on **Azure Container Apps** with images in **Azure Container Registry** and data in **Azure Database for PostgreSQL – Flexible Server**. Infrastructure is defined in [`deploy/azure/main.bicep`](../deploy/azure/main.bicep); GitHub Actions deploys every push to `main`.

```
GitHub Actions ──OIDC──▶ Entra ID (managed identity "feedbackflow-github")
     │ docker push                       │ az containerapp update
     ▼                                   ▼
Container Registry ◀──AcrPull── Container Apps environment
                                  ├─ feedbackflow-app       (external HTTPS, :8000)
                                  └─ feedbackflow-notifier  (internal only, :8002) ──▶ webhooks
                                         │
                                         ▼
                         PostgreSQL Flexible Server (B1ms, TLS)
```

## What it costs

With an Azure for Students subscription:

| Resource | SKU | Cost |
| --- | --- | --- |
| Container Apps | Consumption, scale to zero | Within the monthly free grant for this workload |
| PostgreSQL Flexible Server | Burstable B1ms, 32 GB | 750 h/month free for 12 months, then roughly $13–15/month |
| Container Registry | Basic | About $5/month (paid from student credit) |
| Log Analytics | Pay-as-you-go, capped at 1 GB/day | First 5 GB/month free |

When you are done, delete everything with `az group delete -n feedbackflow-rg`.

## First deployment

Requirements: Azure CLI, Docker, openssl, python3. `gh` is optional.

```sh
az login --use-device-code
deploy/azure/bootstrap.sh
```

You can override the defaults with environment variables:

- `AZURE_RESOURCE_GROUP` (default `feedbackflow-rg`)
- `AZURE_LOCATION` (default `canadacentral`)
- `AZURE_POSTGRES_LOCATION`: set this if your subscription isn't allowed to create flexible servers in that region.
- `GITHUB_REPO`: taken from `origin` by default.

The script does the following:

1. Registers the resource providers. Generates passwords and tokens into `deploy/azure/.secrets.env`, which is gitignored; keep it, because reruns reuse it.
2. Deploys the registry, PostgreSQL, identities, Log Analytics and the Container Apps environment.
3. Builds both images locally and pushes them to ACR. ACR Tasks / `az acr build` is not available on free and student subscriptions.
4. Deploys both container apps and polls `https://<app>/api/health` until it reports the database is reachable.
5. Prints the GitHub repository variables. If `gh` is logged in, it also sets them.

The script is idempotent: rerun it after editing `main.bicep` or `.secrets.env`. For example, to point the notifier at a Slack incoming webhook, set `WEBHOOK_URLS=https://hooks.slack.com/…` and `WEBHOOK_FORMAT=slack`, then rerun.

## Continuous deployment

`.github/workflows/ci.yml` runs these jobs on every push and pull request:

1. **backend**: ruff, pytest, and Alembic migrations against PostgreSQL.
2. **frontend**: ESLint, tsc, Vitest, and the Vite build.
3. **notifier**: tsc, Vitest with coverage, and the build.
4. **kind e2e**: builds both images, deploys `deploy/k8s/overlays/local` to a kind cluster, and checks widget → API → notifier → webhook.
5. **Deploy to Azure** (pushes to `main` only, once the repository variables exist):
   - logs in with OIDC;
   - pushes `feedbackflow-{app,notifier}:<sha>` to ACR;
   - runs `az containerapp update` for each app;
   - smoke-tests `/api/health`.

The deploy job has no stored Azure credentials. GitHub's OIDC token is exchanged for a token for the `feedbackflow-github` managed identity. That identity can push to the registry and manage this resource group, and only for runs on `refs/heads/main` of this repository.

Repository variables (Settings → Secrets and variables → Actions → Variables): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `ACR_NAME`, `AZURE_APP_NAME`, `AZURE_NOTIFIER_NAME`.

## Operating it

```sh
az containerapp logs show -g feedbackflow-rg -n feedbackflow-app --follow
az containerapp logs show -g feedbackflow-rg -n feedbackflow-notifier --follow
az containerapp revision list -g feedbackflow-rg -n feedbackflow-app -o table
# Roll back to a previous image
az containerapp update -g feedbackflow-rg -n feedbackflow-app --image <acr>.azurecr.io/feedbackflow-app:<older-sha>
```

Both apps scale to zero when idle. The first request after a quiet period takes several seconds while the app starts.
