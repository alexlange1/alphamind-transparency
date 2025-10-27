# Salvaging Historic TAO Price Snapshots

This spec documents how to regenerate the cleaned `emissions_v2_*.json` files from the raw daily snapshots under `jsons/`.

## Requirements
- Python 3.8+ on PATH (script uses only the standard library).
- Raw snapshot files located in `jsons/` relative to the repo root.

## Script
- Entry point: `salvage_jsons.py` (repository root).
- Outputs into `jsons_salvaged/` by default; destination files are named `emissions_v2_<YYYYMMDD>.json`.
- Use `python3 salvage_jsons.py --help` for full CLI options.

## Processing Rules
1. **Input parsing**
   - Reads each `.json` file and strips console preamble to reach the embedded JSON object.
   - Skips the file if the JSON cannot be decoded or the top-level value is not an object.
2. **Price & validator extraction**
   - Requires a `prices` array of objects with integer `netuid` and numeric `price_tao_per_alpha`.
   - Ignores non-dict entries, non-integer netuids, and non-numeric prices.
   - Drops **netuid 0** entirely; only non-zero netuids are retained.
   - Skips the file if **no numeric prices** are found, or if only netuid 0 had numeric data.
   - When a price entry contains `validators.matched_coldkeys`, each match (uid, coldkey, optional hotkey) is preserved. Salvaged outputs now include a top-level `validators` mapping from stringified netuid to:
     ```json
     {
       "block": 6593785,
       "matched": [
         { "uid": 12, "coldkey": "5GZSA…", "hotkey": "5CCx…" },
         { "uid": 225, "coldkey": "5HBtp…", "hotkey": "5EFZ…" }
       ]
     }
     ```
     Subnets without matches are omitted, and the entire block is omitted when no subnet provided validator metadata.
3. **Timestamp guard**
   - Parses `requested_local_noon` and `block_timestamp_utc` (ISO 8601).
   - Skips the file if both parse successfully and their calendar dates differ (prevents using “future” requested days with present block data).
4. **Metadata**
   - `collection_method`: `btsdk scripts v2`.
   - `date`: filename stem without dashes (e.g., `20251020`).
   - `requested_local_time`: copies the original `requested_local_noon` string.
   - Adds `closest_block`, `network`, `timestamp`, plus derived totals: `total_active_subnets`, `total_emission_rate`.
5. **Statistics**
   - Recomputes `active_subnets`, `avg_emission_rate`, `min_emission_rate`, `max_emission_rate`, and `total_emission_rate` from the salvaged prices.
6. **Emissions block**
   - Keys are stringified netuids; values are the salvaged prices.
   - Ordering is numeric (ascending netuid) via `OrderedDict`.
7. **Top-level extras**
   - Includes `generated_at` with the UTC timestamp of the conversion run.

## Running the Pipeline
```bash
# Preview which files will be converted and why others are skipped
python3 salvage_jsons.py --dry-run

# Generate JSON outputs into jsons_salvaged/
python3 salvage_jsons.py
```
- Use `--input <dir>` or `--output <dir>` to override defaults if necessary.
- The script reports the number of processed files and lists every skipped file with a reason.

## Post-run Checklist
- Inspect `jsons_salvaged/` to confirm new `emissions_v2_*.json` files exist for expected dates.
- Spot-check a few outputs to verify that:
  - `emissions` omits netuid 0 and is numerically ordered.
  - `metadata.collection_method` reads `btsdk scripts v2`.
  - Timestamps align with the source and `generated_at` reflects run time.
