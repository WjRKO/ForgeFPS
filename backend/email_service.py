"""email_service.py — Resend transactional emails per FrameForge.

Template supportati:
    - trial_started        (POST /api/subscriptions/start-trial)
    - trial_ending         (cron daily, T-3 e T-1 giorni)
    - welcome              (POST /api/auth/register)
    - payment_success      (Stripe webhook checkout.session.completed)
    - payment_failed       (Stripe webhook invoice.payment_failed)

Filosofia:
    - Fire-and-forget: se Resend fallisce, loggamo e proseguiamo (mai bloccare user flow)
    - Sync SDK Resend chiamato via asyncio.to_thread per non bloccare l'event loop
    - Template inline (HTML tables, inline CSS) per max compatibilita' client email
    - Sender = SENDER_EMAIL da .env (default onboarding@resend.dev per test mode)
"""
from __future__ import annotations
import os
import asyncio
import logging
from typing import Optional

import resend
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("boostpc.email")

_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
REPLY_TO = os.environ.get("REPLY_TO_EMAIL", "support@forgefps.dev")
APP_ORIGIN = os.environ.get("APP_ORIGIN", "https://forgefps.dev")

if _API_KEY:
    resend.api_key = _API_KEY
else:
    logger.warning("RESEND_API_KEY not set — emails disabled")


