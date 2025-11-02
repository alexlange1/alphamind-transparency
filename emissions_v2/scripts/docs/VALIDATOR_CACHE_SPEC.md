# Validator Cache Spec

Script: `scripts/cache_validators.py`

---

## Purpose
Collect a day-by-day record of where specific validator coldkeys are registered.
For each UTC day the script resolves the midnight block, scans the subnet
registry at that block, and writes a JSON file summarising the tracked
validators’ `(netuid, uid, hotkey)` placements. The cache is meant to support
future dividend / staking analysis without re-reading the chain.

---

## CLI Flags
| Flag | Default | Description |
|------|---------|-------------|
| `--network` | `finney` | Bittensor network or WS endpoint; passed to `bt.Subtensor`. |
| `--date` | — | Single day (`YYYY-MM-DD`). Emits one JSON (stdout or `--output`). |
| `--date-range` | — | Inclusive range (`YYYY-MM-DD:YYYY-MM-DD`). Writes one JSON per day into `--output-dir` (default `validator_cache/`). |
| `--midnight-blocks` | `midnight_blocks.json` | Cache of midnight blocks; used to avoid binary searching unless a date is missing. |
| `--coldkey` | five defaults | Repeatable flag to provide/override tracked coldkeys. When absent, the script uses the built-in list. |
| `--output` | — | Single-day mode only: write JSON to this path (parent dirs auto-created). |
| `--output-dir` | `validator_cache` | Directory where `validators_<day>.json` files are written in range mode. |
| `--dry-run` | off | Parse and log without writing files. |

---

## Workflow
1. **Day setup**
   - Load the midnight cache (if present) and resolve the block for each
     requested day; fall back to binary search when the cache lacks an entry.
   - Fetch the block timestamp for logging/context.
2. **Validator lookup**
   - Perform a full scan for every day:
     - Call `get_all_subnets_info(block=…)` to list netuids.
     - For each netuid, call `neurons_lite(netuid=…, block=…)` and capture any
       neurons whose `coldkey` is in the tracked set.
3. **Output**
   - Write one JSON per day with the structure below, including only the
     netuids that contain tracked validators.
   - Files are flushed as soon as a day completes so memory remains bounded.

---

## Output Layout
```json
{
  "block": 5014632,
  "date": "2025-02-27",
  "network": "ws://localhost:9944",
  "validators": {
    "12": [
      { "coldkey": "5GZ…", "hotkey": "5F4…", "uid": 5 },
      { "coldkey": "5HB…", "hotkey": "5CC…", "uid": 225 }
    ],
    "17": [
      { "coldkey": "5Fuz…", "hotkey": "5DY…", "uid": 48 }
    ]
  },
  "tracked_coldkeys": [
    "5HBtpwxuGNL1gwzwomwR7sjwUt8WXYSuWcLYN6f9KpTZkP4k",
    "5GZSAgaVGQqegjhEkxpJjpSVLVmNnE2vx2PFLzr7kBBMKpGQ",
    "5E9fVY1jexCNVMjd2rdBsAxeamFGEMfzHcyTn2fHgdHeYc5p",
    "5FuzgvtfbZWdKSRxyYVPAPYNaNnf9cMnpT7phL3s2T3Kkrzo",
    "5FHxxe8ZKYaNmGcSLdG5ekxXeZDhQnk9cbpHdsJW8RunGpSs"
  ],
  "generated_at": "2025-02-28T00:00:05.432198+00:00"
}
```

- `validators` includes only netuids that contain one or more tracked coldkeys.
- Within each netuid array, entries are sorted by `uid`; `hotkey` is omitted
  when the RPC does not return it.
- `tracked_coldkeys` records the exact set used for the scan.

---

## Notes
- Every day triggers a full scan: 1 `get_all_subnets_info` call plus
  `neurons_lite` for each netuid observed.
- When no tracked validators are found for a day, the JSON still records the
  block metadata with an empty `validators` map so downstream jobs can detect
  gaps.
