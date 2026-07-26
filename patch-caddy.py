#!/usr/bin/env python3
"""Add compression + immutable asset caching to the live Caddyfile.

Today dist/* is served no-cache and uncompressed: every visit re-downloads
~1 MB of modules. This inserts encode + Cache-Control rules, validates the
config inside the container, reloads on success, and restores the backup on
any failure. Idempotent. Prints only the lines it adds (config is not dumped
— these logs are public).
"""
import os, re, shutil, subprocess, datetime, sys

CF = os.environ.get('CADDYFILE', '/opt/cortexx/Caddyfile')
CTR = os.environ.get('CADDY_CTR', 'cortexx-web-1')
if not os.path.isfile(CF): sys.exit(f'✗ {CF} not found')

src = open(CF).read()
if 'Cache-Control' in src and 'immutable' in src:
    print('✓ caching rules already present — no change'); sys.exit(0)

m = re.search(r'^([ \t]*)root\s+\*\s+\S+.*$', src, re.M)
if not m: sys.exit('✗ no `root *` directive found — not patching blind')
indent = m.group(1) or '\t'

add = []
if not re.search(r'^\s*encode\b', src, re.M):
    add.append(f'{indent}encode zstd gzip')
add += [
    f'{indent}# Precompiled modules are content-stable per release; sw.js CACHE bump invalidates.',
    f'{indent}@immutable path /dist/* /lib/*',
    f'{indent}header @immutable Cache-Control "public, max-age=2592000, immutable"',
    f'{indent}@art path *.png *.svg *.ico *.webp',
    f'{indent}header @art Cache-Control "public, max-age=604800"',
    f'{indent}# The worker and HTML shell are the update channel — never cache.',
    f'{indent}@shell path /sw.js /Cortexx.html /index.html /landing.html /',
    f'{indent}header @shell Cache-Control "no-cache, must-revalidate"',
]
out = src[:m.end()] + '\n' + '\n'.join(add) + src[m.end():]

stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
bak = f'{CF}.bak-{stamp}'; shutil.copy2(CF, bak)
with open(CF, 'w') as fh: fh.write(out)      # truncate — preserves inode for bind mount

def sh(*a): return subprocess.run(a, capture_output=True, text=True, timeout=90)
v = sh('docker', 'exec', CTR, 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
if v.returncode != 0:
    shutil.copy2(bak, CF)
    print('✗ validation failed — reverted. caddy said:'); print((v.stderr or v.stdout)[-600:]); sys.exit(1)

r = sh('docker', 'exec', CTR, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
if r.returncode != 0:
    shutil.copy2(bak, CF); sh('docker', 'restart', CTR)
    print('✗ reload failed — reverted + restarted. caddy said:'); print((r.stderr or r.stdout)[-600:]); sys.exit(1)

print('✓ validated and reloaded. Added:')
for l in add: print('   ' + l.strip())
print(f'↩  Rollback: cp {bak} {CF} && docker exec {CTR} caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile')
