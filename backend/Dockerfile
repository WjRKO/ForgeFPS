# Backend FrameForge — FastAPI + APScheduler
#
# Python 3.11: e' la versione con cui gira la produzione attuale (visibile nei
# log pip del container originale). Non alzarla senza aver ricompilato e
# ritestato requirements.txt, che e' un freeze completo con pin esatti.
#
# Build:  docker build -t forgefps-backend ./backend
# Run:    docker run --env-file backend/.env -p 8001:8001 forgefps-backend

# ---------- stage 1: dipendenze ----------
FROM python:3.11-slim AS builder

# Toolchain per i pochi pacchetti senza wheel precompilata (cffi, argon2,
# lxml...). Resta in questo stage: non finisce nell'immagine finale.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiato da solo: cambia di rado, cosi' il layer di pip resta in cache anche
# quando cambia il codice.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------- stage 2: runtime ----------
FROM python:3.11-slim

# Librerie a runtime per lxml. Niente compilatori qui.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Deliberatamente NON /app: il codice conteneva percorsi /app fissi ereditati
# dalla vecchia piattaforma. Con una directory diversa, un eventuale residuo
# fallisce subito invece di funzionare per caso.
WORKDIR /srv/app

# Gli import del backend sono piatti (`import ai_engine`), quindi i moduli
# devono stare nella working directory.
COPY . .

# Utente non privilegiato.
RUN useradd --create-home --uid 10001 forgefps \
    && chown -R forgefps:forgefps /srv/app
USER forgefps

EXPOSE 8001

# `curl` non c'e' nell'immagine slim: si usa l'interprete gia' presente.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4).status==200 else 1)"

# --proxy-headers: dietro reverse proxy il traffico interno arriva su http, e
# il flusso OAuth di Discord si aspetta di poter leggere X-Forwarded-Proto.
#
# UNA SOLA ISTANZA (niente --workers): APScheduler gira dentro il processo e
# non ha lock distribuito. Con piu' worker, controllo prezzi e reminder
# partirebbero una volta per worker.
CMD ["uvicorn", "server:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
