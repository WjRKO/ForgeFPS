import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Check, X as XIcon, HardDrive, Zap, Video, ArrowRight, Sparkles, Shield,
  RotateCcw, Wallet, ChevronDown, Gift, Undo2,
} from "lucide-react";
import { toast } from "sonner";
import { MarketingNav, MarketingFooter, useLang } from "@/components/MarketingChrome";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

// -----------------------------------------------------------------------------
// Content — bilingual IT/EN
// v0.7.5: full rewrite with monthly/annual toggle, comparison table, FAQ,
// trust signals, and money-back guarantee. Aligned with actual FrameForge
// features (no aspirational copy like "AI applied automatically").
// -----------------------------------------------------------------------------
const COPY = {
  it: {
    meta_t: "Prezzi — FrameForge | Starter, Pro e Streamer",
    meta_d: "Piani FrameForge: Starter gratis, Pro €7/mese (AI Advisor, Full Benchmark, Live Monitor), Streamer €16/mese (OBS overlay, API, benchmark pubblici). Trial Pro 14 giorni senza carta.",
    eyebrow: "// pricing",
    title: "Il tuo PC merita il tier giusto.",
    sub: "Dal monitoraggio base al controllo totale mentre streami. Provalo prima di pagare — 14 giorni di Pro gratis, senza carta.",
    social_proof: "12+ setup FPS certificati · 24 benchmark eseguiti",
    toggle_monthly: "Mensile",
    toggle_annual: "Annuale · risparmi 2 mesi",
    per_month: "/mese",
    billed_monthly: "fatturato mensile",
    billed_annually: (m) => `€${m}/anno · risparmi 17%`,
    trial_badge: "14 giorni gratis · senza carta",
    best_badge: "Più scelto",
    tiers: [
      {
        key: "starter", icon: HardDrive, name: "Starter", accent: "#A1A1AA",
        tagline: "Per capire davvero come sta il tuo PC.",
        price_month: 0, price_year: 0,
        cta: "start", cta_label: "Registrati — è gratis",
        cta_sub: "Setup in 3 minuti. Nessun addebito, mai.",
        items: [
          "1 PC collegato",
          "Health Score live (CPU, GPU, RAM, temp)",
          "Quick Benchmark (~30 secondi)",
          "Storico 7 giorni",
          "Rilevamento hardware automatico",
          "Tracker Amazon (3 prodotti)",
          "Tweak base: Optimize + Restore",
          "Server Discord community",
        ],
      },
      {
        key: "pro", icon: Zap, name: "Pro", accent: "#E5FF00",
        tagline: "Il tuo PC ottimizzato con l'AI. Tutto quello che ti serve per vincere.",
        price_month: 7, price_year: 69, best: true, trial: true,
        cta: "trial", cta_label: "Sblocca Pro gratis per 14 giorni",
        cta_sub: "14 giorni gratis, poi €7/mese. Cancella con un click.",
        items: [
          "Tutto di Starter, più:",
          "3 PC collegati",
          "Full Benchmark ~3 min (CPU multi-thread, RAM, disco, network)",
          "AI Advisor — chat illimitata su misura per il tuo hardware",
          "Live Monitor (CPU/GPU temp, FPS, watt real-time)",
          "Storico 90gg + alert quando l'Health cala",
          "Tweak avanzati: BufferBloat, PreMatch, Booster",
          "Tracker Amazon esteso (25 prodotti + alert email/Discord)",
          "GPU vs Reference (200+ GPU catalogate)",
          "PDF report stampabile",
          "Ruolo @Pro su Discord",
        ],
      },
      {
        key: "streamer", icon: Video, name: "Streamer", accent: "#00E0FF",
        tagline: "Per chi trasforma il PC in reddito. Zero compromessi.",
        price_month: 16, price_year: 159, trial: true,
        cta: "trial_streamer", cta_label: "Sblocca il livello Creator",
        cta_sub: "Trial 14 giorni disponibile — nessuna carta.",
        items: [
          "Tutto di Pro, più:",
          "PC illimitati (gaming + streaming + laptop)",
          "OBS Overlay — telemetria live sul tuo stream",
          "Public benchmark page (forgefps.dev/@tuoNome)",
          "API + Webhook per automazioni",
          "Custom preset condivisibili con i fan",
          "Creator Leaderboard + Verified badge ✓",
          "Early access nuove feature",
          "Priority support (DM Discord, <24h)",
        ],
      },
    ],
    comparison_title: "Confronto rapido",
    comparison_hint: "Scorri orizzontalmente su mobile",
    comparison_footer_monthly: "Prezzo mensile",
    comparison_footer_annual: "Annuale",
    pro_annual_effective: "€5,75",
    streamer_annual_effective: "€13,25",
    features_matrix: [
      { label: "PC collegati", values: ["1", "3", "Illimitati"] },
      { label: "Health Score live", values: [true, true, true] },
      { label: "Storico", values: ["7 giorni", "90 giorni", "90 giorni"] },
      { label: "Quick Benchmark (~30s)", values: [true, true, true] },
      { label: "Full Benchmark (~3min)", values: [false, true, true] },
      { label: "AI Advisor chat illimitata", values: [false, true, true] },
      { label: "Live Monitor", values: [false, true, true] },
      { label: "Health alert automatici", values: [false, true, true] },
      { label: "Tweak avanzati (BufferBloat, PreMatch, Booster)", values: [false, true, true] },
      { label: "Tracker Amazon", values: ["3 prodotti", "25 prodotti", "25 prodotti"] },
      { label: "PDF report", values: [false, true, true] },
      { label: "GPU vs Reference", values: ["20 GPU", "200+ GPU", "200+ GPU"] },
      { label: "OBS Overlay", values: [false, false, true], highlight_streamer: true },
      { label: "Public benchmark page + URL", values: [false, false, true], highlight_streamer: true },
      { label: "API + Webhook", values: [false, false, true], highlight_streamer: true },
      { label: "Creator leaderboard + Verified", values: [false, false, true], highlight_streamer: true },
      { label: "Priority support", values: [false, "Standard", "Priority <24h"] },
    ],
    trust_signals: [
      { icon: Gift, label: "14 giorni Pro gratis", desc: "Nessuna carta, nessun impegno" },
      { icon: Shield, label: "Pagamenti sicuri Stripe", desc: "Standard PCI-DSS. Dati mai sui nostri server." },
      { icon: RotateCcw, label: "Cancelli quando vuoi", desc: "Un click. Nessuna telefonata. Nessuna trappola." },
      { icon: Undo2, label: "Money-back 30gg", desc: "Rimborso completo se non usi Pro nel primo mese." },
    ],
    faq_title: "Domande frequenti",
    faq: [
      { q: "Cosa succede se disdico durante il trial?", a: "Nessun addebito. Il tuo account torna a Starter e conservi tutti i dati (Health Score, storico, benchmark). Puoi rifare il trial più avanti quando ti serve." },
      { q: "Posso cambiare piano nel mezzo del mese?", a: "Sì. Se passi da Pro a Streamer, paghi solo la differenza pro-rata. Se downgradi, il rimborso è accreditato al ciclo successivo." },
      { q: "Il tracker Amazon funziona anche fuori dall'Italia?", a: "Sì. Supportiamo Amazon IT, US, DE, UK, FR, ES. Aggiungiamo altri paesi su richiesta." },
      { q: "L'agent locale è sicuro?", a: "Sì. Sorgente pubblico su GitHub, verifica SHA256 di ogni release, nessun invio dati senza il tuo click, backup automatico prima di ogni tweak con Restore in un click." },
      { q: "Ho bisogno dell'agent locale per usare FrameForge?", a: "Solo se vuoi tracciare Health Score, benchmark, live monitor e tweak. Puoi usare AI Advisor e Tracker Amazon senza installare nulla — ma sarebbe come pagare Netflix senza guardare film." },
      { q: "L'IVA è inclusa nel prezzo?", a: "Sì. I prezzi mostrati sono già IVA-inclusa per utenti privati in Italia. Per Partita IVA e clienti fuori dall'UE, l'IVA viene ricalcolata al checkout." },
      { q: "Che succede se aumentate i prezzi in futuro?", a: "I prezzi che hai al momento del pagamento restano bloccati per te finché non disdici. Se aumentiamo, tu paghi il vecchio prezzo per sempre (o finché resti abbonato senza interruzioni)." },
      { q: "Posso pagare con PayPal o bonifico?", a: "Al momento: solo carta (Stripe). PayPal e bonifico per fatture Pro/annuali sono in roadmap per Q2 2026." },
    ],
    closing_title: "Ancora indeciso?",
    closing_body: "Il piano Starter ti offre già più di quello che ti danno la maggior parte dei \"PC booster\" a pagamento. Iniziare non ti costa nulla, e passare a Pro richiede un click.",
    closing_cta: "Inizia gratis con Starter",
    footer_note: "Cambia piano o disdici in qualsiasi momento · Pagamenti sicuri Stripe · Fatturazione italiana",
    already_logged: "Sei loggato — apri la dashboard",
  },
  en: {
    meta_t: "Pricing — FrameForge | Starter, Pro and Streamer",
    meta_d: "FrameForge plans: Starter free, Pro €7/mo (AI Advisor, Full Benchmark, Live Monitor), Streamer €16/mo (OBS overlay, API, public benchmarks). 14-day free trial, no card.",
    eyebrow: "// pricing",
    title: "Your PC deserves the right tier.",
    sub: "From basic monitoring to full control while streaming. Try it before you pay — 14 days of Pro free, no card required.",
    social_proof: "12+ certified FPS setups · 24 benchmarks completed",
    toggle_monthly: "Monthly",
    toggle_annual: "Annual · save 2 months",
    per_month: "/mo",
    billed_monthly: "billed monthly",
    billed_annually: (m) => `€${m}/year · save 17%`,
    trial_badge: "14 days free · no card",
    best_badge: "Most popular",
    tiers: [
      {
        key: "starter", icon: HardDrive, name: "Starter", accent: "#A1A1AA",
        tagline: "To really understand how your PC is doing.",
        price_month: 0, price_year: 0,
        cta: "start", cta_label: "Sign up — it's free",
        cta_sub: "Setup in 3 minutes. Never a charge.",
        items: [
          "1 connected PC",
          "Live Health Score (CPU, GPU, RAM, temp)",
          "Quick Benchmark (~30s)",
          "7-day history",
          "Automatic hardware detection",
          "Amazon tracker (3 products)",
          "Basic tweaks: Optimize + Restore",
          "Community Discord server",
        ],
      },
      {
        key: "pro", icon: Zap, name: "Pro", accent: "#E5FF00",
        tagline: "Your PC optimized with AI. Everything you need to win.",
        price_month: 7, price_year: 69, best: true, trial: true,
        cta: "trial", cta_label: "Unlock Pro free for 14 days",
        cta_sub: "14 days free, then €7/mo. Cancel with one click.",
        items: [
          "Everything in Starter, plus:",
          "3 connected PCs",
          "Full Benchmark ~3 min (multi-thread CPU, RAM, disk, network)",
          "AI Advisor — unlimited chat tailored to your hardware",
          "Live Monitor (CPU/GPU temp, FPS, watts real-time)",
          "90-day history + alerts when Health drops",
          "Advanced tweaks: BufferBloat, PreMatch, Booster",
          "Extended Amazon tracker (25 products + email/Discord alerts)",
          "GPU vs Reference (200+ GPUs catalogued)",
          "Printable PDF report",
          "@Pro role on Discord",
        ],
      },
      {
        key: "streamer", icon: Video, name: "Streamer", accent: "#00E0FF",
        tagline: "For those who turn their PC into income. Zero compromises.",
        price_month: 16, price_year: 159, trial: true,
        cta: "trial_streamer", cta_label: "Unlock the Creator tier",
        cta_sub: "14-day trial available — no card.",
        items: [
          "Everything in Pro, plus:",
          "Unlimited PCs (gaming + streaming + laptop)",
          "OBS Overlay — live telemetry on your stream",
          "Public benchmark page (forgefps.dev/@yourname)",
          "API + Webhook for automations",
          "Shareable custom presets for your fans",
          "Creator Leaderboard + Verified ✓ badge",
          "Early access to new features",
          "Priority support (Discord DM, <24h)",
        ],
      },
    ],
    comparison_title: "Quick comparison",
    comparison_hint: "Scroll horizontally on mobile",
    comparison_footer_monthly: "Monthly price",
    comparison_footer_annual: "Annual",
    pro_annual_effective: "€5.75",
    streamer_annual_effective: "€13.25",
    features_matrix: [
      { label: "Connected PCs", values: ["1", "3", "Unlimited"] },
      { label: "Live Health Score", values: [true, true, true] },
      { label: "History", values: ["7 days", "90 days", "90 days"] },
      { label: "Quick Benchmark (~30s)", values: [true, true, true] },
      { label: "Full Benchmark (~3min)", values: [false, true, true] },
      { label: "Unlimited AI Advisor chat", values: [false, true, true] },
      { label: "Live Monitor", values: [false, true, true] },
      { label: "Automatic Health alerts", values: [false, true, true] },
      { label: "Advanced tweaks (BufferBloat, PreMatch, Booster)", values: [false, true, true] },
      { label: "Amazon tracker", values: ["3 items", "25 items", "25 items"] },
      { label: "PDF report", values: [false, true, true] },
      { label: "GPU vs Reference", values: ["20 GPUs", "200+ GPUs", "200+ GPUs"] },
      { label: "OBS Overlay", values: [false, false, true], highlight_streamer: true },
      { label: "Public benchmark page + URL", values: [false, false, true], highlight_streamer: true },
      { label: "API + Webhook", values: [false, false, true], highlight_streamer: true },
      { label: "Creator leaderboard + Verified", values: [false, false, true], highlight_streamer: true },
      { label: "Priority support", values: [false, "Standard", "Priority <24h"] },
    ],
    trust_signals: [
      { icon: Gift, label: "14 days Pro free", desc: "No card, no commitment" },
      { icon: Shield, label: "Secure Stripe payments", desc: "PCI-DSS standard. Card data never on our servers." },
      { icon: RotateCcw, label: "Cancel anytime", desc: "One click. No phone calls. No traps." },
      { icon: Undo2, label: "30-day money-back", desc: "Full refund if you don't use Pro in the first month." },
    ],
    faq_title: "Frequently asked",
    faq: [
      { q: "What happens if I cancel during the trial?", a: "No charge. Your account reverts to Starter and you keep all your data (Health Score, history, benchmarks). You can restart the trial later when you need it." },
      { q: "Can I change plans mid-cycle?", a: "Yes. Upgrading from Pro to Streamer only charges the pro-rata difference. Downgrades credit the difference to the next cycle." },
      { q: "Does Amazon tracker work outside Italy?", a: "Yes. We support Amazon IT, US, DE, UK, FR, ES. Other countries on request." },
      { q: "Is the local agent safe?", a: "Yes. Public source on GitHub, SHA256 verification of every release, no data sent without your click, automatic backup before every tweak with one-click Restore." },
      { q: "Do I need the local agent to use FrameForge?", a: "Only if you want Health Score tracking, benchmarks, live monitor and tweaks. You can use AI Advisor and Amazon Tracker without installing anything — but that would be like paying for Netflix without watching movies." },
      { q: "Is VAT included in the price?", a: "Yes. Prices shown are VAT-inclusive for EU private customers. For VAT-registered businesses and non-EU customers, VAT is recalculated at checkout." },
      { q: "What if you raise prices in the future?", a: "The price you pay at signup is locked in as long as you stay subscribed. If we raise prices, you pay the old price forever (as long as you don't cancel)." },
      { q: "Can I pay with PayPal or bank transfer?", a: "Currently: card only (Stripe). PayPal and bank transfer for Pro/annual invoices are on the Q2 2026 roadmap." },
    ],
    closing_title: "Still undecided?",
    closing_body: "The Starter plan alone gives you more than most paid \"PC booster\" tools. Starting costs nothing, and upgrading to Pro takes one click.",
    closing_cta: "Get started free with Starter",
    footer_note: "Change or cancel anytime · Secure Stripe payments · Italian invoicing",
    already_logged: "You're logged in — open dashboard",
  },
};

