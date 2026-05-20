#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:?Usage: deploy.sh <dev|prod> <registry> <image-tag>}
REGISTRY=${2:?Registry required}
IMAGE_TAG=${3:?Image tag required}
NAMESPACE="tradeforge-${ENVIRONMENT}"
MANIFEST_DIR="k8s/${ENVIRONMENT}"

SERVICES=(frontend market-service wallet-service order-service portfolio-service recommendation-service)

kubectl apply -f "${MANIFEST_DIR}/namespace.yaml"
kubectl apply -f "${MANIFEST_DIR}/apps.yaml"

for service in "${SERVICES[@]}"; do
  kubectl -n "${NAMESPACE}" set image deployment/${service} ${service}=${REGISTRY}/tradeforge-${service}:${IMAGE_TAG}
done

for service in "${SERVICES[@]}"; do
  if ! kubectl -n "${NAMESPACE}" rollout status deployment/${service} --timeout=180s; then
    echo "Rollout failed for ${service}; rolling back all services in ${NAMESPACE}"
    for rollback_service in "${SERVICES[@]}"; do
      kubectl -n "${NAMESPACE}" rollout undo deployment/${rollback_service} || true
    done
    exit 1
  fi
done
