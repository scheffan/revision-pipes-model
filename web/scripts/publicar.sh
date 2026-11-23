#!/usr/bin/env bash
# Publica la app en el repo público (GitHub Pages): https://scheffan.github.io/weld-inspection-ai/
# Uso: web/scripts/publicar.sh <carpeta del clon de scheffan/weld-inspection-ai> "mensaje"
# Solo copia la app armada (dist/) y los modelos; README.md y capturas/ del repo público se conservan.
set -euo pipefail
DEMO="$1"; MSG="${2:-Actualiza la demo}"
cd "$(dirname "$0")/.."
npm run build
find "$DEMO" -mindepth 1 -maxdepth 1 ! -name .git ! -name README.md ! -name capturas ! -name .nojekyll -exec rm -rf {} +
cp -r dist/. "$DEMO"/
touch "$DEMO/.nojekyll"
git -C "$DEMO" add -A
git -C "$DEMO" commit -m "$MSG"
git -C "$DEMO" -c push.negotiate=true push
