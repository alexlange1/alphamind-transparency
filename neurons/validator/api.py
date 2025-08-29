#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, Request
import logging
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import json
import json as _json
import hashlib
from pydantic import BaseModel
from typing import Optional

from .service import aggregate_and_emit
from ..sim.vault import load_vault, save_vault, apply_mint_with_tao, apply_redeem_in_kind, apply_mint_in_kind, apply_management_fee
from pathlib import Path
from .state import pause as _pause, resume as _resume, is_paused as _is_paused, load_paused as _load_paused
from ..sim.vault import load_fees_ledger, reinvest_fees_to_alpha
from .publish import publish_weightset
from ..common.rate_limiter import rate_limit_mint, rate_limit_aggregate, rate_limit_general
from .publish import _publish_validator_set as _vs_commit  # type: ignore


def _get_default_dir() -> str:
    """Get default directory from settings, avoiding hardcoded paths."""
    from ..common.settings import get_settings
    return get_settings().out_dir


def _resolve_in_dir(in_dir: str | None) -> Path:
    """Resolve input directory, using default if None."""
    if in_dir is None:
        return Path(_get_default_dir())
    return Path(in_dir)


class AggregateReq(BaseModel):
    in_dir: str
    out_file: str
    top_n: int = 20


app = FastAPI(title="TAO20 Validator API", version="0.0.1")
logger = logging.getLogger("validator")

# Simple in-memory metrics counters
_metrics_counters: dict[str, int] = {}

def _bump_counter(name: str, inc: int = 1) -> None:
    try:
        _metrics_counters[name] = int(_metrics_counters.get(name, 0)) + int(inc)
    except Exception:
        pass


# CORS allowlist via AM_CORS_ORIGINS (comma-separated)
_cors_env = os.environ.get("AM_CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )


class _CorsAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            origin = request.headers.get("origin") or request.headers.get("Origin")
            allow_env = os.environ.get("AM_CORS_ORIGINS", "").strip()
            
            # Security: Default to localhost only, no wildcard origins
            if not allow_env:
                        # Production: no default origins allowed
        allowed = []
            else:
                # Parse configured origins, validate no wildcards
                allowed = []
                for o in allow_env.split(","):
                    o = o.strip()
                    if o and o != "*":  # Security: reject wildcard
                        allowed.append(o)
            
            # Only allow requests from explicitly configured origins
            if origin and origin in allowed:
                if request.method.upper() == "OPTIONS":
                    # Preflight
                    resp = Response(status_code=204)
                else:
                    resp = await call_next(request)
                resp.headers["access-control-allow-origin"] = origin
                resp.headers["access-control-allow-credentials"] = "true"
                # Security: limit methods to what's actually needed
                resp.headers["access-control-allow-methods"] = "GET, POST, OPTIONS"
                resp.headers["access-control-allow-headers"] = request.headers.get("access-control-request-headers", "Authorization, Content-Type")
                return resp
        except Exception:
            pass
        return await call_next(request)


app.add_middleware(_CorsAllowlistMiddleware)


class _RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.window_sec = 60
        try:
            self.max_per_min = int(os.environ.get("AM_RATE_LIMIT_PER_MIN", "30"))
        except Exception:
            self.max_per_min = 30
        self._buckets = {}

    async def dispatch(self, request, call_next):
        # Only rate-limit POST requests; per-IP per-path
        if request.method.upper() == "POST":
            try:
                import time as _t
                now = int(_t.time())
                key = (request.client.host if request.client else "unknown", request.url.path)
                bucket = self._buckets.get(key)
                if not bucket or now - bucket["ts"] >= self.window_sec:
                    bucket = {"ts": now, "count": 0}
                bucket["count"] += 1
                self._buckets[key] = bucket
                if bucket["count"] > max(1, int(self.max_per_min)):
                    _bump_counter("rate_limit_hits_total")
                    return Response(json.dumps({"detail": "rate_limited"}), status_code=429, media_type="application/json")
            except Exception:
                pass
        return await call_next(request)


app.add_middleware(_RateLimitMiddleware)


def _require_auth(request: Request) -> None:
    token = os.environ.get("AM_API_TOKEN", "").strip()
    auth = request.headers.get("Authorization", "")
    
    # Security: Always require Bearer token header
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    
    provided = auth.split(" ", 1)[1] if len(auth.split(" ", 1)) > 1 else ""
    
    # Security: Require explicit token configuration, no bypass
    if not token:
        raise HTTPException(status_code=401, detail="AM_API_TOKEN not configured")
    
    # Use constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="unauthorized")


def _require_admin(request: Request) -> None:
    token = os.environ.get("AM_ADMIN_TOKEN", "").strip()
    auth = request.headers.get("Authorization", "")
    
    # Security: Always require Bearer token header and explicit admin token
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    
    if not token:
        raise HTTPException(status_code=401, detail="AM_ADMIN_TOKEN not configured")
    
    provided = auth.split(" ", 1)[1] if len(auth.split(" ", 1)) > 1 else ""
    
    # Use constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="unauthorized")


def _resolve_in_dir(in_dir_str: str) -> Path:
    """Resolve and jail in_dir within AM_OUT_DIR.

    If AM_OUT_DIR is unset or empty, allow any path (dev/test mode).
    """
    env_base = os.environ.get("AM_OUT_DIR", "").strip()
    in_dir = Path(in_dir_str).resolve()
    if not env_base:
        return in_dir
    base_out = Path(env_base).resolve()
    if not str(in_dir).startswith(str(base_out)):
        raise HTTPException(status_code=400, detail="in_dir_out_of_bounds")
    return in_dir

def _ensure_within_out_dir(path: Path) -> None:
    base_out = Path(os.environ.get("AM_OUT_DIR", "/Users/alexanderlange/alphamind/subnet/out")).resolve()
    if not str(path.resolve()).startswith(str(base_out)):
        raise HTTPException(status_code=400, detail="out_of_bounds")


@app.get("/healthz")
def healthz():
    # Echo current consensus/fee params
    import os as _os
    return {
        "ok": True,
        "price": {
            "quorum": float(_os.environ.get("AM_PRICE_QUORUM", 0.33)),
            "band_pct": float(_os.environ.get("AM_PRICE_BAND_PCT", 0.2)),
            "twap_minutes": 30,
        },
        "emissions": {
            "quorum": float(_os.environ.get("AM_EMISSIONS_QUORUM", 0.33)),
            "band_pct": float(_os.environ.get("AM_EMISSIONS_BAND_PCT", 0.5)),
            "mad_k": float(_os.environ.get("AM_EMISSIONS_MAD_K", 5.0)),
            "window_days": 14,
            "eligibility_months": 3,
        },
        "fees": {"tx_bps": 20, "mgmt_apr": 0.01},
    }
@app.get("/readyz")
def readyz():
    import os as _os
    try:
        base = Path(_get_default_dir())
        w = base / "weights.json"
        weights_ok = w.exists() and len((w.read_text(encoding="utf-8") or "").strip()) > 0
        # vault writability
        vw = base / "vault_state.json"
        try:
            tmp = base / ".__wtest__"
            tmp.write_text("ok", encoding="utf-8")
            tmp.unlink(missing_ok=True)
            vault_writable = True
        except Exception:
            vault_writable = False
        # Quorum and staleness
        from .service import load_price_reports
        prs = load_price_reports(base)
        latest_ts = max([p.ts for p in prs], default="1970-01-01T00:00:00Z")
        import time as _time
        def _parse(ts: str):
            try:
                import datetime as _dt
                return int(_dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc).timestamp())
            except Exception:
                return 0
        staleness_sec = max(0, int(_time.time()) - _parse(latest_ts))
        # Compute simple quorum signal: proportion of nets with non-stale prices in last window
        from .service import consensus_prices_with_twap, build_miner_stake_map, load_reports
        em_reps = load_reports(base)
        twap_prices, quorum_map, staleness = consensus_prices_with_twap(prs, stake_by_miner=build_miner_stake_map(em_reps), window_minutes=30, outlier_k=5.0, quorum_threshold=float(_os.environ.get("AM_PRICE_QUORUM", 0.33)), price_band_pct=float(_os.environ.get("AM_PRICE_BAND_PCT", 0.2)), stale_sec=int(_os.environ.get("AM_PRICE_STALE_SEC", 120)), out_dir=base)
        quorum_ok = all(v >= float(_os.environ.get("AM_PRICE_QUORUM", 0.33)) for v in quorum_map.values()) if quorum_map else False
        ok = weights_ok and vault_writable and quorum_ok and all((s <= int(_os.environ.get("AM_PRICE_STALE_SEC", 120))) for s in staleness.values())
        if not ok:
            # FastAPI convention: raise to produce non-200 status
            raise HTTPException(status_code=503, detail={
                "weights_ok": weights_ok,
                "vault_writable": vault_writable,
                "quorum_ok": quorum_ok,
                "staleness_sec": staleness_sec,
                "price_quorum": quorum_map,
                "price_staleness_sec": staleness,
                "paused_tokens": list(_load_paused(base)),
            })
        return {"ok": True, "weights_ok": weights_ok, "vault_writable": vault_writable, "quorum_ok": quorum_ok, "staleness_sec": staleness_sec, "price_quorum": quorum_map, "price_staleness_sec": staleness, "paused_tokens": list(_load_paused(base))}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/aggregate")
