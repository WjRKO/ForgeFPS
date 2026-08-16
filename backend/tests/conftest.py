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
    _ensure_admin_plan()


def _ensure_admin_plan():
    """Garantisce che l'utente admin abbia un piano a pagamento.

    Buona parte della suite chiama endpoint riservati a Pro/Streamer e si
    aspetta 200. `plan_gate.py` decide solo in base al campo `plan`: il ruolo
    admin NON da' diritti sulle feature. Su un database appena creato l'admin
    nasce senza piano (vedi seed_admin), quindi quegli endpoint rispondono 402
    e decine di test falliscono per un motivo che non c'entra col codice sotto
    esame. Qui il piano viene allineato a quello che i test presuppongono.
    """
    email = os.environ.get("ADMIN_EMAIL")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not (email and mongo_url and db_name):
        return  # senza coordinate del DB si lascia lo stato com'e'
    try:
        from pymongo import MongoClient
        users = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)[db_name].users
        u = users.find_one({"email": email}, {"plan": 1})
        if u and u.get("plan") not in ("streamer", "pro"):
            users.update_one({"_id": u["_id"]}, {"$set": {"plan": "streamer"}})
    except Exception as exc:  # pragma: no cover - diagnostica, non deve bloccare
        print(f"[conftest] piano admin non allineato: {exc}")


_DB_CACHE = []


def _test_db():
    """Handle sul database sotto test, o None se le coordinate non ci sono.

    Il client viene creato una volta sola per processo: aprirne uno nuovo a
    ogni test significa rifare la discovery del server ogni volta, e su ~430
    test la suite passava da 4 a oltre 10 minuti.
    """
    if _DB_CACHE:
        return _DB_CACHE[0]
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not (mongo_url and db_name):
        return None
    try:
        from pymongo import MongoClient
        db = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)[db_name]
    except Exception:
        return None
    _DB_CACHE.append(db)
    return db


@pytest.fixture(autouse=True)
def _reset_login_lockout():
    """Azzera il contatore di tentativi falliti prima di ogni test.

    Diversi test provano di proposito password sbagliate. Il lockout di
    auth.py e' per (ip, email): dopo 5 tentativi l'admin resta bloccato 15
    minuti e tutti i test successivi falliscono con 429, per un motivo che non
    c'entra con cio' che stanno verificando. Ripulire PRIMA di ogni test lascia
    intatti i test che il 429 lo cercano davvero: quelli generano da soli i
    propri tentativi falliti dentro il test.
    """
    db = _test_db()
    if db is not None:
        try:
            db.login_attempts.delete_many({})
        except Exception:
            pass
    yield


@pytest.fixture(scope="session", autouse=True)
def _clean_lab_sessions():
    """Chiude le sessioni Lab rimaste aperte da esecuzioni precedenti.

    L'endpoint rifiuta una nuova sessione se ne esiste gia' una attiva, quindi
    un run interrotto a meta' faceva fallire tutti i test Lab di quello dopo.
    """
    db = _test_db()
    if db is not None:
        try:
            db.lab_sessions.delete_many({})
        except Exception:
            pass
    yield
