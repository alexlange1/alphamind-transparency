# TAO20 Protocol v1 Specification

## 🎯 **Subnet Overview**

The Alphamind TAO20 subnet creates a **decentralized ETF** that tracks the top 20 Bittensor subnets by 14-day average TAO emissions. The protocol operates through two distinct participant roles:

### **🛡️ Validators (Subnet Operators)**
**Responsibilities:**
- Aggregate price and emissions data from miners using stake-weighted consensus
- Calculate top-20 subnet weights based on 14-day rolling emissions
- Simulate TAO20 vault operations (mint/redeem with fees)
- Score miner performance and apply deviation penalties
- Serve public API endpoints for weights, prices, and NAV
- Publish cryptographic proofs of weightset calculations on-chain

**Incentives:**
- Earn fees from TAO20 minting/redemption operations (0.2% transaction fee)
- Receive subnet operation rewards for maintaining infrastructure
- Share in management fee revenue (1% annual fee on AUM)

### **⛏️ Miners (Data Oracles)**
**Responsibilities:**
- Monitor Bittensor network for real-time subnet emission data
- Fetch current prices from AMM pools and exchanges
- Calculate Net Asset Value (NAV) for the TAO20 index
- Submit signed reports with HMAC or hotkey cryptographic verification
- Maintain data accuracy and timeliness to avoid penalties

**Incentives:**
- Earn rewards proportional to data accuracy and stake weight
- Receive bonuses for early/timely report submission
- Avoid penalties through consistent, accurate data provision

## 🔄 **Protocol Flow**

1. **Miners** collect emissions and price data from Bittensor network
2. **Validators** aggregate reports using stake-weighted median consensus
3. **Index calculation** determines top 20 subnets by 14-day emissions
4. **Vault simulation** enables TAO20 minting/redemption at current NAV
5. **Scoring system** rewards accurate miners and penalizes outliers
6. **On-chain proofs** provide transparency and verifiability

## ⚙️ **Protocol Parameters**

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Index Size** | Top 20 | Number of subnets in index |
| **Rebalance Period** | 14 days | Emission averaging window |
| **Transaction Fee** | 0.2% (20 bps) | Fee on mint/redeem operations |
| **Management Fee** | 1.0% annual | Annual fee on assets under management |
| **Emissions Quorum** | 33% | Minimum stake for emissions consensus |
| **Price Quorum** | 33% | Minimum stake for price consensus |
| **Staleness Limit** | 5 minutes | Maximum age for price data |

---

## 📊 **Technical Operations**

Guards & hardening
- Require hotkey signatures for miner reports: set `AM_REQUIRE_SIGNING=1` and `AM_REQUIRE_HOTKEY=1` (reject HMAC with `AM_REJECT_HMAC=1`).
- Mint via TAO enforces constituent pool reserves when `AM_REQUIRE_RESERVES=1`; if missing and `AM_VALIDATOR_SELF_REFRESH=1`, validator self-refreshes once. Persisting failures return 409 with `missing_reserve_uids`.
- Rate limiting on POST with `AM_RATE_LIMIT_PER_MIN` (counter exposed via metrics).

## EmissionsReport v1 (miner → validator)
Canonical JSON (keys shown as JSON types):
```
{
  "schema_version": "1.0.0",
  "snapshot_ts": "ISO8601Z",
  "epoch_day": <int>,
  "emissions_by_netuid": {"<uid>": <float>, ...},
  // Compatibility: alternatively `emissions: [{"uid": <int>, "emissions_tao": <float>}, ...]`
  "miner_id": "<string>",
  "stake_tao": <float>,
  "signature": "<hex>",
  "signer_ss58": "<ss58>",
  // Optional metadata (non-breaking):
  "miner_hotkey": "<ss58>",
  "sig_scheme": "HMAC|HOTKEY"
}
```
Notes:
- Validators accept either `emissions_by_netuid` or the legacy `emissions[]` array. JSON maps use string keys for `<uid>`.
- `signer_ss58` is preferred for signature verification. `miner_id` is an operator label; when using hotkey signing they may be identical.

