"""Un '*' in una variabile d'ambiente non deve diventare il wildcard CORS.

Il middleware gira con `allow_credentials=True`. Accettare ogni origin facendone
l'eco significa che qualunque sito puo' fare richieste autenticate e leggerne la
risposta: e' la combinazione che le librerie normalmente vietano, ed era
raggiungibile mettendo '*' in CORS_ORIGINS - cosa gia' successa una volta per far
funzionare un preview (memory/PRD.md, deployment run 1).
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import settings as _settings


@pytest.fixture
def con_ambiente(monkeypatch):
    def _impostare(**env):
        for chiave in ("CORS_ORIGINS", "CORS_ORIGIN_REGEX", "FRONTEND_URL"):
            monkeypatch.delenv(chiave, raising=False)
        monkeypatch.setenv("FRONTEND_URL", "https://forgefps.dev")
        for chiave, valore in env.items():
            monkeypatch.setenv(chiave, valore)
        return importlib.reload(_settings)
    yield _impostare
    importlib.reload(_settings)


def test_il_wildcard_non_diventa_una_regex(con_ambiente):
    s = con_ambiente(CORS_ORIGINS="*")
    assert s.get_cors_origin_regex() is None, "'*' e' tornato a produrre una regex che accetta tutti"
    assert s.get_cors_origins() == ["https://forgefps.dev"]


def test_un_wildcard_in_mezzo_alla_lista_viene_scartato(con_ambiente):
    s = con_ambiente(CORS_ORIGINS="https://a.dev,*,https://b.dev")
    assert "*" not in s.get_cors_origins()
    assert s.get_cors_origins() == ["https://a.dev", "https://b.dev", "https://forgefps.dev"]


def test_il_frontend_e_sempre_ammesso(con_ambiente):
    s = con_ambiente(CORS_ORIGINS="")
    assert s.get_cors_origins() == ["https://forgefps.dev"]


def test_una_regex_circoscritta_passa(con_ambiente):
    """I preview URL con prefisso casuale sono il motivo per cui il wildcard era
    stato messo: serve una via legittima, altrimenti torna il '*'."""
    pattern = r"https://[a-z0-9-]+\.preview\.esempio\.com"
    s = con_ambiente(CORS_ORIGIN_REGEX=pattern)
    assert s.get_cors_origin_regex() == pattern


@pytest.mark.parametrize("pattern", [".*", ".+", "(?s).*", "https?://.*", "^.*$"])
def test_una_regex_che_accetta_chiunque_viene_rifiutata(pattern, con_ambiente):
    """Si controlla il comportamento, non la stringa: cosi' non serve elencare
    tutti i modi di scrivere "qualunque cosa"."""
    s = con_ambiente(CORS_ORIGIN_REGEX=pattern)
    assert s.get_cors_origin_regex() is None


def test_una_regex_rotta_non_fa_esplodere_l_avvio(con_ambiente):
    s = con_ambiente(CORS_ORIGIN_REGEX="https://[")
    assert s.get_cors_origin_regex() is None


def test_il_confronto_usa_lo_stesso_metro_di_starlette(con_ambiente):
    """Starlette usa fullmatch: una regex ancorata solo all'inizio accetterebbe
    `https://forgefps.dev.attaccante.test`, e va vista come aperta."""
    s = con_ambiente(CORS_ORIGIN_REGEX=r"https://forgefps\.dev")
    assert s.get_cors_origin_regex() is not None
    import re
    assert not re.compile(s.get_cors_origin_regex()).fullmatch("https://forgefps.dev.attaccante.test")
