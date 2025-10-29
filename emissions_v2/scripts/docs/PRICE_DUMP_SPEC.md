# Subnet Price Snapshot — Script Spec

File: `scripts/dump_prices_at_block.py`

---

## Purpose
Collect per-subnet price snapshots at (or near) target UTC timestamps. The
script is archive-node friendly (binary-searches the first sample each day,
then estimates subsequent blocks) and can run for a single day or across a
date range, emitting one JSON file per day.

---

## CLI Inputs
| Flag | Default | Description |
|------|---------|-------------|
| `--network` | `finney` | Bittensor network or Substrate endpoint (e.g. `ws://localhost:9944`). Passed to `bt.Subtensor`. |
| `--date` | _required (if no range)_ | Single day `YYYY-MM-DD`. |
| `--date-range` | _required (if no single day)_ | Inclusive `YYYY-MM-DD:YYYY-MM-DD`. Creates/overwrites `scripts/outputs/prices_<day>.json` for every day. |
| `--time` | `00:00+00:00` | First snapshot time with offset. Additional samples are evenly spaced across the next 24 hours. |
| `--samples-per-day` | `1` | Number of snapshots per calendar day (e.g. `24` → hourly, `2` → midnight + 12h later). |
| `--sample-workers` | `4` | Parallel sample fetchers per day (set to `1` to disable concurrency). |
| `--midnight-blocks` | `midnight_blocks.json` | Precomputed midnight block cache (see `precompute_midnight_blocks.py`). |
| `--output` | _stdout_ | Single-day mode only. When provided, writes JSON to the given path (parents auto-created). |
| `--output-dir` | `outputs` (range) | Directory for auto-named JSON files. Date-range mode defaults here; single-day mode writes `prices_<day>.json` when set. |

---

## Midnight Block Cache

Run `scripts/precompute_midnight_blocks.py` to build `midnight_blocks.json`. The
file stores the block numbers closest to `00:00:00+00:00` UTC for every day
since 2025-02-08. `dump_prices_at_block.py` reads this cache (via
`--midnight-blocks`) to skip the initial binary search: when the requested time
is midnight the script simply reuses the stored block, falling back to live
search only if the cache entry is missing. New or improved midnight samples are
written back to the same JSON file at the end of the run, keeping the cache fresh.

---

## Output Structure (per day)
```json
{
  "date": "2025-10-05",
  "network": "ws://localhost:9944",
  "samples_per_day": 2,
  "samples": [
    {
      "requested_time": "2025-10-05T00:00:00+00:00",
      "closest_block": 6588760,
      "block_timestamp_utc": "2025-10-05T00:00:00.004000+00:00",
      "prices": [
        {
          "netuid": 12,
          "price_tao_per_alpha": 0.006521844
        },
        { "netuid": 13, "price_tao_per_alpha": 0.007975205 },
        …
      ]
    },
    {
      "requested_time": "2025-10-05T12:00:00+00:00",
      "closest_block": 6593785,
      "block_timestamp_utc": null,
      "prices": [ … ]
    }
  ]
}
```
`price_tao_per_alpha` may be `null` when the node’s RPC lacks swap/reserve
modules. `block_timestamp_utc` is omitted (`null`) when the node cannot return
the timestamp for the estimated block. When `--samples-per-day` is `1`, the
top-level object also repeats the first sample’s fields
(`requested_time`, `closest_block`, `block_timestamp_utc`, `prices`)
for backwards compatibility.

---

## Workflow Summary

1. **Block selection**
   - Build the day’s sampling schedule: start at `--time` and add evenly spaced
     offsets so that `--samples-per-day` snapshots cover the next 24 hours.
   - Convert each scheduled time (`%Y-%m-%d %H:%M%z`) to UTC.
   - Sample 1 performs the original binary search to find the nearest block with
     a Timestamp extrinsic.
   - Every later sample estimates its block by adding `(Δ seconds ÷ 12)` to the
     first sample’s block and reads that block directly—no backtracking is
     attempted. Missing timestamps are logged but the block is kept.

2. **Price retrieval**
   - Primary path: `sub.get_subnet_prices(block=…)`.
   - Fallback path: `sub.all_subnets(block=…)` (reserve-based price snapshot).
   - `--sample-workers` controls a thread pool that resolves follow-up samples
     in parallel so multiple scheduled times can be fetched concurrently. Each
     worker maintains its own Subtensor connection to avoid RPC contention.
   - Both paths may fail on custom RPC nodes → script logs warnings to stderr
     but still emits output (with `null` prices if necessary).

3. **Date-range loop & output**
   - Creates `scripts/<output-dir>/` (default `outputs/`) and writes
     `prices_<YYYY-MM-DD>.json` for each day.
   - Each JSON contains a `samples` array with one entry per scheduled snapshot;
     when only one sample is requested the top-level object mirrors its fields.

4. **Logging**
   - Human-readable `[info]/[warn]` messages go to stderr (safe to redirect).
   - JSON is printed to stdout only in single-day/no-output mode.

---

## Failure / Edge Handling
| Scenario | Behavior |
|----------|----------|
| Timestamp missing during binary search | Skips the block and continues searching. |
| Timestamp missing for an estimated block | Logs a warning and records `null` in `block_timestamp_utc`. |
| `get_all_subnets_info` missing fields | Warns and proceeds with empty subnet info list (price fallback may still populate). |
| Price RPC modules absent | Logs `[info]/[warn]`, emits `null` price values. |
| Estimated block far from true time | Script does not adjust; consider lowering `--samples-per-day` if drift becomes an issue. |
| Archive node pruned | Binary search or timestamp lookup may fail; warnings explain the missing data. |
| Multiple runs | Safe to re-run; files are overwritten per day. |

---

## Usage Notes
- Prefer archive nodes (e.g. `ws://localhost:9944`) for historical data; non-
  archive nodes usually fail beyond ~35 days.
- Adjust `--sample-workers` to match your node’s RPC limits. Higher values pull
  samples faster but open more concurrent connections.
- Refresh the midnight cache periodically with `precompute_midnight_blocks.py`
  so new dates are available without extra binary searches. The main dump script
  will append any newly fetched midnight entries automatically.
- Estimated blocks assume ~12 seconds per block. When capturing many samples,
  verify the timestamps periodically and rerun with a smaller interval if drift
  becomes noticeable.
- To resume after a timeout: inspect `scripts/outputs` for the last date and
  restart with `--date-range <next-date>:<end-date>`.
- To capture raw output without logs, redirect stderr:
  `python … 2>run.log`.

---
