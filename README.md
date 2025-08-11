# Alphamind (TAO20 Subnet)

What is Alphamind?

Alphamind is a decentralized ETF subnet that creates and manages the TAO20 Index — an emissions‑weighted index of the top 20 Bittensor subnets by 14‑day average TAO emissions. Think of it as the "S&P 500 for Bittensor subnets."

## What this subnet provides

### For investors
- **Buy TAO20 tokens** that represent proportional ownership of the top 20 Bittensor subnets
- **Automatic rebalancing** every 2 weeks based on subnet performance
- **Professional management** with transparent fees (0.2% transaction + 1% annual)
- **Diversification** across the best-performing subnets without managing 20+ individual positions

### For the ecosystem
- **Objective subnet ranking** based on actual TAO emissions data
- **Price discovery** through decentralized oracle network
- **Capital allocation** directing funds to top-performing subnets
- **Market infrastructure** enabling institutional participation in Bittensor

## Roles: validators and miners

### Validators (subnet operators)
What they do:
- Aggregate price and emissions data from miners
- Compute consensus using stake-weighted median algorithms
- Calculate index weights (top 20 subnets by 14d emissions)
- Simulate vault operations (mint/redeem TAO20 tokens)
- Serve public API for index weights, prices, and NAV
- Score miner performance and apply penalties for bad data
- Publish on-chain proofs of weightset calculations

Resources needed:
- Moderate compute (API server + data processing)
- Reliable internet connection
- Storage for historical data and state
- TAO stake for validator registration

### Miners (data oracles)
What they do:
- Monitor Bittensor network for subnet emission data
- Fetch real-time prices from AMM pools and exchanges
- Calculate Net Asset Value (NAV) for the TAO20 index
- Submit signed reports with cryptographic verification
- Compete for rewards based on data accuracy and timeliness

Resources needed:
- Light compute (data collection scripts)
- Access to Bittensor RPC endpoints
- Minimal bandwidth for report submission
- Minimal TAO stake for miner registration

## Incentive structure

| Role | Primary Rewards | Requirements |
|------|----------------|--------------|
| **Validators** | Subnet operation fees, consensus rewards | Higher TAO stake, reliable infrastructure |
| **Miners** | Accuracy-based scoring, emission sharing | Data accuracy, timely reporting |

## How it works

1. **Miners** collect emissions data and prices from Bittensor network
2. **Validators** aggregate miner reports using consensus algorithms  
3. **Index weights** are calculated (top 20 subnets by 14d emissions)
4. **TAO20 tokens** can be minted/redeemed based on current NAV
5. **Rebalancing** happens automatically every 2 weeks
6. **On-chain proofs** are published for transparency

## Key features
- Decentralized oracle network: stake‑weighted median consensus with outlier detection
- Automatic rebalancing: 14‑day emissions‑based weightset updates
- Vault and token contracts: NAV‑based mint/redeem with fee accrual
- Transparent scoring: miner performance tracking with penalties for deviations
- API service: dashboard, metrics, and administrative endpoints
- Smart‑contract integration: on‑chain proof publication and validation

## Repository structure
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

## Quick start

### Option A: Using the Alphamind CLI (recommended)
```bash
# Install dependencies
pip install -r subnet/requirements.txt

# Make CLI executable
chmod +x alphamind

# Run complete demo
./alphamind demo --scenario full

# Start API server
./alphamind validator serve
```

### Option B: Manual setup
```bash
pip install -r subnet/requirements.txt
export AM_OUT_DIR=$(pwd)/subnet/out
export AM_API_TOKEN=dev
uvicorn subnet.validator.api:app --host 127.0.0.1 --port 8000
```

Dashboard: http://127.0.0.1:8000/dashboard

## CLI commands

### Miner operations
```bash
# Emit reports (one-time)
./alphamind miner emit-once --type both

# Run continuous miner
./alphamind miner run --interval 300
```

### Validator operations
```bash
# Aggregate miner reports
./alphamind validator aggregate

# Start API server
./alphamind validator serve --port 8000
```

### Vault simulation
```bash
# Simulate minting
./alphamind vault mint --amount 100.0

# Check vault status
./alphamind vault status
```

### System management
```bash
# Check system health
./alphamind deploy health

# Initialize deployment
./alphamind deploy init --network testnet

# Run demonstrations
./alphamind demo --scenario full
```

## Documentation

### Getting started
- Quick start: [docs/QUICKSTART.md](docs/QUICKSTART.md) — get running in minutes
- Validator setup: [docs/VALIDATOR_SETUP.md](docs/VALIDATOR_SETUP.md)
- Miner setup: [docs/MINER_SETUP.md](docs/MINER_SETUP.md)

### Technical details
- Protocol specification: [docs/PROTOCOL_V1.md](docs/PROTOCOL_V1.md)
- Security guide: [docs/SECURITY_GUIDE.md](docs/SECURITY_GUIDE.md)
- Deployment: [docs/DEPLOYMENT_SECURITY.md](docs/DEPLOYMENT_SECURITY.md)

