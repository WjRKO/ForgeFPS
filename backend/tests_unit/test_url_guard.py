"""Un URL scritto dall'utente non e' un posto dove il backend puo' andare.

`POST /api/products/track` accettava una stringa qualsiasi e la passava a
`requests.get`. Il backend e' l'unica cosa che raggiunge MongoDB - il
docker-compose lo mette apposta su una rete interna non pubblicata - quindi
quell'URL era la strada per arrivarci, insieme al servizio di metadata del cloud
e agli endpoint interni del backend stesso. E lo scheduler dei prezzi rilegge gli
URL salvati a intervalli: bastava salvarne uno.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import url_guard as g


def _rifiutato(url):
    with pytest.raises(g.UrlNonAmmesso):
        g.controlla(url)


# ---------- cosa non si raggiunge ----------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://localhost/",
    "http://10.0.0.5/",
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data/",   # metadata del cloud
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",                 # loopback travestito da IPv6
    "http://0.0.0.0/",
])
def test_gli_indirizzi_interni_sono_fuori(url):
    _rifiutato(url)


def test_l_ipv4_mappato_in_ipv6_non_rientra_dalla_finestra():
    """`::ffff:127.0.0.1` e' loopback scritto in IPv6: senza ricondurlo al suo
    IPv4 prima del giudizio, `is_loopback` risponderebbe di no."""
    _rifiutato("http://[::ffff:169.254.169.254]/")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x/", "ftp://x/", "//example.com/"])
def test_solo_http_e_https(url):
    _rifiutato(url)


def test_le_porte_non_web_sono_fuori():
    """Un host con IP pubblico basterebbe a raggiungere un servizio interno
    esposto su una porta alta."""
    _rifiutato("https://example.com:27017/")
    _rifiutato("http://example.com:8001/")


def test_un_host_che_non_risolve_non_passa():
    _rifiutato("http://host-che-non-esiste-davvero-12345.invalid/")


def test_url_vuoto_o_senza_host():
    _rifiutato("")
    _rifiutato(None)
    _rifiutato("http:///percorso")


# ---------- cosa si raggiunge ----------

def test_un_negozio_vero_passa():
    assert g.controlla("https://www.amazon.it/dp/B0XXXX") == "https://www.amazon.it/dp/B0XXXX"


def test_gli_spazi_intorno_non_contano():
    assert g.controlla("  https://www.amazon.it/dp/X  ") == "https://www.amazon.it/dp/X"


# ---------- il giudizio si rifa' a ogni salto ----------

def test_i_redirect_non_sono_automatici():
    """Con `allow_redirects=True` un 302 verso 127.0.0.1 aggirerebbe qualunque
    controllo fatto sul solo URL iniziale."""
    import inspect
    src = inspect.getsource(g.fetch)
    assert "allow_redirects=False" in src
    assert "controlla(" in src.split("for _ in range")[1], "la destinazione del redirect va rivalidata"


def test_basta_un_indirizzo_privato_per_rifiutare(monkeypatch):
    """Chi controlla il DNS puo' rispondere con un indirizzo pubblico E uno
    privato: chiedere che siano *tutti* privati gli lascerebbe la strada."""
    import ipaddress
    monkeypatch.setattr(g, "_indirizzi",
                        lambda host: [ipaddress.ip_address("93.184.216.34"), ipaddress.ip_address("127.0.0.1")])
    _rifiutato("https://misto.example/")


# ---------- lo scraper lo usa davvero ----------

def test_lo_scraper_non_chiama_piu_requests_diretto():
    percorso = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()
    assert "url_guard.fetch(" in src
    assert "requests.get(" not in src, "una GET diretta e' tornata nello scraper"


def test_il_messaggio_di_errore_non_e_piu_un_oracolo():
    """Il testo dell'eccezione distingueva connessione rifiutata, timeout ed
    errore DNS: era una scansione della rete interna fatta dal server."""
    percorso = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()
    assert "str(e)[:120]" not in src
    assert 'logger.warning("scraping fallito' in src, "il motivo preciso deve restare nel log"
