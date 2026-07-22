import uuid
import secrets
from datetime import datetime, timezone

import push
from database import db, now_iso
from scraper import scrape_product


# ---------- Hardware specs formatting ----------
def _line_with_extras(name: str, main: str, extras: list) -> str:
    return f"{name}: {main}" + (f" ({', '.join(extras)})" if extras else "")


def _cpu_line(d: dict) -> str:
    extras = []
    if d.get("cpu_cores"):
        extras.append(f"{d['cpu_cores']} core")
    if d.get("cpu_threads"):
        extras.append(f"{d['cpu_threads']} thread")
    if d.get("cpu_clock_ghz"):
        extras.append(f"{d['cpu_clock_ghz']} GHz")
    return _line_with_extras("CPU", d["cpu"], extras)


def _gpu_line(d: dict) -> str:
    extras = []
    if d.get("gpu_vram_gb"):
        extras.append(f"{d['gpu_vram_gb']} GB VRAM")
    if d.get("gpu_driver_version"):
        extras.append(f"driver {d['gpu_driver_version']}")
    return _line_with_extras("GPU", d["gpu"], extras)


def _ram_line(d: dict) -> str:
    extras = []
    if d.get("ram_type"):
        extras.append(d["ram_type"])
    if d.get("ram_speed_mhz"):
        extras.append(f"{d['ram_speed_mhz']} MHz")
    if d.get("ram_modules"):
        extras.append(f"{d['ram_modules']} moduli")
    return _line_with_extras("RAM", d["ram"], extras)


def _motherboard_line(d: dict) -> str:
    mb = d["motherboard"]
    if d.get("bios"):
        mb += f" [BIOS: {d['bios']}]"
    return f"Scheda madre (da WMI, può essere un codice OEM es. MS-7C56=MSI B550): {mb}"


def _platform_line(d: dict) -> str | None:
    parts = []
    if d.get("cpu_socket"):
        parts.append(f"socket {d['cpu_socket']}")
    if d.get("chipset"):
        parts.append(f"chipset {d['chipset']}")
    return "Piattaforma: " + ", ".join(parts) if parts else None


def _monitor_line(d: dict) -> str:
    res = d["resolution"]
    if d.get("refresh_hz"):
        res += f" @ {d['refresh_hz']}Hz"
    return f"Monitor: {res}"


def specs_to_text(specs: dict) -> str:
    if not specs:
        return ""
    d = specs.get("data", {})
    lines = []
    if d.get("os"):
        lines.append(f"OS: {d['os']}")
    if d.get("cpu"):
        lines.append(_cpu_line(d))
    if d.get("gpu"):
        lines.append(_gpu_line(d))
    if d.get("ram"):
        lines.append(_ram_line(d))
    if d.get("disk"):
        lines.append(f"Storage: {d['disk']}")
    if d.get("motherboard"):
        lines.append(_motherboard_line(d))
    platform = _platform_line(d)
    if platform:
        lines.append(platform)
    if d.get("system_model") and d["system_model"].lower() not in (d.get("motherboard", "").lower(), "system product name"):
        lines.append(f"Modello sistema: {d['system_model']}")
    if d.get("resolution"):
        lines.append(_monitor_line(d))
    return "\n".join(lines)


