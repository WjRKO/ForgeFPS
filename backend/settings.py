import os

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def get_cors_origins():
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
    if FRONTEND_URL not in origins:
        origins.append(FRONTEND_URL)
    return origins
