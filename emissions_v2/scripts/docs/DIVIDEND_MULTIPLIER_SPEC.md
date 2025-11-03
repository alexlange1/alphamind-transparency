# Dividend Multiplier Cache Spec

Script: `scripts/cache_dividend_ratios.py`

---

## Purpose
Capture per-block staking rewards for a small set of known validators. For each
UTC day (or range of days) the script walks the block interval starting at
midnight, samples every `N`th block, and records each tracked validator’s stake,
dividends, and derived payout ratio. The resulting JSON lets downstream tools
chain the per-block multipliers to estimate daily or monthly rewards.

---

## CLI Flags
| Flag | Default | Description |
|------|---------|-------------|
| `--network` | `finney` | Bittensor network / endpoint provided to `bt.Subtensor`. |
| `--date` | — | Single UTC day (`YYYY-MM-DD`). |
| `--date-range` | — | Inclusive range (`YYYY-MM-DD:YYYY-MM-DD`). |
| `--midnight-blocks` | `midnight_blocks.json` | Midnight block cache (same file used by other scripts). |
| `--validator-cache` | `validator_cache` | Directory containing `validators_<day>.json` files produced by `cache_validators.py`. |
| `--coldkey` | built-in list | Repeat for additional tracked coldkeys. When omitted the default 5 coldkeys are used. |
| `--block-step` | `1` | Sample every `N`th block (`1` means every block). |
| `--block-offset` | `0` | Skip the first `offset` blocks after midnight before sampling. |
| `--workers` | `4` | Concurrent block fetchers (each maintains its own Subtensor client). |
| `--output` | — | Single-day mode only: write JSON here (parents auto-created). |
| `--output-dir` | `dividend_cache` | Directory for `dividends_<day>.json` files in range mode. |
| `--dry-run` | off | Parse and log without writing output. |

---

## Workflow
1. Resolve the midnight block for each requested day via the cache or binary
   search.
2. Load that day’s validator cache (`validators_<day>.json`) to obtain the
   expected `(netuid, uid, hotkey)` placement for every tracked coldkey.
   Validators missing from the cache are marked as `not_cached` and skipped.
3. Build the block schedule using `--block-offset` and `--block-step`.
4. For each sampled block:
   - Fetch `neurons_lite(netuid, block)` once per netuid present in the cache.
   - Confirm every cached validator entry (coldkey/uid/hotkey) still matches the
     live neuron; mismatches are tagged accordingly.
   - Capture validator-level `stake`, `dividends`, and compute
     `payout_ratio = dividends / stake` (when stake > 0). The ratio is also
     scaled to integer nanos (`payout_ratio_nanos = round(payout_ratio * 1e9)`)
     for precise downstream multiplication.
5. Emit one JSON per day containing metadata, tracked coldkeys, and an array of
   block samples (written immediately after each day completes).

---

## Output Layout
```json
{
  "date": "2025-02-27",
  "network": "ws://localhost:9944",
  "config": {
    "block_step": 12,
    "block_offset": 0,
    "workers": 4
  },
  "tracked_coldkeys": [ "5HB…", "5GZ…", "5E9…", "5Fuz…", "5FH…" ],
  "samples": [
    {
      "block": 5014632,
      "block_timestamp_utc": "2025-02-27T00:00:00+00:00",
      "netuids": {
        "12": [
          {
            "coldkey": "5HB…",
            "uid": 225,
            "status": "ok",
            "observed_coldkey": "5HB…",
            "observed_hotkey": "5CC…",
            "stake": 12345.6789,
            "dividends": 12.3456,
            "payout_ratio": 0.000999,
            "payout_ratio_nanos": 999000
          },
          {
            "coldkey": "5GZ…",
            "uid": 5,
            "status": "ok",
            "observed_coldkey": "5GZ…",
            "observed_hotkey": "5F4…",
            "stake": 54321.1234,
            "dividends": 21.0123,
            "payout_ratio": 0.000387,
            "payout_ratio_nanos": 387000
          }
        ],
        "17": [
          {
            "coldkey": "5Fuz…",
            "uid": 48,
            "status": "coldkey_mismatch",
            "observed_coldkey": "5XXX…",
            "observed_hotkey": "5YYY…"
          }
        ]
      },
      "uncached_coldkeys": [ "5FH…" ]
    }
  ],
  "generated_at": "2025-02-27T23:59:59.123456+00:00"
}
```

- `status` values:
  - `ok` — cached uid still maps to the expected coldkey.
  - `not_found` — uid not returned in `neurons_lite`.
  - `missing_metrics` — `neurons_lite` call returned no data for the subnet.
  - `coldkey_mismatch` — uid returned but with a different coldkey.
  - `error` — RPC failure (see `error` field for details).
- `uncached_coldkeys` lists tracked coldkeys absent from the validator cache.
- Numeric fields are omitted when the status is not `ok`.

---

## Notes
- The script never performs a full subnet scan; it relies entirely on the
  validator cache. Ensure `cache_validators.py` has been run for the date range.
- Use `--block-step` to control resolution (e.g., `12` ≈ one sample per ~2 min).
- Large block counts can be heavy; raise `--block-step` or lower `--workers` if
  the node struggles.
- Downstream tools can reconstruct per-block multipliers using
  `1 + payout_ratio` or by multiplying `payout_ratio_nanos / 1e9`.
