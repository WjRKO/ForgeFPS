"""FrameForge Discord Bot (discord.py 2.x, persistent WebSocket).

Comandi slash disponibili nel guild configurato via DISCORD_GUILD_ID:
- /mypc          Mostra il tuo Health Score
- /benchmark     Ultimo benchmark salvato
- /leaderboard   Top 10 utenti per punteggio
- /link          Istruzioni per collegare l'account su FrameForge
- /help          Aiuto

Eventi:
- on_member_join: welcome DM + assegna ruolo Boosted PC se configurato

Il bot legge MongoDB direttamente (stesso DB del backend FastAPI).

Avvio:
    python -m backend.discord_bot
Gestito da supervisor come processo separato dal backend FastAPI.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# Carica .env dal path del backend
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

import discord
from discord import app_commands
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("frameforge.bot")

BOT_TOKEN = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
GUILD_ID = (os.environ.get("DISCORD_GUILD_ID") or "").strip()
ROLE_BOOSTED_ID = (os.environ.get("DISCORD_ROLE_BOOSTED_ID") or "").strip()
ROLE_PRO_ID = (os.environ.get("DISCORD_ROLE_PRO") or "").strip()
ROLE_CREATOR_ID = (os.environ.get("DISCORD_ROLE_CREATOR_VERIFIED") or "").strip()
CHANNEL_CREATOR_REVIEW_ID = (os.environ.get("DISCORD_CHANNEL_CREATOR_REVIEW") or "").strip()
PRO_PLANS = {"pro", "creator"}  # piani che ottengono il ruolo Pro
PRO_SYNC_INTERVAL = int(os.environ.get("DISCORD_PRO_SYNC_INTERVAL", "300"))  # 5 min
CREATOR_REAPPLY_DAYS = int(os.environ.get("DISCORD_CREATOR_REAPPLY_DAYS", "7"))
MONGO_URL = (os.environ.get("MONGO_URL") or "").strip()
DB_NAME = (os.environ.get("DB_NAME") or "test_database").strip()
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "https://forgefps.dev").strip().rstrip("/")

if not BOT_TOKEN:
    raise SystemExit("[bot] DISCORD_BOT_TOKEN non impostato in .env")
if not GUILD_ID:
    raise SystemExit("[bot] DISCORD_GUILD_ID non impostato in .env")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # richiede Privileged Intent "Server Members" nel Portal
intents.message_content = False  # non serve per slash commands

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
GUILD = discord.Object(id=int(GUILD_ID))

# Mongo async
_mongo = AsyncIOMotorClient(MONGO_URL)
db = _mongo[DB_NAME]


# --------- helpers ---------
async def _find_user_by_discord_id(discord_user_id: str):
    return await db.users.find_one({"discord_user_id": str(discord_user_id)})


async def _get_health_score(user_doc: dict) -> int:
    """Prende l'ultimo Health Score dal documento utente / da pc_specs."""
    uid = str(user_doc.get("_id") or user_doc.get("id") or "")
    specs = await db.pc_specs.find_one({"user_id": uid})
    if not specs:
        return 0
    return int(specs.get("health_score") or 0)


async def _last_benchmark(user_doc: dict) -> dict | None:
    uid = str(user_doc.get("_id") or user_doc.get("id") or "")
    bench = await db.benchmarks.find_one({"user_id": uid}, sort=[("timestamp", -1)])
    return bench


def _user_plan(user_doc: dict) -> str:
    """Ritorna il piano dell'utente (default: free). Normalizzato lowercase."""
    return (user_doc.get("plan") or "free").strip().lower()


async def _sync_role(member: discord.Member, role_id: str, should_have: bool, reason: str) -> str:
    """Aggiunge/rimuove un ruolo Discord sul membro in modo idempotente.
    Ritorna: 'added' | 'removed' | 'noop' | 'skip'."""
    if not role_id:
        return "skip"
    role = member.guild.get_role(int(role_id))
    if not role:
        logger.warning("Ruolo %s non trovato nel guild", role_id)
        return "skip"
    has_role = role in member.roles
    try:
        if should_have and not has_role:
            await member.add_roles(role, reason=reason)
            return "added"
        if (not should_have) and has_role:
            await member.remove_roles(role, reason=reason)
            return "removed"
    except discord.Forbidden as e:
        logger.warning("Permessi insufficienti per ruolo %s su %s: %s", role_id, member.id, e)
        return "skip"
    except Exception as e:
        logger.warning("Sync ruolo %s per %s fallito: %s", role_id, member.id, e)
        return "skip"
    return "noop"


