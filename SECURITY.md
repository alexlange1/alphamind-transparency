# Security Policy

- Report vulnerabilities privately to security@alphamind.xyz
- Do not open public issues for sensitive findings
- We aim to acknowledge within 48 hours

## Hardening
- Require `AM_API_TOKEN` and `AM_ADMIN_TOKEN`
- Set `AM_REQUIRE_SIGNING=1`, `AM_REQUIRE_HOTKEY=1`, `AM_REJECT_HMAC=1`
- Set `AM_RATE_LIMIT_PER_MIN`
- Enforce `AM_OUT_DIR` path jail (already applied to endpoints)
