import os
import json
import re
import uuid
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone, ImageContent

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-6"
AI_TIMEOUT = 45

ADVISOR_SYSTEM = (
    "You are BOOST AI, an expert PC optimization assistant for gamers and streamers. "
    "Provide practical, precise and step-by-step advice on: Windows tweaks, GPU settings (NVIDIA/AMD), "
    "OBS/streaming, temperature management, safe overclocking, drivers, startup and background apps, latency and FPS. "
    "Be concise, technical yet accessible. Format responses in Markdown: use bold, headings, bullet lists and numbered steps. "
    "When providing Windows commands, wrap them in PowerShell code blocks (```powershell ... ```). "
    "If an action is risky, warn the user. Never invent commands that don't exist."
)

BENCH_SYSTEM = (
    "Sei un tecnico esperto di PC gaming. Spieghi i risultati dei benchmark in modo chiaro, onesto e concreto, "
    "senza esagerare i numeri. Rispondi in Markdown semplice (grassetto ed elenchi puntati), massimo 220 parole."
)


async def explain_benchmark(specs_text: str, before: dict | None, after: dict, lang: str = "it") -> str:
    import uuid as _uuid
    lang_line = "Rispondi in italiano." if (lang or "it").startswith("it") else "Answer in English."
    prompt = (
        f"Hardware dell'utente:\n{specs_text or 'sconosciuto'}\n\n"
        f"Benchmark PRIMA dell'ottimizzazione: {json.dumps(before, ensure_ascii=False) if before else 'non disponibile'}\n"
        f"Benchmark DOPO/ATTUALE: {json.dumps(after, ensure_ascii=False)}\n\n"
        "Significato metriche: cpu_score (piu alto=meglio), ram_mbps (banda RAM), disk_write_mbps/disk_read_mbps "
        "(MB/s sequenziali reali), iops_4k (scritture casuali 4K sincrone: reattivita del disco), dpc_ms (latenza "
        "scheduler/DPC p95: piu bassa=meglio, sopra 2ms causa micro-stutter nei giochi), ping_ms e jitter_ms (rete), "
        "boot_s (secondi di avvio Windows), score (punteggio composito 0-100), free_ram_pct (RAM libera).\n"
        "Scrivi: 1) se esiste un PRIMA, cosa e migliorato e di quanto (in percentuale); 2) il punto piu debole del "
        "sistema e la causa probabile; 3) 2-3 consigli concreti e sicuri per migliorarlo. " + lang_line
    )
    chat = build_chat(f"bench-explain-{_uuid.uuid4()}", BENCH_SYSTEM)
    text = await asyncio.wait_for(_collect(chat, prompt), timeout=AI_TIMEOUT)
    return text.strip()


def get_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


def build_chat(session_id: str, system: str = ADVISOR_SYSTEM) -> LlmChat:
    return LlmChat(api_key=get_key(), session_id=session_id,
                   system_message=system).with_model(MODEL_PROVIDER, MODEL_NAME)


async def stream_advisor(session_id: str, history: list, message: str, specs_text: str = "", lang: str = "it", image_data_url: str = ""):
    system = ADVISOR_SYSTEM
    # Language directive: explicit, always present (Claude follows the last relevant instruction).
    is_en = (lang or "it").startswith("en")
    if is_en:
        system += "\n\nLANGUAGE: Reply ENTIRELY in English. Keep Markdown formatting and PowerShell code blocks."
    else:
        system += "\n\nLINGUA: Rispondi INTERAMENTE in italiano. Mantieni il Markdown e i blocchi di codice PowerShell."
    if specs_text:
        if is_en:
            system += ("\n\n[USER PC CONTEXT - use these REAL data for personalized advice. "
                       "Proactively reference Health Score, detected issues, temperatures, benchmarks and "
                       "startup programs when relevant (e.g. cite the real value: 'your driver is X days old', "
                       "'CPU at Y degC'). Precisely identify generation and tier of CPU and GPU (e.g. Ampere/Ada, "
                       "Zen3/Zen4). If the motherboard is listed as an OEM code (e.g. MS-7C56, MS-7B86), translate "
                       "it to the real commercial name (e.g. MSI B550 Tomahawk) and verify socket/chipset compatibility. "
                       "When suggesting Windows commands, provide them in PowerShell code blocks (```powershell ... ```) "
                       "so the user can copy them. Use Markdown: bold, lists, headings.]\n" + specs_text)
        else:
            system += ("\n\n[CONTESTO PC DELL'UTENTE - usa questi dati REALI per consigli su misura. "
                       "Fai riferimento PROATTIVO a Health Score, problemi rilevati, temperature, benchmark e "
                       "programmi all'avvio quando pertinenti (es. cita il valore reale: 'il tuo driver ha X giorni', "
                       "'CPU a Y°C'). Identifica con precisione generazione e fascia di CPU e GPU (es. Ampere/Ada, "
                       "Zen3/Zen4). Se la scheda madre è indicata come codice OEM (es. MS-7C56, MS-7B86), traducilo "
                       "nel nome commerciale reale (es. MSI B550 Tomahawk) e verifica la compatibilità socket/chipset. "
                       "Quando suggerisci comandi Windows, forniscili in blocchi di codice PowerShell (```powershell ... ```) "
                       "così l'utente può copiarli. Usa Markdown: grassetto, elenchi, titoli.]\n" + specs_text)
    chat = build_chat(session_id, system)
    # replay history into context
    context = ""
    if history:
        recent = history[-8:]
        role_user = "User" if is_en else "Utente"
        context = "\n".join(f"{role_user if m['role']=='user' else 'BOOST AI'}: {m['content']}" for m in recent)
    if context:
        prev_hdr = "[Previous conversation]" if is_en else "[Conversazione precedente]"
        new_hdr = "[New message]" if is_en else "[Nuovo messaggio]"
        full = f"{prev_hdr}\n{context}\n\n{new_hdr}\n{message}"
    else:
        full = message
    kwargs = {"text": full}
    if image_data_url and image_data_url.startswith("data:image/"):
        try:
            b64 = image_data_url.split(",", 1)[1]
            kwargs["file_contents"] = [ImageContent(image_base64=b64)]
        except Exception:
            pass
    async for event in chat.stream_message(UserMessage(**kwargs)):
        if isinstance(event, TextDelta):
            yield event.content
        elif isinstance(event, StreamDone):
            break


