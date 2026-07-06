import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

const resources = {
  it: {
    translation: {
      nav: {
        dashboard: "Dashboard",
        pc: "Il mio PC",
        advisor: "AI Advisor",
        commands: "Comandi Utili",
        bios: "BIOS & Ripristino",
        desktop: "Collega il PC",
        gaming: "Gaming",
        builds: "Consiglia Build",
        upgrade: "Upgrade & FPS",
        tracker: "Prezzi",
        admin: "Admin",
      },
      section: { optimize: "Ottimizza il PC", buy: "Acquisti" },
      common: { logout: "Esci", open: "Apri", console: "Console", language: "Lingua" },
      dashboard: {
        eyebrow: "// Command Center",
        greeting: "Ciao, {{name}}",
        start3: "Inizia in 3 passi",
        step1_title: "Collega il PC",
        step1_desc: "Un comando da copiare: rileva il tuo hardware. Nessun download.",
        step2_title: "Ottimizza",
        step2_desc: "L'AI ti guida a velocizzare il PC e guadagnare FPS.",
        step3_title: "Traccia i prezzi",
        step3_desc: "Segui i tuoi prodotti e ricevi avvisi quando calano.",
        stat_tracked: "Prodotti tracciati",
        stat_builds: "Build salvate",
        stat_chats: "Sessioni AI",
        stat_saved: "Risparmio (€)",
        quick_advisor_title: "Ottimizza il PC",
        quick_advisor_desc: "Chiedi consigli all'AI advisor",
        quick_builds_title: "Genera una build",
        quick_builds_desc: "Gaming/streaming sul tuo budget",
        quick_tracker_title: "Traccia un prezzo",
        quick_tracker_desc: "Monitora Amazon & altri store",
        recent: "Prodotti recenti",
        see_all: "Vedi tutti",
        empty: "Nessun prodotto tracciato.",
        add_one: "Aggiungine uno",
      },
    },
  },
  en: {
    translation: {
      nav: {
        dashboard: "Dashboard",
        pc: "My PC",
        advisor: "AI Advisor",
        commands: "Useful Commands",
        bios: "BIOS & Restore",
        desktop: "Connect PC",
        gaming: "Gaming",
        builds: "Build Advisor",
        upgrade: "Upgrade & FPS",
        tracker: "Prices",
        admin: "Admin",
      },
      section: { optimize: "Optimize PC", buy: "Shopping" },
      common: { logout: "Log out", open: "Open", console: "Console", language: "Language" },
      dashboard: {
        eyebrow: "// Command Center",
        greeting: "Hi, {{name}}",
        start3: "Get started in 3 steps",
        step1_title: "Connect your PC",
        step1_desc: "One command to copy: detects your hardware. No download.",
        step2_title: "Optimize",
        step2_desc: "The AI guides you to speed up your PC and gain FPS.",
        step3_title: "Track prices",
        step3_desc: "Follow your products and get alerts when prices drop.",
        stat_tracked: "Tracked products",
        stat_builds: "Saved builds",
        stat_chats: "AI sessions",
        stat_saved: "Savings (€)",
        quick_advisor_title: "Optimize your PC",
        quick_advisor_desc: "Ask the AI advisor for tips",
        quick_builds_title: "Generate a build",
        quick_builds_desc: "Gaming/streaming on your budget",
        quick_tracker_title: "Track a price",
        quick_tracker_desc: "Monitor Amazon & other stores",
        recent: "Recent products",
        see_all: "See all",
        empty: "No products tracked yet.",
        add_one: "Add one",
      },
    },
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "it",
    supportedLngs: ["it", "en"],
    load: "languageOnly",
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "boostpc_lang",
      caches: ["localStorage"],
    },
    interpolation: { escapeValue: false },
  });

export default i18n;
