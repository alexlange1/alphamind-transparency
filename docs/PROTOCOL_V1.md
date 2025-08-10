# TAO20 Protocol v1 Schemas

Operations notes
- /readyz returns 200 when: weights present, vault writable, price quorum satisfied, staleness under AM_PRICE_STALE_SEC, and no critical errors. 503 otherwise with details.
- Dashboard lights: Prices quorum (green when quorum OK), Oldest price age (sec), Paused token list, Epoch countdown, links to latest weightset JSON and .sha256.
- Admin: POST /admin/pause-token and /admin/resume-token require Bearer auth, used to set circuit breaker per netuid. Paused tokens block mint/redeem touching them.

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

### Hashing and proofs
- Canonical object for hashing is a reduced form with sorted keys: `{epoch_id, as_of_ts, weights}`.
- SHA-256 of the canonical JSON is written alongside as `weightset_epoch_<id>.sha256`.

### Signatures
- Miners SHOULD sign reports with their hotkey and set `signer_ss58`; validators verify when present.
- HMAC is accepted only for legacy/demo; production SHOULD require hotkey signatures.


