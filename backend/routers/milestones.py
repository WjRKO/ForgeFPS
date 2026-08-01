"""FrameForge Milestones router — /api/milestones/*
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import HTMLResponse

from database import db
from milestones import (
    MILESTONES_CATALOG,
    MILESTONE_BY_CODE,
    _ensure_progress_doc,
    dismiss_notification,
    enrich_catalog_for_user,
    check_beta_tester,
    xp_to_tier,
)


def build(get_current_user):
    r = APIRouter(prefix="/api/milestones", tags=["milestones"])

    _rarity_cache = {"at": 0.0, "data": {}}

    async def _get_rarity():
        """% di utenti flotta che hanno sbloccato ogni milestone. Cache 1h."""
        import time
        if time.time() - _rarity_cache["at"] < 3600:
            return _rarity_cache["data"]
        total = max(await db.user_progress.count_documents({}), 1)
        data = {}
        async for row in db.user_progress.aggregate([
            {"$unwind": "$unlocked"},
            {"$group": {"_id": "$unlocked", "n": {"$sum": 1}}},
        ]):
            data[row["_id"]] = round(100 * row["n"] / total, 1)
        _rarity_cache["at"] = time.time()
        _rarity_cache["data"] = data
        return data

    @r.get("")
    async def list_milestones(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        # Beta tester check (idempotent, safe to run every call)
        await check_beta_tester(db, uid, user.get("created_at"))
        progress = await _ensure_progress_doc(db, uid)
        catalog = enrich_catalog_for_user(progress)
        rarity = await _get_rarity()
        masked = []
        for m in catalog:
            m["rarity_pct"] = rarity.get(m["code"])
            if m.get("secret") and not m["unlocked"]:
                # Non rivelare nome/descrizione dei segreti bloccati
                m = {**m, "name_it": "???", "name_en": "???",
                     "desc_it": "Trofeo segreto — continua a usare FrameForge per scoprirlo.",
                     "desc_en": "Secret trophy — keep using FrameForge to discover it.",
                     "icon": "Lock", "progress": 0, "threshold": 1, "reward": None}
            masked.append(m)
        return {
            "xp": int(progress.get("xp", 0)),
            "tier": progress.get("tier", "bronze"),
            "unlocked_count": len(progress.get("unlocked", []) or []),
            "total_count": len(MILESTONES_CATALOG),
            "milestones": masked,
            "features": progress.get("features", {}) or {},
        }

    @r.get("/me")
    async def me_summary(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        await check_beta_tester(db, uid, user.get("created_at"))
        progress = await _ensure_progress_doc(db, uid)
        pending = list(progress.get("pending_notify", []) or [])
        pending_full = [
            {**MILESTONE_BY_CODE[c], "unlocked_at": (progress.get("unlocked_at") or {}).get(c)}
            for c in pending if c in MILESTONE_BY_CODE
        ]
        xp = int(progress.get("xp", 0))
        tier = progress.get("tier") or xp_to_tier(xp)
        # Next tier progress bar helper
        thresholds = {"bronze": 100, "silver": 300, "gold": 800, "platinum": 800}
        next_target = thresholds.get(tier, 800)
        return {
            "xp": xp,
            "tier": tier,
            "next_tier_at": next_target,
            "unlocked_count": len(progress.get("unlocked", []) or []),
            "total_count": len(MILESTONES_CATALOG),
            "features": progress.get("features", {}) or {},
            "pending_notify": pending_full,
        }

    @r.post("/dismiss/{code}")
    async def dismiss(code: str = Path(...), user: dict = Depends(get_current_user)):
        if code not in MILESTONE_BY_CODE:
            raise HTTPException(404, "unknown milestone")
        uid = str(user["_id"])
        await dismiss_notification(db, uid, code, "dashboard")
        return {"ok": True}

    # ---------------- OBS overlay milestone popup ----------------
    # Public endpoint by design (like /api/overlay/{token}): OBS Browser Source
    # cannot send Authorization headers, so auth is via the token itself which
    # comes from agent_tokens (already scoped per-user).
    @r.get("/overlay/{token}/poll")
    async def overlay_poll(token: str):
        """Returns the next pending unlock (if any). OBS polls this every ~3s."""
        at = await db.agent_tokens.find_one({"token": token})
        if not at:
            raise HTTPException(404, "invalid token")
        uid = str(at.get("user_id"))
        progress = await db.user_progress.find_one({"user_id": uid})
        if not progress:
            return {"unlock": None}
        pending = list(progress.get("obs_pending", []) or [])
        if not pending:
            return {"unlock": None}
        code = pending[0]
        # Auto-dismiss so we don't repeat (fire once)
        await dismiss_notification(db, uid, code, "obs")
        m = MILESTONE_BY_CODE.get(code)
        if not m:
            return {"unlock": None}
        return {
            "unlock": {
                "code": m["code"],
                "name": m.get("name_en") or m.get("name_it"),
                "desc": m.get("desc_en") or m.get("desc_it"),
                "tier": m.get("tier"),
                "xp": m.get("xp"),
                "icon": m.get("icon"),
            }
        }

    @r.get("/overlay/{token}", response_class=HTMLResponse)
    async def overlay_html(token: str):
        """Standalone OBS Browser Source HTML — polls /poll and shows 5s
        animated popup on unlock. Loops silently otherwise."""
        at = await db.agent_tokens.find_one({"token": token})
        if not at:
            raise HTTPException(404, "invalid token")
        # HTML is self-contained: minimal deps, no external CDN, streamer-friendly transparent background.
        html = _OVERLAY_HTML.replace("__TOKEN__", token)
        return HTMLResponse(content=html)

    return r


_OVERLAY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>FrameForge Milestone Overlay</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; height: 100%; background: transparent; font-family: 'Segoe UI', -apple-system, sans-serif; overflow: hidden; }
#stage { position: fixed; inset: 0; display: flex; align-items: flex-start; justify-content: flex-end; padding: 32px; pointer-events: none; }
.card { position: relative; display: flex; align-items: center; gap: 16px; min-width: 380px; max-width: 520px;
  padding: 18px 22px; background: linear-gradient(135deg, #0F0F12 0%, #1A1A24 100%);
  border: 2px solid #E5FF00; box-shadow: 0 0 0 4px rgba(229,255,0,0.15), 0 12px 40px rgba(0,0,0,0.6);
  opacity: 0; transform: translateX(80px) scale(0.95); transition: opacity 320ms ease, transform 420ms cubic-bezier(0.2, 0.9, 0.3, 1.3);
}
.card.show { opacity: 1; transform: translateX(0) scale(1); }
.card.leave { opacity: 0; transform: translateX(80px) scale(0.95); }
.card.tier-silver { border-color: #B0B7C3; box-shadow: 0 0 0 4px rgba(176,183,195,0.18), 0 12px 40px rgba(0,0,0,0.6); }
.card.tier-gold { border-color: #FFB800; box-shadow: 0 0 0 4px rgba(255,184,0,0.2), 0 12px 40px rgba(0,0,0,0.6); }
.card.tier-platinum { border-color: #00E0FF; box-shadow: 0 0 0 4px rgba(0,224,255,0.22), 0 12px 40px rgba(0,0,0,0.6); }
.badge {
  width: 60px; height: 60px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  border: 2px solid currentColor; color: #E5FF00; font-size: 28px; font-weight: 900;
  background: rgba(0,0,0,0.4);
}
.card.tier-silver .badge { color: #B0B7C3; }
.card.tier-gold .badge { color: #FFB800; }
.card.tier-platinum .badge { color: #00E0FF; }
.body { flex: 1; min-width: 0; color: #fff; }
.eyebrow { font-size: 10px; font-weight: 900; letter-spacing: 3px; text-transform: uppercase; color: currentColor; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
.eyebrow .dot { width: 8px; height: 8px; background: #00FF66; border-radius: 50%; animation: pulse 1.6s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
.title { font-size: 22px; font-weight: 900; line-height: 1.1; margin-bottom: 4px; letter-spacing: -0.3px; }
.desc { font-size: 12px; color: #A0A0B0; line-height: 1.35; }
.xp { position: absolute; top: -12px; right: 12px; padding: 2px 10px; background: #000; border: 2px solid currentColor; color: currentColor; font-size: 11px; font-weight: 900; letter-spacing: 2px; }
</style>
</head>
<body>
<div id="stage"></div>
<script>
(function(){
  var TOKEN = "__TOKEN__";
  var stage = document.getElementById("stage");
  var busy = false;
  function tierColor(t){ return "tier-" + (t || "bronze"); }
  function iconChar(name){
    // lightweight glyphs mapped from lucide icon names (avoid CDN dependency)
    var map = { Search:'\u26B2', Sparkles:'\u2728', Zap:'\u26A1', Radio:'\u25CF',
      Wrench:'\u1F527', Cpu:'CPU', Activity:'\u26A1', HeartPulse:'\u2661',
      Gamepad2:'\u2660', Library:'\u25A6', Clock:'\u25CB', Timer:'\u25CF',
      Crown:'\u2655', Star:'\u2605' };
    return map[name] || '\u2605';
  }
  function show(u){
    if (busy) return;
    busy = true;
    var card = document.createElement("div");
    card.className = "card " + tierColor(u.tier);
    card.innerHTML =
      '<div class="badge">' + iconChar(u.icon) + '</div>' +
      '<div class="body">' +
        '<div class="eyebrow"><span class="dot"></span> Milestone Unlocked</div>' +
        '<div class="title">' + escapeHtml(u.name) + '</div>' +
        '<div class="desc">' + escapeHtml(u.desc) + '</div>' +
      '</div>' +
      '<div class="xp">+' + (u.xp||0) + ' XP</div>';
    stage.appendChild(card);
    requestAnimationFrame(function(){ card.classList.add("show"); });
    setTimeout(function(){
      card.classList.remove("show");
      card.classList.add("leave");
      setTimeout(function(){ card.remove(); busy = false; }, 500);
    }, 6000);
  }
  function escapeHtml(s){ return String(s||"").replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }
  function poll(){
    fetch('/api/milestones/overlay/' + TOKEN + '/poll', { cache: 'no-store' })
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(j){ if (j && j.unlock) show(j.unlock); })
      .catch(function(){});
  }
  setInterval(poll, 3000);
  poll();
})();
</script>
</body>
</html>
"""