### Architecture
- System overview: [docs/API.md](docs/API.md)
- Smart contracts: [contracts/README.md](contracts/README.md)

## Project structure

### Project Structure
```
alphamind/
├── alphamind              # Main CLI tool
├── subnet/                # Core subnet implementation
│   ├── miner/            # Miner logic and templates
│   ├── validator/        # Validator aggregation and API
│   ├── tao20/           # Index design and consensus
│   ├── sim/             # Vault simulation
│   └── common/          # Shared utilities
├── contracts/            # Solidity smart contracts
├── templates/            # Quick start templates
├── examples/             # Usage examples
│   ├── miners/          # Miner examples
│   ├── validators/      # Validator examples
│   └── docker/          # Container deployment
└── docs/                 # Documentation
```

### Legacy commands (still supported)
For backward compatibility, you can also use:
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
- `AM_ADMIN_TOKEN` — required for `/admin/*` endpoints
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
- `POST /weightset-commit` — commit current weights to `ValidatorSet` (requires chain env)

Mutations require `Authorization: Bearer <AM_API_TOKEN>`.

## Environment variables (common)
- `AM_OUT_DIR` — IO directory (defaults to `subnet/out`)
- `AM_BTCLI` — path to `btcli` for price/emission reads
- `AM_PRICE_QUORUM`, `AM_PRICE_BAND_PCT`, `AM_PRICE_STALE_SEC`
- `AM_EMISSIONS_QUORUM`, `AM_EMISSIONS_BAND_PCT`, `AM_EMISSIONS_MAD_K`
- `AM_MINT_FEE_BPS`, `AM_REDEEM_FEE_BPS`, `AM_MAX_SLIPPAGE_BPS`
- `AM_API_TOKEN`, `AM_ADMIN_TOKEN`, `AM_CORS_ORIGINS`
- Publish: `AM_CHAIN`, `AM_RPC_URL`, `AM_CHAIN_PRIVKEY`, `AM_REGISTRY_ADDR`, `AM_VALIDATORSET_ADDR`, `AM_PUBLISH_MODE`, `AM_REQUIRE_PUBLISH`

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
Set strong `AM_API_TOKEN` and `AM_ADMIN_TOKEN` in all non-dev deployments. Prefer hotkey signatures for miner reports over HMAC (enable `AM_REQUIRE_SIGNING=1`, `AM_REQUIRE_HOTKEY=1`, `AM_REJECT_HMAC=1`).

## Miners: how to participate
- Emissions report:
  - Daily at snapshot time (e.g., 16:00 UTC), produce a signed `EmissionsReport` with rolling 14‑day averages and your stake.
  - Use hotkey signatures (`signer_ss58`); HMAC is rejected in production.
  - CLI: `python subnet/miner/loop.py --emit-emissions-once` (for demo)
- Price report:
  - Publish every ~60s; include `prices_by_netuid` and (ideally) enriched `prices[]` with pinned `block_time` and pool reserves.
  - CLI: `python subnet/miner/loop.py --emit-prices-once` (for demo)
- NAV report (optional):
  - Publish signed periodic NAV estimates if you run a full mirror of the vault.
- Scoring and slashing:
  - Deviations and latency are logged; repeated offenses may suspend your hotkey. View scores at `/scores` and `/scores/{hotkey}`.

## Validators: how to operate
- Start the API (Python 3.11), set `AM_OUT_DIR`, `AM_API_TOKEN`, `AM_CORS_ORIGINS`.
- Aggregate:
  - Hit `/aggregate` (or auto-generate via `/weights`) to produce `weights.json` and epoch artifacts.
- Publish proofs (optional but recommended):
  - Set chain env (`AM_CHAIN=1`, `AM_RPC_URL`, `AM_CHAIN_PRIVKEY`, `AM_REGISTRY_ADDR`).
  - Call `/weightset-publish` to publish to registry (manifest includes `tx_hash`, `chain_id`, `tx_receipt_status`, `verify_ok`).
  - Optionally, with `AM_VALIDATORSET_ADDR`, call `/weightset-commit` to commit weights to `ValidatorSet`.
- Ops & monitoring:
  - Health: `/readyz` (200 when weights present, vault writable, price quorum/staleness OK, no critical errors)
  - Metrics: `/metrics` (JSON), `/metrics/prom` (Prometheus text). Watch `quorum_pct`, `max_price_staleness_sec`, `publish_*` fields.
  - Circuit breakers: `/admin/pause-token`, `/admin/resume-token` (use `AM_ADMIN_TOKEN`).


## Documentation
- Protocol: `docs/PROTOCOL_V1.md`
- Architecture: `subnet/specs/ARCHITECTURE.md`

## Verify it yourself
1) Download latest weightset JSON:
```bash
curl -s http://127.0.0.1:8000/weightset | jq -c > /tmp/weightset.json
```
2) Hash and compare to published SHA:
```bash
shasum -a 256 /tmp/weightset.json
curl -s http://127.0.0.1:8000/weightset-sha
```
3) Fetch proof object (signature, signer, refs):
```bash
curl -s http://127.0.0.1:8000/weightset-proof | jq
```
