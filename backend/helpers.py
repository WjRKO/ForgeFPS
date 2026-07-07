import uuid
import secrets
from datetime import datetime, timezone

import push
from database import db, now_iso
from scraper import scrape_product


# ---------- Hardware specs formatting ----------
def specs_to_text(specs: dict) -> str:
    if not specs:
        return ""
    d = specs.get("data", {})
    lines = []
    if d.get("os"):
        lines.append(f"OS: {d['os']}")
    if d.get("cpu"):
        extra = []
        if d.get("cpu_cores"):
            extra.append(f"{d['cpu_cores']} core")
        if d.get("cpu_threads"):
            extra.append(f"{d['cpu_threads']} thread")
        if d.get("cpu_clock_ghz"):
            extra.append(f"{d['cpu_clock_ghz']} GHz")
        lines.append(f"CPU: {d['cpu']}" + (f" ({', '.join(extra)})" if extra else ""))
    if d.get("gpu"):
        g_extra = []
        if d.get("gpu_vram_gb"):
            g_extra.append(f"{d['gpu_vram_gb']} GB VRAM")
        if d.get("gpu_driver_version"):
            g_extra.append(f"driver {d['gpu_driver_version']}")
        lines.append(f"GPU: {d['gpu']}" + (f" ({', '.join(g_extra)})" if g_extra else ""))
    if d.get("ram"):
        r_extra = []
        if d.get("ram_type"):
            r_extra.append(d["ram_type"])
        if d.get("ram_speed_mhz"):
            r_extra.append(f"{d['ram_speed_mhz']} MHz")
        if d.get("ram_modules"):
            r_extra.append(f"{d['ram_modules']} moduli")
        lines.append(f"RAM: {d['ram']}" + (f" ({', '.join(r_extra)})" if r_extra else ""))
    if d.get("disk"):
        lines.append(f"Storage: {d['disk']}")
    if d.get("motherboard"):
        mb = d["motherboard"]
        if d.get("bios"):
            mb += f" [BIOS: {d['bios']}]"
        lines.append(f"Scheda madre (da WMI, può essere un codice OEM es. MS-7C56=MSI B550): {mb}")
    if d.get("chipset") or d.get("cpu_socket"):
        sc = []
        if d.get("cpu_socket"):
            sc.append(f"socket {d['cpu_socket']}")
        if d.get("chipset"):
            sc.append(f"chipset {d['chipset']}")
        lines.append("Piattaforma: " + ", ".join(sc))
    if d.get("system_model") and d["system_model"].lower() not in (d.get("motherboard", "").lower(), "system product name"):
        lines.append(f"Modello sistema: {d['system_model']}")
    if d.get("resolution"):
        res = d["resolution"]
        if d.get("refresh_hz"):
            res += f" @ {d['refresh_hz']}Hz"
        lines.append(f"Monitor: {res}")
    return "\n".join(lines)


