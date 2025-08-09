TAO20 Subnet Prototype

Overview
- Minimal scaffolding to start implementing the $TAO20 subnet logic off-chain:
  - Price feed from btcli AMM table
  - Stake-weighted median consensus util
  - Emission-based index weighting (top-20 by 14d avg)
  - Simple CLI for demos

Layout
- `tao20/price_feed.py`: reads prices from `btcli subnets list --network finney`
- `tao20/consensus.py`: stake-weighted median and aggregation helpers
- `tao20/index_design.py`: emissions → top-20 selection → normalized weights
- `cli.py`: small CLI to run sample ops

Quick start
```bash
cd /Users/alexanderlange/alphamind/subnet
python3 cli.py prices --btcli /Users/alexanderlange/.venvs/alphamind/bin/btcli
python3 cli.py demo-weights --n 20
```

Next steps
- Replace demo emissions with real snapshots produced by miners
- Add validator loop to aggregate miner reports and publish index weights
- Add slashing and scoring integration (foundation in `consensus.py`)


