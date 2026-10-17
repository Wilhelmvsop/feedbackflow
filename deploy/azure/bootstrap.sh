#!/usr/bin/env bash
# One-time (and re-runnable) Azure setup for FeedbackFlow. Needs: az (logged in), docker, openssl, python3.
#
#   az login --use-device-code
#   deploy/azure/bootstrap.sh            # INFRA_ONLY=1 stops before images/apps (no Docker needed)
#
# Without a local Docker (or with BUILDER=acr) images are built in the cloud with ACR Tasks instead.
# Works from Git Bash on Windows too.
#
# Creates the resource group and everything in main.bicep, pushes the first images, deploys both
# container apps, smoke-tests the public URL, and prints (or sets, if `gh` is logged in) the GitHub
# repository variables the deploy workflow needs. Generated secrets are kept in deploy/azure/.secrets.env.
set -euo pipefail

RG=${AZURE_RESOURCE_GROUP:-feedbackflow-rg}
LOCATION=${AZURE_LOCATION:-canadacentral}
PG_LOCATION=${AZURE_POSTGRES_LOCATION:-$LOCATION}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SECRETS=$HERE/.secrets.env
GITHUB_REPO=${GITHUB_REPO:-$(git -C "$ROOT" remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')}
# Numeric owner/repo ids for the id-based OIDC subject GitHub issues to newer repositories (needs gh).
GITHUB_REPO_IDS=${GITHUB_REPO_IDS:-$(gh api "repos/$GITHUB_REPO" --jq '"\(.owner.id)/\(.id)"' 2>/dev/null | tr -d '\r' || true)}
BUILDER=${BUILDER:-$(command -v docker >/dev/null && echo docker || echo acr)}
# az and python on Windows print UTF-8 with CRLF line endings; keep both out of captured values.
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

az account show --query '{subscription:name, user:user.name}' -o table

log "Registering resource providers (first run on a new subscription can take a few minutes)"
for ns in Microsoft.App Microsoft.ContainerRegistry Microsoft.DBforPostgreSQL Microsoft.ManagedIdentity Microsoft.OperationalInsights; do
  az provider register --namespace "$ns" --wait
done

if [[ ! -f $SECRETS ]]; then
  log "Generating $SECRETS"
  umask 077
  cat >"$SECRETS" <<EOF
POSTGRES_ADMIN_PASSWORD=$(openssl rand -hex 24)
DEMO_PASSWORD=$(openssl rand -hex 12)
NOTIFIER_TOKEN=$(openssl rand -hex 24)
WEBHOOK_SECRET=$(openssl rand -hex 24)
# Optional: comma-separated webhook URLs (e.g. a Slack incoming webhook) and their format (json|slack).
WEBHOOK_URLS=
WEBHOOK_FORMAT=json
EOF
fi
# shellcheck disable=SC1090
source "$SECRETS"

deploy() {  # deploy <deployApps> [appImage notifierImage]
  az deployment group create -g "$RG" -n feedbackflow --template-file "$HERE/main.bicep" \
    --parameters location="$LOCATION" postgresLocation="$PG_LOCATION" githubRepo="$GITHUB_REPO" githubRepoIds="$GITHUB_REPO_IDS" \
      deployApps="$1" appImage="${2:-}" notifierImage="${3:-}" \
      postgresAdminPassword="$POSTGRES_ADMIN_PASSWORD" demoPassword="$DEMO_PASSWORD" \
      notifierToken="$NOTIFIER_TOKEN" webhookSecret="$WEBHOOK_SECRET" \
      webhookUrls="$WEBHOOK_URLS" webhookFormat="$WEBHOOK_FORMAT" \
    --query properties.outputs -o json
}
output() { python3 -c "import json, sys; print(json.load(sys.stdin)['$1']['value'])" <<<"$OUTPUTS" | tr -d '\r'; }
account() { az account show --query "$1" -o tsv | tr -d '\r'; }

log "Resource group $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" -o none

log "Deploying registry, database, identities, environment (PostgreSQL takes ~5-10 min the first time)"
OUTPUTS=$(deploy false)
ACR=$(output registryName)
LOGIN_SERVER=$(output registryLoginServer)
if [[ ${INFRA_ONLY:-0} == 1 ]]; then
  log "Infrastructure ready (registry $LOGIN_SERVER). Re-run without INFRA_ONLY to push images and deploy the apps."
  exit 0
fi

TAG=$(git -C "$ROOT" rev-parse --short HEAD)
[[ -z $(git -C "$ROOT" status --porcelain) ]] || TAG="$TAG-dirty-$(date +%s)"
APP_IMAGE=$LOGIN_SERVER/feedbackflow-app:$TAG
NOTIFIER_IMAGE=$LOGIN_SERVER/feedbackflow-notifier:$TAG

log "Building and pushing $TAG to $LOGIN_SERVER ($BUILDER)"
if [[ $BUILDER == acr ]]; then
  push() { az acr build -r "$ACR" -t "${1#"$LOGIN_SERVER"/}" --platform linux/amd64 "$2" -o none; }
else
  az acr login -n "$ACR"
  # Container Apps rejects Docker v2 (legacy builder) layer media types, so push OCI images via BuildKit.
  docker buildx inspect feedbackflow >/dev/null 2>&1 || docker buildx create --name feedbackflow --driver docker-container >/dev/null
  push() { docker buildx build --builder feedbackflow --provenance=false --output type=image,push=true,oci-mediatypes=true -t "$1" "$2"; }
fi
push "$APP_IMAGE" "$ROOT"
push "$NOTIFIER_IMAGE" "$ROOT/services/notifier"

log "Deploying container apps"
OUTPUTS=$(deploy true "$APP_IMAGE" "$NOTIFIER_IMAGE")
APP_URL=$(output appUrl)

log "Smoke test $APP_URL (the first request wakes the app from zero)"
for _ in $(seq 40); do
  if curl -fsS --max-time 20 "$APP_URL/api/health"; then echo; break; fi
  sleep 6
done
curl -fsS --max-time 20 "$APP_URL/api/health" >/dev/null

declare -A VARS=(
  [AZURE_CLIENT_ID]=$(output githubClientId)
  [AZURE_TENANT_ID]=$(account tenantId)
  [AZURE_SUBSCRIPTION_ID]=$(account id)
  [AZURE_RESOURCE_GROUP]=$RG
  [ACR_NAME]=$ACR
  [AZURE_APP_NAME]=$(output appName)
  [AZURE_NOTIFIER_NAME]=$(output notifierName)
)
log "GitHub Actions repository variables for $GITHUB_REPO"
for key in "${!VARS[@]}"; do echo "$key=${VARS[$key]}"; done
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  for key in "${!VARS[@]}"; do gh variable set "$key" --repo "$GITHUB_REPO" --body "${VARS[$key]}"; done
  echo "Set via gh."
else
  echo "Set these under Settings → Secrets and variables → Actions → Variables (or log in with gh and re-run)."
fi

log "Done: $APP_URL"
echo "Sign in: demo@feedbackflow.local / $DEMO_PASSWORD"
echo "Tear everything down: az group delete -n $RG"
