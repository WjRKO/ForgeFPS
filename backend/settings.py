import logging
import os
import re

logger = logging.getLogger("boostpc.settings")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Origin di prova per riconoscere una regex che, di fatto, accetta chiunque.
# Si controlla il COMPORTAMENTO invece della stringa: cosi' cadono `.*`, `.+`,
# `(?s).*` e `https?://.*` senza doverli elencare.
_ORIGIN_ESTRANEE = ("https://esempio-non-nostro.invalid", "http://attaccante.test:1234")


def get_cors_origins():
    """Gli origin consentiti. Un '*' viene ignorato, non tradotto.

    Il middleware gira con `allow_credentials=True`: accettare ogni origin
    facendone l'eco significa che qualunque sito puo' fare richieste
    autenticate e leggerne la risposta. E' la combinazione che le librerie
    normalmente vietano, ed era raggiungibile mettendo '*' in una variabile
    d'ambiente - cosa gia' successa una volta, per far funzionare un preview
    (vedi memory/PRD.md, deployment run 1).

    Se serve accettare un insieme di sottodomini - i preview URL con prefisso
    casuale sono il caso vero - si usa CORS_ORIGIN_REGEX, che e' esplicito e
    circoscritto. `FRONTEND_URL` e' sempre incluso.
    """
    raw = os.environ.get("CORS_ORIGINS", "")
    voci = [o.strip() for o in raw.split(",") if o.strip()]
    if any(v == "*" for v in voci):
        logger.warning(
            "CORS_ORIGINS contiene '*': ignorato. Con allow_credentials un wildcard "
            "permette a qualunque sito richieste autenticate. Elenca gli origin, "
            "oppure usa CORS_ORIGIN_REGEX per un insieme di sottodomini.")
    origins = [v for v in voci if v != "*"]
    if FRONTEND_URL not in origins:
        origins.append(FRONTEND_URL)
    return origins


def get_cors_origin_regex():
    """La regex per allow_origin_regex, presa da CORS_ORIGIN_REGEX. None se assente.

    Non viene piu' derivata da un '*' in CORS_ORIGINS: quel ramo trasformava una
    svista di configurazione in `.*`, cioe' nel wildcard con credenziali.
    Una regex che accetta anche gli estranei viene rifiutata: sarebbe lo stesso
    buco da un'altra porta.
    """
    raw = (os.environ.get("CORS_ORIGIN_REGEX") or "").strip()
    if not raw:
        return None
    try:
        compilata = re.compile(raw)
    except re.error as exc:
        logger.warning("CORS_ORIGIN_REGEX non compila (%s): ignorata.", exc)
        return None
    # Starlette confronta con fullmatch: si prova con lo stesso metro.
    if any(compilata.fullmatch(o) for o in _ORIGIN_ESTRANEE):
        logger.warning(
            "CORS_ORIGIN_REGEX accetta origin estranei: ignorata. "
            "Restringila ai domini che devono davvero poter chiamare l'API.")
        return None
    return raw


def get_api_base(default: str = "") -> str:
    """Origin su cui le API sono raggiungibili: ci si appende '/api/...'.

    In produzione front-end e API stanno sullo stesso dominio, quindi il default
    del chiamante va bene. In locale sono due porte diverse e il dev server NON
    inoltra '/api': chi costruisce un URL con il default finisce sulla porta del
    front-end e riceve l'HTML della SPA invece della risorsa vera.

    E' il motivo per cui esiste AGENT_BACKEND_URL, che qui ha la precedenza.
    """
    return ((os.environ.get("AGENT_BACKEND_URL") or default or "").strip()).rstrip("/")