// =============================================================================
// Sub-components
// =============================================================================

function BillingToggle({ annual, onToggle, c }) {
  return (
    <div className="inline-flex items-center bg-[#0F0F12] border border-[#2A2A35] p-1" data-testid="billing-toggle">
      <button
        onClick={() => onToggle(false)}
        data-testid="toggle-monthly"
        className={`px-4 py-2 text-xs uppercase tracking-widest font-mono transition-colors ${!annual ? "bg-[#E5FF00] text-black font-bold" : "text-zinc-400 hover:text-zinc-200"}`}>
        {c.toggle_monthly}
      </button>
      <button
        onClick={() => onToggle(true)}
        data-testid="toggle-annual"
        className={`px-4 py-2 text-xs uppercase tracking-widest font-mono transition-colors relative ${annual ? "bg-[#E5FF00] text-black font-bold" : "text-zinc-400 hover:text-zinc-200"}`}>
        {c.toggle_annual}
      </button>
    </div>
  );
}

function PricingCard({ tier, annual, c, onCta, isLogged, lang }) {
  const Icon = tier.icon;
  const isFree = tier.price_month === 0;
  const rawMonthly = annual && !isFree ? (tier.price_year / 12).toFixed(2) : String(tier.price_month);
  // Localize decimal separator (IT uses comma, EN uses dot)
  const displayPrice = lang === "it" ? rawMonthly.replace(".", ",") : rawMonthly;
  const priceLabel = isFree ? "€0" : `€${displayPrice}`;
  const isBest = tier.best;

  return (
    <div
      data-testid={`pricing-${tier.key}`}
      className={`relative flex flex-col bg-[#0F0F12] p-7 transition-transform hover:-translate-y-1 ${isBest ? "border-2 border-[#E5FF00] shadow-[0_0_40px_-10px_#E5FF0055]" : "border border-[#2A2A35]"}`}
    >
      {isBest && (
        <span className="absolute -top-3 left-7 bg-[#E5FF00] text-black text-[10px] font-mono uppercase tracking-widest px-2 py-1 flex items-center gap-1">
          <Sparkles size={11} /> {c.best_badge}
        </span>
      )}

      <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center mb-4" style={{ color: tier.accent }}>
        <Icon size={20} />
      </div>

      <h2 className="font-display font-black text-2xl tracking-tight mb-1">{tier.name}</h2>
      <p className="text-sm text-zinc-500 leading-relaxed mb-6 min-h-[2.5rem]">{tier.tagline}</p>

      {/* Price block */}
      <div className="mb-5">
        <div className="flex items-baseline gap-1.5">
          <span className="font-display font-black text-4xl" style={{ color: tier.accent }} data-testid={`price-${tier.key}`}>
            {priceLabel}
          </span>
          {!isFree && <span className="text-sm text-zinc-500">{c.per_month}</span>}
        </div>
        {!isFree && (
          <div className="text-[11px] text-zinc-500 mt-1 font-mono">
            {annual ? c.billed_annually(tier.price_year) : c.billed_monthly}
          </div>
        )}
      </div>

      {tier.trial && (
        <div className="mb-5 -mx-2 px-3 py-1.5 bg-[#E5FF00]/10 border-l-2 border-[#E5FF00] text-[11px] font-mono uppercase tracking-wider text-[#E5FF00] flex items-center gap-1.5">
          <Gift size={12} /> {c.trial_badge}
        </div>
      )}

      <ul className="space-y-2.5 mb-8 flex-1">
        {tier.items.map((it, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm text-zinc-300">
            <Check size={15} className="shrink-0 mt-0.5" style={{ color: tier.accent }} /> {it}
          </li>
        ))}
      </ul>

      <button
        onClick={() => onCta(tier)}
        data-testid={`pricing-cta-${tier.key}`}
        className={`group inline-flex items-center justify-center gap-2 py-3 uppercase tracking-wide text-sm font-bold transition-colors ${
          isBest
            ? "bg-[#E5FF00] text-black hover:bg-[#D4EC00] btn-volt"
            : tier.key === "streamer"
            ? "bg-[#00E0FF] text-black hover:bg-[#00C0DD]"
            : "bg-zinc-100 text-black hover:bg-white"
        }`}
      >
        {isLogged && tier.cta === "start" ? c.already_logged : tier.cta_label}
        <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform" />
      </button>
      <p className="text-[11px] text-zinc-500 text-center mt-2 leading-snug">{tier.cta_sub}</p>
    </div>
  );
}

