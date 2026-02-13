#!/usr/bin/env bash
set -euo pipefail

PAGE="https://www.minecraft.net/en-us/download/server/bedrock"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

echo "[1] Baixando HTML da página..."
html="$(curl -L --http1.1 --connect-timeout 8 --max-time 30 -fsSL -A "$UA" \
  -H "Accept-Language: en-US,en;q=0.9" \
  "$PAGE")"
echo "[ok] HTML bytes: ${#html}"

echo "[2] Tentando extrair URL do ZIP (bin-linux)..."
zip_url="$(
  printf '%s' "$html" | tr '"' '\n' \
  | grep -E '^https://.*/bin-linux/bedrock-server-.*\.zip$' \
  | head -n1 || true
)"

if [[ -z "${zip_url:-}" ]]; then
  echo "[info] Não achei bin-linux explícito. Tentando achar qualquer bedrock-server-*.zip no HTML..."
  zip_url="$(
    printf '%s' "$html" | tr '"' '\n' \
    | grep -E '^https://.*bedrock-server-.*\.zip(\?.*)?$' \
    | head -n1 || true
  )"
fi

if [[ -n "${zip_url:-}" ]]; then
  echo "[ok] Achei URL no HTML:"
  echo "$zip_url"
  echo "[3] Baixando bedrock-server.zip..."
  curl -L --http1.1 --connect-timeout 8 --max-time 300 -fS -A "$UA" -o bedrock-server.zip "$zip_url"
  echo "[done] Salvo em ./bedrock-server.zip"
  exit 0
fi

echo "[warn] Não encontrei URL do ZIP no HTML."
echo "[4] Fallback: baixar por versão (endpoint direto)."

read -r -p "Informe a versão (ex: 1.21.31.04): " VER
if [[ -z "${VER:-}" ]]; then
  echo "Versão vazia; abortando."
  exit 2
fi

direct_url="https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-$VER.zip"
echo "[info] Tentando: $direct_url"

curl -L --http1.1 --connect-timeout 8 --max-time 300 -fS -A "$UA" -o bedrock-server.zip "$direct_url"
echo "[done] Salvo em ./bedrock-server.zip"
