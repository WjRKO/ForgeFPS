"""overlay.py — OBS Browser Source overlay per streamer.

Espone:
    POST /api/overlay/token   -> genera/rotate token (streamer only)
    GET  /api/overlay/config  -> settings + full URL corrente (streamer only)
    PUT  /api/overlay/config  -> aggiorna preferenze visuali (position, theme)
    GET  /api/overlay/{token}       -> HTML page (pubblica, servita a OBS)
    GET  /api/overlay/{token}/data  -> JSON con stats live (pubblica)

Il token e' un secret cripto-strong, salvato in db.overlay_tokens (indice unico).
Gli endpoint pubblici sono no-auth (OBS Browser Source non porta cookies), ma
il token stesso agisce da capability. Rotate = invalida il vecchio URL.
"""
from __future__ import annotations
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from database import db
from plan_gate import require_streamer


APP_ORIGIN = os.environ.get("APP_ORIGIN", "https://forgefps.dev")

_ALLOWED_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right"}
_ALLOWED_THEMES = {"neon", "minimal", "dark"}
_ALLOWED_LAYOUTS = {"card", "bar"}
_ALLOWED_SIZES = {"small", "medium", "large"}
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


class OverlayConfigUpdate(BaseModel):
    position: Optional[str] = Field(default=None)
    theme: Optional[str] = Field(default=None)
    layout: Optional[str] = Field(default=None)
    size: Optional[str] = Field(default=None)
    accent: Optional[str] = Field(default=None)  # "#RRGGBB" oppure "" per reset al tema
    show_fps: Optional[bool] = None
    show_cpu: Optional[bool] = None
    show_gpu: Optional[bool] = None
    show_ping: Optional[bool] = None
    show_health: Optional[bool] = None
    source_device: Optional[str] = None  # Multi-PC: quale PC alimenta l'overlay ("" = attivo)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build(get_current_user):
    r = APIRouter(prefix="/api/overlay", tags=["overlay"])
    require_streamer_dep = require_streamer(get_current_user)

    async def _get_or_init_config(user_id: str) -> dict:
        doc = await db.overlay_tokens.find_one({"user_id": user_id})
        if doc:
            return doc
        token = secrets.token_urlsafe(24)  # ~32 chars url-safe
        new_doc = {
            "user_id": user_id,
            "token": token,
            "position": "top-right",
            "theme": "neon",
            "show_fps": True,
            "show_cpu": True,
            "show_gpu": True,
            "show_ping": True,
            "show_health": True,
            "created_at": _now_iso(),
            "rotated_at": None,
        }
        await db.overlay_tokens.insert_one(new_doc)
        return new_doc

    def _config_response(doc: dict) -> dict:
        return {
            "token": doc["token"],
            "url": f"{APP_ORIGIN}/api/overlay/{doc['token']}",
            "position": doc.get("position", "top-right"),
            "theme": doc.get("theme", "neon"),
            "layout": doc.get("layout", "card"),
            "size": doc.get("size", "medium"),
            "accent": doc.get("accent"),
            "show_fps": doc.get("show_fps", True),
            "show_cpu": doc.get("show_cpu", True),
            "show_gpu": doc.get("show_gpu", True),
            "show_ping": doc.get("show_ping", True),
            "show_health": doc.get("show_health", True),
            "source_device": doc.get("source_device"),
            "rotated_at": doc.get("rotated_at"),
        }

    @r.get("/config")
    async def get_config(user: dict = Depends(require_streamer_dep)):
        """Ritorna URL overlay + preferenze visuali. Al primo accesso crea automaticamente
        token e settings default (top-right, neon theme, tutte le stats visibili).
        """
        doc = await _get_or_init_config(str(user["_id"]))
        return _config_response(doc)

    @r.post("/token")
    async def rotate_token(user: dict = Depends(require_streamer_dep)):
        """Rigenera il token (invalida il vecchio URL). Utile se si e' condiviso per errore."""
        uid = str(user["_id"])
        new_token = secrets.token_urlsafe(24)
        await db.overlay_tokens.update_one(
            {"user_id": uid},
            {"$set": {
                "user_id": uid,
                "token": new_token,
                "rotated_at": _now_iso(),
            }},
            upsert=True,
        )
        doc = await db.overlay_tokens.find_one({"user_id": uid})
        # v0.7.7 Milestones: first overlay created
        try:
            from milestones import bump_counter
            await bump_counter(db, uid, "overlays_created", 1)
        except Exception:
            pass
        return _config_response(doc)

    @r.put("/config")
    async def update_config(body: OverlayConfigUpdate, user: dict = Depends(require_streamer_dep)):
        uid = str(user["_id"])
        update = {}
        if body.position is not None:
            if body.position not in _ALLOWED_POSITIONS:
                raise HTTPException(status_code=400, detail=f"position deve essere uno di {sorted(_ALLOWED_POSITIONS)}")
            update["position"] = body.position
        if body.theme is not None:
            if body.theme not in _ALLOWED_THEMES:
                raise HTTPException(status_code=400, detail=f"theme deve essere uno di {sorted(_ALLOWED_THEMES)}")
            update["theme"] = body.theme
        if body.layout is not None:
            if body.layout not in _ALLOWED_LAYOUTS:
                raise HTTPException(status_code=400, detail=f"layout deve essere uno di {sorted(_ALLOWED_LAYOUTS)}")
            update["layout"] = body.layout
        if body.size is not None:
            if body.size not in _ALLOWED_SIZES:
                raise HTTPException(status_code=400, detail=f"size deve essere uno di {sorted(_ALLOWED_SIZES)}")
            update["size"] = body.size
        if body.accent is not None:
            if body.accent == "":
                update["accent"] = None
            elif _HEX_RE.match(body.accent):
                update["accent"] = body.accent.upper()
            else:
                raise HTTPException(status_code=400, detail="accent deve essere un colore hex #RRGGBB")
        for k in ("show_fps", "show_cpu", "show_gpu", "show_ping", "show_health"):
            v = getattr(body, k)
            if v is not None:
                update[k] = bool(v)
        if body.source_device is not None:
            if body.source_device == "":
                update["source_device"] = None
            else:
                from devices import slug_device
                did = slug_device(body.source_device)
                if not await db.devices.find_one({"user_id": uid, "device_id": did}, {"_id": 1}):
                    raise HTTPException(status_code=400, detail="Device non trovato")
                update["source_device"] = did
        if not update:
            raise HTTPException(status_code=400, detail="Nessun campo da aggiornare")
        # Ensure config exists first
        await _get_or_init_config(uid)
        await db.overlay_tokens.update_one({"user_id": uid}, {"$set": update})
        doc = await db.overlay_tokens.find_one({"user_id": uid})
        return _config_response(doc)

    # -------- PUBLIC endpoints (no auth, token = capability) ------------------
    @r.get("/{token}/data")
    async def overlay_data(token: str):
        """Ritorna l'ultimo sample telemetry + health score dell'utente
        associato al token. Cache: no-cache (browser deve pollare fresco)."""
        cfg = await db.overlay_tokens.find_one({"token": token})
        if not cfg:
            raise HTTPException(status_code=404, detail="Overlay non trovato")
        uid = cfg["user_id"]
        # Multi-PC: l'overlay puo' essere alimentato da un PC specifico (source_device),
        # altrimenti dal PC attivo/primario dell'utente.
        from devices import get_active_device
        _src = cfg.get("source_device") or await get_active_device(db, uid)
        _tf = {"user_id": uid, **({"device_id": _src} if _src else {})}
        # Ultimo sample telemetry — l'agent PS emette chiavi diverse dal nostro naming:
        #   cpu_util, gpu_util, ram_used_pct (non cpu_pct/gpu_pct/ram_pct)
        # Facciamo il mapping qui.
        tel = await db.pc_telemetry.find_one(_tf, {"_id": 0, "samples": {"$slice": -1}, "updated_at": 1})
        last = None
        stale_seconds = None
        if tel and tel.get("samples"):
            last = tel["samples"][-1]
            # Stale check: se l'ultimo sample e' > 10s fa, consideriamo il monitor "off"
            try:
                sample_ts = last.get("ts")
                if sample_ts:
                    from dateutil import parser as _p
                    ts_dt = _p.parse(sample_ts)
                    if ts_dt.tzinfo is None:
                        ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                    stale_seconds = int((datetime.now(timezone.utc) - ts_dt).total_seconds())
            except Exception:
                stale_seconds = None
        is_live = last is not None and (stale_seconds is None or stale_seconds < 15)
        # Ultimo ping_ms dal net_results o benchmark
        ping_ms = None
        try:
            net = await db.net_results.find_one(_tf, {"_id": 0, "result.idle_ms": 1})
            if net and net.get("result", {}).get("idle_ms") is not None:
                ping_ms = int(net["result"]["idle_ms"])
        except Exception:
            pass
        # Ultimo health score
        health = await db.health_history.find_one(_tf, {"_id": 0, "score": 1, "grade": 1}, sort=[("created_at", -1)])
        payload = {
            "fps": (last or {}).get("fps"),
            # Mapping dai campi ps_agent -> overlay
            "cpu_pct": (last or {}).get("cpu_util"),
            "gpu_pct": (last or {}).get("gpu_util"),
            "cpu_temp": (last or {}).get("cpu_temp"),
            "gpu_temp": (last or {}).get("gpu_temp"),
            "ram_pct": (last or {}).get("ram_used_pct"),
            "ping_ms": ping_ms,
            "health_score": (health or {}).get("score"),
            "health_grade": (health or {}).get("grade"),
            "ts": (last or {}).get("ts"),
            "stale_seconds": stale_seconds,
            "live": is_live,
        }
        return JSONResponse(payload, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

    @r.get("/{token}", response_class=HTMLResponse)
    async def overlay_page(token: str):
        """HTML page per OBS Browser Source. Transparent bg + auto-poll ogni 1s."""
        cfg = await db.overlay_tokens.find_one({"token": token})
        if not cfg:
            # Fallback: token non valido -> pagina di aiuto invece di 404 secco
            # (OBS mostrerebbe una schermata vuota; meglio dare feedback all'utente)
            help_html = """<!doctype html>
<html><head><meta charset="utf-8"><title>FrameForge Overlay - Token non valido</title>
<style>
  html, body { margin:0; padding:0; background:transparent; font-family:'Consolas','Monaco','Courier New',monospace; overflow:hidden; }
  body { display:flex; justify-content:flex-start; align-items:flex-start; min-height:100vh; padding:16px; box-sizing:border-box; }
  .err { background:rgba(139,0,0,0.85); border-left:3px solid #FF3B30; padding:12px 16px; color:#F4F4F5; font-size:12px; min-width:260px; }
  .err .brand { font-size:9px; text-transform:uppercase; letter-spacing:2px; color:#FF3B30; font-weight:900; margin-bottom:8px; }
  .err b { color:#FFB6B6; }
</style></head>
<body>
<div class="err">
  <div class="brand">// FRAMEFORGE - ERRORE</div>
  <div>Token overlay <b>non valido o scaduto</b>.</div>
  <div style="margin-top:6px;opacity:0.8;">Vai su <b>forgefps.dev/app/live</b>, rigenera il token e aggiorna l'URL in OBS.</div>
</div>
</body></html>"""
            return HTMLResponse(help_html, status_code=200, headers={
                "Cache-Control": "no-store, no-cache",
                "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline';",
            })

        position = cfg.get("position", "top-right")
        theme = cfg.get("theme", "neon")
        layout = cfg.get("layout", "card")
        size = cfg.get("size", "medium")
        accent_override = cfg.get("accent")
        show_fps = cfg.get("show_fps", True)
        show_cpu = cfg.get("show_cpu", True)
        show_gpu = cfg.get("show_gpu", True)
        show_ping = cfg.get("show_ping", True)
        show_health = cfg.get("show_health", True)

        # Position -> flex alignment
        pos_map = {
            "top-left":     ("flex-start", "flex-start"),
            "top-right":    ("flex-start", "flex-end"),
            "bottom-left":  ("flex-end",   "flex-start"),
            "bottom-right": ("flex-end",   "flex-end"),
        }
        vert, horiz = pos_map.get(position, ("flex-start", "flex-end"))

        # Theme palette (bg, accent, accent-glow, border-accent-alpha, secondary-text)
        theme_map = {
            "neon": {
                "bg": "rgba(10,10,15,0.88)",
                "accent": "#E5FF00",
                "accent_glow": "rgba(229,255,0,0.35)",
                "border": "rgba(229,255,0,0.35)",
                "text": "#F4F4F5",
                "muted": "#71717A",
                "trim": "#0F0F12",
            },
            "dark": {
                "bg": "rgba(6,6,10,0.92)",
                "accent": "#00E0FF",
                "accent_glow": "rgba(0,224,255,0.30)",
                "border": "rgba(0,224,255,0.30)",
                "text": "#E4E4E7",
                "muted": "#52525B",
                "trim": "#0A0A10",
            },
            "minimal": {
                "bg": "rgba(0,0,0,0.55)",
                "accent": "#FFFFFF",
                "accent_glow": "rgba(255,255,255,0.20)",
                "border": "rgba(255,255,255,0.18)",
                "text": "#F4F4F5",
                "muted": "#A1A1AA",
                "trim": "transparent",
            },
        }
        c = theme_map.get(theme, theme_map["neon"])
        if accent_override and _HEX_RE.match(accent_override):
            c = dict(c)
            c["accent"] = accent_override
            c["accent_glow"] = _hex_rgba(accent_override, 0.35)
            c["border"] = _hex_rgba(accent_override, 0.35)
        zoom = {"small": 0.85, "medium": 1.0, "large": 1.35}.get(size, 1.0)

        # Build metric rows dynamically. Each has: key, label, icon SVG path, unit, whether it takes a temp badge.
        ICONS = {
            "fps": "M8 5v14l11-7L8 5z",  # play
            "cpu_pct": "M4 4h16v16H4V4zm2 2v12h12V6H6zm2 2h8v2H8V8zm0 3h8v2H8v-2zm0 3h5v2H8v-2z",  # chip
            "gpu_pct": "M2 4h20v14H2V4zm2 2v10h16V6H4zm2 2h4v2H6V8zm6 0h6v2h-6V8zM6 12h4v2H6v-2zm6 0h6v2h-6v-2z",  # gpu
            "ping_ms": "M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm1 15h-2v-2h2v2zm2.07-7.75-.9.92C13.45 10.9 13 11.5 13 13h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z",  # help/signal
            "health_score": "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",  # heart
        }
        METRIC_META = [
            ("fps", "FPS", "", "", show_fps, False),
            ("cpu_pct", "CPU", "%", "cpu_temp", show_cpu, True),
            ("gpu_pct", "GPU", "%", "gpu_temp", show_gpu, True),
            ("ping_ms", "PING", "ms", "", show_ping, False),
            ("health_score", "HEALTH", "", "", show_health, False),
        ]
        rows_html = []
        for key, lbl, unit, temp_key, show, has_bar in METRIC_META:
            if not show:
                continue
            icon_path = ICONS.get(key, "")
            temp_span = f'<span class="temp" data-field="{temp_key}"></span>' if temp_key else ""
            unit_span = f'<span class="unit">{unit}</span>' if unit else ""
            bar_span = f'<div class="bar-track"><div class="bar-fill" data-bar="{key}"></div></div>' if has_bar else ""
            rows_html.append(
                f'<div class="metric" data-metric="{key}">'
                f'<svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="{icon_path}"/></svg>'
                f'<div class="label">{lbl}</div>'
                f'<div class="value"><span class="num" data-field="{key}">--</span>{unit_span}{temp_span}</div>'
                f'{bar_span}'
                f'</div>'
            )
        rows_str = "\n".join(rows_html)

        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>FrameForge Overlay</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin:0; padding:0; background:transparent !important; overflow:hidden;
                font-family: 'Segoe UI', 'SF Pro Display', system-ui, -apple-system, sans-serif; }}
  body {{ display:flex; justify-content:{horiz}; align-items:{vert};
          min-height:100vh; padding:8px; }}
  .card {{
    background: {c['bg']};
    border: 1px solid {c['border']};
    border-left: 3px solid {c['accent']};
    padding: 10px 12px 8px 12px;
    color: {c['text']};
    min-width: 220px;
    max-width: calc(100vw - 16px);
    backdrop-filter: blur(10px) saturate(120%);
    -webkit-backdrop-filter: blur(10px) saturate(120%);
    box-shadow:
      0 8px 32px rgba(0,0,0,0.55),
      0 0 40px {c['accent_glow']};
    position: relative;
  }}
  .card::before {{
    content: '';
    position: absolute; top:0; left:0; width:100%; height:2px;
    background: linear-gradient(90deg, transparent, {c['accent']}, transparent);
    opacity: 0.7;
  }}
  .header {{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom: 6px;
    padding-bottom: 5px;
    border-bottom: 1px solid {c['border']};
  }}
  .brand {{
    font-family: 'Consolas','Monaco','Courier New',monospace;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: {c['accent']};
    text-shadow: 0 0 8px {c['accent_glow']};
  }}
  .status {{
    display:inline-flex; align-items:center; gap: 5px;
    font-family: 'Consolas','Monaco','Courier New',monospace;
    font-size: 8px; font-weight: 700; letter-spacing: 1.2px;
    color: {c['muted']};
    text-transform: uppercase;
  }}
  .status .dot {{
    width: 6px; height: 6px; border-radius: 50%;
    background: {c['muted']};
    box-shadow: 0 0 4px transparent;
    transition: all 0.25s ease;
  }}
  .card.live .status {{ color: #00FF66; }}
  .card.live .status .dot {{
    background: #00FF66;
    box-shadow: 0 0 8px rgba(0,255,102,0.8);
    animation: pulse 1.6s ease-in-out infinite;
  }}
  .card.offline .status {{ color: #FF9500; }}
  .card.offline .status .dot {{ background: #FF9500; box-shadow: 0 0 6px rgba(255,149,0,0.6); animation: pulse 2s ease-in-out infinite; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}

  .metric {{
    display: grid;
    grid-template-columns: 14px 38px 1fr;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
    position: relative;
  }}
  .metric .icon {{
    width: 12px; height: 12px;
    color: {c['muted']};
    transition: color 0.3s ease;
  }}
  .card.live .metric .icon {{ color: {c['accent']}; opacity: 0.85; }}
  .metric .label {{
    font-family: 'Consolas','Monaco','Courier New',monospace;
    font-size: 9px;
    letter-spacing: 1.2px;
    font-weight: 700;
    color: {c['muted']};
    text-transform: uppercase;
  }}
  .metric .value {{
    display:flex; align-items: baseline; gap: 4px;
    justify-content: flex-end;
  }}
  .metric .num {{
    font-family: 'Consolas','Monaco','Courier New',monospace;
    font-size: 16px;
    font-weight: 700;
    color: {c['accent']};
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.5px;
    line-height: 1;
    transition: color 0.3s ease, transform 0.2s ease;
  }}
  .metric .num.pop {{ transform: scale(1.08); }}
  .metric .unit {{
    font-family: 'Consolas','Monaco','Courier New',monospace;
    font-size: 10px;
    font-weight: 500;
    color: {c['muted']};
  }}
  .metric .temp {{
    display:inline-block;
    margin-left: 4px;
    padding: 1px 5px;
    font-family: 'Consolas','Monaco','Courier New',monospace;
    font-size: 9px;
    font-weight: 600;
    background: {c['trim']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 2px;
    opacity: 0.9;
  }}
  .metric .temp:empty {{ display:none; }}
  .metric .temp.hot {{ background: rgba(255,59,48,0.2); color: #FF3B30; border-color: rgba(255,59,48,0.4); }}
  .metric .num.waiting {{ color: {c['muted']}; font-weight: 400; }}
  .bar-track {{
    grid-column: 1 / -1;
    height: 3px;
    background: {c['trim']};
    border-radius: 2px;
    overflow: hidden;
    margin-top: -2px;
  }}
  .bar-fill {{
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, {c['accent']}, {c['accent']}88);
    box-shadow: 0 0 6px {c['accent_glow']};
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .bar-fill.warn {{ background: linear-gradient(90deg, #FF9500, #FF3B30); box-shadow: 0 0 6px rgba(255,149,0,0.4); }}

  /* Theme-specific tweaks */
  {"" if theme != "minimal" else ".card { border-left: none; } .card::before { display: none; }"}

  /* Size (nativo, piu' nitido dello scaling OBS) */
  .card {{ zoom: {zoom}; }}

  /* Layout "bar": ticker orizzontale compatto */
  {'''
  .card { display: flex; align-items: center; gap: 18px; padding: 7px 16px;
          min-width: 0; width: max-content;
          border-left: 1px solid ''' + c['border'] + '''; border-top: 3px solid ''' + c['accent'] + '''; }
  .header { margin: 0; padding: 0; border-bottom: none; gap: 8px; flex-shrink: 0; }
  .metric { display: flex; grid-template-columns: none; align-items: baseline; gap: 7px; padding: 0; flex-shrink: 0; }
  .metric .icon { display: none; }
  .metric .label { font-size: 8px; }
  .metric .value { justify-content: flex-start; }
  .bar-track { display: none; }
  ''' if layout == "bar" else ""}
</style></head>
<body>
<div class="card" id="ovl">
  <div class="header">
    <div class="brand">// FRAMEFORGE</div>
    <div class="status"><span class="dot"></span><span class="txt">CONNECTING</span></div>
  </div>
  {rows_str}
</div>
<script>
  const TOKEN = {token!r};
  const DATA_URL = window.location.origin + '/api/overlay/' + TOKEN + '/data';
  const card = document.getElementById('ovl');
  const statusTxt = card.querySelector('.status .txt');
  const prevVals = {{}};
  async function tick() {{
    try {{
      const r = await fetch(DATA_URL, {{ cache: 'no-store' }});
      if (!r.ok) throw new Error('http ' + r.status);
      const d = await r.json();
      card.classList.toggle('live', d.live);
      card.classList.toggle('offline', !d.live);
      statusTxt.textContent = d.live ? 'LIVE' : 'MONITOR OFF';
      card.querySelectorAll('.metric').forEach(row => {{
        const metric = row.dataset.metric;
        const numEl = row.querySelector('[data-field="' + metric + '"]');
        const v = d[metric];
        if (numEl) {{
          if (v == null) {{
            numEl.textContent = '--';
            numEl.classList.add('waiting');
          }} else {{
            const rounded = (metric === 'cpu_pct' || metric === 'gpu_pct' || metric === 'ram_pct') ? Math.round(v) : v;
            const prev = prevVals[metric];
            if (prev != null && prev !== rounded) {{
              numEl.classList.add('pop');
              setTimeout(() => numEl.classList.remove('pop'), 220);
            }}
            numEl.textContent = rounded;
            numEl.classList.remove('waiting');
            prevVals[metric] = rounded;
          }}
        }}
        // Temp badge
        const tempEl = row.querySelector('.temp');
        if (tempEl) {{
          const tf = tempEl.dataset.field;
          const tv = d[tf];
          if (tv == null || tv === 0) {{
            tempEl.textContent = '';
          }} else {{
            tempEl.textContent = tv + '°C';
            tempEl.classList.toggle('hot', tv >= 80);
          }}
        }}
        // Bar
        const barEl = row.querySelector('.bar-fill');
        if (barEl) {{
          const bv = (v == null) ? 0 : Math.min(100, Math.max(0, v));
          barEl.style.width = bv + '%';
          barEl.classList.toggle('warn', bv >= 85);
        }}
      }});
    }} catch (e) {{
      card.classList.remove('live');
      card.classList.add('offline');
      statusTxt.textContent = 'NO CONNECTION';
    }}
  }}
  tick();
  setInterval(tick, 1000);
</script>
</body></html>"""
        return HTMLResponse(html, headers={
            "Cache-Control": "no-store, no-cache",
            # CSP permissivo per l'overlay: serve inline style + script.
            # Nessuna risorsa esterna (solo self + inline).
            "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self' data:;",
        })

    return r
