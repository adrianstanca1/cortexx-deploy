#!/usr/bin/env bash
# CortexBuild Pro — run this ON the VPS (Hostinger hPanel → browser terminal)
# Deploys: phase120 crash guard, patched shell (prod React), sw v3-1-017,
# redesigned marketing page. Additive; backs up what it replaces.
set -euo pipefail
BASE="${GIST_BASE:?GIST_BASE not set}"

# Locate the web root: explicit WEB_ROOT wins; otherwise search the filesystem.
ROOT="${WEB_ROOT:-}"
if [ -z "$ROOT" ]; then
  for r in /var/www/cortexx /var/www/html /srv/cortexx /var/www/cortexbuildpro.com /usr/share/caddy; do
    [ -f "$r/Cortexx.html" ] && ROOT="$r" && break
  done
fi
if [ -z "$ROOT" ]; then
  HIT=$(find / -name Cortexx.html \
        -not -path "/root/*" -not -path "*/.backup/*" -not -path "/proc/*" -not -path "/sys/*" \
        2>/dev/null | head -1)
  [ -n "$HIT" ] && ROOT=$(dirname "$HIT")
fi
if [ -z "$ROOT" ] || [ "$ROOT" = "." ]; then
  echo "✗ Could not find the web root on this filesystem."
  echo ""
  echo "── Diagnostics (paste this output back) ──"
  echo "• Caddy config roots/proxies:"
  grep -rEn "root |reverse_proxy|file_server" /etc/caddy/ 2>/dev/null | head -20
  ls /etc/caddy 2>/dev/null
  echo "• Containers:"
  docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}" 2>/dev/null || echo "  (docker not present)"
  echo "• Caddy process:"
  ps aux | grep -i [c]addy | head -3
  exit 1
fi
[ -f "$ROOT/Cortexx.html" ] || { echo "✗ $ROOT has no Cortexx.html — refusing to deploy there."; exit 1; }
echo "▶ Web root: $ROOT"

# Clean up the earlier mis-deploy into /root (harmless files, wrong place)
rm -rf /root/dist/screens-phase120.js /root/lib/screens-phase120.js 2>/dev/null
rm -f /root/Cortexx.html /root/sw.js /root/Cortexx_Marketing.html 2>/dev/null
rmdir /root/dist /root/lib 2>/dev/null || true

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