async def generate_followups(history: list, lang: str = "it") -> list:
    """Genera 3 follow-up chip cliccabili dalla conversazione. Ritorna [str, str, str]."""
    if not history:
        return []
    recent = history[-6:]
    is_en = (lang or "it").startswith("en")
    convo = "\n".join(f"{'User' if m['role']=='user' else 'AI'}: {(m['content'] or '')[:400]}" for m in recent)
    if is_en:
        system = (
            "You generate 3 possible FOLLOW-UP questions the user might ask next. "
            "Each must be SHORT (max 8 words), specific to the context, and each should open a different "
            "direction (technical deep-dive, practical action, comparison). "
            "Reply ONLY with 3 lines, one per line, no numbering, no other text. Language: English."
        )
        prompt = f"Conversation:\n{convo}\n\n3 follow-ups:"
    else:
        system = (
            "Sei un assistente che genera 3 possibili domande di FOLLOW-UP che l'utente potrebbe fare "
            "dopo la conversazione. Devono essere BREVI (max 8 parole), specifiche al contesto, e ognuna "
            "deve aprire una direzione diversa (approfondimento tecnico, azione pratica, confronto). "
            "Rispondi ESCLUSIVAMENTE con 3 righe, una per riga, senza numerazione, senza altro testo. Lingua: italiano."
        )
        prompt = f"Conversazione:\n{convo}\n\n3 follow-up:"
    chat = build_chat(str(uuid.uuid4()), system)
    text = await _collect(chat, prompt)
    lines = [ln.strip("-* \t") for ln in (text or "").strip().split("\n") if ln.strip()]
    return lines[:3]


async def one_shot_advisor(prompt: str, specs_text: str = "", lang: str = "it") -> str:
    """Chiama l'AI advisor una volta con context PC completo (no chat history).
    Ritorna testo raw. Usato per diagnosi strutturate JSON."""
    system = ADVISOR_SYSTEM
    if (lang or "it").startswith("en"):
        system += "\n\nReply in English."
    if specs_text:
        system += (
            "\n\n[CONTESTO PC DELL'UTENTE - usa questi dati REALI per la diagnosi. "
            "Fai riferimento a valori concreti quando possibile.]\n" + specs_text
        )
    chat = build_chat(str(uuid.uuid4()), system)
    return await _collect(chat, prompt)


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
    try:
        text = await asyncio.wait_for(_collect(chat, prompt), timeout=AI_TIMEOUT)
    except asyncio.TimeoutError:
        raise ValueError("La generazione della build ha impiegato troppo tempo (timeout). Riprova.")
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


async def _collect(chat, prompt: str) -> str:
    text = ""
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            text += event.content
        elif isinstance(event, StreamDone):
            break
    return text


async def _run_json(session_id: str, system: str, prompt: str) -> dict:
    chat = build_chat(session_id, system)
    try:
        text = await asyncio.wait_for(_collect(chat, prompt), timeout=AI_TIMEOUT)
    except asyncio.TimeoutError:
        raise ValueError("La richiesta AI ha impiegato troppo tempo (timeout). Riprova.")
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
        "Identifica con precisione il tier esatto di CPU e GPU (generazione e fascia) e considera VRAM, "
        "frequenza RAM e refresh del monitor. Stima gli FPS medi realistici basandoti su benchmark noti "
        "per quella specifica combinazione hardware. Restituisci un JSON con struttura ESATTA:\n"
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