# ---------- Health score ----------
def days_since(date_str: str):
    try:
        d = datetime.fromisoformat(str(date_str)[:10]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days
    except Exception:
        return None


# Numeric checks: (id, label, weight, key, thresholds, fmt, fix, mkey, higher_bad)
# `key` is either the raw health field or a callable(health) returning the value.
_HEALTH_NUMERIC_CHECKS = [
    ("temp", "File temporanei", 8, "temp_mb", (1500, 5000),
     lambda v: f"{int(v)} MB",
     "Esegui la pulizia file temporanei (FrameForge Agent -> GUI)", "mb", True),
    ("startup", "Programmi all'avvio", 10, "startup_count", (8, 15),
     lambda v: f"{int(v)} programmi",
     "Disabilita gli avvii non essenziali (pagina 'Il mio PC')", "programs", True),
    ("ram", "Uso RAM", 10, "ram_used_pct", (80, 90),
     lambda v: f"{int(v)}% in uso",
     "Chiudi app in background o aggiungi RAM", "ram_pct", True),
    ("disk", "Spazio disco (C:)", 12, "disk_free_pct", (12, 6),
     lambda v: f"{int(v)}% libero",
     "Libera spazio: pulizia disco (FrameForge Agent -> GUI)", "disk_pct", False),
    ("driver", "Driver GPU", 12,
     lambda h: days_since(h["gpu_driver_date"]) if h.get("gpu_driver_date") else None,
     (180, 365),
     lambda v: f"aggiornato {int(v)} giorni fa",
     "Aggiorna i driver della GPU", "driver_days", True),
    ("gpu_temp", "Temperatura GPU", 12,
     lambda h: h["gpu_temp"] if (h.get("gpu_temp") is not None and h["gpu_temp"] > 0) else None,
     (75, 84), lambda v: f"{int(v)}°C",
     "Migliora airflow/curva ventole: rischio throttling", "temp_c", True),
    ("cpu_temp", "Temperatura CPU", 10,
     lambda h: h["cpu_temp"] if (h.get("cpu_temp") is not None and h["cpu_temp"] > 0) else None,
     (80, 89), lambda v: f"{int(v)}°C",
     "Verifica dissipatore/pasta termica: rischio throttling", "temp_c", True),
]

# Boolean toggle checks: (id, label, health_key, weight, fix)
_HEALTH_TOGGLE_CHECKS = [
    ("game_mode", "Game Mode", "game_mode", 8, "Attiva Game Mode (FrameForge Agent -> GUI)"),
    ("hags", "GPU Scheduling (HAGS)", "gpu_scheduling", 6, "Abilita HAGS (FrameForge Agent -> GUI)"),
]


def _numeric_status(value, thresholds, higher_bad):
    ok_t, warn_t = thresholds
    if higher_bad:
        return "ok" if value <= ok_t else ("warn" if value <= warn_t else "bad")
    return "ok" if value >= ok_t else ("warn" if value >= warn_t else "bad")


def _score_from_lost(lost: float, total_weight: float) -> tuple[int, str, str]:
    score = round(100 * (1 - (lost / total_weight))) if total_weight else 100
    score = max(0, min(100, score))
    grade_key = ("ottimo" if score >= 85 else "buono" if score >= 70
                 else "migliorare" if score >= 50 else "critico")
    grade = {"ottimo": "Ottimo", "buono": "Buono",
             "migliorare": "Da migliorare", "critico": "Critico"}[grade_key]
    return score, grade, grade_key


def compute_health(health: dict) -> dict:
    checks = []
    total_weight = 0.0
    lost = 0.0

    # Numeric checks via registry
    for cid, label, weight, key, thresholds, fmt, fix, mkey, higher_bad in _HEALTH_NUMERIC_CHECKS:
        value = key(health) if callable(key) else health.get(key)
        if value is None:
            checks.append({"id": cid, "label": label, "status": "unknown",
                           "message": "Dato non disponibile", "fix": None,
                           "mkey": "na", "mval": None})
            continue
        status = _numeric_status(value, thresholds, higher_bad)
        total_weight += weight
        if status == "bad":
            lost += weight
        elif status == "warn":
            lost += weight * 0.5
        checks.append({"id": cid, "label": label, "status": status,
                       "message": fmt(value),
                       "fix": None if status == "ok" else fix,
                       "mkey": mkey, "mval": int(value)})

    # Power plan (has custom string logic, kept inline)
    power = (health.get("power_plan") or "").lower()
    hp = any(x in power for x in ("high", "prestazioni elevate", "ultimate"))
    total_weight += 15
    if not hp:
        lost += 15
    checks.append({"id": "power", "label": "Piano energetico",
                   "status": "ok" if hp else "bad",
                   "message": "Alte prestazioni" if hp else "Non ottimale",
                   "fix": None if hp else "Attiva 'Alte prestazioni' (FrameForge Agent -> GUI)",
                   "mkey": "power_hp" if hp else "power_bad", "mval": None})

    # Boolean toggle checks via registry
    for cid, label, key, weight, fix in _HEALTH_TOGGLE_CHECKS:
        present = key in health
        val = bool(health.get(key))
        if present:
            total_weight += weight
            if not val:
                lost += weight
        checks.append({"id": cid, "label": label,
                       "status": ("ok" if val else "bad") if present else "unknown",
                       "message": ("Attivo" if val else "Disattivato") if present else "Dato non disponibile",
                       "fix": None if (val or not present) else fix,
                       "mkey": ("on" if val else "off") if present else "na", "mval": None})

    _gpu_t = next((c["mval"] for c in checks if c["id"] == "gpu_temp"), None)
    _cpu_t = next((c["mval"] for c in checks if c["id"] == "cpu_temp"), None)
    score, grade, grade_key = _score_from_lost(lost, total_weight)
    return {"score": score, "grade": grade, "grade_key": grade_key, "checks": checks,
            "driver_version": health.get("gpu_driver_version"),
            "gpu_temp": _gpu_t, "cpu_temp": _cpu_t,
            "gpu": health.get("gpu"), "updated_at": now_iso()}


def grade_bufferbloat(result: dict) -> dict:
    """Compute bufferbloat grade (A+..F) from idle vs loaded latency (Waveform-style)."""
    idle = result.get("idle_ms")
    down = result.get("down_ms")
    up = result.get("up_ms")
    incs = [x - idle for x in (down, up) if x is not None and idle is not None]
    inc = max(incs) if incs else None

    def grade_for(v):
        if v is None:
            return None
        if v <= 5: return "A+"
        if v <= 30: return "A"
        if v <= 60: return "B"
        if v <= 200: return "C"
        if v <= 400: return "D"
        return "F"

    bloat_grade = grade_for(inc)
    down_grade = grade_for(down - idle) if (down is not None and idle is not None) else None
    up_grade = grade_for(up - idle) if (up is not None and idle is not None) else None

    # Base latency quality (idle RTT to reference host)
    base = "great" if (idle is not None and idle <= 20) else "good" if (idle is not None and idle <= 50) else "fair" if (idle is not None and idle <= 100) else "poor"
    loss = result.get("loss_pct")
    return {
        **result,
        "bufferbloat_ms": round(inc) if inc is not None else None,
        "grade": bloat_grade,
        "down_grade": down_grade,
        "up_grade": up_grade,
        "base_quality": base,
        "loss_pct": loss,
    }



def pc_context_text(specs: dict) -> str:
    """Rich PC context for the AI Advisor: hardware + health + temps + benchmark + startup."""
    if not specs:
        return ""
    parts = [specs_to_text(specs)]
    health = specs.get("health")
    if health:
        h = compute_health(health)
        parts.append(f"\n[SALUTE PC] Health Score: {h['score']}/100 ({h['grade']}).")
        issues = [c for c in h["checks"] if c["status"] in ("warn", "bad")]
        if issues:
            parts.append("Problemi rilevati (usa questi per consigli mirati):")
            for c in issues:
                line = f"- {c['label']}: {c['message']}"
                if c.get("fix"):
                    line += f" -> {c['fix']}"
                parts.append(line)
        temps = []
        if h.get("cpu_temp") is not None:
            temps.append(f"CPU {h['cpu_temp']}°C")
        if h.get("gpu_temp") is not None:
            temps.append(f"GPU {h['gpu_temp']}°C")
        if temps:
            parts.append("Temperature: " + ", ".join(temps))
        if h.get("driver_version"):
            parts.append(f"Driver GPU installato: {h['driver_version']}")
    bench = specs.get("benchmark")
    if bench:
        a = bench.get("after") or bench
        if isinstance(a, dict) and a.get("overall") is not None:
            parts.append(f"\n[BENCHMARK] CPU {a.get('cpu_score')}, RAM {a.get('ram_mbps')} MB/s, "
                         f"Disco W/R {a.get('disk_write_mbps')}/{a.get('disk_read_mbps')} MB/s, "
                         f"Ping {a.get('ping_ms')} ms, punteggio totale {a.get('overall')}")
    startup = specs.get("startup")
    if startup:
        parts.append(f"\n[AVVIO] {len(startup)} programmi all'avvio: " + ", ".join(startup[:15]))
    # Benchmark trend history (ultimi 5)
    hist = specs.get("benchmark_history") or []
    if hist and len(hist) >= 2:
        latest = hist[0].get("after", {}).get("overall") or 0
        oldest = hist[-1].get("after", {}).get("overall") or 0
        if latest and oldest:
            delta = round(((latest - oldest) / oldest) * 100, 1)
            arrow = "in miglioramento" if delta > 0 else ("stabile" if -3 <= delta <= 3 else "in peggioramento")
            parts.append(
                f"\n[TREND BENCH] Ultimi {len(hist)} benchmark: {oldest} -> {latest} ({delta:+}%, {arrow})"
            )
    # Tracker
    tp = specs.get("tracker_summary")
    if tp:
        parts.append(
            f"\n[TRACKER] {tp.get('count', 0)} prodotti monitorati, "
            f"risparmio totale finora {tp.get('total_saved', 0)}€"
        )
    return "\n".join(p for p in parts if p)



# ---------- Product tracking helpers ----------
def record_history(product_id: str, price: float) -> dict:
    return {"product_id": product_id, "price": price, "recorded_at": now_iso()}


async def create_notification(user_id: str, product: dict, old_price, new_price, hit_target: bool):
    title = product.get("title")
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "user_id": user_id, "product_id": product["id"],
        "title": title, "old_price": old_price, "new_price": new_price,
        "currency": product.get("currency", "EUR"),
        "type": "target" if hit_target else "drop",
        "message": (f"Prezzo target raggiunto! Ora {new_price}" if hit_target
                    else f"Prezzo sceso da {old_price} a {new_price}"),
        "read": False, "created_at": now_iso()})
    await push.send_push_to_user(db, user_id, {
        "title": "🎯 Prezzo target!" if hit_target else "📉 Calo di prezzo!",
        "body": f"{title} → {new_price} {product.get('currency', 'EUR')}",
        "url": f"/app/tracker/{product['id']}"})


