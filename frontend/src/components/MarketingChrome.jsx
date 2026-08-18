import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Zap, ShieldCheck, Menu, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { FooterCommunity, FooterLegal } from "@/components/FooterExtras";

export const useLang = () => {
  const { i18n } = useTranslation();
  return (i18n.language || "it").startsWith("en") ? "en" : "it";
};

const NAV = [
  { to: "/security", it: "Sicurezza", en: "Security" },
  { to: "/privacy-telemetry", it: "Privacy", en: "Privacy" },
  { to: "/guida", it: "Guida", en: "Guide" },
  { to: "/changelog", it: "Changelog", en: "Changelog" },
  { to: "/pricing", it: "Prezzi", en: "Pricing" },
];

export const MarketingNav = () => {
  const lang = useLang();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);

  // chiude il drawer al cambio pagina e con Esc
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="fixed top-0 w-full z-50 bg-[#050505]/80 backdrop-blur-xl border-b border-[#1A1A24]" data-testid="marketing-nav">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-2">
        <Link to="/" className="flex items-center gap-2 shrink-0 py-1" data-testid="nav-home-logo">
          <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center shrink-0"><Zap size={18} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter text-base sm:text-lg">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
        </Link>

        <nav className="hidden lg:flex items-center gap-1">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} data-testid={`nav-${n.to.slice(1)}`}
              className={`text-xs font-mono uppercase tracking-widest px-3 py-3 transition-colors ${pathname === n.to ? "text-[#E5FF00]" : "text-zinc-400 hover:text-white"}`}>
              {n[lang]}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="hidden lg:flex"><LanguageSwitcher /></div>
          <Link to="/login" data-testid="nav-login-link" className="text-sm text-zinc-400 hover:text-white transition-colors px-3 py-2.5 hidden sm:block">{lang === "en" ? "Sign in" : "Accedi"}</Link>
          <Link to="/register" data-testid="nav-register-link" className="text-xs sm:text-sm bg-[#E5FF00] text-black font-bold px-3 sm:px-4 py-3 sm:py-2.5 whitespace-nowrap hover:bg-[#D4EC00] transition-colors btn-volt">{lang === "en" ? "Get started" : "Inizia"}</Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="lg:hidden w-10 h-10 flex items-center justify-center border border-[#2A2A35] text-zinc-300 hover:border-[#E5FF00] hover:text-[#E5FF00] transition-colors"
            aria-label={lang === "en" ? "Menu" : "Apri menu"}
            aria-expanded={open}
            data-testid="marketing-nav-toggle">
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {open && (
        <div className="lg:hidden border-t border-[#1A1A24] bg-[#050505]/95 backdrop-blur-xl" data-testid="marketing-nav-drawer">
          <nav className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex flex-col">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} data-testid={`navm-${n.to.slice(1)}`}
                className={`text-xs font-mono uppercase tracking-widest py-3.5 border-b border-[#1A1A24] transition-colors ${pathname === n.to ? "text-[#E5FF00]" : "text-zinc-400 hover:text-white"}`}>
                {n[lang]}
              </Link>
            ))}
            <Link to="/login" data-testid="navm-login-link" className="sm:hidden text-xs font-mono uppercase tracking-widest py-3.5 border-b border-[#1A1A24] text-zinc-400 hover:text-white transition-colors">
              {lang === "en" ? "Sign in" : "Accedi"}
            </Link>
            <div className="pt-4 pb-1"><LanguageSwitcher /></div>
          </nav>
        </div>
      )}
    </header>
  );
};

export const MarketingFooter = () => {
  const lang = useLang();
  const { t } = useTranslation();
  return (
    <footer className="bg-[#050505] border-t border-[#1A1A24] px-6 py-14" data-testid="marketing-footer">
      <div className="max-w-6xl mx-auto grid md:grid-cols-4 gap-10">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 bg-[#E5FF00] flex items-center justify-center"><Zap size={15} className="text-black" /></div>
            <span className="font-display font-black tracking-tighter">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
          </div>
          <p className="text-zinc-500 text-sm leading-relaxed">{t("landing.footer_bio")}</p>
          <div className="flex items-center gap-2 mt-4 text-xs font-mono text-[#00FF66]">
            <ShieldCheck size={13} /> {t("landing.footer_status")}
          </div>
        </div>
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-4">{t("landing.footer_product")}</div>
          <ul className="space-y-0.5 text-sm text-zinc-400">
            {NAV.map((n) => (
              <li key={n.to}><Link to={n.to} className="inline-block py-2.5 hover:text-[#E5FF00] transition-colors">{n[lang]}</Link></li>
            ))}
          </ul>
        </div>
        <FooterCommunity t={t} />
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-4">{t("landing.footer_account")}</div>
          <ul className="space-y-0.5 text-sm text-zinc-400">
            <li><Link to="/login" className="inline-block py-2.5 hover:text-[#E5FF00] transition-colors">{lang === "en" ? "Sign in" : "Accedi"}</Link></li>
            <li><Link to="/register" className="inline-block py-2.5 hover:text-[#E5FF00] transition-colors">{lang === "en" ? "Get started" : "Inizia ora"}</Link></li>
          </ul>
        </div>
      </div>
      <FooterLegal t={t} />
    </footer>
  );
};
