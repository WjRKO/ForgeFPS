import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, HelpCircle } from "lucide-react";
import { useLang } from "@/components/MarketingChrome";

const COPY = {
  it: {
    eyebrow: "// faq sicurezza",
    title: "\"Ma è sicuro?\" — sì, e te lo dimostriamo.",
    sub: "Le domande che ci fanno più spesso. Nessuna risposta vaga.",
    items: [
      { q: "Rovinerà il mio PC?", a: "No. FrameForge crea un backup automatico prima di ogni modifica e ogni tweak è annullabile con un click ('Ripristina tutto'). Non tocchiamo mai Windows Defender, il firewall o i servizi di sistema critici: ci sono guardrail integrati che lo impediscono." },
      { q: "Perché il mio antivirus lo segnala?", a: "È un falso positivo euristico comune per gli eseguibili non ancora firmati creati con PyInstaller — non significa che ci sia un virus. Puoi verificare l'hash SHA256, controllare il file su VirusTotal, oppure usare lo script PowerShell (.ps1) leggibile. Stiamo completando la firma digitale (SignPath) che eliminerà l'avviso." },
      { q: "Raccogliete i miei dati o le mie password?", a: "No. Nessun dato personale, nessuna password. L'agent invia solo metriche hardware anonime su connessione cifrata (HTTPS). L'architettura è local-first: le ottimizzazioni girano sul tuo PC. Gli strumenti di analisi si attivano solo con il tuo consenso esplicito (banner cookie)." },
      { q: "Come annullo le modifiche?", a: "In qualsiasi momento: l'agent ha un pulsante 'Ripristina tutto' e ogni singola ottimizzazione è reversibile grazie al backup automatico creato prima di applicarla." },
      { q: "Serve accedere come amministratore?", a: "Solo per applicare le ottimizzazioni reali di sistema, con privilegi minimi. Il codice è open source (licenza MIT): puoi ispezionare esattamente cosa fa prima di eseguirlo." },
      { q: "Devo per forza scaricare qualcosa per provarlo?", a: "No. Puoi fare una scansione reale (hardware + test di rete) direttamente dal browser, senza account e senza download. L'agent serve solo per le ottimizzazioni reali e la telemetria live." },
    ],
  },
  en: {
    eyebrow: "// security faq",
    title: "\"But is it safe?\" — yes, and we prove it.",
    sub: "The questions we get most often. No vague answers.",
    items: [
      { q: "Will it break my PC?", a: "No. FrameForge creates an automatic backup before every change and every tweak is one-click reversible ('Restore all'). We never touch Windows Defender, the firewall or critical system services — built-in guardrails prevent it." },
      { q: "Why does my antivirus flag it?", a: "It's a common heuristic false positive for unsigned executables built with PyInstaller — it doesn't mean there's a virus. You can verify the SHA256 hash, check the file on VirusTotal, or use the readable PowerShell (.ps1) script. We're finalizing code signing (SignPath) which will remove the warning." },
      { q: "Do you collect my data or passwords?", a: "No. No personal data, no passwords. The agent only sends anonymous hardware metrics over an encrypted (HTTPS) connection. The architecture is local-first: optimizations run on your PC. Analytics only run with your explicit consent (cookie banner)." },
      { q: "How do I undo changes?", a: "Anytime: the agent has a 'Restore all' button and every single optimization is reversible thanks to the automatic backup created before applying it." },
      { q: "Do I need administrator access?", a: "Only to apply real system optimizations, with least privilege. The code is open source (MIT license): you can inspect exactly what it does before running it." },
      { q: "Do I have to download something to try it?", a: "No. You can run a real scan (hardware + network test) right from your browser, no account and no download. The agent is only needed for real optimizations and live telemetry." },
    ],
  },
};

export const SecurityFaq = () => {
  const lang = useLang();
  const c = COPY[lang];
  const [open, setOpen] = useState(0);

  return (
    <section className="max-w-3xl" data-testid="security-faq">
      <div className="text-xs font-mono tracking-[0.2em] uppercase text-[#E5FF00] mb-3">{c.eyebrow}</div>
      <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tight mb-2">{c.title}</h2>
      <p className="text-zinc-500 text-sm mb-8">{c.sub}</p>

      <div className="space-y-2.5">
        {c.items.map((it, i) => {
          const isOpen = open === i;
          return (
            <div key={i} className="bg-[#0F0F12] border border-[#1A1A24]" data-testid={`faq-item-${i}`}>
              <button
                onClick={() => setOpen(isOpen ? -1 : i)}
                data-testid={`faq-toggle-${i}`}
                className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-[#12121a] transition-colors">
                <span className="flex items-center gap-3">
                  <HelpCircle size={16} className={isOpen ? "text-[#E5FF00]" : "text-zinc-600"} />
                  <span className="font-semibold text-sm text-zinc-100">{it.q}</span>
                </span>
                <ChevronDown size={17} className={`shrink-0 text-zinc-500 transition-transform ${isOpen ? "rotate-180" : ""}`} />
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }} className="overflow-hidden">
                    <p className="px-5 pb-5 pl-14 text-sm text-zinc-400 leading-relaxed">{it.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </section>
  );
};
