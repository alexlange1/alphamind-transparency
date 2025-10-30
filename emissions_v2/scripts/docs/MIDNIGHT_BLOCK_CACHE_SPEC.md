# Midnight Block Cache — Script Spec

File: `scripts/precompute_midnight_blocks.py`

---

## Purpose
Generate `midnight_blocks.json`, a reusable map of block numbers that occur
closest to `00:00:00+00:00` UTC for each calendar day. Other tools (notably
`dump_prices_at_block.py`) load this file to avoid repeating an expensive
binary search every time they need a midnight sample.

---

## CLI Inputs
| Flag | Default | Description |
|------|---------|-------------|
| `--network` | `finney` | Bittensor network or endpoint passed to `bt.Subtensor`. |
| `--start-date` | `2025-02-08` | First day in `YYYY-MM-DD` (inclusive). |
| `--end-date` | _today (UTC)_ | Last day in `YYYY-MM-DD` (inclusive). |
| `--output` | `midnight_blocks.json` | Destination JSON path (relative paths resolve next to the script). |
| `--overwrite` | `False` | When set, recompute all dates even if they’re already cached. Otherwise the script skips existing entries. |

---

## Output Structure
```json
{
  "network": "finney",
  "start_date": "2025-02-08",
  "end_date": "2025-02-10",
  "generated_at": "2025-02-10T09:15:03.214589+00:00",
  "blocks": {
    "2025-02-08": {
      "block": 5983120,
      "block_timestamp_utc": "2025-02-08T00:00:00.004000+00:00"
    },
    "2025-02-09": {
      "block": 5990320,
      "block_timestamp_utc": "2025-02-09T00:00:00.011000+00:00"
    }
  }
}
```
`block_timestamp_utc` is omitted (`null`) when the node cannot return the block’s
timestamp. Downstream scripts still use the `block` value in that case.

---

## Workflow Summary

1. **Load existing cache (if any)**
   - Reads the JSON at `--output`, validating that `blocks` is a dictionary and
     normalising entries into `{"block": <int>, "block_timestamp_utc": <str|null>}`.
   - Warns if the cached network doesn’t match `--network` but continues using
     the stored data.

2. **Iterate over requested dates**
   - Skips dates already present unless `--overwrite` is set.
   - For the first missing date (or when the cache is empty) performs the full
     binary search via `find_block_at_time`.
   - For subsequent dates:
     1. Estimate the next midnight block as `prev_block + 7200`.
     2. Fetch the timestamp for that estimate; compute the time delta to midnight.
     3. Adjust by `(delta_seconds / 12)` blocks and retry.
     4. Accept as soon as the block is within ±11 seconds of midnight.
     5. If the heuristic cannot converge in six attempts (or timestamps are
        unavailable), fall back to a full binary search.

3. **Persist the map**
   - Updates metadata (`network`, `start_date`, `end_date`, `generated_at`), writes
     the JSON back to disk with pretty formatting, and logs how many dates were
     recomputed versus skipped.

---

## Usage Notes
- Run the script periodically to extend the cache; `dump_prices_at_block.py`
  defaults to `midnight_blocks.json` but accepts `--midnight-blocks` if you keep
  the file elsewhere.
- The shortcut assumes ~12 seconds per block. Large drifts are rare on Finney
  but, if you notice warnings about repeated fallbacks, refreshing the cache
  with `--overwrite` ensures the stored data stays accurate.
- The script depends on `bittensor`; ensure your environment can import it before running.
