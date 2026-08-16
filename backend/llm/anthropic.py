"""Provider basato sul Claude API di Anthropic (SDK ufficiale `anthropic`).

Sostituisce Emergent come motore dell'AI Advisor. Modello predefinito:
claude-haiku-4-5 (200K di contesto, 64K di output massimo, $1/$5 per milione
di token) — scelto per il rapporto costo/qualita' su questo carico: spiegare
tweak di Windows e leggere specifiche hardware.

Configurazione (backend/.env):
    ANTHROPIC_API_KEY     obbligatoria, altrimenti il provider non parte
    ANTHROPIC_MODEL       opzionale, per passare a un modello piu' capace
    ANTHROPIC_MAX_TOKENS  opzionale, tetto di output per risposta

Per cambiare modello NON serve toccare questo file: basta la variabile
d'ambiente. Gli identificativi vanno scritti esatti e senza suffisso di data
(`claude-sonnet-5`, non `claude-sonnet-5-20260101`).
"""
import base64
import logging
import os
from typing import AsyncIterator

from .base import LLMProvider, LLMUnavailable

logger = logging.getLogger("boostpc.llm.anthropic")

DEFAULT_MODEL = "claude-haiku-4-5"

#: Tetto di output per risposta. L'advisor produce risposte da poche centinaia
#: di token: 4096 lascia margine abbondante e al tempo stesso limita il danno
#: se un prompt anomalo fa partire una risposta fiume. Il massimo del modello
#: sarebbe 64K.
DEFAULT_MAX_TOKENS = 4096

#: Firme dei formati immagine accettati dal Claude API. Il chiamante ci passa
#: il base64 senza prefisso data-url (vedi ai_engine.stream_advisor), quindi il
#: media type e' andato perso e va riconosciuto dai primi byte: dichiararlo
#: sbagliato fa fallire la richiesta.
_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _sniff_media_type(image_b64: str) -> str:
    """Media type dedotto dai primi byte, con PNG come ripiego."""
    try:
        head = base64.b64decode(image_b64[:64], validate=False)
    except Exception:
        return "image/png"
    for signature, media_type in _IMAGE_SIGNATURES:
        if head.startswith(signature):
            return media_type
    # WebP: "RIFF" + 4 byte di lunghezza + "WEBP"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        # Client e chiave si risolvono alla prima chiamata, non qui: l'istanza
        # del provider viene memoizzata in llm/__init__.py e l'ambiente puo'
        # essere popolato dopo l'avvio del processo (stessa ragione per cui
        # emergent.py legge la chiave a ogni invocazione).
        self._client = None
        self._client_key = None

    def _get_client(self):
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise LLMUnavailable(
                "ANTHROPIC_API_KEY non impostata: l'AI Advisor resta spento. "
                "Aggiungila a backend/.env e riavvia il backend."
            )
        if self._client is None or self._client_key != key:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise LLMUnavailable(
                    "pacchetto 'anthropic' non installato: "
                    "pip install -r requirements-windows.txt"
                ) from exc
            self._client = AsyncAnthropic(api_key=key)
            self._client_key = key
        return self._client

    async def stream(
        self,
        *,
        session_id: str,
        system: str,
        text: str,
        image_b64: str | None = None,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL
        try:
            max_tokens = int(os.environ.get("ANTHROPIC_MAX_TOKENS") or DEFAULT_MAX_TOKENS)
        except ValueError:
            logger.warning("ANTHROPIC_MAX_TOKENS non numerica, uso %s", DEFAULT_MAX_TOKENS)
            max_tokens = DEFAULT_MAX_TOKENS

        # L'immagine va prima del testo: e' l'ordine consigliato quando la
        # domanda si riferisce all'immagine stessa.
        content: list[dict] = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _sniff_media_type(image_b64),
                    "data": image_b64,
                },
            })
        content.append({"type": "text", "text": text})

        # `session_id` non viene usato: il Claude API e' stateless e la
        # cronologia la ricostruisce gia' ai_engine.stream_advisor dentro il
        # prompt. Resta nella firma perche' altri provider la usano.
        try:
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
            ) as stream:
                async for delta in stream.text_stream:
                    yield delta
        except Exception as exc:
            # Le eccezioni dell'SDK sono tipizzate (RateLimitError,
            # AuthenticationError, APIConnectionError...). Qui vengono
            # normalizzate in LLMUnavailable, che e' cio' che i router sanno
            # gestire, ma il tipo originale finisce nel log per la diagnosi.
            logger.warning("chiamata a %s fallita: %s: %s",
                           model, type(exc).__name__, exc)
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