# --- CORE SEND FUNCTION ------------------------------------------------------
async def send_email(to: str, subject: str, html: str, tag: str = "generic") -> Optional[str]:
    """Invia email via Resend in modo async e non-bloccante.

    Ritorna l'email_id di Resend, o None se disabilitato/errore.
    Fire-and-forget: NON solleva eccezioni (loggamo e continuiamo).
    """
    if not _API_KEY:
        logger.info("[email:%s] SKIPPED (no API key) to=%s subject=%r", tag, to, subject)
        return None

    params = {
        "from": f"FrameForge <{SENDER}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": REPLY_TO,
        "tags": [{"name": "template", "value": tag}],
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        email_id = result.get("id") if isinstance(result, dict) else None
        logger.info("[email:%s] SENT to=%s id=%s", tag, to, email_id)
        return email_id
    except Exception as e:
        logger.error("[email:%s] FAILED to=%s err=%s", tag, to, e)
        return None


# --- SHARED TEMPLATE WRAPPER -------------------------------------------------
def _wrap(title: str, preheader: str, body_html: str, cta_url: Optional[str] = None, cta_label: str = "Vai al pannello") -> str:
    """Wrapper HTML uniforme (dark theme, brand colors giallo neon #E5FF00)."""
    cta_block = ""
    if cta_url:
        cta_block = f"""
        <tr><td style="padding:24px 0 0 0;">
            <table cellpadding="0" cellspacing="0" border="0"><tr><td style="background:#E5FF00;padding:14px 28px;">
                <a href="{cta_url}" style="color:#000000;text-decoration:none;font-family:Arial,sans-serif;font-size:14px;font-weight:900;letter-spacing:1px;text-transform:uppercase;">{cta_label}</a>
            </td></tr></table>
        </td></tr>"""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#050505;font-family:Arial,Helvetica,sans-serif;color:#E4E4E7;">
<div style="display:none;font-size:1px;color:#050505;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#050505;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;background:#0A0A0F;border:1px solid #2A2A35;">
    <tr><td style="padding:20px 32px;border-bottom:1px solid #2A2A35;">
        <span style="color:#E5FF00;font-weight:900;letter-spacing:2px;font-size:14px;text-transform:uppercase;">// FRAMEFORGE</span>
    </td></tr>
    <tr><td style="padding:32px;">
        <h1 style="margin:0 0 8px 0;color:#FAFAFA;font-size:28px;font-weight:900;letter-spacing:-0.5px;line-height:1.1;">{title}</h1>
        <div style="color:#D4D4D8;font-size:15px;line-height:1.6;">{body_html}</div>
        {cta_block}
    </td></tr>
    <tr><td style="padding:20px 32px;border-top:1px solid #2A2A35;color:#71717A;font-size:12px;line-height:1.5;">
        FrameForge · Optimize your PC · <a href="{APP_ORIGIN}" style="color:#E5FF00;text-decoration:none;">forgefps.dev</a><br>
        Domande? Rispondi a questa email o scrivi a <a href="mailto:{REPLY_TO}" style="color:#E5FF00;text-decoration:none;">{REPLY_TO}</a>
    </td></tr>
</table>
</td></tr></table></body></html>"""


# --- TEMPLATES ---------------------------------------------------------------
async def send_welcome(to: str, name: str = "") -> Optional[str]:
    display = name.strip() if name else to.split("@")[0]
    body = f"""
    <p>Ciao <strong style="color:#FAFAFA;">{display}</strong>,</p>
    <p>Benvenuto su FrameForge — l'AI che boosta il tuo PC e ti trova le migliori build da gaming/streaming.</p>
    <p>Cosa puoi fare da subito (piano <strong>Starter</strong>, gratis):</p>
    <ul style="padding-left:20px;color:#D4D4D8;">
        <li>Scaricare il FrameForge Agent per Windows e ottenere l'analisi hardware</li>
        <li>Vedere il tuo Health Score PC 0-100</li>
        <li>Tracciare i prezzi di prodotti su Amazon</li>
    </ul>
    <p>Vuoi provare AI Advisor + Live Monitor? <strong>Attiva 14 giorni di Pro gratis</strong>, senza carta.</p>
    """
    return await send_email(to, "Benvenuto su FrameForge", _wrap("Benvenuto su FrameForge", "Il tuo account e' pronto — iniziamo?", body, f"{APP_ORIGIN}/app", "Vai al Dashboard"), tag="welcome")


async def send_trial_started(to: str, name: str, tier: str, days: int, expires_iso: str) -> Optional[str]:
    display = name.strip() if name else to.split("@")[0]
    tier_label = "Streamer" if tier.startswith("streamer") else "Pro"
    from datetime import datetime
    try:
        exp_date = datetime.fromisoformat(expires_iso.replace("Z", "+00:00")).strftime("%d %B %Y")
    except Exception:
        exp_date = f"tra {days} giorni"
    body = f"""
    <p>Ciao <strong style="color:#FAFAFA;">{display}</strong>,</p>
    <p>Il tuo trial <strong style="color:#E5FF00;">{tier_label}</strong> e' attivo — hai <strong>{days} giorni</strong> di accesso completo, senza carta.</p>
    <p style="color:#A1A1AA;font-size:14px;">Scade il <strong style="color:#FAFAFA;">{exp_date}</strong>.</p>
    <p>Cosa hai sbloccato:</p>
    <ul style="padding-left:20px;color:#D4D4D8;">
        <li><strong>AI Advisor</strong> — consigli su misura per il tuo hardware</li>
        <li><strong>Live Monitor</strong> — telemetria in tempo reale</li>
        <li><strong>Full Benchmark</strong> con explainer AI</li>
        <li><strong>Report PDF</strong> di ogni ottimizzazione</li>
    </ul>
    """
    return await send_email(to, f"Trial {tier_label} attivato — 14 giorni di accesso", _wrap(f"Trial {tier_label} attivo", f"Hai {days} giorni per esplorare tutto", body, f"{APP_ORIGIN}/app", "Inizia ora"), tag="trial_started")


async def send_trial_ending(to: str, name: str, tier: str, days_left: int) -> Optional[str]:
    display = name.strip() if name else to.split("@")[0]
    tier_label = "Streamer" if tier.startswith("streamer") else "Pro"
    urgency = "domani" if days_left == 1 else f"tra {days_left} giorni"
    urgency_upper = "DOMANI" if days_left == 1 else f"TRA {days_left} GIORNI"
    body = f"""
    <p>Ciao <strong style="color:#FAFAFA;">{display}</strong>,</p>
    <p>Il tuo trial <strong style="color:#E5FF00;">{tier_label}</strong> scade <strong style="color:#FF9500;">{urgency}</strong>.</p>
    <p>Continua senza interruzioni — {tier_label} parte da <strong style="color:#FAFAFA;">€{'16' if tier_label=='Streamer' else '7'}/mese</strong>, cancelli quando vuoi.</p>
    <p style="color:#A1A1AA;font-size:13px;">Se scegli l'annuale risparmi 2 mesi (~€{'32' if tier_label=='Streamer' else '14'}/anno).</p>
    """
    return await send_email(to, f"Il tuo trial {tier_label} scade {urgency}", _wrap(f"Trial in scadenza {urgency_upper}", f"Non perdere l'accesso a {tier_label}", body, f"{APP_ORIGIN}/pricing", "Continua con {tier_label}".replace("{tier_label}", tier_label)), tag="trial_ending")


async def send_payment_success(to: str, name: str, tier: str, amount: int, currency: str = "eur") -> Optional[str]:
    display = name.strip() if name else to.split("@")[0]
    tier_label = "Streamer" if tier.startswith("streamer") else "Pro"
    amount_str = f"{amount / 100:.2f} {currency.upper()}"
    body = f"""
    <p>Ciao <strong style="color:#FAFAFA;">{display}</strong>,</p>
    <p>Pagamento ricevuto — grazie per aver scelto <strong style="color:#E5FF00;">FrameForge {tier_label}</strong>!</p>
    <p style="color:#A1A1AA;font-size:14px;">Importo: <strong style="color:#FAFAFA;">{amount_str}</strong> · Metodo di pagamento gestito via Stripe.</p>
    <p>Il tuo piano e' ora <strong>attivo</strong>. Puoi gestire fatture, cambiare carta o cancellare in qualsiasi momento dal pannello Fatturazione.</p>
    """
    return await send_email(to, f"Pagamento confermato — FrameForge {tier_label} attivo", _wrap(f"Grazie, {display}!", "Il tuo piano FrameForge e' ora attivo", body, f"{APP_ORIGIN}/app/billing", "Gestisci fatturazione"), tag="payment_success")


async def send_payment_failed(to: str, name: str, tier: str) -> Optional[str]:
    display = name.strip() if name else to.split("@")[0]
    tier_label = "Streamer" if tier.startswith("streamer") else "Pro"
    body = f"""
    <p>Ciao <strong style="color:#FAFAFA;">{display}</strong>,</p>
    <p>Il rinnovo del tuo abbonamento <strong style="color:#E5FF00;">{tier_label}</strong> non e' andato a buon fine.</p>
    <p style="color:#A1A1AA;font-size:14px;">Cause comuni: carta scaduta, fondi insufficienti, o limite di transazione della banca.</p>
    <p>Non preoccuparti — <strong>hai 7 giorni</strong> per aggiornare il metodo di pagamento prima che il piano venga sospeso.</p>
    """
    return await send_email(to, f"Rinnovo FrameForge {tier_label} fallito — azione richiesta", _wrap("Rinnovo pagamento fallito", "Aggiorna il metodo di pagamento entro 7 giorni", body, f"{APP_ORIGIN}/app/billing", "Aggiorna pagamento"), tag="payment_failed")
