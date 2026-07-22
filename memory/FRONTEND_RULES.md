# FrameForge — Regole di codice frontend

> Documento breve con le policy stabilite finora. Va aggiornato quando decidiamo nuove regole.

---

## 1. Bottoni: usa sempre `BTN_CLASSES` o i componenti canonici

`/app/frontend/src/components/hud.jsx` è la single source of truth (SSOT) per lo stile bottoni. **NON** duplicare le stringhe Tailwind in altre pagine.

### Varianti disponibili
| Utilizzo | Componente | Class constant |
|---|---|---|
| Hero CTA (max 1/pagina) | `<PrimaryButton>` | `BTN_CLASSES.primary` |
| Azione standard | `<SecondaryButton>` | `BTN_CLASSES.secondary` |
| Azione terziaria/testo | `<GhostButton tone="muted\|accent\|danger">` | `BTN_CLASSES.ghost` |
| CTA HUD (uppercase mono) | — | `BTN_CLASSES.primaryMono` / `.secondaryMono` / `.ghostMono` |

### Quando applicare la migrazione
Applica **opportunisticamente**: solo quando tocchi una pagina per altre ragioni (bug fix, nuova feature, refactor). Non fare mai bulk-rewrite dei bottoni — troppi rischi visivi.

### Esempio migrazione durante bug fix
```jsx
// PRIMA (inline classes)
<button className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2.5 text-sm hover:bg-[#D4EE00] transition-colors"
  onClick={handler} data-testid="save-btn">
  Salva
</button>

// DOPO (canonical)
import { PrimaryButton } from "@/components/hud";
<PrimaryButton onClick={handler} testid="save-btn">Salva</PrimaryButton>

// OPPURE (se il markup deve restare un <Link> per la router)
import { BTN_CLASSES } from "@/components/hud";
<Link to="/target" data-testid="save-link" className={BTN_CLASSES.primary}>Salva</Link>
```

### NON migrare (per ora)
- Bottoni con classi custom (`btn-volt`, `btn-ghost` in CSS globale) — sono link ad animazioni CSS specifiche
- Bottoni con colori non-accent (Discord blue `#5865F2`, danger red `#FF3B30` dedicati)
- Bottoni dentro componenti shadcn (`Button` da `@/components/ui/button`)

---

## 2. Tooltip per termini tecnici → `<TechTerm>`

Se aggiungi una parola tecnica (bufferbloat, MPO, HAGS, MSI mode, ecc.) in una nuova pagina, usa il componente `<TechTerm term="key">Label</TechTerm>`.

### Come aggiungere un nuovo termine
1. Aggiungi la definizione in `/app/frontend/src/components/TechTerm.jsx` (nei dict `GLOSSARY_IT` + `GLOSSARY_EN`)
2. Wrappalo intorno al testo:  `<TechTerm term="msi_mode">MSI Mode</TechTerm>`
3. Testalo: `Ctrl+Hover` mostra la definizione dopo 200ms

Termini già disponibili: `bufferbloat, mpo, hags, msi_mode, mmcss, ulps, hiberfil, dpi, dwm, ping, jitter, frametime`.

---

## 3. Next Best Action banners → `<NextActionBanner kind="...">`

Se una pagina completa un'azione significativa (sync, apply, benchmark, first login), mostra un banner contestuale.

Presets disponibili:
- `no-hw` — quando l'utente non ha collegato il PC
- `post-sync` — dopo un sync completato
- `post-apply` — dopo aver applicato tweak
- `post-benchmark` — dopo un benchmark

Il banner è dismiss-per-24h automaticamente (localStorage). Se serve un preset custom, passa `custom={{ icon, text, ctaLabel, to, accent }}`.

---

## 4. Bottleneck detection → `<BottleneckDetector>`

Se aggiungi una pagina che mostra telemetria live (CPU/GPU/RAM), includi il detector:

```jsx
import BottleneckDetector from "@/components/BottleneckDetector";
// Grande banner:
<BottleneckDetector />
// Compact badge:
<BottleneckDetector compact />
```

Legge automaticamente `/api/pc-telemetry`, polling 4s, classifica in 6 stati (CPU-BOUND, GPU-BOUND, RAM-SAT, BALANCED, IDLE, MIXED). Se nessun sample recente, renderizza `null`.

---

## 5. Freshness badge

`<FreshnessBadge />` è già montato globalmente in `Layout.jsx` (header top-right). Non aggiungere copie in singole pagine — è sempre visibile.

---

## 6. Mobile Handoff

Il bottone "Telefono" è già nell'header globale (`Layout.jsx`). Non aggiungere pulsanti duplicati nel body delle pagine.

---

## 7. Terminologia unificata (IT+EN)

Nomi da usare sempre nel testo user-facing:
- **FrameForge Agent** — mai "Desktop Agent", "Companion", "Local App"
- **Health Score** — punteggio globale salute PC (temp + tweak + sync freshness)
- **Performance Score** — solo per benchmark CPU/RAM/disco/net
- **Tweak** — azione atomica applicabile in GUI (ok tecnico, gamer-friendly)
- **Ottimizzazione** — pubblicità/copy user-facing (evita "tweak" nella landing)

---

*Ultima modifica: 2026-02-22*
