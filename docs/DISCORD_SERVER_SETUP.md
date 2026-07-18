# FrameForge - Discord Server Setup

Guida pronta per configurare il server community FrameForge. Copia/incolla i nomi canali, incolla i testi nei "topic" di ogni canale, e usa i template di benvenuto e regole.

## Nome del server
- **Nome**: FrameForge
- **Icona**: usa il logo giallo lime (`E5FF00`) su fondo nero
- **Banner** (Boost livello 2): screenshot della GUI moderna dell'agent
- **Descrizione**: "AI Performance Command Center per streamer & gamer. Boost, benchmark, tweak trasparenti."

## Ruoli (in questo ordine dall'alto, il primo ha priorita' maggiore)

| Nome ruolo | Colore | Chi lo riceve | Permessi chiave |
|---|---|---|---|
| **Founder** | `#E5FF00` (giallo lime) | Tu (owner) | Admin totale |
| **Staff** | `#00E0FF` (cyan) | Collaboratori/moderatori | Kick, ban, gestione messaggi |
| **Creator Verified** | `#B388FF` (viola) | Streamer/YouTuber verificati | Post in canali speciali, colore visibile |
| **Pro** | `#FF3355` (rosso) | Utenti piano Pro | Accesso canali #pro-only |
| **Boosted PC** | `#00FF66` (verde) | Chi ha collegato l'account FrameForge | Nome verde in chat |
| **@everyone** | grigio default | Tutti | Read + send messaggi base |

## Struttura canali

### CATEGORIA: BENVENUTO
- **# regole** (read-only) - Regole del server
- **# annunci** (read-only) - News ufficiali FrameForge, release notes
- **# leggimi-prima** (read-only) - Come iniziare, link app, link scarica agent

### CATEGORIA: COMMUNITY
- **# generale** - Chat libera
- **# presentazioni** - Nuovi membri si presentano
- **# meme-e-showcase** - Screenshot benchmark, setup gaming, meme

### CATEGORIA: BOOST & PERFORMANCE
- **# help-supporto** - Domande generiche sull'app
- **# condividi-il-tuo-score** - Benchmark result, before/after
- **# tweak-avanzati** - Discussioni tra power users
- **# bug-report** - Segnalazioni bug (link a GitHub Issues)

### CATEGORIA: GAMING
- **# gaming-generale** - Chat gaming
- **# looking-for-team** - Cerca compagni per FPS competitivi
- **# streamers-lounge** (solo Creator Verified) - Networking tra streamer

### CATEGORIA: DEV (read-only per @everyone)
- **# changelog-automatico** - Release note via webhook
- **# price-drops** - Notifiche cali prezzo dai product tracker
- **# github** - Commit e PR via webhook GitHub

### CATEGORIA: PRO (solo ruolo Pro)
- **# pro-lounge** - Chat esclusiva Pro
- **# feature-requests** - Vota feature future

### CANALE VOCALE
- **General Voice**
- **Streaming Party** (Creator only)
- **AFK** (spostare utenti inattivi qui automaticamente)

## Testo canale # regole

```
**FRAMEFORGE — REGOLE**

1) Rispetto e civilta'. Zero tolleranza verso hate speech, molestie o discriminazioni.
2) No spam, self-promo o inviti ad altri server nei canali generali.
3) I bug si segnalano in # bug-report o su GitHub Issues, non in DM al Founder.
4) NSFW / illegale = ban immediato.
5) Non chiedere di rimuovere i controlli antivirus / firewall. L'agent NON lo fa MAI.
6) Le domande sull'app vanno in # help-supporto, non in DM.

Rompere le regole = warn -> mute -> kick -> ban.
```

## Testo canale # leggimi-prima

```
**Benvenuto su FrameForge!**

**Cosa e' FrameForge**
AI Performance Command Center per streamer e gamer. Ottimizza il PC, tracka benchmark, applica tweak trasparenti e reversibili.

**Inizia subito**
- Sito: https://forgefps.dev
- Guida rapida: https://forgefps.dev/guida
- Scarica l'agent: https://forgefps.dev/#download

**Collega il tuo account al server**
Usa il comando `/link` nel canale # help-supporto per legare il tuo account FrameForge a Discord. Otterrai il ruolo Boosted PC e sbloccherai i comandi speciali.

**Comandi del bot**
- `/mypc` - Mostra il tuo Health Score
- `/benchmark` - Ultimo benchmark salvato
- `/leaderboard` - Top 10 utenti per punteggio
- `/help` - Aiuto
```

## Messaggio di benvenuto (automatico su nuovo membro)

```
Benvenuto {user} in FrameForge!

- Leggi le regole in <# regole>
- Presentati in <# presentazioni>
- Collega il tuo account con `/link` per sbloccare il ruolo Boosted PC e i comandi bot
- Domande? <# help-supporto>

Buon boost!
```

## Bot base consigliati (moderazione)

Finche' il bot ufficiale FrameForge e' in build, usa:

- **Dyno** (https://dyno.gg) - Automod, welcome, ruoli reaction, ban temporanei
- **YAGPDB** (https://yagpdb.xyz) - Alternativa piu' avanzata, custom commands

Setup minimo Dyno:
1. Antispam ON (max 5 msg/2s)
2. Automod parole vietate (lista base + hate speech)
3. Welcome message → # generale
4. Reaction role in # leggimi-prima per assegnare @everyone al ruolo "Membro"

## Permessi consigliati per @everyone

**Consenti**: View channels, Send messages, Read message history, Add reactions, Connect (voice), Speak (voice)
**Nega**: Mention @everyone, Mention roles, External emojis (finche' non ci sono Creator), Embed links (per anti-spam iniziale)

## Onboarding integrato Discord

Attiva **Server Onboarding** in Impostazioni Server:
- **Domanda 1**: "Cosa fai principalmente?" → risposte: Gaming, Streaming, Entrambi (assegna ruolo)
- **Domanda 2**: "Piattaforma preferita?" → PC, Console, Mobile (solo tag stats, no ruolo)
- **Domanda 3**: "Hai gia' usato FrameForge?" → Si/No (se No, ping ruolo Staff per welcome piu' caloroso)

## Server Boost - obiettivi

- **Livello 1** (2 boost): banner personalizzato, emoji custom
- **Livello 2** (7 boost): banner animato, /vanity URL (`discord.gg/frameforge`)
- **Livello 3** (14 boost): stream 1080p60 (utile per Creator lounge)

## Vanity URL

Appena raggiungi il Livello 2, prendi `discord.gg/frameforge` e mettilo nel footer del sito.
