"""Provider basato su emergentintegrations (Emergent Universal Key).

Unico punto del backend che importa `emergentintegrations`. Finche' questo
resta il provider attivo, `emergentintegrations` e il wheel `litellm` ospitato
sul CDN Emergent restano necessari in requirements.txt.
"""
import os
from typing import AsyncIterator

from .base import LLMProvider, LLMUnavailable

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-6"


class EmergentProvider(LLMProvider):
    name = "emergent"

    async def stream(
        self,
        *,
        session_id: str,
        system: str,
        text: str,
        image_b64: str | None = None,
    ) -> AsyncIterator[str]:
        # Import ritardato: cosi' chi passa a un altro provider non ha bisogno
        # di avere emergentintegrations installato.
        from emergentintegrations.llm.chat import (
            LlmChat, UserMessage, TextDelta, StreamDone, ImageContent,
        )

        # Letta a ogni chiamata (non in __init__) perche' l'ambiente puo'
        # essere popolato dopo l'avvio del processo.
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            raise LLMUnavailable("EMERGENT_LLM_KEY non impostata")

        chat = LlmChat(
            api_key=key, session_id=session_id, system_message=system,
        ).with_model(MODEL_PROVIDER, MODEL_NAME)

        kwargs = {"text": text}
        if image_b64:
            kwargs["file_contents"] = [ImageContent(image_base64=image_b64)]

        async for event in chat.stream_message(UserMessage(**kwargs)):
            if isinstance(event, TextDelta):
                yield event.content
            elif isinstance(event, StreamDone):
                break
