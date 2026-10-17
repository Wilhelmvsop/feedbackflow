#!/usr/bin/env bash
# Build both images, run FeedbackFlow on a local kind cluster, and smoke-test it end to end.
#   deploy/k8s/kind-up.sh            # create/update cluster "feedbackflow" and deploy
#   KEEP_SECRETS=0 deploy/k8s/kind-up.sh   # regenerate overlays/local/secrets.env
# Afterwards: http://localhost:8080 (demo@feedbackflow.local / DEMO_PASSWORD from secrets.env)
set -euo pipefail

CLUSTER=${CLUSTER:-feedbackflow}
INGRESS_NGINX_VERSION=${INGRESS_NGINX_VERSION:-controller-v1.15.1}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
K8S=$ROOT/deploy/k8s
SECRETS=$K8S/overlays/local/secrets.env
NS=feedbackflow

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  log "Creating kind cluster $CLUSTER"
  kind create cluster --name "$CLUSTER" --config "$K8S/kind-config.yaml" --wait 120s
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

log "Installing ingress-nginx ($INGRESS_NGINX_VERSION)"
kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/$INGRESS_NGINX_VERSION/deploy/static/provider/kind/deploy.yaml" >/dev/null

log "Building images"
docker build -t feedbackflow-app:local "$ROOT"
docker build -t feedbackflow-notifier:local "$ROOT/services/notifier"
kind load docker-image --name "$CLUSTER" feedbackflow-app:local feedbackflow-notifier:local

if [[ ! -f $SECRETS || ${KEEP_SECRETS:-1} == 0 ]]; then
  log "Generating $SECRETS"
  rand() { openssl rand -hex 16; }
  pg=$(rand)
  cat >"$SECRETS" <<EOF
POSTGRES_PASSWORD=$pg
DATABASE_URL=postgresql+psycopg://feedbackflow:$pg@postgres:5432/feedbackflow
DEMO_PASSWORD=$(rand)
NOTIFIER_TOKEN=$(rand)
WEBHOOK_SECRET=$(rand)
WEBHOOK_URLS=http://webhook-echo/feedbackflow
AI_API_KEY=
EOF
fi

kubectl -n ingress-nginx wait --for=condition=Available deployment/ingress-nginx-controller --timeout=180s

# The admission webhook can lag behind the controller becoming Available, hence the retries.
log "Applying manifests"
for attempt in 1 2 3 4 5; do
  kubectl apply -k "$K8S/overlays/local" && break
  echo "apply failed (attempt $attempt), retrying in 5s"; sleep 5
done
# Pick up newly built images even when the tag (`local`) did not change.
kubectl -n $NS rollout restart deployment/app deployment/notifier >/dev/null

log "Waiting for rollouts"
kubectl -n $NS rollout status statefulset/postgres --timeout=180s
for d in webhook-echo notifier app; do kubectl -n $NS rollout status deployment/$d --timeout=240s; done

log "Smoke test through the ingress"
base=http://localhost:8080
for _ in $(seq 30); do curl -fsS "$base/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -fsS "$base/api/health"; echo
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$base/api/public/demo/feedback" \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"kind smoke test $(date +%s)\",\"category\":\"bug\"}")
[[ $code == 201 ]] || { echo "feedback submission returned HTTP $code"; exit 1; }
echo "feedback submitted (HTTP $code)"

for _ in $(seq 20); do
  if kubectl -n $NS logs deploy/webhook-echo --tail=200 | grep -q 'kind smoke test'; then
    echo "webhook delivered: API -> notifier -> webhook-echo"
    log "FeedbackFlow is running at $base"
    echo "Sign in: demo@feedbackflow.local / $(grep ^DEMO_PASSWORD= "$SECRETS" | cut -d= -f2)"
    exit 0
  fi
  sleep 2
done
echo "webhook was not delivered; notifier logs:"; kubectl -n $NS logs deploy/notifier --tail=50
exit 1
