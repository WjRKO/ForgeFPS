import os

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def get_cors_origins():
    """Ritorna la lista degli origins consentiti. Se CORS_ORIGINS contiene '*'
    la lista sara' vuota (segnale per il caller di usare allow_origin_regex)."""
    raw = os.environ.get("CORS_ORIGINS", "")
    if "*" in raw:
        return []
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if FRONTEND_URL not in origins:
        origins.append(FRONTEND_URL)
    return origins


def get_cors_origin_regex():
    """Ritorna la regex per allow_origin_regex, o None se non serve.
    Attiva quando CORS_ORIGINS contiene '*' (wildcard) — permette ogni origin
    ma echo dell'origin (compatibile con allow_credentials=True)."""
    raw = os.environ.get("CORS_ORIGINS", "")
    if "*" in raw:
        return ".*"
    return None
