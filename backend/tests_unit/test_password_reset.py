"""Il link di reset arriva all'utente, non ai log.

`forgot` stampava il token su stdout: in un deploy containerizzato quella riga
finisce nell'aggregatore di log della piattaforma, e un token di reset e' una
presa di controllo dell'account per un'ora. Non era una riga di debug
dimenticata - era il canale di consegna, perche' l'email non era collegata.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth
import email_service
from fake_db import FakeDb


def _endpoint(router, path):
    for rotta in router.routes:
        if rotta.path.endswith(path):
            return rotta.endpoint
    raise AssertionError("endpoint %s non trovato" % path)


class _Inviate(list):
    async def __call__(self, to, link, name=""):
        self.append({"to": to, "link": link, "name": name})
        return "id-finto"


@pytest.fixture
def scenario(monkeypatch):
    db = FakeDb()
    inviate = _Inviate()
    monkeypatch.setattr(email_service, "send_password_reset", inviate)
    router, _ = auth.build_auth_router(db)
    forgot = _endpoint(router, "/forgot-password")
    return db, forgot, inviate


def _utente(db):
    asyncio.run(db.users.insert_one({"_id": "u1", "email": "tizio@example.com", "name": "Tizio"}))


def test_il_link_arriva_per_email_e_contiene_il_token(scenario):
    db, forgot, inviate = scenario
    _utente(db)
    asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    rec = asyncio.run(db.password_reset_tokens.find_one({"user_id": "u1"}))
    assert rec is not None, "il token non e' stato creato"
    assert len(inviate) == 1, "nessuna email inviata"
    assert rec["token"] in inviate[0]["link"]
    assert inviate[0]["to"] == "tizio@example.com"


def test_il_token_non_finisce_nei_log(scenario, capsys, caplog):
    db, forgot, inviate = scenario
    _utente(db)
    with caplog.at_level(logging.DEBUG):
        asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    rec = asyncio.run(db.password_reset_tokens.find_one({"user_id": "u1"}))
    uscita = capsys.readouterr()
    testo = uscita.out + uscita.err + caplog.text
    assert rec["token"] not in testo, "il token e' ancora scritto da qualche parte"


def test_niente_secondo_invio_entro_il_freno(scenario):
    """L'endpoint e' pubblico e manda email: senza freno e' un modo per riempire
    la casella di qualcun altro e bruciare la quota di invio."""
    db, forgot, inviate = scenario
    _utente(db)
    asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    assert len(inviate) == 1
    tutti = asyncio.run(db.password_reset_tokens.find({}).to_list(10))
    assert len(tutti) == 1, "un secondo token e' stato coniato dentro la finestra"


def test_passato_il_freno_si_puo_richiedere(scenario):
    db, forgot, inviate = scenario
    _utente(db)
    asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    vecchio = asyncio.run(db.password_reset_tokens.find_one({"user_id": "u1"}))
    vecchio["created_at"] = datetime.now(timezone.utc) - timedelta(minutes=auth.RESET_COOLDOWN_MINUTES + 1)
    asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    assert len(inviate) == 2


def test_un_email_sconosciuta_non_si_distingue(scenario):
    """La risposta e' la stessa: l'endpoint non dice chi ha un account."""
    db, forgot, inviate = scenario
    _utente(db)
    noto = asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    ignoto = asyncio.run(forgot(auth.ForgotInput(email="nessuno@example.com"), None))
    assert noto == ignoto
    assert len(inviate) == 1, "nessuna email per un indirizzo che non esiste"


def test_se_l_email_non_parte_il_token_non_viene_stampato(scenario, capsys, caplog, monkeypatch):
    """Il pannello admin resta la via di riserva, ma nel log ci va il fatto, non
    il segreto."""
    db, forgot, _ = scenario
    _utente(db)

    async def _fallisce(*a, **k):
        raise RuntimeError("resend giu'")

    monkeypatch.setattr(email_service, "send_password_reset", _fallisce)
    with caplog.at_level(logging.DEBUG):
        asyncio.run(forgot(auth.ForgotInput(email="tizio@example.com"), None))
    rec = asyncio.run(db.password_reset_tokens.find_one({"user_id": "u1"}))
    uscita = capsys.readouterr()
    testo = uscita.out + uscita.err + caplog.text
    assert rec["token"] not in testo
    assert "password-resets" in testo, "senza indicazione, chi legge il log non sa dove trovare il link"
