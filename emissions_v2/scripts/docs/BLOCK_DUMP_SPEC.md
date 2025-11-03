# Per-Block Price Dump Spec

Script: `scripts/dump_prices_full_day.py`

---

## Purpose
Collect subnet price snapshots *for every block* (or a configurable stride) in a
single UTC day or an inclusive range of days. Each day is written to its own
`prices_<YYYY-MM-DD>.json` file that matches the structure consumed by
`translate_price_dumps.py`.

---

## CLI Flags
| Flag | Default | Description |
|------|---------|-------------|
| `--network` | `finney` | Bittensor network/endpoint string passed to `bt.Subtensor`. |
| `--date` | — | Single UTC day (`YYYY-MM-DD`). Emits one JSON (stdout or `--output`). |
| `--date-range` | — | Inclusive range (`YYYY-MM-DD:YYYY-MM-DD`). Writes one file per day into `--output-dir` (or `outputs/`). |
| `--midnight-blocks` | `midnight_blocks.json` | Cache of midnight blocks. Falls back to live binary search when missing. |
| `--workers` | `4` | Size of the thread pool. Every worker keeps its own Subtensor connection. |
| `--block-step` | `1` | Sample every _N_ blocks (stride). Set to `12` for roughly two-minute spacing, etc. |
| `--block-offset` | `0` | Skip `N` blocks after the day’s midnight anchor before sampling begins. |
| `--output` | — | Single-day mode only: write JSON to this path (parents auto-created). |
| `--output-dir` | `outputs` | Range mode: directory where `prices_<day>.json` files are placed. |

---

## Workflow
1. **Day bounds**
   - Load midnight hints from `--midnight-blocks`.
   - When missing, binary-search for the block whose timestamp is at/after UTC midnight.
   - Repeat for the day after the final request to establish an end bound.
2. **Block queue**
   - For each day, build the range `[midnight+offset, next_midnight)` using the chosen stride (`--block-step`).
   - Submit each block to a `ThreadPoolExecutor`. Workers reuse connections via thread-local `bt.Subtensor` clients.
3. **Snapshot capture**
   - For each block fetch:
     - Timestamp via `get_block_timestamp`.
     - Prices via `get_subnet_prices` and reserve fallback.
     - Filter `netuid 0` and compute emissions statistics.
   - Samples are stored in chronological order with `sample_index`, `closest_block`, `block_timestamp_utc`, `prices`, `emissions`, and `statistics`.
4. **Daily output**
   - Build metadata from the first sample (timestamp, block, requested time, stride count).
   - Attach per-sample entries and, when multiple samples exist, a `summary` block (min/max/avg totals).
   - Write `prices_<YYYY-MM-DD>.json` as soon as the day completes; for single-day runs, print or write to `--output`.

---

## Output Layout (per day)
```json
{
  "metadata": {
    "collection_method": "btsdk scripts v2 / per-block",
    "date": "20250227",
    "network": "ws://localhost:9944",
    "timestamp": "2025-02-27T00:00:00+00:00",
    "closest_block": 5014632,
    "requested_time": "2025-02-27T00:00:00+00:00",
    "samples_per_day": 7200,
    "primary_sample_index": 0
  },
  "statistics": {
    "active_subnets": 70,
    "avg_emission_rate": 0.0189,
    "max_emission_rate": 0.1673,
    "min_emission_rate": 0.0023,
    "total_emission_rate": 1.3252
  },
  "samples": [
    {
      "sample_index": 0,
      "closest_block": 5014632,
      "block_timestamp_utc": "2025-02-27T00:00:00+00:00",
      "requested_time": "2025-02-27T00:00:00+00:00",
      "prices": [ … ],
      "emissions": { "1": 0.032001981, "2": 0.004196618, … },
      "statistics": { … }
    },
    {
      "sample_index": 1,
      "closest_block": 5014633,
      "block_timestamp_utc": null,
      "requested_time": null,
      "prices": [ … ],
      "emissions": { … },
      "statistics": { … }
    }
  ],
  "summary": {
    "observations": 7200,
    "active_subnets_min": 68,
    "active_subnets_max": 70,
    "total_emission_rate_min": 1.24,
    "total_emission_rate_max": 1.33,
    "total_emission_rate_avg": 1.29
  },
  "generated_at": "2025-02-27T23:59:59.123456+00:00"
}
```

- `requested_time` mirrors the timestamp when available; otherwise `null`.
- `prices` includes raw RPC values (including `netuid 0` as a reference point).
- `emissions` omits `netuid 0` and is sorted by netuid string key.
- `summary` is omitted when fewer than two samples survive the stride.

---

## Operational Notes
- Memory is bounded by a single day’s worth of samples; each day writes before proceeding.
- Increase `--block-step` or lower `--workers` if you need to reduce memory/CPU.
- Choose `--block-offset` when you want to skip an initial warm-up window after midnight.
- The produced JSON is ready for `translate_price_dumps.py` → `emissions_v2_<YYYYMMDD>.json`.
