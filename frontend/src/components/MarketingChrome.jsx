import { Link, useLocation } from "react-router-dom";
import { Zap, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export const useLang = () => {
  const { i18n } = useTranslation();
  return (i18n.language || "it").startsWith("en") ? "en" : "it";
};

const NAV = [
  { to: "/security", it: "Sicurezza", en: "Security" },
  { to: "/privacy-telemetry", it: "Privacy", en: "Privacy" },
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
  return (
    <footer className="bg-[#050505] border-t border-[#1A1A24] px-6 py-12" data-testid="marketing-footer">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-[#E5FF00] flex items-center justify-center"><Zap size={15} className="text-black" /></div>
          <span className="font-display font-black tracking-tighter">FRAME<span className="text-[#E5FF00]">FORGE</span></span>
        </div>
        <nav className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-zinc-400">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} className="hover:text-[#E5FF00] transition-colors">{n[lang]}</Link>
          ))}
        </nav>
        <div className="flex items-center gap-2 text-xs font-mono text-[#00FF66]"><ShieldCheck size={13} /> {lang === "en" ? "Security-first · Local-first" : "Security-first · Local-first"}</div>
      </div>
      <div className="max-w-6xl mx-auto mt-8 pt-6 border-t border-[#1A1A24] text-center text-zinc-600 text-xs font-mono">
        FrameForge · Performance Command Center
      </div>
    </footer>
  );
};