def aggregate(req: AggregateReq, request: Request):
    _require_auth(request)
    try:
        base_out = Path(_get_default_dir()).resolve()
        in_dir = Path(req.in_dir).resolve()
        out_path = Path(req.out_file).resolve()
        # Enforce jail within AM_OUT_DIR
        if not str(out_path).startswith(str(base_out)):
            raise HTTPException(status_code=400, detail="out_of_bounds")
        if not str(in_dir).startswith(str(base_out)):
            raise HTTPException(status_code=400, detail="in_dir_out_of_bounds")
        aggregate_and_emit(in_dir, out_path, top_n=req.top_n)
        # Try to append sim NAV to history file
        try:
            import json as _json
            data = _json.loads(out_path.read_text(encoding="utf-8"))
            sim_nav = float(data.get("sim_nav", 0.0))
            if sim_nav:
                _append_nav_history(in_dir, sim_nav)
        except Exception:
            pass
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PauseReq(BaseModel):
    uid: int


@app.post("/admin/pause-token")
def pause_token(req: PauseReq, request: Request):
    _require_admin(request)
    try:
        base = Path(_get_default_dir())
        _pause(base, int(req.uid))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/resume-token")
def resume_token(req: PauseReq, request: Request):
    _require_admin(request)
    try:
        base = Path(_get_default_dir())
        _resume(base, int(req.uid))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scores")