async def _sync_pro_role_for_member(guild: discord.Guild, member: discord.Member, user_doc: dict | None) -> str:
    """Wrapper legacy per la sync del ruolo Pro (mantenuto per /set-plan)."""
    is_pro = bool(user_doc) and _user_plan(user_doc) in PRO_PLANS
    return await _sync_role(member, ROLE_PRO_ID, is_pro, f"Pro auto-sync (plan={_user_plan(user_doc or {})})")


async def _sync_all_roles_for_member(member: discord.Member, user_doc: dict | None) -> dict:
    """Allinea tutti i ruoli auto (Boosted PC + Pro) sul membro."""
    is_linked = bool(user_doc)
    is_pro = is_linked and _user_plan(user_doc) in PRO_PLANS
    return {
        "boosted": await _sync_role(member, ROLE_BOOSTED_ID, is_linked, "Boosted PC auto-sync (account collegato)"),
        "pro": await _sync_role(member, ROLE_PRO_ID, is_pro, f"Pro auto-sync (plan={_user_plan(user_doc or {})})"),
    }


async def _pro_sync_loop():
    """Task background: ogni PRO_SYNC_INTERVAL secondi allinea i ruoli Boosted PC + Pro
    a tutti gli utenti che hanno Discord linkato. Idempotente."""
    await client.wait_until_ready()
    if not (ROLE_PRO_ID or ROLE_BOOSTED_ID):
        logger.info("Role sync loop: nessun ROLE_ID impostato, skip")
        return
    guild = client.get_guild(int(GUILD_ID))
    if not guild:
        logger.warning("Role sync loop: guild %s non trovato, skip", GUILD_ID)
        return
    while not client.is_closed():
        try:
            counts = {"boosted_added": 0, "boosted_removed": 0, "pro_added": 0, "pro_removed": 0, "skip": 0}
            cursor = db.users.find(
                {"discord_user_id": {"$exists": True, "$nin": [None, ""]}},
                {"discord_user_id": 1, "plan": 1, "email": 1},
            )
            async for udoc in cursor:
                did = str(udoc.get("discord_user_id") or "")
                if not did:
                    continue
                member = guild.get_member(int(did))
                if not member:
                    try:
                        member = await guild.fetch_member(int(did))
                    except Exception:
                        continue
                res = await _sync_all_roles_for_member(member, udoc)
                for role_name, result in res.items():
                    if result in ("added", "removed"):
                        counts[f"{role_name}_{result}"] = counts.get(f"{role_name}_{result}", 0) + 1
                    elif result == "skip":
                        counts["skip"] += 1
            logger.info(
                "Role sync: boosted +%d/-%d, pro +%d/-%d, skip=%d",
                counts["boosted_added"], counts["boosted_removed"],
                counts["pro_added"], counts["pro_removed"], counts["skip"],
            )
        except Exception as e:
            logger.exception("Role sync loop errore: %s", e)
        await asyncio.sleep(PRO_SYNC_INTERVAL)


def _link_hint_embed() -> discord.Embed:
    return discord.Embed(
        title="Collega il tuo account FrameForge",
        description=(
            f"Non sei ancora collegato. Vai su [Account]({FRONTEND_URL}/app/account) "
            f"e clicca **Collega Discord**."
        ),
        color=0xE5FF00,
    )


