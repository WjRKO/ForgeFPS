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


# --------- Eventi ---------
@client.event
async def on_ready():
    logger.info("Bot connesso come %s (id=%s)", client.user, client.user.id if client.user else "?")
    try:
        synced = await tree.sync(guild=GUILD)
        logger.info("Slash commands sincronizzati (%d) nel guild %s", len(synced), GUILD_ID)
    except Exception as e:
        logger.warning("Sync commands fallito: %s", e)


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
    # se ha gia' l'account collegato -> assegna ruolo
    if not ROLE_BOOSTED_ID:
        return
    doc = await _find_user_by_discord_id(str(member.id))
    if doc:
        role = member.guild.get_role(int(ROLE_BOOSTED_ID))
        if role:
            try:
                await member.add_roles(role, reason="Boosted PC (account collegato)")
            except Exception as e:
                logger.warning("add_roles fallito per %s: %s", member.id, e)


def main():
    logger.info("Avvio FrameForge bot...")
    client.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
