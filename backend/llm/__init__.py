"""Selezione del provider LLM.

Il provider attivo si sceglie con la variabile d'ambiente LLM_PROVIDER.
Per aggiungerne uno: crea `llm/<nome>.py` con una classe che eredita da
LLMProvider e registralo in _PROVIDERS. Nessun altro file va toccato.
"""
import os

from .base import LLMProvider, LLMUnavailable

DEFAULT_PROVIDER = "emergent"

#: nome -> (modulo, classe). Import pigro: si carica solo quello richiesto.
_PROVIDERS: dict[str, tuple[str, str]] = {
    "anthropic": (".anthropic", "AnthropicProvider"),
    "emergent": (".emergent", "EmergentProvider"),
}

_cache: dict[str, LLMProvider] = {}


def get_provider(name: str | None = None) -> LLMProvider:
    """Istanza (memoizzata) del provider richiesto, o di quello di default."""
    key = (name or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if key in _cache:
        return _cache[key]
    try:
        module_name, class_name = _PROVIDERS[key]
    except KeyError:
        raise LLMUnavailable(
            f"Provider LLM sconosciuto: '{key}'. Disponibili: {', '.join(sorted(_PROVIDERS))}"
        ) from None
    from importlib import import_module
    provider = getattr(import_module(module_name, __name__), class_name)()
    _cache[key] = provider
    return provider


__all__ = ["LLMProvider", "LLMUnavailable", "get_provider", "DEFAULT_PROVIDER"]