# --------- Slash Commands ---------
@tree.command(name="mypc", description="Mostra il tuo Health Score PC", guild=GUILD)
async def cmd_mypc(interaction: discord.Interaction):
    doc = await _find_user_by_discord_id(str(interaction.user.id))
    if not doc:
        return await interaction.response.send_message(embed=_link_hint_embed(), ephemeral=True)
    score = await _get_health_score(doc)
    color = 0x00FF66 if score >= 75 else (0xFFAA00 if score >= 50 else 0xFF3355)
    emb = discord.Embed(
        title=f"Health Score: {score}/100",
        description="I dati vengono aggiornati dal desktop agent FrameForge.",
        color=color,
        url=f"{FRONTEND_URL}/app/pc",
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(name="benchmark", description="Ultimo benchmark salvato", guild=GUILD)
async def cmd_benchmark(interaction: discord.Interaction):
    doc = await _find_user_by_discord_id(str(interaction.user.id))
    if not doc:
        return await interaction.response.send_message(embed=_link_hint_embed(), ephemeral=True)
    b = await _last_benchmark(doc)
    if not b:
        return await interaction.response.send_message("Nessun benchmark ancora salvato. Lancia l'agent con `--mode optimize` e attiva la spunta *Benchmark PRIMA/DOPO*.", ephemeral=True)
    score = int(b.get("score") or 0)
    ts = b.get("timestamp") or ""
    metrics = b.get("metrics") or {}
    emb = discord.Embed(title=f"Benchmark: {score}/100", color=0x00E0FF, url=f"{FRONTEND_URL}/app/pc")
    emb.add_field(name="DPC latency", value=f"{metrics.get('dpc_us','?')} μs", inline=True)
    emb.add_field(name="Disk IOPS", value=f"{metrics.get('iops','?')}", inline=True)
    emb.add_field(name="Jitter", value=f"{metrics.get('jitter_ms','?')} ms", inline=True)
    if ts:
        emb.set_footer(text=f"Salvato: {ts}")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(name="leaderboard", description="Top 10 utenti per Health Score", guild=GUILD)
async def cmd_leaderboard(interaction: discord.Interaction):
    cursor = db.pc_specs.find({"health_score": {"$gt": 0}}).sort("health_score", -1).limit(10)
    lines = []
    rank = 1
    async for row in cursor:
        uid = row.get("user_id")
        udoc = await db.users.find_one({"_id": uid}) if uid else None
        name = "Anonimo"
        if udoc:
            name = udoc.get("discord_username") or udoc.get("name") or udoc.get("email", "").split("@")[0] or "Anonimo"
        lines.append(f"**{rank}.** {name} — {int(row.get('health_score') or 0)}")
        rank += 1
    desc = "\n".join(lines) if lines else "Nessun punteggio ancora."
    emb = discord.Embed(title="Leaderboard FrameForge", description=desc, color=0xE5FF00, url=f"{FRONTEND_URL}/app/pc")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(name="link", description="Istruzioni per collegare l'account FrameForge", guild=GUILD)
async def cmd_link(interaction: discord.Interaction):
    doc = await _find_user_by_discord_id(str(interaction.user.id))
    if doc:
        await interaction.response.send_message(
            f"Sei gia' collegato come **{doc.get('discord_username') or doc.get('name') or doc.get('email','')}**. "
            f"Se vuoi scollegarti vai su {FRONTEND_URL}/app/account.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(embed=_link_hint_embed(), ephemeral=True)


@tree.command(name="help", description="Aiuto e comandi disponibili", guild=GUILD)
async def cmd_help(interaction: discord.Interaction):
    emb = discord.Embed(
        title="\u26a1 FrameForge Bot \u00b7 Guida ai comandi",
        description="Il bot ufficiale di **FrameForge**. Ecco cosa puoi fare qui su Discord:",
        color=0xE5FF00,
    )
    emb.add_field(
        name="\ud83d\udd17 Onboarding",
        value=(
            "**/link** \u2014 collega il tuo account FrameForge (obbligatorio per gli altri comandi)\n"
            "**/come-iniziare** \u2014 guida rapida in 3 step\n"
            "**/ruoli** \u2014 lista dei ruoli disponibili e come ottenerli\n"
            "**/canali** \u2014 mappa dei canali chiave"
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83c\udfae Gaming & PC",
        value=(
            "**/mypc** \u2014 il tuo Health Score PC (0-100) + hardware\n"
            "**/benchmark** \u2014 ultimo benchmark salvato\n"
            "**/leaderboard** \u2014 top 10 utenti per Health Score"
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83c\udfac Creator",
        value=(
            "**/apply-creator link:<twitch/youtube/kick>** \u2014 candidati al ruolo **Creator Verified**"
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83d\udee1\ufe0f Admin",
        value=(
            "**/set-plan** \u2014 cambia il piano di un utente collegato\n"
            "**/announce-release** \u2014 annuncia una release sul canale changelog"
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83c\udf10 Link utili",
        value=(
            f"[Sito]({FRONTEND_URL}) \u00b7 "
            f"[Guida completa]({FRONTEND_URL}/guida) \u00b7 "
            f"[Changelog]({FRONTEND_URL}/changelog) \u00b7 "
            f"[Scarica agent]({FRONTEND_URL}/app/desktop)"
        ),
        inline=False,
    )
    emb.set_footer(text="I comandi funzionano solo se hai collegato l'account con /link")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(name="come-iniziare", description="Guida rapida in 3 step per i nuovi membri", guild=GUILD)
async def cmd_come_iniziare(interaction: discord.Interaction):
    emb = discord.Embed(
        title="\ud83d\ude80 Come iniziare su FrameForge",
        description="Benvenuto! Ecco cosa fare nei primi minuti:",
        color=0x00E0FF,
    )
    emb.add_field(
        name="1\ufe0f\u20e3  Crea un account (30 secondi)",
        value=f"Vai su {FRONTEND_URL} e clicca **Inizia ora**. Bastano email + password.",
        inline=False,
    )
    emb.add_field(
        name="2\ufe0f\u20e3  Collega Discord all'account",
        value=(
            f"Sulla pagina [Account]({FRONTEND_URL}/app/account) clicca **Collega Discord**.\n"
            "Oppure fai `/link` qui su Discord e segui le istruzioni.\n"
            "Otterrai automaticamente il ruolo **Boosted PC**."
        ),
        inline=False,
    )
    emb.add_field(
        name="3\ufe0f\u20e3  Scarica il Desktop Agent",
        value=(
            f"Dalla pagina [Desktop Agent]({FRONTEND_URL}/app/desktop) scarica `.exe` firmato.\n"
            "L'agent rileva il tuo hardware, calcola il tuo Health Score e ti suggerisce boost personalizzati.\n"
            f"Nel dubbio, apri la [Guida completa]({FRONTEND_URL}/guida)."
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83c\udfa4 Sei streamer/creator?",
        value="Fai `/apply-creator link:<tuo canale>` per candidarti al ruolo **Creator Verified**.",
        inline=False,
    )
    emb.set_footer(text="Serve aiuto? Chiedi in #aiuto o menziona lo staff.")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(name="ruoli", description="Lista dei ruoli disponibili e come ottenerli", guild=GUILD)
async def cmd_ruoli(interaction: discord.Interaction):
    emb = discord.Embed(
        title="\ud83c\udfad Ruoli del server",
        description="Ecco tutti i ruoli disponibili e come ottenerli:",
        color=0xE5FF00,
    )
    emb.add_field(
        name="\ud83c\udfae Boosted PC \u2014 automatico",
        value="Assegnato appena colleghi l'account FrameForge con `/link` o dalla pagina Account.",
        inline=False,
    )
    emb.add_field(
        name="\u2b50 Pro \u2014 automatico",
        value=(
            "Assegnato agli utenti con piano **Pro** o **Creator** attivo su FrameForge.\n"
            "Sincronizzato in tempo reale col database (max 5 min di ritardo)."
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83c\udfac Creator Verified \u2014 su candidatura",
        value=(
            "Riservato a streamer e content creator verificati.\n"
            "Candidati con `/apply-creator link:<twitch/youtube/kick>` \u2014 lo staff revisiona la richiesta."
        ),
        inline=False,
    )
    emb.add_field(
        name="\ud83d\udee1\ufe0f Staff \u2014 nomina manuale",
        value="Assegnato solo dai fondatori a moderatori e collaboratori attivi.",
        inline=False,
    )
    emb.set_footer(text="I ruoli auto vengono sincronizzati ogni 5 minuti.")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(name="canali", description="Mappa dei canali del server", guild=GUILD)
async def cmd_canali(interaction: discord.Interaction):
    emb = discord.Embed(
        title="\ud83d\uddfa\ufe0f Mappa dei canali",
        description="Cosa trovi dove:",
        color=0x00FF66,
    )
    emb.add_field(name="\ud83d\udcdc  #regole", value="Le regole del server. Leggile prima di scrivere.", inline=False)
    emb.add_field(name="\ud83d\udc4b  #benvenuto / #presentazioni", value="Presentati! Nome, PC, giochi preferiti.", inline=False)
    emb.add_field(name="\ud83d\udce3  #annunci", value="Novit\u00e0 dal team, roadmap, sondaggi.", inline=False)
    emb.add_field(name="\ud83d\udcdd  #changelog", value="Annunci automatici delle nuove release FrameForge.", inline=False)
    emb.add_field(name="\ud83d\udcb0  #price-drops", value="Notifiche automatiche di cali di prezzo dai tracker degli utenti.", inline=False)
    emb.add_field(name="\ud83c\udfc6  #scores / #showcase", value="Condividi il tuo Health Score e i tuoi setup.", inline=False)
    emb.add_field(name="\ud83d\udcac  #chat-generale", value="Chiacchiere libere: gaming, hardware, streaming.", inline=False)
    emb.add_field(name="\ud83c\udd98  #aiuto", value="Bloccato con un tweak? L'AI o lo staff ti aiuta qui.", inline=False)
    emb.set_footer(text="Il nome esatto dei canali pu\u00f2 variare. Usa la barra laterale per orientarti.")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@tree.command(
    name="set-plan",
    description="[ADMIN] Cambia il piano di un utente collegato (free/pro/creator)",
    guild=GUILD,
)
@app_commands.describe(user="Membro Discord (deve aver linkato l'account)", plan="Piano da assegnare")
@app_commands.choices(plan=[
    app_commands.Choice(name="free", value="free"),
    app_commands.Choice(name="pro", value="pro"),
    app_commands.Choice(name="creator", value="creator"),
])
async def cmd_set_plan(
    interaction: discord.Interaction,
    user: discord.Member,
    plan: app_commands.Choice[str],
):
    # Permesso: solo Administrator del server
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "Solo gli Amministratori del server possono usare questo comando.",
            ephemeral=True,
        )
    # Defer subito: DB + role update superano il timeout di 3s di Discord
    await interaction.response.defer(ephemeral=True)
    try:
        doc = await _find_user_by_discord_id(str(user.id))
        if not doc:
            return await interaction.followup.send(
                f"{user.mention} non ha ancora collegato l'account FrameForge. "
                f"Chiedigli di fare `/link` o di visitare {FRONTEND_URL}/app/account.",
                ephemeral=True,
            )
        new_plan = plan.value.strip().lower()
        await db.users.update_one(
            {"_id": doc["_id"]},
            {"$set": {"plan": new_plan, "plan_updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        # sync ruolo immediato
        doc["plan"] = new_plan
        result = await _sync_pro_role_for_member(interaction.guild, user, doc)
        role_msg = {
            "added": "\u2705 Ruolo Pro aggiunto.",
            "removed": "\u2705 Ruolo Pro rimosso.",
            "noop": "Nessuna modifica al ruolo (gi\u00e0 corretto).",
            "skip": "\u26a0\ufe0f Sync ruolo saltato (bot senza permesso o ruolo pi\u00f9 in alto nella gerarchia).",
        }.get(result, result)
        await interaction.followup.send(
            f"Piano di {user.mention} aggiornato a **{new_plan}**. {role_msg}",
            ephemeral=True,
        )
    except Exception as e:
        logger.exception("/set-plan errore: %s", e)
        await interaction.followup.send(f"Errore: {e}", ephemeral=True)


@tree.command(
    name="announce-release",
    description="[ADMIN] Forza l'annuncio di una release sul canale changelog",
    guild=GUILD,
)
@app_commands.describe(
    version="Versione (es. 0.6.3). Deve essere presente in /app/data/releases.json",
    force="Se true, ri-annuncia anche se gia' annunciata in passato",
)
async def cmd_announce_release(
    interaction: discord.Interaction, version: str, force: bool = False
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "Solo gli Amministratori del server possono usare questo comando.",
            ephemeral=True,
        )
    await interaction.response.defer(ephemeral=True)
    try:
        from services.release_announcer import announce_release_by_version
        ok, msg = await announce_release_by_version(version.strip(), force=force)
        emoji = "\u2705" if ok else "\u26a0\ufe0f"
        await interaction.followup.send(f"{emoji} {msg}", ephemeral=True)
    except Exception as e:
        logger.exception("/announce-release errore: %s", e)
        await interaction.followup.send(f"Errore interno: {e}", ephemeral=True)



# --------- /apply-creator: richiesta ruolo Creator Verified con approvazione staff ---------

_CREATOR_URL_HOSTS = ("twitch.tv", "youtube.com", "youtu.be", "kick.com")


def _is_valid_creator_url(url: str) -> bool:
    """Valida che sia un link Twitch, YouTube o Kick."""
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return False
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        host = host.lower().lstrip("www.")
        return any(host == h or host.endswith("." + h) for h in _CREATOR_URL_HOSTS)
    except Exception:
        return False


class CreatorReviewView(discord.ui.View):
    """View persistente per l'approvazione/rifiuto delle richieste creator.
    I bottoni hanno custom_id fisso per sopravvivere ai restart del bot."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approva", style=discord.ButtonStyle.success, emoji="\u2705", custom_id="creator_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, approved=True)

    @discord.ui.button(label="Rifiuta", style=discord.ButtonStyle.danger, emoji="\u274c", custom_id="creator_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, approved=False)

    async def _decide(self, interaction: discord.Interaction, approved: bool):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "Solo gli Amministratori possono approvare/rifiutare le richieste.",
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        app_doc = await self._load_application(interaction)
        if app_doc is None:
            return
        applicant = await self._resolve_applicant(interaction, app_doc)
        await self._persist_decision(app_doc, interaction, approved)
        role_msg = await self._assign_creator_role(interaction, applicant, approved)
        await self._notify_applicant(applicant, app_doc, approved)
        await self._update_review_message(interaction, approved)
        state = "APPROVATA" if approved else "RIFIUTATA"
        await interaction.followup.send(
            f"\u2705 Richiesta {state.lower()}.{role_msg}",
            ephemeral=True,
        )

    async def _load_application(self, interaction: discord.Interaction):
        """Fetch application by message id; None if missing or already processed."""
        msg = interaction.message
        app_doc = await db.creator_applications.find_one({"message_id": str(msg.id)})
        if not app_doc:
            await interaction.followup.send(
                "Richiesta non trovata nel database (potrebbe essere gia' stata processata).",
                ephemeral=True,
            )
            return None
        if app_doc.get("status") in ("approved", "rejected"):
            await interaction.followup.send(
                f"Richiesta gia' processata (status={app_doc.get('status')}) da {app_doc.get('reviewed_by_name', '?')}.",
                ephemeral=True,
            )
            return None
        return app_doc

    async def _resolve_applicant(self, interaction, app_doc):
        applicant_id = int(app_doc["discord_user_id"])
        return interaction.guild.get_member(applicant_id) or await interaction.guild.fetch_member(applicant_id)

    async def _persist_decision(self, app_doc, interaction, approved: bool):
        await db.creator_applications.update_one(
            {"_id": app_doc["_id"]},
            {"$set": {
                "status": "approved" if approved else "rejected",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by_id": str(interaction.user.id),
                "reviewed_by_name": interaction.user.display_name,
            }},
        )

    async def _assign_creator_role(self, interaction, applicant, approved: bool) -> str:
        if not (approved and ROLE_CREATOR_ID and applicant):
            return ""
        role = interaction.guild.get_role(int(ROLE_CREATOR_ID))
        if not role:
            return ""
        try:
            await applicant.add_roles(role, reason=f"Creator Verified approvato da {interaction.user.display_name}")
            return " Ruolo assegnato."
        except discord.Forbidden:
            return " \u26a0\ufe0f Impossibile assegnare il ruolo (permessi/gerarchia)."
        except Exception as e:
            logger.warning("add creator role failed: %s", e)
            return f" \u26a0\ufe0f Errore assegnazione: {e}"

    async def _notify_applicant(self, applicant, app_doc, approved: bool):
        if not applicant:
            return
        if approved:
            text = (
                "\ud83c\udf89 **La tua richiesta Creator Verified su FrameForge \u00e8 stata approvata!**\n"
                f"Ora hai il ruolo **Creator Verified**. Buon boost e buon lavoro con il tuo canale! \ud83d\ude80\n\n"
                f"Link condiviso: {app_doc.get('url', '-')}"
            )
        else:
            text = (
                "\ud83d\ude14 **La tua richiesta Creator Verified su FrameForge \u00e8 stata rifiutata.**\n"
                f"Puoi riprovare tra {CREATOR_REAPPLY_DAYS} giorni con `/apply-creator`.\n\n"
                f"Link inviato: {app_doc.get('url', '-')}"
            )
        try:
            await applicant.send(text)
        except discord.Forbidden:
            pass  # DM chiusi

    async def _update_review_message(self, interaction, approved: bool):
        msg = interaction.message
        emb = msg.embeds[0] if msg.embeds else discord.Embed()
        emb.color = 0x00FF66 if approved else 0xFF3B30
        state = "APPROVATA" if approved else "RIFIUTATA"
        emb.add_field(name="Decisione", value=f"**{state}** da {interaction.user.mention}", inline=False)
        new_view = discord.ui.View(timeout=None)  # disable buttons
        try:
            await msg.edit(embed=emb, view=new_view)
        except Exception as e:
            logger.warning("edit review message failed: %s", e)


async def _check_creator_reapply_cooldown(interaction):
    """Return True if applicant is blocked by recent rejection cooldown (also sends the ephemeral response)."""
    recent_reject = await db.creator_applications.find_one(
        {"discord_user_id": str(interaction.user.id), "status": "rejected"},
        sort=[("reviewed_at", -1)],
    )
    if not (recent_reject and recent_reject.get("reviewed_at")):
        return False
    try:
        reviewed = datetime.fromisoformat(recent_reject["reviewed_at"].replace("Z", "+00:00"))
    except Exception:
        return False
    elapsed_days = (datetime.now(timezone.utc) - reviewed).days
    if elapsed_days < CREATOR_REAPPLY_DAYS:
        remain = CREATOR_REAPPLY_DAYS - elapsed_days
        await interaction.followup.send(
            f"La tua richiesta e' stata rifiutata di recente. Potrai riprovare tra **{remain} giorni**.",
            ephemeral=True,
        )
        return True
    return False


async def _resolve_review_channel(interaction):
    channel = interaction.guild.get_channel(int(CHANNEL_CREATOR_REVIEW_ID))
    if channel:
        return channel
    try:
        return await client.fetch_channel(int(CHANNEL_CREATOR_REVIEW_ID))
    except Exception:
        return None


def _build_creator_review_embed(interaction, user_doc: dict, link: str) -> discord.Embed:
    emb = discord.Embed(
        title="\ud83c\udfac Richiesta Creator Verified",
        color=0xE5FF00,
        timestamp=datetime.now(timezone.utc),
    )
    emb.set_author(
        name=f"{interaction.user.display_name} (@{interaction.user.name})",
        icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None,
    )
    emb.add_field(name="Utente Discord", value=interaction.user.mention, inline=True)
    emb.add_field(name="Utente FrameForge", value=user_doc.get("email", "-"), inline=True)
    emb.add_field(name="Piano", value=_user_plan(user_doc), inline=True)
    emb.add_field(name="Link canale", value=link, inline=False)
    emb.set_footer(text=f"Discord ID: {interaction.user.id}")
    return emb


@tree.command(
    name="apply-creator",
    description="Candidati al ruolo Creator Verified. Serve un link Twitch/YouTube/Kick.",
    guild=GUILD,
)
@app_commands.describe(link="Link al tuo canale Twitch, YouTube o Kick")
async def cmd_apply_creator(interaction: discord.Interaction, link: str):
    await interaction.response.defer(ephemeral=True)
    # 1. Config
    if not ROLE_CREATOR_ID or not CHANNEL_CREATOR_REVIEW_ID:
        return await interaction.followup.send(
            "Il flusso Creator Verified non e' configurato. Contatta uno Staff.",
            ephemeral=True,
        )
    # 2. Link validation
    link = (link or "").strip()
    if not _is_valid_creator_url(link):
        return await interaction.followup.send(
            "Link non valido. Deve essere un URL Twitch (twitch.tv), YouTube (youtube.com) o Kick (kick.com).",
            ephemeral=True,
        )
    # 3. Account linked?
    user_doc = await _find_user_by_discord_id(str(interaction.user.id))
    if not user_doc:
        return await interaction.followup.send(
            f"Devi prima collegare il tuo account FrameForge. Vai su {FRONTEND_URL}/app/account "
            f"o usa `/link`.",
            ephemeral=True,
        )
    # 4. Already Creator?
    if interaction.guild:
        role = interaction.guild.get_role(int(ROLE_CREATOR_ID))
        if role and role in interaction.user.roles:
            return await interaction.followup.send(
                "Hai gia' il ruolo **Creator Verified**. Nulla da fare!",
                ephemeral=True,
            )
    # 5. Pending?
    if await db.creator_applications.find_one({"discord_user_id": str(interaction.user.id), "status": "pending"}):
        return await interaction.followup.send(
            "Hai gia' una richiesta in attesa di revisione. Attendi il verdetto dello staff.",
            ephemeral=True,
        )
    # 6. Cooldown?
    if await _check_creator_reapply_cooldown(interaction):
        return
    # 7. Post to staff channel
    channel = await _resolve_review_channel(interaction)
    if not channel:
        return await interaction.followup.send(
            "Canale review staff non raggiungibile. Contatta un admin.",
            ephemeral=True,
        )
    emb = _build_creator_review_embed(interaction, user_doc, link)
    try:
        review_msg = await channel.send(embed=emb, view=CreatorReviewView())
    except discord.Forbidden:
        return await interaction.followup.send(
            "Il bot non ha permessi di scrittura sul canale staff. Contatta un admin.",
            ephemeral=True,
        )
    # 8. Persist
    await db.creator_applications.insert_one({
        "discord_user_id": str(interaction.user.id),
        "discord_username": interaction.user.name,
        "user_id": str(user_doc.get("_id") or ""),
        "email": user_doc.get("email", ""),
        "url": link,
        "message_id": str(review_msg.id),
        "channel_id": str(channel.id),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await interaction.followup.send(
        f"\u2705 Richiesta inviata! Lo staff la esaminera' e ti scriver\u00f2 in DM con l'esito.\n"
        f"Link inviato: {link}",
        ephemeral=True,
    )



# --------- Eventi ---------
@client.event
async def on_ready():
    logger.info("Bot connesso come %s (id=%s)", client.user, client.user.id if client.user else "?")
    # Registra View persistente per approvazione Creator (sopravvive ai restart)
    try:
        client.add_view(CreatorReviewView())
    except Exception as e:
        logger.warning("add_view CreatorReviewView failed: %s", e)
    try:
        synced = await tree.sync(guild=GUILD)
        logger.info("Slash commands sincronizzati (%d) nel guild %s", len(synced), GUILD_ID)
    except Exception as e:
        logger.warning("Sync commands fallito: %s", e)
    # avvia task periodico Pro sync (solo una volta)
    if ROLE_PRO_ID and not getattr(client, "_pro_sync_started", False):
        client._pro_sync_started = True
        client.loop.create_task(_pro_sync_loop())
        logger.info("Pro sync loop avviato (intervallo=%ds)", PRO_SYNC_INTERVAL)


@client.event
async def on_member_join(member: discord.Member):
    logger.info("Nuovo membro: %s (%s)", member, member.id)
    # welcome DM (fallback silente se DM chiusi)
    try:
        await member.send(
            f"Benvenuto in FrameForge! Collega il tuo account su {FRONTEND_URL}/app/account "
            f"con il pulsante *Collega Discord* per sbloccare i comandi bot e il ruolo Boosted PC."
        )
    except discord.Forbidden:
        pass
    # se ha gia' l'account collegato -> assegna ruoli
    doc = await _find_user_by_discord_id(str(member.id))
    if ROLE_BOOSTED_ID and doc:
        role = member.guild.get_role(int(ROLE_BOOSTED_ID))
        if role:
            try:
                await member.add_roles(role, reason="Boosted PC (account collegato)")
            except Exception as e:
                logger.warning("add_roles Boosted fallito per %s: %s", member.id, e)
    # sync ruolo Pro (in base a `plan` DB)
    if doc:
        await _sync_pro_role_for_member(member.guild, member, doc)


def main():
    logger.info("Avvio FrameForge bot...")
    client.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
