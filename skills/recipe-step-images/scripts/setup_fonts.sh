#!/usr/bin/env bash
# 下载菜谱排版所需字体（Noto Serif SC Bold）到 assets/fonts/
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/assets/fonts"
mkdir -p "$DIR"
BASE="https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.0.0/files"
for f in noto-serif-sc-chinese-simplified-700-normal.woff2 noto-serif-sc-latin-700-normal.woff2; do
  if [ ! -s "$DIR/$f" ]; then
    echo "下载 $f"
    curl -sSL --max-time 180 "$BASE/$f" -o "$DIR/$f"
  fi
done
ls -l "$DIR"
