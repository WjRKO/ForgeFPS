import os
import json
import re
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-6"

ADVISOR_SYSTEM = (
    "Sei BOOST AI, un esperto assistente italiano di ottimizzazione PC per gamer e streamer. "
    "Dai consigli pratici, precisi e passo-passo su: tweak di Windows, impostazioni GPU (NVIDIA/AMD), "
    "OBS/streaming, gestione temperature, overclock sicuro, driver, avvio e background apps, latenza e FPS. "
    "Rispondi sempre in italiano, in modo conciso e tecnico ma comprensibile. Usa elenchi puntati e passi numerati "
    "quando utile. Se un'azione è rischiosa, avvisa l'utente. Non inventare comandi inesistenti."
)


def get_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


def build_chat(session_id: str, system: str = ADVISOR_SYSTEM) -> LlmChat:
    return LlmChat(api_key=get_key(), session_id=session_id,
                   system_message=system).with_model(MODEL_PROVIDER, MODEL_NAME)


async def stream_advisor(session_id: str, history: list, message: str):
    chat = build_chat(session_id)
    # replay history into context
    context = ""
    if history:
        recent = history[-8:]
        context = "\n".join(f"{'Utente' if m['role']=='user' else 'BOOST AI'}: {m['content']}" for m in recent)
    full = f"[Conversazione precedente]\n{context}\n\n[Nuovo messaggio]\n{message}" if context else message
    async for event in chat.stream_message(UserMessage(text=full)):
        if isinstance(event, TextDelta):
            yield event.content
        elif isinstance(event, StreamDone):
            break


BUILD_SYSTEM = (
    "Sei un configuratore hardware esperto. Generi build PC complete e bilanciate per gaming e streaming. "
    "Rispondi SOLO con un oggetto JSON valido, senza testo aggiuntivo, senza markdown."
)


async def generate_build(budget: int, use_case: str, resolution: str, notes: str = "") -> dict:
    prompt = (
        f"Genera una build PC per '{use_case}' con budget circa {budget} EUR, target {resolution}. "
        f"Note aggiuntive: {notes or 'nessuna'}. "
        "Restituisci un JSON con questa struttura ESATTA:\n"
        "{\n"
        '  "name": "nome accattivante della build",\n'
        '  "summary": "riassunto di 2 frasi in italiano",\n'
        '  "estimated_total": numero_intero_eur,\n'
        '  "estimated_fps": "es. 144+ FPS a 1440p",\n'
        '  "components": [\n'
        '    {"category": "CPU", "name": "modello preciso", "price": numero, "reason": "perché in italiano"},\n'
        '    {"category": "GPU", "name": "", "price": 0, "reason": ""},\n'
        '    {"category": "RAM", "name": "", "price": 0, "reason": ""},\n'
        '    {"category": "Motherboard", "name": "", "price": 0, "reason": ""},\n'
        '    {"category": "Storage", "name": "", "price": 0, "reason": ""},\n'
        '    {"category": "PSU", "name": "", "price": 0, "reason": ""},\n'
        '    {"category": "Case", "name": "", "price": 0, "reason": ""},\n'
        '    {"category": "Cooling", "name": "", "price": 0, "reason": ""}\n'
        "  ],\n"
        '  "streaming_tips": ["consiglio 1", "consiglio 2", "consiglio 3"]\n'
        "}\n"
        "Usa prezzi realistici del mercato europeo. Categorie in inglese, testi in italiano."
    )
    chat = build_chat(f"build-{budget}-{use_case}", BUILD_SYSTEM)
    text = ""
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            text += event.content
        elif isinstance(event, StreamDone):
            break
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    raise ValueError("Impossibile generare la build, riprova.")
