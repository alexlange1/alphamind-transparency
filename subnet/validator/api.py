#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
import json as _json
import hashlib
from pydantic import BaseModel

from .service import aggregate_and_emit
from ..sim.vault import load_vault, save_vault, apply_mint_with_tao, apply_redeem_in_kind, apply_mint_in_kind, apply_management_fee
from pathlib import Path


class AggregateReq(BaseModel):
    in_dir: str
    out_file: str
    top_n: int = 20


app = FastAPI(title="TAO20 Validator API", version="0.0.1")


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
        base = Path(_os.environ.get("AM_OUT_DIR", "/Users/alexanderlange/alphamind/subnet/out"))
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
        quorum_ok = True  # conservative default; detailed quorum surfaced per-net in /weights
        return {"ok": weights_ok and vault_writable, "weights_ok": weights_ok, "vault_writable": vault_writable, "quorum_ok": quorum_ok, "staleness_sec": staleness_sec}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/aggregate")
def aggregate(req: AggregateReq):
    try:
        in_dir = Path(req.in_dir)
        out_path = Path(req.out_file)
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


class MintReq(BaseModel):
    in_dir: str
    amount_tao: float


@app.post("/mint-tao")
def mint_tao(req: MintReq):
    try:
        in_dir = Path(req.in_dir)
        from .service import consensus_prices, load_price_reports
        from .service import load_reports
        from ..tao20.validator import compute_index_weights_from_reports

        prices = consensus_prices(load_price_reports(in_dir))
        weights = compute_index_weights_from_reports(load_reports(in_dir))
        vault_path = in_dir / "vault_state.json"
        state = load_vault(vault_path)
        if state is None:
            from ..sim.vault import initialize_vault
            state = initialize_vault(weights, prices)
        # Opportunistic management fee accrual
        state = apply_management_fee(prices, state)
        state = apply_mint_with_tao(req.amount_tao, weights, prices, state)
        save_vault(vault_path, state)
        return {"status": "ok", "new_nav": state.last_nav_tao, "supply": state.tao20_supply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RedeemReq(BaseModel):
    in_dir: str
    amount_tao20: float


@app.post("/redeem")
def redeem(req: RedeemReq):
    try:
        in_dir = Path(req.in_dir)
        vault_path = in_dir / "vault_state.json"
        state = load_vault(vault_path)
        if state is None:
            raise HTTPException(status_code=400, detail="vault not initialized")
        from .service import consensus_prices, load_price_reports
        prices = consensus_prices(load_price_reports(in_dir))
        # Opportunistic management fee accrual
        state = apply_management_fee(prices, state)
        state = apply_redeem_in_kind(req.amount_tao20, prices, state)
        save_vault(vault_path, state)
        return {"status": "ok", "new_nav": state.last_nav_tao, "supply": state.tao20_supply}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weights")
def get_weights(in_dir: str = "/Users/alexanderlange/alphamind/subnet/out"):
    p = Path(in_dir) / "weights.json"
    if not p.exists():
        try:
            aggregate_and_emit(Path(in_dir), p, top_n=20)
        except Exception:
            raise HTTPException(status_code=404, detail="weights.json not found and auto-aggregate failed")
    # Also append NAV history if present
    try:
        import json as _json
        data = _json.loads(p.read_text(encoding="utf-8"))
        sim_nav = float(data.get("sim_nav", 0.0))
        if sim_nav:
            _append_nav_history(Path(in_dir), sim_nav)
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
      <div><a id='wsLink' href='#' target='_blank' rel='noopener'>Download WeightSet</a></div>
      <pre id='wsJson' style='max-height:280px; overflow:auto; background:#f6f8fa; padding:8px; border-radius:6px;'></pre>
    </div>
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


@app.get("/nav-history")
def nav_history(in_dir: str = "/Users/alexanderlange/alphamind/subnet/out"):
    p = Path(in_dir) / "sim_nav_history.tsv"
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


@app.post("/mint-in-kind")
def mint_in_kind(req: InKindMintReq):
    try:
        in_dir = Path(req.in_dir)
        from .service import consensus_prices, load_price_reports
        prices = consensus_prices(load_price_reports(in_dir))
        vault_path = in_dir / "vault_state.json"
        state = load_vault(vault_path)
        if state is None:
            raise HTTPException(status_code=400, detail="vault not initialized")
        # Opportunistic management fee accrual
        state = apply_management_fee(prices, state)
        state = apply_mint_in_kind(req.basket or {}, prices, state)
        save_vault(vault_path, state)
        return {"status": "ok", "new_nav": state.last_nav_tao, "supply": state.tao20_supply}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weightset")
def get_weightset(in_dir: str = "/Users/alexanderlange/alphamind/subnet/out", download: int = 0):
    base = Path(in_dir)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


