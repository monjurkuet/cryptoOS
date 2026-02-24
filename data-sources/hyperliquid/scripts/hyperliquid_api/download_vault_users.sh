#!/bin/bash
# Download Hyperliquid Vault Users

set -e

API_URL="https://api.hyperliquid.xyz/info"
VAULT_ADDRESS="${1:-0x00043d4a2c258892172dc6ce5f62e2e3936ae0dc}"
OUTPUT_FILE="${2:-data/hyperliquid/vault_users.json}"

echo "👥 Downloading vaultUsers for $VAULT_ADDRESS..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"vaultUsers\",\"vaultAddress\":\"$VAULT_ADDRESS\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
