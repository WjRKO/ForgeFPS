"""Interfaccia neutra verso il fornitore di modelli linguistici.

Nessun modulo del backend deve importare direttamente l'SDK di un fornitore:
tutto passa da qui. Cambiare motore significa aggiungere un file in questo
package e cambiare la variabile d'ambiente LLM_PROVIDER, senza toccare
ai_engine.py ne' i router.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMUnavailable(RuntimeError):
    """Provider non configurato (chiave mancante) o non raggiungibile."""


class LLMProvider(ABC):
    """Un fornitore di completamenti in streaming.

    Lo streaming e' l'unica primitiva: le chiamate non-streaming si ottengono
    concatenando i delta (vedi ai_engine._collect).
    """

    #: identificativo usato in LLM_PROVIDER e nei log
    name: str = "base"

    @abstractmethod
    def stream(
        self,
        *,
        session_id: str,
        system: str,
        text: str,
        image_b64: str | None = None,
    ) -> AsyncIterator[str]:
        """Restituisce i delta di testo man mano che il modello risponde.

        `session_id` serve ai provider che mantengono contesto lato loro; quelli
        stateless possono ignorarlo. `image_b64` e' un'immagine base64 senza
        prefisso data-url, per le richieste multimodali.
        """
        raise NotImplementedError
