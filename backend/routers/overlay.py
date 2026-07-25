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


class OverlayConfigUpdate(BaseModel):
    position: Optional[str] = Field(default=None)
    theme: Optional[str] = Field(default=None)
    show_fps: Optional[bool] = None
    show_cpu: Optional[bool] = None
    show_gpu: Optional[bool] = None
    show_ping: Optional[bool] = None
    show_health: Optional[bool] = None


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
            "show_fps": doc.get("show_fps", True),
            "show_cpu": doc.get("show_cpu", True),
            "show_gpu": doc.get("show_gpu", True),
            "show_ping": doc.get("show_ping", True),
            "show_health": doc.get("show_health", True),
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
        for k in ("show_fps", "show_cpu", "show_gpu", "show_ping", "show_health"):
            v = getattr(body, k)
            if v is not None:
                update[k] = bool(v)
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
        # Ultimo sample telemetry
        tel = await db.pc_telemetry.find_one({"user_id": uid}, {"_id": 0, "samples": {"$slice": -1}})
        last = None
        if tel and tel.get("samples"):
            last = tel["samples"][-1]
        # Ultimo health score
        health = await db.health_history.find_one({"user_id": uid}, {"_id": 0, "score": 1, "grade": 1}, sort=[("created_at", -1)])
        payload = {
            "fps": (last or {}).get("fps"),
            "cpu_pct": (last or {}).get("cpu_pct"),
            "gpu_pct": (last or {}).get("gpu_pct"),
            "cpu_temp": (last or {}).get("cpu_temp"),
            "gpu_temp": (last or {}).get("gpu_temp"),
            "ram_pct": (last or {}).get("ram_pct"),
            "ping_ms": (last or {}).get("ping_ms"),
            "health_score": (health or {}).get("score"),
            "health_grade": (health or {}).get("grade"),
            "ts": (last or {}).get("ts"),
            "live": last is not None,
        }
        return JSONResponse(payload, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

    @r.get("/{token}", response_class=HTMLResponse)
    async def overlay_page(token: str):
        """HTML page per OBS Browser Source. Transparent bg + auto-poll ogni 1s."""
        cfg = await db.overlay_tokens.find_one({"token": token})
        if not cfg:
            raise HTTPException(status_code=404, detail="Overlay non trovato")

        position = cfg.get("position", "top-right")
        theme = cfg.get("theme", "neon")
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

        # Theme -> colors
        theme_map = {
            "neon":    {"bg": "rgba(10,10,15,0.72)", "border": "#E5FF00", "accent": "#E5FF00", "text": "#F4F4F5"},
            "minimal": {"bg": "rgba(0,0,0,0.55)",   "border": "#FFFFFF33", "accent": "#FFFFFF", "text": "#FFFFFF"},
            "dark":    {"bg": "rgba(0,0,0,0.85)",   "border": "#00E0FF", "accent": "#00E0FF", "text": "#F4F4F5"},
        }
        c = theme_map.get(theme, theme_map["neon"])

        rows = []
        if show_fps:    rows.append(("FPS",    "fps",         "",  ""))
        if show_cpu:    rows.append(("CPU",    "cpu_pct",     "%", "cpu_temp"))
        if show_gpu:    rows.append(("GPU",    "gpu_pct",     "%", "gpu_temp"))
        if show_ping:   rows.append(("PING",   "ping_ms",     " ms", ""))
        if show_health: rows.append(("HEALTH", "health_score", "/100", ""))

        rows_html = "\n".join(
            f'<div class="row" data-metric="{key}"><span class="lbl">{lbl}</span>'
            f'<span class="val"><span data-field="{key}">--</span><span class="u">{unit}</span>'
            + (f'<span class="tmp" data-field="{temp_field}"></span>' if temp_field else '')
            + '</span></div>'
            for lbl, key, unit, temp_field in rows
        )

        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>FrameForge Overlay</title>
<style>
  html, body {{ margin:0; padding:0; background:transparent; font-family:'JetBrains Mono', monospace; overflow:hidden; }}
  body {{ display:flex; justify-content:{horiz}; align-items:{vert}; min-height:100vh; padding:16px; box-sizing:border-box; }}
  .card {{
    background:{c['bg']}; border-left:3px solid {c['border']}; padding:10px 14px;
    color:{c['text']}; font-size:13px; letter-spacing:0.5px;
    backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
    min-width:150px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }}
  .brand {{ font-size:9px; text-transform:uppercase; letter-spacing:2px; color:{c['accent']}; opacity:0.9; margin-bottom:6px; font-weight:900; }}
  .row {{ display:flex; justify-content:space-between; align-items:baseline; padding:2px 0; gap:16px; }}
  .lbl {{ opacity:0.7; font-size:10px; text-transform:uppercase; letter-spacing:1.5px; }}
  .val {{ font-weight:700; font-size:14px; color:{c['accent']}; font-variant-numeric: tabular-nums; }}
  .val .u {{ opacity:0.6; font-size:10px; margin-left:2px; font-weight:500; }}
  .tmp {{ display:inline-block; margin-left:6px; padding:1px 5px; font-size:9px; background:rgba(255,255,255,0.08); color:{c['text']}; border-radius:2px; }}
  .tmp:empty {{ display:none; }}
  .offline {{ opacity:0.5; }}
  .offline .val {{ color:#71717A; }}
</style></head>
<body>
<div class="card" id="ovl">
  <div class="brand">// FRAMEFORGE</div>
  {rows_html}
</div>
<script>
  const TOKEN = {token!r};
  const DATA_URL = window.location.origin + '/api/overlay/' + TOKEN + '/data';
  const card = document.getElementById('ovl');
  async function tick() {{
    try {{
      const r = await fetch(DATA_URL, {{ cache: 'no-store' }});
      if (!r.ok) throw new Error('http ' + r.status);
      const d = await r.json();
      card.classList.toggle('offline', !d.live);
      const rows = card.querySelectorAll('.row');
      rows.forEach(row => {{
        const metric = row.dataset.metric;
        const valEl = row.querySelector('[data-field="' + metric + '"]');
        if (valEl) {{
          const v = d[metric];
          valEl.textContent = (v == null) ? '--' : (metric === 'gpu_pct' || metric === 'cpu_pct' || metric === 'ram_pct') ? Math.round(v) : v;
        }}
        // Temp badge (per CPU/GPU)
        const tempEl = row.querySelector('.tmp');
        if (tempEl) {{
          const tf = tempEl.dataset.field;
          const tv = d[tf];
          tempEl.textContent = (tv == null || tv === 0) ? '' : tv + '°C';
        }}
      }});
    }} catch (e) {{
      card.classList.add('offline');
    }}
  }}
  tick();
  setInterval(tick, 1000);
</script>
</body></html>"""
        return HTMLResponse(html, headers={"Cache-Control": "no-store, no-cache"})

    return r
