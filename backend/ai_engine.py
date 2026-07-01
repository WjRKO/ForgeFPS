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


async def stream_advisor(session_id: str, history: list, message: str, specs_text: str = ""):
    system = ADVISOR_SYSTEM
    if specs_text:
        system += ("\n\n[SPECIFICHE HARDWARE DELL'UTENTE - usa questi dati per consigli su misura]\n"
                   + specs_text)
    chat = build_chat(session_id, system)
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


async def _run_json(session_id: str, system: str, prompt: str) -> dict:
    chat = build_chat(session_id, system)
    text = ""
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            text += event.content
        elif isinstance(event, StreamDone):
            break
    return _parse_json(text)


UPGRADE_SYSTEM = ("Sei un tecnico esperto di upgrade PC per gaming/streaming. Analizzi l'hardware attuale, "
                  "individui il collo di bottiglia e proponi SOLO i componenti da cambiare. "
                  "Rispondi SOLO con JSON valido, senza markdown.")


async def generate_upgrade(specs_text: str, budget: int, goal: str) -> dict:
    prompt = (
        f"Hardware attuale dell'utente:\n{specs_text or 'sconosciuto'}\n\n"
        f"Obiettivo: {goal}. Budget upgrade massimo: {budget} EUR.\n"
        "Analizza e restituisci un JSON con questa struttura ESATTA:\n"
        "{\n"
        '  "bottleneck": "componente collo di bottiglia (es. GPU)",\n'
        '  "assessment": "valutazione sintetica in italiano (2-3 frasi)",\n'
        '  "recommendations": [\n'
        '    {"category":"GPU","current":"pezzo attuale o n/d","suggested":"modello consigliato","price":numero,"priority":"alta|media|bassa","reason":"perché in italiano","expected_gain":"es. +40% FPS a 1440p"}\n'
        "  ],\n"
        '  "estimated_total": numero_eur,\n'
        '  "keep": ["componenti che vanno bene e NON cambiare"]\n'
        "}\n"
        "Includi solo upgrade sensati entro il budget. Prezzi realistici mercato europeo. Testi in italiano."
    )
    return await _run_json("upgrade", UPGRADE_SYSTEM, prompt)


FPS_SYSTEM = ("Sei un benchmark expert. Stimi gli FPS attesi di un gioco su un dato hardware. "
              "Rispondi SOLO con JSON valido, senza markdown.")


async def estimate_fps(specs_text: str, game: str, resolution: str) -> dict:
    prompt = (
        f"Hardware:\n{specs_text or 'sconosciuto'}\n\n"
        f"Gioco: {game}. Risoluzione: {resolution}.\n"
        "Stima gli FPS medi realistici e restituisci un JSON con struttura ESATTA:\n"
        "{\n"
        '  "game": "nome gioco",\n'
        '  "resolution": "risoluzione",\n'
        '  "estimates": [\n'
        '    {"preset":"Basso","fps":numero},{"preset":"Medio","fps":numero},{"preset":"Alto","fps":numero},{"preset":"Ultra","fps":numero}\n'
        "  ],\n"
        '  "recommended_preset": "preset consigliato per il miglior compromesso",\n'
        '  "notes": "consigli di settaggio in italiano (2-3 punti)",\n'
        '  "confidence": "alta|media|bassa"\n'
        "}\n"
        "Se l'hardware è sconosciuto, dai una stima generica e imposta confidence bassa. Testi in italiano."
    )
    return await _run_json("fps", FPS_SYSTEM, prompt)


STARTUP_SYSTEM = ("Sei un esperto di ottimizzazione avvio Windows. Analizzi i programmi in avvio automatico "
                  "e indichi quali disabilitare in sicurezza. Rispondi SOLO con JSON valido, senza markdown.")


async def analyze_startup(startup_list: list) -> dict:
    items = "\n".join(f"- {s}" for s in startup_list[:40]) or "nessun dato"
    prompt = (
        f"Programmi in avvio automatico rilevati:\n{items}\n\n"
        "Restituisci un JSON con struttura ESATTA:\n"
        "{\n"
        '  "items": [\n'
        '    {"name":"nome programma","recommendation":"disabilita|mantieni|valuta","reason":"motivo breve in italiano","safe":true}\n'
        "  ],\n"
        '  "summary": "riassunto in italiano di cosa disabilitare per un boot più veloce"\n'
        "}\n"
        "Non consigliare MAI di disabilitare antivirus, driver audio/grafici o servizi di sistema critici. Testi in italiano."
    )
    return await _run_json("startup", STARTUP_SYSTEM, prompt)

