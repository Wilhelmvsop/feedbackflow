# Publish FeedbackFlow on Render

This publishes the dashboard/API and a bearer-protected MCP endpoint at HTTPS URLs, and provisions PostgreSQL. The Blueprint is configured for Render's free web service and free PostgreSQL plan, suitable for a portfolio demo. Free PostgreSQL databases expire 30 days after creation, so upgrade the database before then if you need to preserve the demo data.

## 1. Put the project in a GitHub repository

Render deploys from a Git repository. Push this repository to GitHub:

```sh
git remote add origin https://github.com/YOUR_ACCOUNT/feedbackflow.git
git push -u origin main
```

Do not commit `.env`, passwords, database files, or model API keys. The repository `.gitignore` excludes `.env`, local databases, caches, and dependency folders.

## 2. Create the Render deployment

1. Sign in to Render and connect the GitHub repository.
2. In the Render dashboard, choose **New → Blueprint** and select the repository.
3. Review the resources shown from `render.yaml`: two Docker web services and one PostgreSQL database, all in Ohio; the services and database use the free plan.
4. During Blueprint creation, enter a strong `DEMO_PASSWORD` and save it for sign-in. Render generates `MCP_ACCESS_TOKEN` and injects the managed database connection string. No model key is needed for the offline analyzer.
5. Wait for the database health check and the Docker build/deploy to finish. Open the service URL shown in Render, such as `https://feedbackflow.onrender.com` if that name is available.

The main service URL serves the React app, API, and widget. The second service exposes MCP at `/mcp` and requires `Authorization: Bearer <MCP_ACCESS_TOKEN>` on every request. The Docker image builds the dashboard and starts each server on Render's assigned `PORT`. The main service applies database migrations on start; the MCP service runs with `AUTO_MIGRATE=false` so the two never race. The main app's `/api/health` check must pass before Render routes traffic to it.

## 3. Verify the public demo

Replace `YOUR_APP_URL` with the URL shown in the Render dashboard:

```sh
curl -fsS https://YOUR_APP_URL/api/health
```

Expected response: `{"ok":true,"database":"ok",...}`. Open `https://YOUR_APP_URL`, sign in using `demo@feedbackflow.local` and the generated `DEMO_PASSWORD` shown in the service's Environment page, then try the seeded feedback, analysis, linked draft, task, confirmation, and delivery flow.

In the `feedbackflow-mcp` service's Environment page, reveal and copy `MCP_ACCESS_TOKEN` into a secure MCP client configuration. The endpoint URL is `https://YOUR_MCP_SERVICE_URL/mcp`; pass the token as an HTTP `Authorization` bearer header. Keep this token private: it can read demo feedback and create drafts in the shared workspace. A request without the token should receive HTTP 401.

To test the widget from another HTTPS page, embed:

```html
<script src="https://YOUR_APP_URL/feedbackflow.js" data-api="https://YOUR_APP_URL/api" data-project="demo"></script>
```

Submitting feedback is public in this single-workspace demo. The current page path is attached only when the visitor checks the consent box. The demo stores feedback in its shared workspace, so use synthetic examples rather than private customer data.

## 4. Keep it available

- Free Render web services spin down after 15 minutes without traffic and can take about a minute to start on the next request. The two public services share the workspace's free instance-hour allowance.
- Free PostgreSQL has a 1 GB limit, no backups, and expires 30 days after creation. Upgrade it in Render before expiration if the data matters.
- Set `AI_API_KEY` in the `feedbackflow` service Environment page only if you choose to send feedback text to an external model provider. By default, the app uses its local deterministic analyzer.
- After pushing a change to `main`, Render rebuilds and deploys the service from the repository.
- For a custom domain, configure it in Render and follow its DNS/HTTPS instructions. When embedding the widget on a different origin, add that site's exact origin to the service's `CORS_ORIGINS` environment variable, then deploy the change.

## Troubleshooting

- **Build fails:** open Render's deploy logs; check that the Blueprint root is the repository root and the Dockerfile and frontend dependency manifests are present.
- **Health check fails:** verify the service starts on Render's `PORT`, then inspect the service logs for database connection or Python import errors.
- **Login fails:** read the current `DEMO_PASSWORD` from the service Environment page. If the demo account was created before changing the variable, changing the env var does not reset the existing account password.
- **Widget cannot submit from another site:** set `CORS_ORIGINS` to the embedding site's origin, for example `https://portfolio.example`, with no path, then redeploy.
- **Database is unavailable:** confirm the Postgres resource is running and the web service's `DATABASE_URL` references that Blueprint database.
