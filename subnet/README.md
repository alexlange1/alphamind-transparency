TAO20 Subnet Prototype

Overview
- Off-chain prototype components for TAO20:
  - Miner: emits signed `EmissionsReport` and `PriceReport`
  - Validator: aggregates reports → weights, prices, NAV (sim)
  - Sim: vault, scheduler, epoch helpers

Layout
- `tao20/price_feed.py`: read prices via `btcli subnets list`
- `tao20/consensus.py`: stake-weighted medians
- `tao20/index_design.py`: emissions → top-20 → normalized weights
- `tao20/models.py`: report/weightset schemas
- `validator/service.py`: aggregation, TWAP/quorum, eligibility, epoch artifacts
- `validator/api.py`: FastAPI endpoints and dashboard
- `miner/loop.py`: one-shot emissions/prices, hotkey/HMAC signing
- `sim/vault.py`: mint/redeem and fees; extended ops with slippage guards
- `sim/scheduler.py`: daily aggregator + epoch snapshots
- `emissions/snapshot.py`: helpers to snapshot/roll emissions
- `common/*`: signing and settings

Quick start
```bash
pip install -r requirements.txt
export AM_OUT_DIR=$(pwd)/out
python -m validator.api  # FastAPI at 127.0.0.1:8000
```

Miner one-shots
```bash
# Emissions
python miner/loop.py --emit-emissions-once
# Prices
python miner/loop.py --emit-prices-once
```

CLI demos
```bash
python cli.py prices --btcli /path/to/btcli
python cli.py demo-weights --n 20
python cli.py aggregate-demo --n 5
```

Docs
- Protocol: `../docs/PROTOCOL_V1.md`
- Architecture: `specs/ARCHITECTURE.md`

Publishing (smoke)
```bash
make -C . aggregate
curl -s http://127.0.0.1:8000/weightset-publish | jq
```


