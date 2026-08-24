# -*- coding: utf-8 -*-
"""Un URL scritto dall'utente non e' un posto dove il backend puo' andare.

`POST /api/products/track` accettava una stringa qualsiasi e la passava a
`requests.get`. Il backend e' l'unica cosa che raggiunge MongoDB - il
docker-compose lo mette apposta su una rete interna non pubblicata - quindi
quell'URL era la strada per arrivarci, insieme a `169.254.169.254` (metadata
del cloud) e agli endpoint interni del backend stesso. E non era una richiesta
cieca: il messaggio d'errore riportava il testo dell'eccezione, cosi' connessione
rifiutata, timeout ed errore DNS diventavano distinguibili - una scansione della
rete interna fatta dal server. Peggio ancora, lo scheduler dei prezzi rilegge gli
URL salvati a intervalli, quindi bastava salvarlo una volta.

Qui la regola e': si esce solo verso indirizzi PUBBLICI, in http o https, sulle
porte del web, e la stessa verifica si rifa' **a ogni redirect** - perche' un
sito che risponde 302 verso 127.0.0.1 aggirerebbe qualunque controllo fatto solo
sull'URL iniziale.

--- Cosa questo modulo NON garantisce ---

Fra il momento in cui risolviamo il nome e quello in cui `requests` apre la
connessione, il DNS puo' cambiare risposta (DNS rebinding). Chiuderlo del tutto
vorrebbe dire connettersi all'IP verificato e passare il nome nell'header Host,
cioe' un transport adapter su misura. Qui si alza molto il costo dell'attacco -
si rifiutano gli host che risolvono a un indirizzo privato anche solo in parte -
ma la finestra resta, ed e' meglio scritto qui che scoperto dopo.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests

SCHEMI_AMMESSI = ("http", "https")
# Le porte del web. Senza questo limite un host con IP pubblico basterebbe a
# raggiungere qualunque servizio interno esposto su una porta alta.
PORTE_AMMESSE = (80, 443)
MAX_REDIRECT = 3
TIMEOUT_S = 15


class UrlNonAmmesso(ValueError):
    """L'URL non e' un posto verso cui il backend puo' fare una richiesta."""


def _e_pubblico(ip: ipaddress._BaseAddress) -> bool:
    """Falso per loopback, reti private, link-local, multicast e riservati.

    Gli indirizzi IPv6 che mappano un IPv4 (`::ffff:127.0.0.1`) vengono
    ricondotti al loro IPv4 prima del giudizio: senza, il loopback rientrerebbe
    dalla porta di servizio.
    """
    mappato = getattr(ip, "ipv4_mapped", None)
    if mappato is not None:
        ip = mappato
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def _indirizzi(host: str) -> list:
    try:
        info = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise UrlNonAmmesso("host non risolvibile")
    fuori = []
    for famiglia, _, _, _, sockaddr in info:
        try:
            fuori.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    if not fuori:
        raise UrlNonAmmesso("host senza indirizzi utilizzabili")
    return fuori


def controlla(url: str) -> str:
    """Verifica un URL e lo ritorna, o solleva UrlNonAmmesso.

    Basta UN indirizzo privato fra quelli risolti per rifiutare: un attaccante
    che controlla il DNS puo' rispondere con un indirizzo pubblico e uno privato,
    e chiedere che siano *tutti* privati gli lascerebbe la strada aperta.
    """
    if not url or not isinstance(url, str):
        raise UrlNonAmmesso("URL mancante")
    pezzi = urlparse(url.strip())
    if pezzi.scheme.lower() not in SCHEMI_AMMESSI:
        raise UrlNonAmmesso("sono ammessi solo indirizzi http e https")
    host = pezzi.hostname
    if not host:
        raise UrlNonAmmesso("URL senza host")
    porta = pezzi.port or (443 if pezzi.scheme.lower() == "https" else 80)
    if porta not in PORTE_AMMESSE:
        raise UrlNonAmmesso("porta non ammessa")
    # Un IP scritto direttamente nell'URL non passa dal DNS: si giudica com'e'.
    for ip in _indirizzi(host):
        if not _e_pubblico(ip):
            raise UrlNonAmmesso("indirizzo non pubblico")
    return url.strip()


def fetch(url: str, *, headers: dict | None = None, timeout: int = TIMEOUT_S):
    """GET con la stessa verifica ripetuta a ogni salto.

    `allow_redirects=False` non e' pigrizia: e' l'unico modo di rivedere ogni
    destinazione. Con i redirect automatici, `requests` seguirebbe un 302 verso
    l'interno senza che nessuno lo guardi.
    """
    corrente = controlla(url)
    for _ in range(MAX_REDIRECT + 1):
        resp = requests.get(corrente, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code not in (301, 302, 303, 307, 308):
            return resp
        destinazione = resp.headers.get("Location")
        if not destinazione:
            return resp
        corrente = controlla(urljoin(corrente, destinazione))
    raise UrlNonAmmesso("troppi reindirizzamenti")
