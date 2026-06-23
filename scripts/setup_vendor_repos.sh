#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p vendor

clone_if_missing() {
  local url="$1"
  local dir="$2"
  if [ -d "$dir/.git" ]; then
    echo "already cloned: $dir"
  else
    git clone --depth 1 "$url" "$dir"
  fi
}

clone_if_missing \
  "https://github.com/akash-kumar5/CryptoMarket_Regime_Classifier.git" \
  "vendor/CryptoMarket_Regime_Classifier"

clone_if_missing \
  "https://github.com/jayd-bit/Market-Regime-Modeling-and-Rates-Prediction-Analysis.git" \
  "vendor/Market-Regime-Modeling-and-Rates-Prediction-Analysis"

echo "Vendor repos ready under vendor/"
