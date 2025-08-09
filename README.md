# Alphamind (TAO20 Subnet Prototype)

Alphamind is an end-to-end prototype of the TAO20 subnet. Miners produce signed emissions and price reports; a validator aggregates them to compute index weights (top-20 by 14d emissions), simulates a vault for mint/redeem with fees, and serves an API + dashboard. On-chain publishing hooks are stubbed for later wiring.

## Features
- Stake-weighted median consensus for emissions and prices with MAD outlier filters and quorum/staleness guards
- 14d rolling emissions and 90d continuity-based eligibility; top-20 weighting and deterministic epoch artifacts with SHA-256 proofs
- Simulated vault with mint (TAO and in-kind), redeem in-kind, tx fee (20 bps) and management fee (1% APR) accrual
- Miner scoring and lightweight slashing signals (deviation strikes, suspension, multipliers)
- FastAPI service exposing weights, metrics, dashboard, and mint/redeem operations

## Repository layout
- `contracts/` — Solidity contracts (Vault, Token, ValidatorSet, etc.)
- `subnet/` — Off-chain prototype (miner, validator, sim, scoring)
  - `tao20/` models, consensus utils, price feed, index design
  - `validator/` aggregation service, API, scoring, publish stub
  - `miner/` one-shot report emitter
  - `sim/` vault, scheduler, epoch helpers
  - `emissions/` snapshot utilities
- `docs/PROTOCOL_V1.md` — protocol spec and report schemas

## Prerequisites
- Python 3.11+
- Optional: `btcli` (for real price/emission reads), Docker 24+, Make

## Quick start (local, Python)
```bash
pip install -r subnet/requirements.txt
export AM_OUT_DIR=$(pwd)/subnet/out
python -m subnet.validator.api  # starts FastAPI at http://127.0.0.1:8000
```

Open the dashboard at:
```
http://127.0.0.1:8000/dashboard
```

### Emit demo reports (miner one-shots)
```bash
# Emissions (uses btcli if available, else empty/demo)
python subnet/miner/loop.py --emit-emissions-once

# Prices (reads via btcli "subnets list"). Set AM_BTCLI if not on PATH.
python subnet/miner/loop.py --emit-prices-once
```

### Aggregate weights and view
Weights are auto-generated when hitting `/weights`. You can also trigger explicitly:
```bash
curl -s -X POST \
  -H "Authorization: Bearer ${AM_API_TOKEN:-dev}" \
  -H 'content-type: application/json' \
  -d '{"in_dir":"'"$AM_OUT_DIR"'","out_file":"'"$AM_OUT_DIR"'/weights.json","top_n":20}' \
  http://127.0.0.1:8000/aggregate

curl -s http://127.0.0.1:8000/weights | jq .
```

## Quick start (Docker)
```bash
# Runs validator API with volume-mapped out dir
docker compose up --build validator
# Open http://localhost:8003/dashboard (proxied to container 8000)
```
Environment:
- `AM_API_TOKEN` — required for mutating endpoints (defaults to `dev` in compose)
- `AM_CORS_ORIGINS` — allowed origins for the API
- Volume `./subnet/out` is mounted to persist artifacts

## API (selected)
- `GET /weights` — current weights + consensus prices + NAV (sim)
- `GET /dashboard` — simple UI
- `GET /readyz` — readiness including quorum/staleness and paused tokens
- `POST /mint-tao` — mint TAO20 via TAO input (Bearer token required)
- `POST /mint-in-kind` — mint with basket (Bearer)
- `POST /redeem` — redeem TAO20 in-kind (Bearer)
- `POST /aggregate` — run aggregation once (Bearer)

Mutations require `Authorization: Bearer <AM_API_TOKEN>`.

## Environment variables (common)
- `AM_OUT_DIR`/`AM_IN_DIR` — IO directory (defaults to `subnet/out`)
- `AM_BTCLI` — path to `btcli` for price/emission reads
- `AM_PRICE_QUORUM`, `AM_PRICE_BAND_PCT`, `AM_PRICE_STALE_SEC`
- `AM_EMISSIONS_QUORUM`, `AM_EMISSIONS_BAND_PCT`, `AM_EMISSIONS_MAD_K`
- `AM_MINT_FEE_BPS`, `AM_REDEEM_FEE_BPS`, `AM_MAX_SLIPPAGE_BPS`
- `AM_API_TOKEN`, `AM_CORS_ORIGINS`

See `subnet/validator/api.py` and `subnet/validator/service.py` for full details.

## Development
```bash
pip install -r subnet/requirements.txt
pytest -q
```

Helpful scripts:
- CLI demos: `python subnet/cli.py prices --btcli <path>`, `demo-weights`, `aggregate-demo`
- Scheduler (daily aggregation + epoch snapshots): `python -m subnet.sim.scheduler`

## Security
Set `AM_API_TOKEN` in all non-dev deployments. Prefer hotkey signatures for miner reports over HMAC.

## Documentation
- Protocol: `docs/PROTOCOL_V1.md`
- Architecture: `subnet/specs/ARCHITECTURE.md`
