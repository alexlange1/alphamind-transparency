# Subnet Price & Validator Snapshot — Script Spec

File: `scripts/dump_prices_at_block.py`

---

## Purpose
Collect per-subnet price snapshots at (or near) a target UTC timestamp and
optionally enrich each subnet with validator identity metadata. The script is
archive-node friendly (binary-searches blocks, backtracks when a node pruned
state) and can run for a single day or across a date range, emitting one JSON
file per day.

---

## CLI Inputs
| Flag | Default | Description |
|------|---------|-------------|
| `--network` | `finney` | Bittensor network or Substrate endpoint (e.g. `ws://localhost:9944`). Passed to `bt.Subtensor`. |
| `--date` | _required (if no range)_ | Single day `YYYY-MM-DD`. |
| `--date-range` | _required (if no single day)_ | Inclusive `YYYY-MM-DD:YYYY-MM-DD`. Creates/overwrites `scripts/outputs/prices_<day>.json` for every day. |
| `--time` | `00:00+00:00` | First snapshot time with offset. Additional samples are evenly spaced across the next 24 hours. |
| `--samples-per-day` | `1` | Number of snapshots per calendar day (e.g. `24` → hourly, `2` → midnight + 12h later). |
| `--output` | _stdout_ | Single-day mode only. When provided, writes JSON to the given path (parents auto-created). |
| `--output-dir` | `outputs` (range) | Directory for auto-named JSON files. Date-range mode defaults here; single-day mode writes `prices_<day>.json` when set. |
| `--validator-coldkey` | – | Extra coldkeys to track. Multiple flags allowed. |
| `--no-default-validator-coldkeys` | `False` | Skip the embedded trio of coldkeys (otherwise they’re always included). |
| `--validator-netuid` | all subnets | Restrict validator lookups to the listed netuids. Without this flag every subnet is checked. |
| `--validator-max-backtrack` | `0` | Blocks to walk backwards when a coldkey is missing (use `-1` for unlimited). |
| `--no-validator-info` | `False` | Disable validator enrichment entirely. |
| `--include-all-validators` | `False` | When set, attach the full validator list (`entries`) per subnet (expensive). Otherwise only the matched coldkeys are stored. |

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
          "price_tao_per_alpha": 0.006521844,
          "validators": {
            "block": 6588760,
            "matched_coldkeys": [
              { "uid": 12, "hotkey": "<…>", "coldkey": "5GZSA…" },
              { "uid": 225, "hotkey": "<…>", "coldkey": "5HBtp…" }
            ]
          }
        },
        { "netuid": 13, "price_tao_per_alpha": 0.007975205, "validators": { … } },
        …
      ]
    },
    {
      "requested_time": "2025-10-05T12:00:00+00:00",
      "closest_block": 6593785,
      "block_timestamp_utc": "2025-10-05T12:00:00.001000+00:00",
      "prices": [ … ]
    }
  ]
}
```
`price_tao_per_alpha` may be `null` when the node’s RPC lacks swap/reserve
modules. If `--include-all-validators` is used, each `validators` object gains
an `entries` array containing every validator (uid/hotkey/coldkey) seen on that
subnet at the sampled block. When `--samples-per-day` is `1`, the top-level
object also repeats the first sample’s fields (`requested_time`, `closest_block`,
`block_timestamp_utc`, `prices`) for backwards compatibility.

---

## Workflow Summary

1. **Block selection**
   - Build the day’s sampling schedule: start at `--time` and add evenly spaced
     offsets so that `--samples-per-day` snapshots cover the next 24 hours.
   - Convert each scheduled time (`%Y-%m-%d %H:%M%z`) to UTC.
   - For every sample (processed chronologically), binary search between the
     previous block (if any) and roughly two days ahead to locate the closest
     block with a Timestamp extrinsic.
   - If bounds are invalid or timestamps unavailable, fall back to a full-range
     search (1 → latest).

2. **Price retrieval**
   - Primary path: `sub.get_subnet_prices(block=…)`.
   - Fallback path: `sub.all_subnets(block=…)` (reserve-based price snapshot).
   - Both paths may fail on custom RPC nodes → script logs warnings to stderr
     but still emits output (with `null` prices if necessary).

3. **Validator enrichment**
   - Default coldkeys:
     ```
     5GZSA... (ALPHA Labs)
     5HBtp... (ALPHA Labs)
     5Fuzg... (ALPHA Labs)
     ```
   - This list is merged with any `--validator-coldkey` flags.
   - Per subnet:
     1. Fetch the validator set via `sub.neurons_lite(netuid, block)`.
     2. Try to satisfy matches from the cache (UID → coldkey). Cache key: `(netuid, coldkey)`.
     3. Missing entries trigger `find_validators_until_coldkeys` which walks
        backwards block-by-block (respecting `--validator-max-backtrack`) until
        the coldkeys appear, or raises (logged as warning, match list left empty).
     4. Successful matches refresh the cache, so subsequent days reuse the same
        UID without rescanning unless the coldkey disappears.
   - `validators` object always includes `block` and `matched_coldkeys`; only
     `--include-all-validators` adds the `entries` list.

4. **Date-range loop**
   - Creates `scripts/<output-dir>/` (default `outputs/`) and writes
     `prices_<YYYY-MM-DD>.json` for each day.
   - Each JSON contains a `samples` array with one entry per scheduled snapshot.
   - Reuses the previous block (across samples and days) as the lower bound to
     accelerate block searches.
   - Shares a single validator cache across the whole run, minimizing costly
     backtracking.

5. **Logging**
   - Human-readable `[info]/[warn]` messages go to stderr (safe to redirect).
   - JSON is printed to stdout only in single-day/no-output mode.

---

## Failure / Edge Handling
| Scenario | Behavior |
|----------|----------|
| Timestamp missing for a block | Binary search skips that block and continues. |
| `get_all_subnets_info` missing fields | Warns and proceeds with empty subnet info list (price fallback may still populate). |
| Price RPC modules absent | Logs `[info]/[warn]`, emits `null` price values. |
| Validator coldkey not found within backtrack window | Logs warning, stores empty `matched_coldkeys` for that subnet/day. |
| Archive node pruned | `find_validators_until_coldkeys` keeps stepping backwards until data is available or the backtrack limit is hit. |
| Multiple runs | Safe to re-run; files are overwritten per day. |

---

## Usage Notes
- Prefer archive nodes (e.g. `ws://localhost:9944`) for historical data; non-
  archive nodes usually fail beyond ~35 days.
- For long ranges, run in chunks (the script is CPU-heavy when validator
  backtracking is required).
- To resume after a timeout: inspect `scripts/outputs` for the last date and
  restart with `--date-range <next-date>:<end-date>`.
- To capture raw output without logs, redirect stderr:
  `python … 2>run.log`.

---
