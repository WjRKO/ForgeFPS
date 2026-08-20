"""Guardie del self-updater dell'agent: da dove accetta un pacchetto e come lo verifica.

Finche' l'eseguibile non e' firmato, queste due funzioni sono l'unico controllo
che sta fra una release e il `xcopy` sopra l'installazione dell'utente. Il
percorso di aggiornamento e' anche l'unico download che avviene senza che
nessuno guardi: sulla pagina Download l'hash viene mostrato e l'utente puo'
confrontarlo, qui no.
"""
import hashlib
import os
import sys

import pytest

_AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "agent-build")

try:
    _saved_argv = sys.argv
    # --register-protocol e' l'unica mode che non chiede un token all'import.
    sys.argv = ["forgefps-agent", "--register-protocol"]
    sys.path.insert(0, _AGENT_DIR)
    import forgefps_agent as fa
except Exception as exc:  # pragma: no cover - agent assente o non importabile
    fa = None
    _import_error = exc
finally:
    sys.argv = _saved_argv

pytestmark = pytest.mark.skipif(fa is None, reason="agent non importabile su questa piattaforma")

VALID = "https://github.com/WjRKO/ForgeFPS/releases/download/v0.8.1/forgefps-agent.zip"


# ---------- da dove accettiamo un aggiornamento ----------

def test_la_release_ufficiale_e_accettata():
    assert fa._is_allowed_update_url(VALID) is True


@pytest.mark.parametrize("url, perche", [
    ("http://github.com/WjRKO/ForgeFPS/releases/download/v0.8.1/a.zip", "senza TLS"),
    ("https://evil.example/WjRKO/ForgeFPS/releases/download/v0.8.1/a.zip", "altro host"),
    ("https://github.com.evil.example/WjRKO/ForgeFPS/releases/download/v0.8.1/a.zip", "host sosia"),
    ("https://github.com@evil.example/WjRKO/ForgeFPS/releases/download/v0.8.1/a.zip", "userinfo"),
    ("https://github.com/altro/repo/releases/download/v1/a.zip", "altro repository"),
    ("https://github.com/WjRKO/ForgeFPS/releases/download/../../../a.zip", "risalita di percorso"),
    ("", "vuoto"),
    (None, "assente"),
])
def test_url_non_consentiti(url, perche):
    assert fa._is_allowed_update_url(url) is False, perche


# ---------- verifica del pacchetto ----------

def test_riconosce_un_digest_valido():
    assert fa._looks_like_sha256("a" * 64) is True
    assert fa._looks_like_sha256(hashlib.sha256(b"x").hexdigest()) is True


@pytest.mark.parametrize("v", ["", "abc", "A" * 64, "z" * 64, "a" * 63, "a" * 65])
def test_scarta_un_digest_malformato(v):
    """Maiuscolo incluso: il chiamante normalizza prima, e un valore non
    normalizzato qui significa che qualcosa a monte non ha fatto il suo lavoro."""
    assert fa._looks_like_sha256(v) is False


def test_hash_del_file_letto_a_blocchi(tmp_path):
    """Il pacchetto sono ~9 MB: si legge a blocchi, e il risultato deve
    coincidere con l'hash del contenuto intero."""
    blob = os.urandom(3 * 1024 * 1024 + 7)
    p = tmp_path / "pacchetto.zip"
    p.write_bytes(blob)
    assert fa._sha256_file(str(p)) == hashlib.sha256(blob).hexdigest()


def test_un_byte_diverso_cambia_l_hash(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    blob = b"pacchetto dell'agent" * 1000
    a.write_bytes(blob)
    b.write_bytes(blob[:-1] + b"X")
    assert fa._sha256_file(str(a)) != fa._sha256_file(str(b))
