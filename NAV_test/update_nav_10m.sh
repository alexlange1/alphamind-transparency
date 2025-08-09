#!/bin/bash
set -euo pipefail

# Resolve to the directory of this script so it works anywhere it's placed
PROJ="$(cd "$(dirname "$0")" && pwd)"
VENV="/Users/alexanderlange/.venvs/alphamind"
BTCLI="$VENV/bin/btcli"
PY="$VENV/bin/python"

cd "$PROJ"

PORT="$PROJ/state/tao20_portfolio.json"
NAVTSV="$PROJ/nav_history.tsv"
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Build price map from table output
PRICES_JSON=$(/usr/bin/python3 - <<'PY'
import os, json
text = os.popen("/Users/alexanderlange/.venvs/alphamind/bin/btcli subnets list --network finney").read()
prices={}
for line in text.splitlines():
    if '│' not in line: continue
    parts=[p.strip() for p in line.split('│')]
    if not parts or not parts[0].isdigit(): continue
    if len(parts)<3: continue
    try:
        netuid=int(parts[0])
    except: continue
    price_col=parts[2]
    num=''
    for ch in price_col:
        if ch.isdigit() or ch=='.': num+=ch
        elif num: break
    try:
        prices[netuid]=float(num)
    except:
        prices[netuid]=0.0
print(json.dumps(prices))
PY)

# Compute NAV
NAV=$(/usr/bin/python3 - <<PY
import json, sys
prices=json.loads('''$PRICES_JSON''')
try:
    p=json.load(open('$PORT','r'))
except Exception:
    p={'cash_tao':0,'alpha':{}}
nav=float(p.get('cash_tao',0.0))
alpha=p.get('alpha') or {}
for k,v in alpha.items():
    n=int(k); a=float(v)
    nav += a*float(prices.get(n,0.0))
print(f"{nav}")
PY)

# Append NAV row
if [ ! -f "$NAVTSV" ]; then
  echo -e "timestamp\tnav_tao\tcash_tao\tpositions_json" > "$NAVTSV"
fi
# Extract POS and CASH using Python (avoid jq dependency)
read -r POS CASH < <(/usr/bin/python3 - <<PY
import json, sys
try:
    p=json.load(open("$PORT","r"))
except Exception:
    p={}
alpha=p.get('alpha') or {}
cash=p.get('cash_tao', 0)
print(json.dumps(alpha, separators=(',',':')) , cash)
PY
)

echo -e "$TS\t$NAV\t$CASH\t$POS" >> "$NAVTSV"

# Regenerate HTML chart
"$PY" "$PROJ/gen_nav_html.py"


