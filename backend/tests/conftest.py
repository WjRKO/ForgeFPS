"""Configurazione comune della suite.

Le credenziali di test stavano scritte in chiaro dentro i singoli file; ora
arrivano dall'ambiente. Senza di esse i test fallirebbero con un 401 opaco,
quindi qui l'errore viene reso esplicito subito.

Uso:
    export ADMIN_PASSWORD='...'          # obbligatoria
    export ADMIN_EMAIL='admin@...'       # opzionale, ha un default
    export REACT_APP_BACKEND_URL='...'   # opzionale, default http://localhost:8001
    export STARTER_PASSWORD='...'        # solo per i test sul piano Starter
"""
import os

import pytest


def pytest_configure(config):
    if not os.environ.get("ADMIN_PASSWORD"):
        raise pytest.UsageError(
            "ADMIN_PASSWORD non impostata: la suite si autentica come utente admin.\n"
            "Impostala nell'ambiente prima di lanciare pytest, per esempio:\n"
            "    export ADMIN_PASSWORD='la-password-admin'\n"
            "Non reintrodurre il valore nei file di test: questo repository e' pubblico."
        )
