#!/usr/bin/env bash
# deploy-container.sh — build and push the segment-frame-extractor container image to ECR
#
# Builds src/container/ for linux/arm64 (matches the ECS Fargate task definition),
# logs in to ECR, and pushes :latest + :<git-sha> tags.
#
# Usage:
#   ./scripts/deploy-container.sh [--env <dev|prod>] [--region <region>]
#
# Environments:
#   dev   (default) — pushes to lectureclip-dev-segment-frame-extractor
#   prod            — pushes to lectureclip-prod-segment-frame-extractor
#
# Prerequisites:
#   - Docker with buildx support (docker buildx version)
#   - AWS CLI with credentials that have:
#       ecr:GetAuthorizationToken  (account-scoped)
#       ecr:BatchCheckLayerAvailability, ecr:CompleteLayerUpload,
#       ecr:InitiateLayerUpload, ecr:PutImage, ecr:UploadLayerPart
#       on lectureclip-{env}-segment-frame-extractor
#
# Examples:
#   ./scripts/deploy-container.sh
#   ./scripts/deploy-container.sh --env prod
#   AWS_PROFILE=dev ./scripts/deploy-container.sh --env dev --region ca-central-1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── helpers ───────────────────────────────────────────────────────────────────

log()  { echo "  [deploy] $*"; }
err()  { echo "  [error]  $*" >&2; exit 1; }
step() { echo ""; echo "▸ $*"; }

# ── defaults ──────────────────────────────────────────────────────────────────

REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-ca-central-1}}"
ENV="dev"

# ── arg parsing ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)    ENV="$2";    shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/{ /^#/{ s/^# \?//; p } }' "$0"
      exit 0
      ;;
    *) err "unknown argument: $1" ;;
  esac
done

[[ "$ENV" == "dev" || "$ENV" == "prod" ]] || err "--env must be 'dev' or 'prod' (got '$ENV')"

# ── resolve account + repo ────────────────────────────────────────────────────

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "$REGION")"
REPO_NAME="lectureclip-${ENV}-segment-frame-extractor"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${REPO_NAME}"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"

echo ""
echo "  env      : $ENV"
echo "  region   : $REGION"
echo "  registry : $ECR_REGISTRY"
echo "  repo     : $REPO_NAME"
echo "  tags     : latest, $GIT_SHA"

# ── ecr login ─────────────────────────────────────────────────────────────────
# Use a temporary Docker config directory so credentials are never passed
# through the system credential store (pass/gpg/keychain).

step "ECR login"
DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '{}' > "$DOCKER_CONFIG/config.json"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"
log "done ✓"

# ── build & push ──────────────────────────────────────────────────────────────

step "docker buildx build + push (linux/arm64)"

# Ensure a buildx builder is available that supports multi-platform builds.
# 'default' driver only supports the host platform; use docker-container driver.
BUILDER_NAME="lectureclip-builder"
if ! docker buildx inspect "$BUILDER_NAME" &>/dev/null; then
  log "creating buildx builder: $BUILDER_NAME"
  docker buildx create --name "$BUILDER_NAME" --driver docker-container --use
else
  docker buildx use "$BUILDER_NAME"
fi

docker buildx build \
  --platform linux/arm64 \
  --push \
  --tag "${IMAGE_URI}:latest" \
  --tag "${IMAGE_URI}:${GIT_SHA}" \
  src/container/

log "pushed ${IMAGE_URI}:latest"
log "pushed ${IMAGE_URI}:${GIT_SHA}"
log "done ✓"

echo ""
echo "  Deploy complete."
echo ""