def scores(in_dir: str = None):
    try:
        from .scoring import load_scores as _load_scores
        base = _resolve_in_dir(in_dir)
        return _load_scores(base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/leaderboard")
def leaderboard(in_dir: str = None, limit: int = 100, window: str = "24h"):
    try:
        from .scoring import load_scores as _load_scores
        data = _load_scores(_resolve_in_dir(in_dir))
        rows = []
        for hk, ent in data.items():
            rows.append({
                "hotkey": hk,
                "score": float(ent.get("score", 0.0)),
                "accuracy": float(ent.get("accuracy", 0.0)),
                "uptime": float(ent.get("uptime", 0.0)),
                "latency": float(ent.get("latency", 0.0)),
                "trust": float(ent.get("trust", 0.0)),
                "strikes": int(ent.get("strikes", 0)),
                "suspended": bool(ent.get("suspended", False)),
            })
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows[: max(1, int(limit))]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scores/{hotkey}")
def score_detail(hotkey: str, in_dir: str = None, last: int = 200):
    try:
        from .scoring import load_scores as _load_scores
        from .scoreboard import _samples_path as _sb_samples_path
        base = Path(in_dir)
        scores = _load_scores(base)
        detail = scores.get(hotkey)
        samples = {}
        try:
            samples = json.loads(_sb_samples_path(base).read_text(encoding="utf-8")).get(hotkey) or {}
        except Exception:
            samples = {}
        # Compute quick stats
        import statistics as _stats
        prs = samples.get("prices") or []
        ems = samples.get("emissions") or []
        def _pct(arr: list, key: str, q: float) -> float:
            if not arr:
                return 0.0
            xs = sorted([abs(float(x.get(key, 0))) for x in arr])
            idx = min(len(xs) - 1, max(0, int(q * (len(xs) - 1))))
            return xs[idx]
        price_p50 = _pct(prs, "dev_bps", 0.50)
        price_p90 = _pct(prs, "dev_bps", 0.90)
        em_delay_avg = (sum(int(x.get("delay_sec", 0)) for x in ems) / float(len(ems))) if ems else 0.0
        price_ontime = (sum(1 for x in prs if bool(x.get("early", False))) / float(len(prs))) if prs else 0.0
        return {
            "hotkey": hotkey,
            "score": detail.get("score") if detail else None,
            "components": {k: detail.get(k) for k in ("accuracy", "uptime", "latency", "trust")} if detail else {},
            "strikes": detail.get("strikes") if detail else 0,
            "suspended": detail.get("suspended") if detail else False,
            "samples": {"prices": len(prs), "emissions": len(ems)},
            "stats": {
                "price_dev_bps_p50": price_p50,
                "price_dev_bps_p90": price_p90,
                "emissions_avg_delay_sec": em_delay_avg,
                "price_early_ratio": price_ontime,
            },
            "recent": {
                "prices": prs[-max(0, int(last)):],
                "emissions": ems[-max(0, int(last)):],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MintReq(BaseModel):
    in_dir: str
    amount_tao: float
    max_slippage_bps: Optional[int] = None


@app.post("/mint-tao")
def mint_tao(req: MintReq, request: Request):
    _require_auth(request)
    
    # Rate limiting
    try:
        from ..common.rate_limiter import _mint_limiter, get_client_identifier
        client_id = get_client_identifier(request)
        if not _mint_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for mint operations",
                headers={"Retry-After": str(_mint_limiter.window_seconds)}
            )
    except HTTPException:
        raise
    except ImportError:
        # Rate limiting module not available - continue without rate limiting
        pass
    except Exception as e:
        # Log rate limiting errors but don't fail the request
        logger.warning(f"Rate limiting failed: {e}")
        pass
    
    # Input validation
    try:
        from ..common.validation import validate_positive_amount, sanitize_file_path
        validate_positive_amount(req.amount_tao, "amount_tao")
        sanitize_file_path(req.in_dir)
        if req.max_slippage_bps is not None:
            from ..common.validation import validate_percentage_bps
            validate_percentage_bps(req.max_slippage_bps, "max_slippage_bps")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"validation_error: {str(e)}")
    
    try:
        in_dir = _resolve_in_dir(req.in_dir)
        from .service import consensus_prices, load_price_reports, load_reports, consensus_prices_with_twap, build_miner_stake_map, extract_reserves_from_price_reports
        from ..tao20.validator import compute_index_weights_from_reports
        from ..sim.vault import mint_tao_extended
        from ..tao20.price_feed import read_prices_items_from_btcli

        price_reports = load_price_reports(in_dir)
        emissions_reports = load_reports(in_dir)
        prices = consensus_prices(price_reports)
        weights = compute_index_weights_from_reports(emissions_reports)
        # Staleness guard: require staleness <= AM_PRICE_STALE_SEC on constituents
        try:
            import os as _os
            _p, _q, staleness = consensus_prices_with_twap(
                price_reports,
                stake_by_miner=build_miner_stake_map(emissions_reports),
                window_minutes=30,
                outlier_k=5.0,
                quorum_threshold=float(_os.environ.get("AM_PRICE_QUORUM", 0.33)),
                price_band_pct=float(_os.environ.get("AM_PRICE_BAND_PCT", 0.2)),
                stale_sec=int(_os.environ.get("AM_PRICE_STALE_SEC", 120)),
                out_dir=in_dir,
            )
            # Optionally self-refresh prices if stale
            def _any_stale() -> bool:
                return any(staleness.get(int(uid), 1e9) > int(_os.environ.get("AM_PRICE_STALE_SEC", 120)) // 2 for uid in weights.keys())

            if _any_stale() and int(_os.environ.get("AM_VALIDATOR_SELF_REFRESH", "0")) == 1:
                # Do a local refresh via btcli for richer items and write a temporary price report
                try:
                    btcli = _os.environ.get("AM_BTCLI", "/Users/alexanderlange/.venvs/alphamind/bin/btcli")
                    items = read_prices_items_from_btcli(btcli)
                    # Synthesize a one-off PriceReport in-memory to recompute prices/quorum/staleness
                    from ..tao20.reports import PriceReport
                    import time as _time
                    now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
                    local = PriceReport(ts=now, prices_by_netuid={it.uid: it.price_in_tao for it in items}, miner_id="validator-local", prices=items, schema_version="1.0.0")
                    price_reports = price_reports + [local]
                    prices = consensus_prices(price_reports)
                    _p2, _q2, staleness2 = consensus_prices_with_twap(price_reports, stake_by_miner=build_miner_stake_map(emissions_reports), window_minutes=30, outlier_k=5.0, quorum_threshold=float(_os.environ.get("AM_PRICE_QUORUM", 0.33)), price_band_pct=float(_os.environ.get("AM_PRICE_BAND_PCT", 0.2)), stale_sec=int(_os.environ.get("AM_PRICE_STALE_SEC", 120)), out_dir=in_dir)
                    staleness = staleness2
                except Exception:
                    pass
            # Final staleness check
            for uid in weights.keys():
                if staleness.get(int(uid), 1e9) > int(_os.environ.get("AM_PRICE_STALE_SEC", 120)):
                    raise HTTPException(status_code=409, detail="stale_or_missing_price")
        except HTTPException:
            raise
        except Exception:
            pass

        vault_path = in_dir / "vault_state.json"
        state = load_vault(vault_path)
        if state is None:
            from ..sim.vault import initialize_vault
            state = initialize_vault(weights, prices)
        # Opportunistic management fee accrual
        state = apply_management_fee(prices, state)
        pool_reserves = extract_reserves_from_price_reports(price_reports)
        # Reserve requirement guard
        try:
            require_reserves = int(os.environ.get("AM_REQUIRE_RESERVES", "0")) == 1
        except Exception:
            require_reserves = False
        if require_reserves:
            missing = [int(uid) for uid in weights.keys() if int(uid) not in pool_reserves]
            if missing:
                # Optional self-refresh to fill reserves
                did_refresh = False
                try:
                    import os as _os
                    if int(_os.environ.get("AM_VALIDATOR_SELF_REFRESH", "0")) == 1:
                        from ..tao20.price_feed import read_prices_items_from_btcli
                        btcli = _os.environ.get("AM_BTCLI", "/usr/bin/false")
                        items = read_prices_items_from_btcli(btcli)
                        from ..tao20.reports import PriceReport
                        import time as _time
                        now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
                        local = PriceReport(ts=now, prices_by_netuid={it.uid: it.price_in_tao for it in items}, miner_id="validator-local", prices=items, schema_version="1.0.0")
                        price_reports = price_reports + [local]
                        pool_reserves = extract_reserves_from_price_reports(price_reports)
                        missing = [int(uid) for uid in weights.keys() if int(uid) not in pool_reserves]
                        did_refresh = True
                except Exception:
                    pass
                if missing:
                    logger.warning("mint-tao blocked: missing reserves for %s (refreshed=%s)", missing, did_refresh)
                    _bump_counter("mint_blocked_missing_reserves_total")
                    raise HTTPException(status_code=409, detail={"missing_reserve_uids": [int(u) for u in missing]})
        # Circuit breakers: reject if any touched token is paused
        for uid in weights.keys():
            if _is_paused(in_dir, int(uid)):
                raise HTTPException(status_code=409, detail=f"token_paused_{int(uid)}")
        state, result = mint_tao_extended(req.amount_tao, weights, prices, state, max_slippage_bps=req.max_slippage_bps, pool_reserves=pool_reserves, fees_base=in_dir)
        save_vault(vault_path, state)
        return {"status": "ok", "minted": result.minted, "nav_per_tao20": result.nav_per_tao20, "residuals": [{"uid": r.uid, "qty": r.qty} for r in result.residuals], "pricing_mode": result.pricing_mode, "supply": state.tao20_supply}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RedeemReq(BaseModel):
    in_dir: str
    amount_tao20: float


@app.post("/redeem")
def redeem(req: RedeemReq, request: Request):
    _require_auth(request)
    try:
        from ..common.validation import validate_positive_amount, sanitize_file_path
        validate_positive_amount(req.amount_tao20, "amount_tao20")
        sanitize_file_path(req.in_dir)

        in_dir = _resolve_in_dir(req.in_dir)
        vault_path = in_dir / "vault_state.json"
        state = load_vault(vault_path)
        if state is None:
            raise HTTPException(status_code=400, detail="vault not initialized")
        from .service import consensus_prices, load_price_reports
        prices = consensus_prices(load_price_reports(in_dir))
        # Opportunistic management fee accrual
        state = apply_management_fee(prices, state)
        # Circuit breaker: if any held token paused and would be touched, block redeem? We block only if paused list not empty to avoid partial redemptions; for now block if any paused exists.
        paused = set(_load_paused(in_dir))
        if paused:
            raise HTTPException(status_code=409, detail="redeem_blocked_paused_tokens")
        from ..sim.vault import redeem_in_kind_extended
        state, result = redeem_in_kind_extended(req.amount_tao20, prices, state, fees_base=in_dir)
        save_vault(vault_path, state)
        return {"status": "ok", "basket_out": [{"uid": r.uid, "qty": r.qty} for r in result.basket_out], "new_nav": state.last_nav_tao, "supply": state.tao20_supply}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Vault state not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weights")
def get_weights(in_dir: str = None):
    in_dir_path = _resolve_in_dir(in_dir)
    p = in_dir_path / "weights.json"
    if not p.exists():
        try:
            aggregate_and_emit(in_dir_path, p, top_n=20)
        except Exception:
            raise HTTPException(status_code=404, detail="weights.json not found and auto-aggregate failed")
    # Also append NAV history if present
    try:
        import json as _json
        data = _json.loads(p.read_text(encoding="utf-8"))
        sim_nav = float(data.get("sim_nav", 0.0))
        if sim_nav:
            _append_nav_history(in_dir_path, sim_nav)
    except Exception:
        pass
    return Response(p.read_text(encoding="utf-8"), media_type="application/json")


@app.get("/dashboard")
def dashboard():
    html = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>TAO20 Weights & NAV</title>
  <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
  <style> body{font-family:-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial;margin:20px} #wrap{max-width:980px;margin:0 auto} canvas{width:100%;height:420px} </style>
  <meta http-equiv='refresh' content='60'/>
  </head>
<body>
  <div id='wrap'>
    <h2>TAO20 Weights & Simulated NAV</h2>
    <div id='epoch'></div>
    <div id='epochMeta' style='color:#555;font-size:0.9em;margin-bottom:8px;'></div>
    <div id='lights' style='display:flex; gap:12px; align-items:center; margin:6px 0;'>
      <div>Prices quorum: <span id='priceLight'>-</span></div>
      <div>Oldest price age: <span id='oldestStale'>-</span>s</div>
      <div>Paused: <span id='pausedList'>-</span></div>
    </div>
    <div id='nav'></div>
    <h3>NAV (sim)</h3>
    <canvas id='navChart'></canvas>
    <h3>Weights</h3>
    <canvas id='wChart'></canvas>
    <h3 style='margin-top:16px;'>Constituents (Top 20)</h3>
    <table id='constituents' border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>
      <thead><tr><th>Netuid</th><th>Weight</th><th>Price (τ)</th><th>Price Quorum</th><th>14d Emissions (τ/day)</th><th>Eligible (90d)</th></tr></thead>
      <tbody></tbody>
    </table>
    <h3 style='margin-top:16px;'>Proofs</h3>
    <div id='proofs'>
      <div>Epoch: <span id='wsEpoch'>-</span></div>
      <div>Hash (sha256): <span id='wsHash'>-</span></div>
      <div>Publish: <span id='wsPub'>-</span></div>
      <div><a id='wsLink' href='#' target='_blank' rel='noopener'>Download WeightSet</a></div>
      <pre id='wsJson' style='max-height:280px; overflow:auto; background:#f6f8fa; padding:8px; border-radius:6px;'></pre>
    </div>
    <h3 style='margin-top:16px;'>Top Miners</h3>
    <table id='miners' border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>
      <thead><tr><th>Hotkey</th><th>Score</th><th>Accuracy</th><th>Uptime</th><th>Latency</th><th>Strikes</th></tr></thead>
      <tbody></tbody>
    </table>
    <div style='margin-top:16px;'>
      <input id='mintAmt' type='number' step='0.01' placeholder='TAO to mint' />
      <button onclick='mint()'>Mint via TAO</button>
      <input id='redeemAmt' type='number' step='0.01' placeholder='TAO20 to redeem' />
      <button onclick='redeem()'>Redeem</button>
    </div>
  </div>
  <script>
  function epochCountdown(){
    // naive countdown using local clock relative to ANCHOR 1700000000 and 14d epochs
    const anchor = 1700000000 * 1000;
    const epochMs = 14 * 24 * 60 * 60 * 1000;
    const now = Date.now();
    const elapsed = Math.max(0, now - anchor);
    const into = elapsed % epochMs;
    const remain = epochMs - into;
    const hrs = Math.floor(remain / (60*60*1000));
    const mins = Math.floor((remain % (60*60*1000)) / (60*1000));
    const secs = Math.floor((remain % (60*1000)) / 1000);
    document.getElementById('epoch').textContent = `Epoch ends in ${hrs}h ${mins}m ${secs}s`;
  }

  async function load(){
    const r = await fetch('/weights');
    const j = await r.json();
    const navDiv = document.getElementById('nav');
    navDiv.textContent = 'Sim NAV (τ): ' + (j.sim_nav ?? 'N/A');
    const em = document.getElementById('epochMeta');
    em.textContent = `Epoch ${j.epoch_id ?? '-'} • Hash ${j.weightset_hash ?? '-'}`;
    epochCountdown();
    setInterval(epochCountdown, 1000);
    const labels = Object.keys(j.weights||{});
    const values = labels.map(k=>j.weights[k]);
    const ctx = document.getElementById('wChart').getContext('2d');
    new Chart(ctx, { type:'bar', data:{ labels, datasets:[{ label:'Weight', data:values, backgroundColor:'rgba(54,162,235,0.5)'}]}, options:{ indexAxis:'x', scales:{ y:{ beginAtZero:true }}}});

    try{
      const h = await fetch('/nav-history');
      const arr = await h.json();
      const hl = arr.map(x=>x.ts);
      const hv = arr.map(x=>x.nav);
      const nctx = document.getElementById('navChart').getContext('2d');
      new Chart(nctx, { type:'line', data:{ labels: hl, datasets:[{ label:'Sim NAV', data: hv, borderColor:'rgba(54,162,235,1)', backgroundColor:'rgba(54,162,235,0.15)', tension:0.2, pointRadius:0 }]}, options:{ responsive:true }});
    }catch(e){}

    try{
      const tbody = document.querySelector('#constituents tbody');
      tbody.innerHTML = '';
      const prices = j.consensus_prices || {};
      const ems = j.emissions_avg_14d || {};
      const elig = j.eligibility || {};
      const quorum = j.price_quorum || {};
      labels.slice(0,20).forEach(k=>{
        const tr = document.createElement('tr');
        const w = j.weights[k];
        const p = prices[k] ?? '';
        const q = quorum[k] ? (quorum[k]*100).toFixed(1)+'%' : '';
        const e = ems[k] ?? '';
        const el = elig[k] ? 'Yes' : 'No';
        tr.innerHTML = `<td>${k}</td><td>${(w*100).toFixed(2)}%</td><td>${p}</td><td>${q}</td><td>${e}</td><td>${el}</td>`;
        tbody.appendChild(tr);
      });
    }catch(e){}

    try{
      const wsr = await fetch('/weightset');
      if(wsr.ok){
        const ws = await wsr.json();
        document.getElementById('wsEpoch').textContent = ws.epoch_id ?? '-';
        document.getElementById('wsHash').textContent = ws.hash_sha256 ?? '-';
        document.getElementById('wsJson').textContent = JSON.stringify(ws.weightset || {}, null, 2);
        if(ws.path){ document.getElementById('wsLink').href = '/weightset?download=1'; }
      }
    }catch(e){}

    try{
      const pr = await fetch('/weightset-publish');
      if(pr.ok){
        const pub = await pr.json();
        const parts = [];
        if(pub.cid){ parts.push(`IPFS ${pub.cid.substring(0,10)}…`); }
        if(pub.github_url){ parts.push('GitHub'); }
        if(pub.local_path){ parts.push('Local'); }
        document.getElementById('wsPub').textContent = parts.join(' | ') || '-';
      }
    }catch(e){}

    try{
      // Lights from readyz
      const rz = await fetch('/readyz');
      const ok = rz.ok;
      const meta = ok ? await rz.json() : (await rz.json()).detail;
      document.getElementById('priceLight').textContent = meta.quorum_ok ? 'OK' : 'MISSING';
      document.getElementById('priceLight').style.color = meta.quorum_ok ? 'green' : 'red';
      document.getElementById('oldestStale').textContent = Math.round(meta.staleness_sec || 0);
      const paused = (meta.paused_tokens||[]);
      document.getElementById('pausedList').textContent = paused.length ? paused.join(',') : 'None';
    }catch(e){}

    try{
      // Top miners
      const lr = await fetch('/leaderboard?limit=20');
      const rows = await lr.json();
      const tbody = document.querySelector('#miners tbody');
      tbody.innerHTML = '';
      rows.forEach(r=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.hotkey}</td><td>${r.score.toFixed(3)}</td><td>${(r.accuracy*100).toFixed(1)}%</td><td>${(r.uptime*100).toFixed(1)}%</td><td>${(r.latency*100).toFixed(1)}%</td><td>${r.strikes}</td>`;
        tbody.appendChild(tr);
      })
    }catch(e){}
  }
  async function mint(){
    const amt = parseFloat(document.getElementById('mintAmt').value||'0');
    if(!amt) return;
    await fetch('/mint-tao',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({in_dir:'/Users/alexanderlange/alphamind/subnet/out',amount_tao:amt})});
    location.reload();
  }
  async function redeem(){
    const amt = parseFloat(document.getElementById('redeemAmt').value||'0');
    if(!amt) return;
    await fetch('/redeem',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({in_dir:'/Users/alexanderlange/alphamind/subnet/out',amount_tao20:amt})});
    location.reload();
  }
  load();
  </script>
</body>
</html>
"""
    return Response(html, media_type="text/html")


@app.get("/prices/latest")
def prices_latest(in_dir: str = None):
    try:
        from .service import load_price_reports, consensus_prices
        base = _resolve_in_dir(in_dir)
        prs = load_price_reports(base)
        prices = consensus_prices(prs)
        return prices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/emissions/latest")
def emissions_latest(in_dir: str = None):
    try:
        from .service import load_reports, compute_rolling_emissions
        base = _resolve_in_dir(in_dir)
        reps = load_reports(base)
        avg, elig = compute_rolling_emissions(base, reps)
        return {"avg_14d": {str(k): float(v) for k, v in avg.items()}, "eligibility": {str(k): bool(v) for k, v in elig.items()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nav-history")
def nav_history(in_dir: str = None):
    in_dir_path = _resolve_in_dir(in_dir)
    p = in_dir_path / "sim_nav_history.tsv"
    if not p.exists():
        return []
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                try:
                    out.append({"ts": parts[0], "nav": float(parts[1])})
                except Exception:
                    continue
    return out


def _append_nav_history(in_dir: Path, nav: float) -> None:
    try:
        hist = in_dir / "sim_nav_history.tsv"
        ts = __import__('time').strftime("%Y-%m-%dT%H:%M:%SZ", __import__('time').gmtime())
        with open(hist, "a", encoding="utf-8") as f:
            f.write(f"{ts}\t{nav}\n")
    except Exception:
        pass


class InKindMintReq(BaseModel):
    in_dir: str
    basket: dict
    max_deviation_bps: Optional[int] = None


@app.post("/mint-in-kind")
def mint_in_kind(req: InKindMintReq, request: Request):
    _require_auth(request)
    try:
        in_dir = _resolve_in_dir(req.in_dir)
        from .service import consensus_prices, load_price_reports, load_reports, consensus_prices_with_twap, build_miner_stake_map
        from ..tao20.validator import compute_index_weights_from_reports
        prices = consensus_prices(load_price_reports(in_dir))
        weights = compute_index_weights_from_reports(load_reports(in_dir))
        # Staleness guard identical to mint-tao
        try:
            import os as _os
            prs = load_price_reports(in_dir)
            ems = load_reports(in_dir)
            _p, _q, staleness = consensus_prices_with_twap(prs, stake_by_miner=build_miner_stake_map(ems), window_minutes=30, outlier_k=5.0, quorum_threshold=float(_os.environ.get("AM_PRICE_QUORUM", 0.33)), price_band_pct=float(_os.environ.get("AM_PRICE_BAND_PCT", 0.2)), stale_sec=int(_os.environ.get("AM_PRICE_STALE_SEC", 120)), out_dir=in_dir)
            for uid in weights.keys():
                if staleness.get(int(uid), 1e9) > int(_os.environ.get("AM_PRICE_STALE_SEC", 120)):
                    raise HTTPException(status_code=409, detail="stale_or_missing_price")
        except HTTPException:
            raise
        except Exception:
            pass
        vault_path = in_dir / "vault_state.json"
        state = load_vault(vault_path)
        if state is None:
            # Align with mint-tao: initialize vault if missing
            from ..sim.vault import initialize_vault
            state = initialize_vault(weights, prices)
        # Opportunistic management fee accrual
        state = apply_management_fee(prices, state)
        for uid in weights.keys():
            if _is_paused(in_dir, int(uid)):
                raise HTTPException(status_code=409, detail=f"token_paused_{int(uid)}")
        from ..sim.vault import mint_in_kind_extended
        state, result = mint_in_kind_extended(req.basket or {}, weights, prices, state, max_deviation_bps=req.max_deviation_bps, fees_base=in_dir)
        save_vault(vault_path, state)
        return {"status": "ok", "minted": result.minted, "nav_per_tao20": result.nav_per_tao20, "pricing_mode": result.pricing_mode, "supply": state.tao20_supply}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weightset")
def get_weightset(in_dir: str = None, download: int = 0):
    base = _resolve_in_dir(in_dir)
    # Prefer by epoch_state
    epoch_file = base / "epoch_state.json"
    target: Path = None  # type: ignore
    epoch_id = None
    try:
        if epoch_file.exists():
            raw = _json.loads(epoch_file.read_text(encoding="utf-8"))
            epoch_id = int(raw.get("epoch_id", 0))
            cand = base / f"weightset_epoch_{epoch_id}.json"
            if cand.exists():
                target = cand
    except Exception:
        pass
    # Fallback: pick highest epoch file
    if target is None:
        try:
            import glob as _glob
            paths = _glob.glob(str(base / "weightset_epoch_*.json"))
            if paths:
                def _parse(p: str) -> int:
                    try:
                        s = Path(p).stem  # weightset_epoch_<id>
                        eid = int(str(s).split("_")[-1])
                        return eid
                    except Exception:
                        return -1
                best = max(paths, key=lambda p: _parse(p))
                target = Path(best)
                if epoch_id is None:
                    epoch_id = _parse(best)
        except Exception:
            pass
    if target is None or not target.exists():
        return {}
    if download:
        return Response(target.read_text(encoding="utf-8"), media_type="application/json")
    # Build canonical object and hash
    try:
        raw = _json.loads(target.read_text(encoding="utf-8"))
        ws = {
            "epoch_id": int(raw.get("epoch_id", epoch_id or 0)),
            "as_of_ts": str(raw.get("as_of_ts", "")),
            "weights": {str(k): float(v) for k, v in (raw.get("weights") or {}).items()},
        }
        canon = _json.dumps(ws, separators=(",", ":"), sort_keys=True)
        sha = hashlib.sha256(canon.encode("utf-8")).hexdigest()
        return {
            "epoch_id": ws["epoch_id"],
            "hash_sha256": sha,
            "weightset": ws,
            "path": str(target),
        }
    except Exception:
        return {}
@app.get("/weightset-publish")
def weightset_publish(in_dir: str = None, request: Request = None):
    _require_admin(request)
    try:
        base = _resolve_in_dir(in_dir)
        # Determine target epoch file
        epoch_file = base / "epoch_state.json"
        target: Path = None  # type: ignore
        epoch_id = None
        try:
            if epoch_file.exists():
                raw = _json.loads(epoch_file.read_text(encoding="utf-8"))
                epoch_id = int(raw.get("epoch_id", 0))
                cand = base / f"weightset_epoch_{epoch_id}.json"
                if cand.exists():
                    target = cand
        except Exception:
            pass
        if target is None:
            import glob as _glob
            paths = _glob.glob(str(base / "weightset_epoch_*.json"))
            if not paths:
                raise HTTPException(status_code=404, detail="weightset_not_found")
            # pick latest by epoch id
            def _parse(p: str) -> int:
                try:
                    s = Path(p).stem
                    return int(str(s).split("_")[-1])
                except Exception:
                    return -1
            best = max(paths, key=lambda p: _parse(p))
            target = Path(best)
            epoch_id = _parse(best)
        # Compute sha256
        data = target.read_text(encoding="utf-8")
        sha = hashlib.sha256(_json.dumps(_json.loads(data), separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
        res = publish_weightset(sha, str(target)) or {}
        # Ensure published_at present
        if "published_at" not in res:
            res["published_at"] = __import__('time').strftime("%Y-%m-%dT%H:%M:%SZ", __import__('time').gmtime())
        # attach epoch and sha
        res.setdefault("epoch", int(epoch_id or 0))
        res.setdefault("sha256", sha)
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/weightset-proof")
def weightset_proof(in_dir: str = None):
    try:
        base = _resolve_in_dir(in_dir)
        # Use manifest if available
        import glob as _glob
        paths = _glob.glob(str(base / "weightset_epoch_*.manifest.json"))
        if not paths:
            raise HTTPException(status_code=404, detail="manifest_not_found")
        latest = max(paths)  # file name includes epoch and sha8; lexicographic ok for simple cases
        man = _json.loads(Path(latest).read_text(encoding="utf-8"))
        return {
            "epoch": int(man.get("epoch", 0)),
            "sha256": str(man.get("sha256", "")),
            "signer_ss58": str(man.get("signer_ss58", "")),
            "sig": str(man.get("sig", "")),
            "cid": str(man.get("cid", "")),
            "github_url": str(man.get("github_url", "")),
            "published_at": str(man.get("published_at", "")),
            "status": str(man.get("status", "")),
            "verify_ok": bool(man.get("verify_ok", False)),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weightset-sha")
def get_weightset_sha(in_dir: str = None):
    base = _resolve_in_dir(in_dir)
    # Find best epoch file like in /weightset
    target: Path = None  # type: ignore
    try:
        import glob as _glob
        paths = _glob.glob(str(base / "weightset_epoch_*.sha256"))
        if paths:
            def _parse(p: str) -> int:
                try:
                    s = Path(p).stem  # weightset_epoch_<id>.sha256
                    eid = int(str(s).split("_")[-1])
                    return eid
                except Exception:
                    return -1
            best = max(paths, key=lambda p: _parse(p))
            target = Path(best)
    except Exception:
        pass
    if target is None or not target.exists():
        raise HTTPException(status_code=404, detail="sha_not_found")
    return Response(target.read_text(encoding="utf-8"), media_type="text/plain")


@app.post("/weightset-commit")
def post_weightset_commit(request: Request, in_dir: str = None):
    _require_admin(request)
    try:
        base = _resolve_in_dir(in_dir)
        p = base / "weights.json"
        if not p.exists():
            raise HTTPException(status_code=404, detail="weights_not_found")
        import json as _j
        raw = _j.loads(p.read_text(encoding="utf-8"))
        wb = raw.get("weights_bps") or {}
        if not isinstance(wb, dict) or not wb:
            raise HTTPException(status_code=400, detail="weights_bps_missing")
        try:
            wb_int = {int(k): int(v) for k, v in wb.items()}
        except Exception:
            wb_int = {}
        epoch_id = int(raw.get("epoch_id", 0) or 0)
        if epoch_id <= 0:
            raise HTTPException(status_code=400, detail="epoch_id_missing")
        txh = _vs_commit(epoch_id, wb_int, str(raw.get("weightset_hash", "")))
        if not txh:
            raise HTTPException(status_code=500, detail="commit_failed")
        return {"status": "ok", "epoch": epoch_id, "validator_tx_hash": txh}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _prom_escape(s: str) -> str:
    try:
        return str(s).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    except Exception:
        return str(s)


@app.get("/metrics/prom")
def metrics_prom(in_dir: str = None):
    try:
        m = metrics(_resolve_in_dir(in_dir))
        lines = []
        lines.append(f"tao20_quorum_pct {m.get('quorum_pct', 0.0)}")
        lines.append(f"tao20_max_price_staleness_sec {m.get('max_price_staleness_sec', 0.0)}")
        lines.append(f"tao20_publish_verify_ok {1 if m.get('publish_verify_ok') else 0}")
        lines.append(f"tao20_publish_last_epoch {m.get('publish_last_epoch', 0)}")
        lines.append(f"tao20_publish_tx_hash_present {1 if m.get('publish_tx_hash_present') else 0}")
        lines.append(f"tao20_publish_chain_id {int(m.get('publish_chain_id', 0) or 0)}")
        lines.append(f"tao20_publish_tx_receipt_status {int(m.get('publish_tx_receipt_status', 0) or 0)}")
        age = m.get('stake_oracle_age_sec')
        if age is not None:
            lines.append(f"tao20_stake_oracle_age_sec {float(age)}")
        fees = m.get('fees') or {}
        lines.append(f"tao20_fees_accrued_tao {float(fees.get('accrued_tao', 0.0))}")
        lines.append(f"tao20_fees_alpha_qty {float(fees.get('alpha_qty', 0.0))}")
        status = _prom_escape(m.get('publish_last_status', ''))
        if status:
            lines.append(f"tao20_publish_status{{status=\"{status}\"}} 1")
        for uid in (m.get('paused_tokens') or []):
            try:
                lines.append(f"tao20_paused_token{{uid=\"{int(uid)}\"}} 1")
            except Exception:
                continue
        ctrs = m.get('counters') or {}
        for k, v in ctrs.items():
            name = _prom_escape(f"tao20_{k}")
            try:
                lines.append(f"{name} {int(v)}")
            except Exception:
                continue
        body = "\n".join(lines) + "\n"
        return Response(body, media_type="text/plain; version=0.0.4; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fees")
def get_fees(in_dir: str = None):
    try:
        from ..common.validation import sanitize_file_path
        sanitize_file_path(in_dir)
        base = _resolve_in_dir(in_dir)
        led = load_fees_ledger(base)
        return {
            "accrued_tao": led.accrued_tao,
            "accrued_tokens": {str(k): v for k, v in (led.accrued_tokens or {}).items()},
            "last_mgmt_fee_ts": led.last_mgmt_fee_ts,
            "alpha_qty": led.alpha_qty,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fees/reinvest")
def post_fees_reinvest(in_dir: str = None, request: Request = None):
    _require_admin(request)
    try:
        from ..common.validation import sanitize_file_path
        sanitize_file_path(in_dir)
        base = _resolve_in_dir(in_dir)
        from .service import consensus_prices, load_price_reports
        prices = consensus_prices(load_price_reports(base))
        led = reinvest_fees_to_alpha(prices, base)
        return {
            "accrued_tao": led.accrued_tao,
            "accrued_tokens": {str(k): v for k, v in (led.accrued_tokens or {}).items()},
            "last_mgmt_fee_ts": led.last_mgmt_fee_ts,
            "alpha_qty": led.alpha_qty,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
def metrics(in_dir: str = None):
    try:
        base = _resolve_in_dir(in_dir)
        # Quorum/staleness
        from .service import load_price_reports, consensus_prices_with_twap, build_miner_stake_map, load_reports
        prs = load_price_reports(base)
        ems = load_reports(base)
        _p, qmap, stale = consensus_prices_with_twap(
            prs,
            stake_by_miner=build_miner_stake_map(ems),
            window_minutes=30,
            outlier_k=5.0,
            quorum_threshold=float(os.environ.get("AM_PRICE_QUORUM", 0.33)),
            price_band_pct=float(os.environ.get("AM_PRICE_BAND_PCT", 0.2)),
            stale_sec=int(os.environ.get("AM_PRICE_STALE_SEC", 120)),
            out_dir=base,
        )
        quorum_covered = list(qmap.values())
        quorum_pct = (sum(1 for v in quorum_covered if v >= float(os.environ.get("AM_PRICE_QUORUM", 0.33))) / float(len(quorum_covered) or 1))
        max_stale = max(stale.values()) if stale else 0.0
        # Publish status from latest manifest if available
        pub_status = ""
        pub_verify = False
        pub_epoch = 0
        try:
            man = json.loads((base / "published_last.json").read_text(encoding="utf-8"))
            pub_status = str(man.get("status", ""))
            pub_verify = bool(man.get("verify_ok", False))
            pub_epoch = int(man.get("epoch", 0))
            pub_tx_hash = str(man.get("tx_hash", ""))
            pub_chain_id = int(man.get("chain_id", 0) or 0)
            pub_tx_status = int(man.get("tx_receipt_status", 0) or 0)
        except Exception:
            pub_tx_hash = ""
            pub_chain_id = 0
            pub_tx_status = 0
        # Paused tokens
        paused = list(_load_paused(base))
        # Slashing deviations count
        dev = 0
        sl_path = base / "slashing_log.jsonl"
        if sl_path.exists():
            with open(sl_path, "r", encoding="utf-8") as f:
                for ln in f:
                    if '\"type\":\"deviation\"' in ln:
                        dev += 1
        # Suspended miners and average score
        try:
            from .scoring import load_scores
            sc = load_scores(base)
            miners_suspended = sum(1 for _k, v in sc.items() if bool(v.get("suspended", False)))
            avg_score = (sum(float(v.get("score", 1.0)) for v in sc.values()) / float(len(sc) or 1))
        except Exception:
            miners_suspended = 0
            avg_score = 1.0
        # Stake oracle age
        try:
            from ..common.stake_oracle import load_stake_oracle
            _oracle, age = load_stake_oracle()
            stake_oracle_age_sec = float(age) if age is not None else None
        except Exception:
            stake_oracle_age_sec = None
        # Fees snapshot
        led = load_fees_ledger(base)
        return {
            "quorum_pct": float(quorum_pct),
            "max_price_staleness_sec": float(max_stale),
            "publish_last_status": pub_status,
            "publish_verify_ok": bool(pub_verify),
            "publish_last_epoch": int(pub_epoch),
            "publish_tx_hash_present": bool(pub_tx_hash != ""),
            "publish_chain_id": int(pub_chain_id),
            "publish_tx_receipt_status": int(pub_tx_status),
            "paused_tokens": paused,
            "stake_oracle_age_sec": stake_oracle_age_sec,
            "slashing_deviation_events": int(dev),
            "miners_suspended": int(miners_suspended),
            "avg_score": float(avg_score),
            "fees": {
                "accrued_tao": float(led.accrued_tao),
                "accrued_tokens_count": len(led.accrued_tokens or {}),
                "alpha_qty": float(led.alpha_qty),
            },
            "counters": {k: int(v) for k, v in (_metrics_counters or {}).items()},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
