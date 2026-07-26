#!/usr/bin/env python3
"""CortexBuild Pro — in-place production patch (run ON the VPS).

Web root is /opt/cortexx, bind-mounted file-by-file into cortexx-web-1.
Single-file bind mounts break if the inode changes, so every write here
truncates in place (open 'w') rather than replacing the file.

Applies:
  1. dist/ + lib/ screens-phase120.js   — Client Portal empty-state crash guard
  2. Cortexx.html                       — register phase120; production React
  3. sw.js                              — CACHE bump, precache phase120 + prod React
Idempotent: re-running is a no-op. Backs up before writing.
"""
import os, re, sys, json, shutil, urllib.request, datetime

ROOT = os.environ.get('WEB_ROOT', '/opt/cortexx')
BASE = os.environ.get('GIST_BASE', 'https://raw.githubusercontent.com/adrianstanca1/cortexx-deploy/main')
NEW_CACHE = 'cortexx-v3-1-017'
ok, warn = [], []

def die(m): print('✗ ' + m); sys.exit(1)
if not os.path.isfile(os.path.join(ROOT, 'Cortexx.html')): die(f'{ROOT}/Cortexx.html not found')

stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
bdir = os.path.join(ROOT, '.backup', stamp); os.makedirs(bdir, exist_ok=True)
for f in ('Cortexx.html', 'sw.js'):
    p = os.path.join(ROOT, f)
    if os.path.isfile(p): shutil.copy2(p, bdir)
print(f'▶ Root: {ROOT}\n▶ Backup: {bdir}')

def write_inplace(path, text):
    with open(path, 'w') as fh: fh.write(text)   # truncate — preserves inode

# ── 1. phase120 module ──────────────────────────────────────────────────────
mod = urllib.request.urlopen(BASE + '/screens-phase120.js', timeout=30).read().decode()
if '__cortexxGuarded' not in mod: die('downloaded phase120 looks wrong')
for sub in ('dist', 'lib'):
    d = os.path.join(ROOT, sub)
    if os.path.isdir(d):
        write_inplace(os.path.join(d, 'screens-phase120.js'), mod); ok.append(f'{sub}/screens-phase120.js')
    else: warn.append(f'{sub}/ missing — skipped')

# ── 2. Cortexx.html ─────────────────────────────────────────────────────────
p = os.path.join(ROOT, 'Cortexx.html'); html = open(p).read(); before = html

if 'screens-phase120' not in html:
    m = re.search(r"const MODULES = \[(.*?)\];", html, re.S)
    if not m: die('MODULES list not found in Cortexx.html')
    if "'app-main'" not in m.group(1): die('unexpected MODULES shape')
    html = html.replace(m.group(0), m.group(0).replace("'app-main'", "'screens-phase120','app-main'", 1), 1)
    ok.append('shell: phase120 registered (loads before app-main)')
else: ok.append('shell: phase120 already registered')

m = re.search(r"const PLAIN_JS = new Set\(\[(.*?)\]\);", html, re.S)
if m and 'screens-phase120' not in m.group(1):
    html = html.replace(m.group(0), m.group(0).replace("]);", ", 'screens-phase120']);", 1), 1)
    ok.append('shell: phase120 marked plain-JS')

# production React — only if the exact dev block is present (SRI must stay matched)
DEV_BLOCK = """    await injectExternalFallback(
      cdnSet('react@18.3.1/umd/react.development.js',
             'react@18.3.1/umd/react.development.js',
             'react/18.3.1/umd/react.development.js'),
      'sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L'
    );
    await injectExternalFallback(
      cdnSet('react-dom@18.3.1/umd/react-dom.development.js',
             'react-dom@18.3.1/umd/react-dom.development.js',
             'react-dom/18.3.1/umd/react-dom.development.js'),
      'sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm'
    );"""
PROD_BLOCK = """    // Dev builds only when hot-editing; production ships the minified runtime
    // (~155 KB lighter, faster renders — no dev-mode invariant checks).
    if (DEV_MODE) {
""" + DEV_BLOCK.replace('\n    ', '\n      ').replace('    await', '      await') + """
    } else {
      await injectExternalFallback(
        cdnSet('react@18.3.1/umd/react.production.min.js',
               'react@18.3.1/umd/react.production.min.js',
               'react/18.3.1/umd/react.production.min.js'),
        'sha384-DGyLxAyjq0f9SPpVevD6IgztCFlnMF6oW/XQGmfe+IsZ8TqEiDrcHkMLKI6fiB/Z'
      );
      await injectExternalFallback(
        cdnSet('react-dom@18.3.1/umd/react-dom.production.min.js',
               'react-dom@18.3.1/umd/react-dom.production.min.js',
               'react-dom/18.3.1/umd/react-dom.production.min.js'),
        'sha384-gTGxhz21lVGYNMcdJOyq01Edg0jhn/c22nsx0kyqP0TxaV5WVdsSH1fSDUf5YJj1'
      );
    }"""
if 'production.min' in html:
    ok.append('shell: production React already active')
elif DEV_BLOCK in html:
    html = html.replace(DEV_BLOCK, PROD_BLOCK, 1); ok.append('shell: production React enabled (dev kept for ?dev=1)')
else:
    warn.append('shell: React block differs from expected — swap SKIPPED (safe: SRI left intact)')

if html != before: write_inplace(p, html)

# ── 3. sw.js ────────────────────────────────────────────────────────────────
p = os.path.join(ROOT, 'sw.js')
if os.path.isfile(p):
    sw = open(p).read(); before = sw
    m = re.search(r"const CACHE = '([^']+)';", sw)
    if m and m.group(1) != NEW_CACHE:
        sw = sw.replace(m.group(0), f"const CACHE = '{NEW_CACHE}';", 1); ok.append(f'sw: CACHE {m.group(1)} → {NEW_CACHE}')
    if 'screens-phase120' not in sw:
        if "'app-main','boot',"  in sw: sw = sw.replace("'app-main','boot',", "'screens-phase120',\n  'app-main','boot',", 1)
        elif "'app-main'" in sw:        sw = sw.replace("'app-main'", "'screens-phase120','app-main'", 1)
        ok.append('sw: phase120 precached')
    if 'react.production.min.js' not in sw and 'react.development.js' in sw:
        sw = sw.replace("'https://cdn.jsdelivr.net/npm/react@18.3.1/umd/react.development.js',",
            "'https://cdn.jsdelivr.net/npm/react@18.3.1/umd/react.production.min.js',\n  'https://cdn.jsdelivr.net/npm/react-dom@18.3.1/umd/react-dom.production.min.js',\n  'https://cdn.jsdelivr.net/npm/react@18.3.1/umd/react.development.js',", 1)
        ok.append('sw: production React precached for offline boot')
    if sw != before: write_inplace(p, sw)
else: warn.append('sw.js not found')

print('\n▶ Applied:');   [print('  ✓ ' + x) for x in ok]
if warn: print('▶ Warnings:'); [print('  ! ' + x) for x in warn]
print(f'\n↩  Rollback:  cp {bdir}/* {ROOT}/')