async def refresh_product_price(product: dict) -> dict:
    scraped = await scrape_product(product["url"])
    price = scraped.get("price")
    update = {"updated_at": now_iso(), "status": scraped.get("status"), "last_error": scraped.get("error")}
    if scraped.get("title") and product.get("title") == "Prodotto senza titolo":
        update["title"] = scraped["title"]
    if scraped.get("store") and not product.get("store"):
        update["store"] = scraped["store"]
    if scraped.get("image") and not product.get("image"):
        update["image"] = scraped["image"]
    notified = False
    if price is not None:
        old = product.get("current_price")
        update["current_price"] = price
        low = product.get("lowest_price")
        if low is None or price < low:
            update["lowest_price"] = price
        await db.price_history.insert_one(record_history(product["id"], price))
        target = product.get("target_price")
        dropped = old is not None and price < old
        hit_target = target is not None and price <= target
        if dropped or hit_target:
            merged = {**product, **update, "id": product["id"], "user_id": product["user_id"]}
            await create_notification(product["user_id"], merged, old, price, hit_target)
            notified = True
    await db.products.update_one({"id": product["id"]}, {"$set": update})
    update["notified"] = notified
    return update


async def track_components(uid: str, group: str, components: list) -> int:
    created = 0
    for c in components:
        name = c.get("name") or c.get("suggested")
        if not name:
            continue
        price = c.get("price")
        title = f"{c.get('category', '')}: {name}".strip(": ")
        existing = await db.products.find_one({"user_id": uid, "group": group, "title": title})
        if existing:
            await db.products.update_one({"id": existing["id"]},
                                         {"$set": {"current_price": price, "updated_at": now_iso()}})
            continue
        pid = str(uuid.uuid4())
        await db.products.insert_one({
            "id": pid, "user_id": uid, "url": "", "title": title,
            "platform": "build-component", "image": None, "currency": "EUR",
            "current_price": price, "initial_price": price, "lowest_price": price,
            "target_price": None, "status": "ok" if price is not None else "no_price",
            "last_error": None, "group": group,
            "created_at": now_iso(), "updated_at": now_iso()})
        if price is not None:
            await db.price_history.insert_one(record_history(pid, price))
        created += 1
    return created


async def get_or_create_agent_token(uid: str) -> str:
    rec = await db.agent_tokens.find_one({"user_id": uid})
    if rec:
        return rec["token"]
    token = secrets.token_urlsafe(24)
    await db.agent_tokens.insert_one({"user_id": uid, "token": token, "created_at": now_iso()})
    return token
