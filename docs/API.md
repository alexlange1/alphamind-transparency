## API Reference (selected)

Base URL: `http://host:port`

Auth: mutating endpoints require `Authorization: Bearer <AM_API_TOKEN>`; admin endpoints require `AM_ADMIN_TOKEN`.

### Read
- `GET /dashboard` — HTML UI
- `GET /weights` — current weights and metadata
- `GET /weightset` — latest weightset canonical object + hash
- `GET /weightset-sha` — latest sha256
- `GET /weightset-proof` — manifest summary (epoch, sha256, signer, tx_hash, status)
- `GET /readyz` — readiness (200/503 with detail)
- `GET /metrics` — JSON metrics
- `GET /metrics/prom` — Prometheus text

### Write
- `POST /aggregate`
  - Body: `{in_dir, out_file, top_n}`
- `POST /mint-tao`
  - Body: `{in_dir, amount_tao, max_slippage_bps?}`
- `POST /mint-in-kind`
  - Body: `{in_dir, basket, max_deviation_bps?}`
- `POST /redeem`
  - Body: `{in_dir, amount_tao20}`
- `POST /weightset-commit` — commit current `weights.json` to ValidatorSet

### Admin
- `POST /admin/pause-token` — `{uid}`
- `POST /admin/resume-token` — `{uid}`

See OpenAPI at `http://host:port/openapi.json`.


