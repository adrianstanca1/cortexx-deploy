#!/usr/bin/env bash
# CortexBuild Pro — run this ON the VPS (Hostinger hPanel → browser terminal)
# Deploys: phase120 crash guard, patched shell (prod React), sw v3-1-017,
# redesigned marketing page. Additive; backs up what it replaces.
set -euo pipefail
BASE="${GIST_BASE:?GIST_BASE not set}"
ROOT=""
for r in /var/www/cortexx /var/www/html /srv/cortexx /var/www/cortexbuildpro.com; do
  [ -f "$r/Cortexx.html" ] && ROOT="$r" && break
done
[ -z "$ROOT" ] && ROOT=$(dirname "$(grep -rl --include=Cortexx.html . /var/www /srv 2>/dev/null | head -1)") 
[ -z "$ROOT" ] && { echo "✗ Could not find web root (no Cortexx.html under /var/www or /srv)"; exit 1; }
echo "▶ Web root: $ROOT"

STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$ROOT/.backup/$STAMP" "$ROOT/dist" "$ROOT/lib"
cp "$ROOT/Cortexx.html" "$ROOT/sw.js" "$ROOT/.backup/$STAMP/" 2>/dev/null || true
echo "▶ Backup: $ROOT/.backup/$STAMP"

fetch(){ curl -fsSL "$BASE/$1" -o "$2"; echo "  ↓ $2"; }
fetch screens-phase120.js       "$ROOT/dist/screens-phase120.js"
cp "$ROOT/dist/screens-phase120.js" "$ROOT/lib/screens-phase120.js"
fetch Cortexx.html              "$ROOT/Cortexx.html"
fetch sw.js                     "$ROOT/sw.js"
fetch Cortexx_Marketing.html    "$ROOT/Cortexx_Marketing.html"

chown www-data:www-data "$ROOT/dist/screens-phase120.js" "$ROOT/lib/screens-phase120.js" \
  "$ROOT/Cortexx.html" "$ROOT/sw.js" "$ROOT/Cortexx_Marketing.html" 2>/dev/null || true

echo "▶ Health checks (live)…"
sleep 1
curl -fsS https://cortexbuildpro.com/dist/screens-phase120.js | grep -q __cortexxGuarded && echo "  ✓ phase120 served" || echo "  ✗ phase120 NOT served (catch-all page returned)"
curl -fsS https://cortexbuildpro.com/sw.js | grep -q v3-1-017 && echo "  ✓ sw v3-1-017" || echo "  ✗ sw still old"
curl -fsS https://cortexbuildpro.com/Cortexx.html | grep -q screens-phase120 && echo "  ✓ shell patched" || echo "  ✗ shell still old"

echo ""
echo "▶ Optional Caddy perf fix (dist/ is currently no-cache + uncompressed):"
echo "  curl -fsSL $BASE/Caddyfile.suggested -o /root/Caddyfile.suggested"
echo "  # merge into /etc/caddy/Caddyfile, then: systemctl reload caddy"
echo ""
echo "✅ Done. Rollback: cp $ROOT/.backup/$STAMP/* $ROOT/"
