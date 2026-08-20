"""Coerenza di cio' che distribuiamo: URL, versione e hash del pacchetto agent.

I tre valori sono mantenuti a mano e sono gia' andati fuori sincrono una volta:
il backend serviva la v0.8.0 mentre l'ultima release pubblicata era la v0.8.1,
quindi chi installava prendeva una versione indietro e il self-updater non
scattava per nessuno. Questi test non impediscono di sbagliare, ma fanno
rumore subito invece che a distribuzione avvenuta.
"""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from routers import pc
except Exception as exc:  # pragma: no cover - manca la configurazione locale
    pc = None
    _import_error = exc

pytestmark = pytest.mark.skipif(pc is None, reason="routers.pc non importabile senza configurazione")


def test_la_versione_dichiarata_viene_dall_url():
    """`LATEST_AGENT_VERSION` e' derivata dall'URL, non scritta a parte: se
    qualcuno cambia solo uno dei due, la derivazione se ne accorge."""
    assert pc.LATEST_AGENT_VERSION in pc.AGENT_ZIP_UPSTREAM


def test_l_url_punta_alle_release_del_repository():
    """Stesso vincolo che l'agent applica sul suo lato: se il default finisse
    altrove, il controllo lato agent rifiuterebbe l'aggiornamento e nessuno
    capirebbe perche'."""
    assert pc.AGENT_ZIP_UPSTREAM.startswith(
        "https://github.com/WjRKO/ForgeFPS/releases/download/")


def test_l_hash_e_un_sha256_normalizzato():
    h = pc.AGENT_ZIP_SHA256
    assert len(h) == 64 and h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


def test_il_frontend_offre_lo_stesso_pacchetto_del_backend():
    """La pagina Download legge costanti hardcoded, il self-updater legge il
    backend: sono due fonti per lo stesso file e devono coincidere."""
    cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "frontend", "src", "config", "agent.js")
    if not os.path.exists(cfg):
        pytest.skip("frontend non presente")
    src = open(cfg, encoding="utf-8").read()
    assert f'"{pc.AGENT_ZIP_UPSTREAM}"' in src, "URL diverso fra frontend e backend"
    assert f'"{pc.AGENT_ZIP_SHA256}"' in src, "SHA256 diverso fra frontend e backend"


# ---------- verifica in fase di distribuzione ----------

def test_il_pacchetto_atteso_passa_la_verifica(monkeypatch):
    blob = b"contenuto del pacchetto"
    monkeypatch.setattr(pc, "AGENT_ZIP_SHA256", hashlib.sha256(blob).hexdigest())
    assert pc._zip_digest_ok(blob) is True


def test_un_pacchetto_alterato_non_viene_distribuito(monkeypatch):
    monkeypatch.setattr(pc, "AGENT_ZIP_SHA256", hashlib.sha256(b"originale").hexdigest())
    assert pc._zip_digest_ok(b"alterato") is False


def test_senza_hash_configurato_non_si_blocca_la_distribuzione(monkeypatch):
    """Un hash mancante e' una configurazione incompleta, non un attacco:
    bloccare i download per quello sarebbe un disservizio autoinflitto."""
    monkeypatch.setattr(pc, "AGENT_ZIP_SHA256", "")
    assert pc._zip_digest_ok(b"qualsiasi cosa") is True
