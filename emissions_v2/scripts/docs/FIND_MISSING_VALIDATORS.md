# Validator Coverage Audit — Script Spec

File: `scripts/find_missing_validators.py`

---

## Purpose
Quickly scan the generated `prices_YYYY-MM-DD.json` snapshots to identify any
subnets that still lack matched validator coldkeys. This provides a checklist of
remaining work when expanding the default coldkey set or re-running historical
backfills (e.g., `dump_prices_at_block.py` with deeper backtracking).

---

## Usage
```bash
# Run from repo root
python3 scripts/find_missing_validators.py scripts/outputs

# Or from scripts/
python3 find_missing_validators.py outputs
```
- Optional positional arg: directory containing `prices_*.json` (default:
  `outputs` relative to current working directory).
- Output: human-readable report on stdout, one line per day with missing
  matches. Exit status is always 0 unless the input directory is missing.

---

## Behavior
1. **File discovery** — Enumerates `prices_*.json` under the target directory,
   sorted lexicographically (chronological if names follow `YYYY-MM-DD`).
2. **JSON extraction** — Strips any console preamble (logs) by finding the first
   `{` and decoding from there.
3. **Validation** — Skips files whose top-level structure is not a dict or
   lacks a `prices` array.
4. **Match detection** — For each subnet entry:
   - Reads `validators.matched_coldkeys` (or `validators.matches` for older
     files).
   - Treats missing/empty lists as “no match,” and records the subnet’s netuid.
5. **Reporting** — Prints `prices_<date>.json: netuid, …` for every file with at
   least one unmatched subnet. When every subnet has matches the script outputs
   `All snapshots contain validator matches for every netuid.`

---

## Extensions / TODOs
- Add `--since` / `--until` date filters to focus on specific windows.
- Support CSV/JSON output for automated dashboards.
- Optionally report how many coldkeys matched per subnet, not just the missing
  ones.
- Allow configurable key names in case the upstream snapshot schema evolves.

---

This lightweight audit helps ensure validator coverage stays consistent as the
price snapshots grow or when retrofitting historical data.
