import { Link, useLocation } from "react-router-dom";
import { Zap, ShieldCheck } from "lucide-react";
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
  return (
    <header className="fixed top-0 w-full z-50 bg-[#050505]/80 backdrop-blur-xl border-b border-[#1A1A24]" data-testid="marketing-nav">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="nav-home-logo">
          <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center"><Zap size={18} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter text-lg">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
        </Link>
        <nav className="hidden md:flex items-center gap-1">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} data-testid={`nav-${n.to.slice(1)}`}
              className={`text-xs font-mono uppercase tracking-widest px-3 py-2 transition-colors ${pathname === n.to ? "text-[#E5FF00]" : "text-zinc-400 hover:text-white"}`}>
              {n[lang]}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link to="/login" data-testid="nav-login-link" className="text-sm text-zinc-400 hover:text-white transition-colors px-3 py-2 hidden sm:block">{lang === "en" ? "Sign in" : "Accedi"}</Link>
          <Link to="/register" data-testid="nav-register-link" className="text-sm bg-[#E5FF00] text-black font-bold px-4 py-2 hover:bg-[#D4EC00] transition-colors btn-volt">{lang === "en" ? "Get started" : "Inizia"}</Link>
        </div>
      </div>
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
          <ul className="space-y-2 text-sm text-zinc-400">
            {NAV.map((n) => (
              <li key={n.to}><Link to={n.to} className="hover:text-[#E5FF00] transition-colors">{n[lang]}</Link></li>
            ))}
          </ul>
        </div>
        <FooterCommunity t={t} />
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-4">{t("landing.footer_account")}</div>
          <ul className="space-y-2 text-sm text-zinc-400">
            <li><Link to="/login" className="hover:text-[#E5FF00] transition-colors">{lang === "en" ? "Sign in" : "Accedi"}</Link></li>
            <li><Link to="/register" className="hover:text-[#E5FF00] transition-colors">{lang === "en" ? "Get started" : "Inizia ora"}</Link></li>
          </ul>
        </div>
      </div>
      <FooterLegal t={t} />
    </footer>
  );
};
