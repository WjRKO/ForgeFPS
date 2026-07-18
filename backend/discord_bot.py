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
PRO_PLANS = {"pro", "creator"}  # piani che ottengono il ruolo Pro
PRO_SYNC_INTERVAL = int(os.environ.get("DISCORD_PRO_SYNC_INTERVAL", "300"))  # 5 min
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
    emb = discord.Embed(title="FrameForge Bot", color=0xE5FF00)
    emb.add_field(name="/mypc", value="Il tuo Health Score PC", inline=False)
    emb.add_field(name="/benchmark", value="Ultimo benchmark salvato", inline=False)
    emb.add_field(name="/leaderboard", value="Top 10 utenti", inline=False)
    emb.add_field(name="/link", value="Istruzioni per collegare l'account", inline=False)
    emb.add_field(name="Sito", value=f"[forgefps.dev]({FRONTEND_URL})", inline=False)
    emb.add_field(name="Guida", value=f"[/guida]({FRONTEND_URL}/guida)", inline=False)
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


# --------- Eventi ---------
@client.event
async def on_ready():
    logger.info("Bot connesso come %s (id=%s)", client.user, client.user.id if client.user else "?")
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
