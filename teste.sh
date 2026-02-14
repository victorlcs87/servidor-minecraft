#!/usr/bin/env bash
set -euo pipefail

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
PAGE="https://minecraft.wiki/w/Bedrock_Dedicated_Server"

echo "[1] Baixando HTML da Wiki ($PAGE)..."
# Baixa o HTML, filtra URLs de linux, ordena por versão (sort -V) e pega a última
zip_url="$(curl -L -A "$UA" -s "$PAGE" | \
  grep -o 'https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-[0-9.]*\.zip' | \
  sort -V | tail -n 1)"

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
