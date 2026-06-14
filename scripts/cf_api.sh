#!/bin/bash
# Cloudflare API helper - reads credentials from Hermes .env
ENV_FILE="$HOME/.hermes/.env"
CF_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
CF_ACCOUNT=$(grep '^CLOUDFLARE_ACCOUNT_ID=' "$ENV_FILE" | head -1 | cut -d= -f2-)

if [ -z "$CF_TOKEN" ] || [ -z "$CF_ACCOUNT" ]; then
  echo "ERROR: Missing Cloudflare credentials in ~/.hermes/.env"
  exit 1
fi

ACTION=$1
shift

case "$ACTION" in
  add-domain)
    DOMAIN=$1
    curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/pages/projects/toknet-affiliate/domains" \
      -H "Authorization: Bearer $CF_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"domain\":\"${DOMAIN}\"}"
    ;;
  list-domains)
    curl -s "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/pages/projects/toknet-affiliate/domains" \
      -H "Authorization: Bearer $CF_TOKEN"
    ;;
  deploy)
    npx wrangler pages deploy dist --project-name=toknet-affiliate 2>&1
    ;;
  *)
    echo "Usage: cf_api.sh [add-domain|list-domains|deploy] [args]"
    exit 1
    ;;
esac
