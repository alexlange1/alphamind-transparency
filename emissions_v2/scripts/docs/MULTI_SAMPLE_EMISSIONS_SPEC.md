# Multi-sample Emissions JSON Spec

This schema extends the historic `emissions_v2_*.json` structure so it can
represent multiple price snapshots taken on the same UTC day. It keeps the
single-sample fields for backward compatibility while adding an explicit
`samples` array that mirrors the original payload shape for each observation.

## Top-level fields
| Key | Type | Notes |
|-----|------|-------|
| `metadata` | object | Primary sample metadata (mirrors legacy single-sample output). |
| `statistics` | object | Primary sample statistics (same fields as legacy output). |
| `samples` | array<object> | One entry per captured sample (ordered chronologically). |
| `summary` | object | Optional cross-sample aggregates (min/max/avg totals). |
| `generated_at` | string | UTC timestamp when the translator ran. |

> **Primary sample** – the first entry (`sample_index == 0`) in the `samples`
> array. Its statistics are duplicated at the top level for compatibility with
> consumers that expect a single-sample payload.

## `metadata`
| Key | Type | Example | Notes |
|-----|------|---------|-------|
| `collection_method` | string | `"btsdk scripts v2"` | Static descriptor. |
| `date` | string | `"20250227"` | UTC day as `YYYYMMDD`. |
| `network` | string | `"ws://localhost:9944"` | RPC endpoint or alias. |
| `timestamp` | string \| null | `"2025-02-27T00:00:00+00:00"` | Primary sample block timestamp. |
| `closest_block` | integer \| null | `5014632` | Primary sample block number. |
| `requested_time` | string \| null | `"2025-02-27T00:00:00+00:00"` | UTC time we requested. |
| `samples_per_day` | integer | `24` | Total samples recorded for the day. |
| `primary_sample_index` | integer | `0` | Index copied to top-level for clarity. |

Additional keys may be added in the future; consumers should ignore unknown
metadata fields.

## `statistics`
Same structure as the legacy file:

```json
{
  "active_subnets": 69,
  "avg_emission_rate": 0.01789,
  "max_emission_rate": 0.2334,
  "min_emission_rate": 0.00012,
  "total_emission_rate": 1.2345
}
```

## `samples`
Each entry mirrors the legacy payload for a single snapshot.

| Key | Type | Notes |
|-----|------|-------|
| `sample_index` | integer | Zero-based, chronological order. |
| `requested_time` | string \| null | ISO8601 timestamp requested (UTC). |
| `block_timestamp_utc` | string \| null | Timestamp returned by the node. |
| `closest_block` | integer \| null | Block used for the snapshot. |
| `emissions` | object | Ordered dict keyed by stringified netuid (netuid `0` omitted). |
| `statistics` | object | Same structure as top-level `statistics`. |

Additional keys may appear as needed (e.g., validator info in the future).

## `summary` (optional)
When available, contains cross-sample aggregates to simplify daily analysis.

```json
{
  "observations": 24,
  "active_subnets_min": 63,
  "active_subnets_max": 69,
  "total_emission_rate_min": 0.98,
  "total_emission_rate_max": 1.24,
  "total_emission_rate_avg": 1.11
}
```

The translator will omit `summary` when fewer than two samples survive
sanitisation.

## Example
```json
{
  "metadata": { … },
  "statistics": { … },
  "samples": [
    {
      "sample_index": 0,
      "requested_time": "2025-02-27T00:00:00+00:00",
      "block_timestamp_utc": "2025-02-27T00:00:00+00:00",
      "closest_block": 5014632,
      "emissions": { … },
      "statistics": { … }
    },
    {
      "sample_index": 1,
      "requested_time": "2025-02-27T01:00:00+00:00",
      "block_timestamp_utc": "2025-02-27T01:00:06+00:00",
      "closest_block": 5014908,
      "emissions": { … },
      "statistics": { … }
    }
  ],
  "summary": { … },
  "generated_at": "2025-03-01T12:34:56.789012+00:00"
}
```

## Translator usage

Run `scripts/translate_price_dumps.py` to convert raw price dumps into this
schema:

```bash
python3 scripts/translate_price_dumps.py \
  --input scripts/multi-24/prices_2025-02-27.json \
  --output translated
```

- `--input` accepts a single file or a directory containing `*.json`.
- `--output` defaults to `translated/` when unspecified.
- `--dry-run` parses inputs without writing files.

Each translated file is named `emissions_v2_<YYYYMMDD>.json` using the date
encoded in the source payload.