function ComparisonTable({ c }) {
  return (
    <section className="mt-24" data-testid="comparison-table">
      <div className="mb-6">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-2">// {c.comparison_title.toLowerCase()}</div>
        <h2 className="font-display font-black text-3xl tracking-tighter">{c.comparison_title}</h2>
        <p className="text-xs text-zinc-500 mt-2 md:hidden">{c.comparison_hint}</p>
      </div>

      <div className="overflow-x-auto border border-[#2A2A35]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#2A2A35] bg-[#0F0F12]">
              <th className="p-4 text-left text-xs uppercase tracking-widest text-zinc-500 font-mono">Feature</th>
              <th className="p-4 text-center text-xs uppercase tracking-widest text-zinc-400 font-display font-black">Starter</th>
              <th className="p-4 text-center text-xs uppercase tracking-widest text-[#E5FF00] font-display font-black">Pro</th>
              <th className="p-4 text-center text-xs uppercase tracking-widest text-[#00E0FF] font-display font-black">Streamer</th>
            </tr>
          </thead>
          <tbody>
            {c.features_matrix.map((row, i) => (
              <tr key={i} className="border-b border-[#1A1A24] hover:bg-[#0F0F12] transition-colors">
                <td className="p-3.5 text-zinc-300">{row.label}</td>
                {row.values.map((v, j) => (
                  <td key={j} className={`p-3.5 text-center ${row.highlight_streamer && j === 2 ? "bg-[#00E0FF]/5" : ""}`}>
                    {v === true ? <Check size={16} className="inline text-[#00FF66]" /> :
                     v === false ? <XIcon size={14} className="inline text-zinc-700" /> :
                     <span className="text-xs text-zinc-300">{v}</span>}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-b border-[#2A2A35] bg-black/60">
              <td className="p-4 uppercase tracking-widest text-xs text-zinc-500 font-mono">{c.comparison_footer_monthly}</td>
              <td className="p-4 text-center text-zinc-400 font-display font-black">€0</td>
              <td className="p-4 text-center text-[#E5FF00] font-display font-black text-lg">€7</td>
              <td className="p-4 text-center text-[#00E0FF] font-display font-black text-lg">€16</td>
            </tr>
            <tr className="bg-black/60">
              <td className="p-4 uppercase tracking-widest text-xs text-zinc-500 font-mono">{c.comparison_footer_annual}</td>
              <td className="p-4 text-center text-zinc-500">—</td>
              <td className="p-4 text-center text-[#E5FF00] font-display font-black">{c.pro_annual_effective}<span className="text-xs text-zinc-400 font-sans">{c.per_month}</span></td>
              <td className="p-4 text-center text-[#00E0FF] font-display font-black">{c.streamer_annual_effective}<span className="text-xs text-zinc-400 font-sans">{c.per_month}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TrustSignals({ c }) {
  return (
    <section className="mt-16 grid sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="trust-signals">
      {c.trust_signals.map((t, i) => {
        const Icon = t.icon;
        return (
          <div key={i} className="bg-[#0F0F12] border border-[#2A2A35] p-5">
            <Icon size={18} className="text-[#E5FF00] mb-3" />
            <div className="font-bold text-sm text-zinc-100 mb-1">{t.label}</div>
            <div className="text-xs text-zinc-500 leading-relaxed">{t.desc}</div>
          </div>
        );
      })}
    </section>
  );
}

function FaqItem({ q, a, idx }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[#2A2A35]" data-testid={`faq-item-${idx}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between py-4 text-left hover:text-[#E5FF00] transition-colors group"
        data-testid={`faq-toggle-${idx}`}
      >
        <span className="font-display font-bold text-base pr-4">{q}</span>
        <ChevronDown size={18} className={`shrink-0 text-zinc-500 group-hover:text-[#E5FF00] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="pb-5 text-sm text-zinc-400 leading-relaxed" data-testid={`faq-answer-${idx}`}>{a}</div>
      )}
    </div>
  );
}

function FaqSection({ c }) {
  return (
    <section className="mt-24 max-w-3xl" data-testid="faq-section">
      <div className="mb-6">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-2">// faq</div>
        <h2 className="font-display font-black text-3xl tracking-tighter">{c.faq_title}</h2>
      </div>
      <div>
        {c.faq.map((f, i) => <FaqItem key={i} q={f.q} a={f.a} idx={i} />)}
      </div>
    </section>
  );
}

// =============================================================================
// Main
// =============================================================================
export default function Pricing() {
  const lang = useLang();
  const c = COPY[lang];
  const [annual, setAnnual] = useState(false);
  const navigate = useNavigate();
  const { user } = useAuth();
  usePageMeta(c.meta_t, c.meta_d);

  const handleCta = async (tier) => {
    // Se free -> signup normale (o dashboard se loggato)
    if (tier.cta === "start") {
      if (user) { navigate("/app"); return; }
      navigate("/register");
      return;
    }
    // Trial pro/streamer
    if (tier.cta === "trial" || tier.cta === "trial_streamer") {
      const planHint = tier.cta === "trial" ? "pro_trial" : "streamer_trial";
      if (user) {
        // Utente loggato -> POST /subscriptions/start-trial direttamente
        try {
          const { data } = await api.post("/subscriptions/start-trial", { plan: planHint });
          toast.success(data.message || "Trial attivato!");
          navigate("/app");
        } catch (e) {
          const detail = e?.response?.data?.detail;
          const msg = typeof detail === "string" ? detail : detail?.message || "Impossibile attivare il trial";
          toast.error(msg);
          // Se ha gia' un piano attivo o trial usato, portalo comunque alla dashboard
          if (detail?.code === "already_on_plan" || detail?.code === "trial_already_used") {
            navigate("/app");
          }
        }
        return;
      }
      // Utente non loggato -> signup con planHint (Auth.jsx auto-attiva trial dopo register)
      navigate(`/register?plan=${planHint}`);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <MarketingNav />

      {/* Hero */}
      <main className="max-w-6xl mx-auto px-6 pt-28 pb-24">
        <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
        <h1 className="font-display font-black text-4xl sm:text-5xl lg:text-6xl tracking-tighter mb-4">{c.title}</h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-2xl leading-relaxed mb-4">{c.sub}</p>
        <p className="text-xs font-mono text-zinc-600 uppercase tracking-widest mb-10" data-testid="social-proof">{c.social_proof}</p>

        {/* Toggle */}
        <div className="flex justify-center mb-12">
          <BillingToggle annual={annual} onToggle={setAnnual} c={c} />
        </div>

        {/* Pricing cards */}
        <div className="grid md:grid-cols-3 gap-5 items-stretch">
          {c.tiers.map((tier) => (
            <PricingCard key={tier.key} tier={tier} annual={annual} c={c} onCta={handleCta} isLogged={!!user} lang={lang} />
          ))}
        </div>

        {/* Trust signals */}
        <TrustSignals c={c} />

        {/* Comparison */}
        <ComparisonTable c={c} />

        {/* FAQ */}
        <FaqSection c={c} />

        {/* Closing CTA */}
        <section className="mt-24 bg-[#0F0F12] border border-[#2A2A35] p-10 text-center" data-testid="closing-cta">
          <Wallet size={28} className="text-[#E5FF00] mx-auto mb-4" />
          <h2 className="font-display font-black text-3xl tracking-tighter mb-3">{c.closing_title}</h2>
          <p className="text-zinc-400 max-w-xl mx-auto leading-relaxed mb-6">{c.closing_body}</p>
          <Link
            to={user ? "/app" : "/register"}
            data-testid="closing-cta-btn"
            className="group inline-flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-3 px-6 uppercase tracking-wide text-sm hover:bg-[#D4EC00] transition-colors btn-volt"
          >
            {user ? c.already_logged : c.closing_cta}
            <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform" />
          </Link>
          <p className="text-[11px] text-zinc-600 mt-4 font-mono">{c.footer_note}</p>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