# ---------- Health score ----------
def days_since(date_str: str):
    try:
        d = datetime.fromisoformat(str(date_str)[:10]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days
    except Exception:
        return None


def compute_health(health: dict) -> dict:
    checks = []
    total_weight = 0
    lost = 0.0

    def check(cid, label, weight, value, thresholds, fmt, fix, mkey, higher_bad=True, present=True):
        nonlocal total_weight, lost
        if not present or value is None:
            checks.append({"id": cid, "label": label, "status": "unknown",
                           "message": "Dato non disponibile", "fix": None,
                           "mkey": "na", "mval": None})
            return
        ok_t, warn_t = thresholds
        if higher_bad:
            status = "ok" if value <= ok_t else ("warn" if value <= warn_t else "bad")
        else:
            status = "ok" if value >= ok_t else ("warn" if value >= warn_t else "bad")
        total_weight += weight
        if status == "bad":
            lost += weight
        elif status == "warn":
            lost += weight * 0.5
        checks.append({"id": cid, "label": label, "status": status,
                       "message": fmt(value), "fix": None if status == "ok" else fix,
                       "mkey": mkey, "mval": int(value)})

    def toggle_check(cid, label, key, weight, fix):
        nonlocal total_weight, lost
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

    check("temp", "File temporanei", 8, health.get("temp_mb"), (1500, 5000),
          lambda v: f"{int(v)} MB", "Esegui la pulizia file temporanei (Desktop Agent opz. 1)",
          "mb", present="temp_mb" in health)
    check("startup", "Programmi all'avvio", 10, health.get("startup_count"), (8, 15),
          lambda v: f"{int(v)} programmi", "Disabilita gli avvii non essenziali (pagina 'Il mio PC')",
          "programs", present="startup_count" in health)

    power = (health.get("power_plan") or "").lower()
    hp = any(x in power for x in ("high", "prestazioni elevate", "ultimate"))
    total_weight += 15
    if not hp:
        lost += 15
    checks.append({"id": "power", "label": "Piano energetico",
                   "status": "ok" if hp else "bad",
                   "message": "Alte prestazioni" if hp else "Non ottimale",
                   "fix": None if hp else "Attiva 'Alte prestazioni' (Desktop Agent opz. 3)",
                   "mkey": "power_hp" if hp else "power_bad", "mval": None})

    toggle_check("game_mode", "Game Mode", "game_mode", 8, "Attiva Game Mode (Desktop Agent opz. 5)")
    toggle_check("hags", "GPU Scheduling (HAGS)", "gpu_scheduling", 6, "Abilita HAGS (Desktop Agent opz. 5)")

    check("ram", "Uso RAM", 10, health.get("ram_used_pct"), (80, 90),
          lambda v: f"{int(v)}% in uso", "Chiudi app in background o aggiungi RAM",
          "ram_pct", present="ram_used_pct" in health)
    check("disk", "Spazio disco (C:)", 12, health.get("disk_free_pct"), (12, 6),
          lambda v: f"{int(v)}% libero", "Libera spazio: pulizia disco (Desktop Agent opz. 6)",
          "disk_pct", higher_bad=False, present="disk_free_pct" in health)

    days = days_since(health["gpu_driver_date"]) if health.get("gpu_driver_date") else None
    check("driver", "Driver GPU", 12, days, (180, 365),
          lambda v: f"aggiornato {int(v)} giorni fa", "Aggiorna i driver della GPU",
          "driver_days", present=days is not None)
    _gpu_t = health.get("gpu_temp")
    _gpu_t = _gpu_t if (_gpu_t is not None and _gpu_t > 0) else None
    _cpu_t = health.get("cpu_temp")
    _cpu_t = _cpu_t if (_cpu_t is not None and _cpu_t > 0) else None
    check("gpu_temp", "Temperatura GPU", 12, _gpu_t, (75, 84),
          lambda v: f"{int(v)}°C", "Migliora airflow/curva ventole: rischio throttling",
          "temp_c", present=_gpu_t is not None)
    check("cpu_temp", "Temperatura CPU", 10, _cpu_t, (80, 89),
          lambda v: f"{int(v)}°C", "Verifica dissipatore/pasta termica: rischio throttling",
          "temp_c", present=_cpu_t is not None)

    score = round(100 * (1 - (lost / total_weight))) if total_weight else 100
    score = max(0, min(100, score))
    grade_key = "ottimo" if score >= 85 else "buono" if score >= 70 else "migliorare" if score >= 50 else "critico"
    grade = {"ottimo": "Ottimo", "buono": "Buono", "migliorare": "Da migliorare", "critico": "Critico"}[grade_key]
    return {"score": score, "grade": grade, "grade_key": grade_key, "checks": checks,
            "driver_version": health.get("gpu_driver_version"),
            "gpu_temp": _gpu_t, "cpu_temp": _cpu_t,
            "gpu": health.get("gpu"), "updated_at": now_iso()}


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