## PriceReport v1 (miner → validator)
Canonical JSON:
```
{
  "schema_version": "1.0.0",
  "ts": "ISO8601Z",
  // Simple form used in consensus
  "prices_by_netuid": {"<uid>": <float>, ...},
  // Optional enriched items for pool-aware logic and pinning
  "prices": [
    {
      "uid": <int>,
      "token": "SN<uid>",
      "price_in_tao": <float>,
      "pool_reserve_token": "<str|null>",
      "pool_reserve_tao": "<str|null>",
      "block": <int|null>,
      "block_time": "ISO8601Z|null",
      "pin_source": "btcli"
    }
  ],
  "miner_id": "<string>",
  "signature": "<hex>",
  "signer_ss58": "<ss58>"
}
```
Notes:
- JSON maps use string keys for `<uid>`.
- `block_time` is preferred for staleness/TWAP windowing when present.

## NavReport v1 (miner → validator)
```
{
  "ts": "ISO8601Z",
  "nav_per_token_tao": <float>,
  "total_supply": <float>,
  "miner_id": "<string>",
  "signature": "<hex>",
  "signer_ss58": "<ss58>"
}
```

## WeightSet v1 (validator → artifacts)
```
{
  "schema_version": "1.0.0",
  "epoch_id": <int>,
  "as_of_ts": "ISO8601Z",
  "weights": {"<uid>": <float>, ...}, // JSON keys are strings
  "epoch_index": <int>,
  "cutover_ts": "ISO8601Z",
  "method": "emissions_weighted_14d",
  "eligibility_min_days": 90,
  "constituents": [{"uid": <int>, "weight_bps": <int>, "emissions_14d": <float>}...]
}
```

### Security Architecture

**Multi-Layer Security Framework:**

**Smart Contract Security:**
- Timelock governance with 24-hour delay for critical changes
- Emergency circuit breaker for immediate protocol halting  
- Reentrancy protection on all mint/redeem functions
- Overflow protection and bounds checking on all parameters
- Maximum fee limits (1% transaction, 5% management)

**Oracle Security:**
- Price staleness checks (5-minute maximum age)
- TWAP integration with 30-minute windows
- Spot vs TWAP deviation limits (20% maximum)
- Quorum requirements (33% minimum stake coverage)
- Progressive slashing for price manipulation

**Consensus Security:**
- Stake-weighted median consensus resistant to outliers
- Outlier detection using Modified Z-Score (5σ threshold)
- Progressive penalty system:
  - Soft violations (5-10%): 5% score reduction
  - Hard violations (>10%): 20% score reduction + strike
  - Suspension after 3 strikes
- Continuous eligibility monitoring (90-day emission history)

**API Security:**
- Rate limiting: 10 mint ops per 5min, 100 general ops per min
- Comprehensive input validation and sanitization
- Bearer token authentication with admin privileges
- Emergency response procedures

### Hashing and proofs
- Canonical object for hashing is a reduced form with sorted keys: `{epoch_id, as_of_ts, weights}`.
- SHA-256 of the canonical JSON is written alongside as `weightset_epoch_<id>.sha256`.

### Signatures
- Miners MUST sign reports with their hotkey and set `signer_ss58` in production
- HMAC is deprecated and rejected when `AM_REJECT_HMAC=1`
- All price and emission reports require cryptographic verification

### Publish & proofs
- Validator produces deterministic WeightSet and SHA-256 (`weightset_epoch_<id>.sha256`).
- On-chain publish (optional): registry contract stores `{epoch, sha256, cid, signer}` and emits `Published` event. Publisher records `tx_hash` (and optional `validator_tx_hash`) in manifest and sets `verify_ok` when on-chain hash matches. `GET /weightset-proof` returns latest manifest summary.
- Metrics: `/metrics` JSON and `/metrics/prom` Prometheus format expose quorum, staleness, publish status, counters.


