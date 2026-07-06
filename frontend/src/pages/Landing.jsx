import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Zap, Cpu, LineChart, MonitorDown, MessageSquareCode, ArrowRight, Gauge } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const FEATURES = [
  { icon: MessageSquareCode, key: "advisor" },
  { icon: Cpu, key: "build" },
  { icon: LineChart, key: "price" },
  { icon: MonitorDown, key: "agent" },
];

export default function Landing() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100">
      <header className="fixed top-0 w-full z-50 bg-black/50 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#E5FF00] flex items-center justify-center"><Zap size={18} className="text-black" /></div>
            <span className="font-display font-black tracking-tighter text-lg">BOOST<span className="text-[#E5FF00]">PC</span></span>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link to="/login" data-testid="nav-login-link" className="text-sm text-zinc-400 hover:text-white transition-colors px-3 py-2">{t("landing.login")}</Link>
            <Link to="/register" data-testid="nav-register-link" className="text-sm bg-[#E5FF00] text-black font-bold px-4 py-2 hover:bg-[#D4EC00] transition-colors btn-volt">{t("landing.start")}</Link>
          </div>
        </div>
      </header>

      <section className="relative pt-40 pb-28 px-6 overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src="https://images.pexels.com/photos/16062772/pexels-photo-16062772.jpeg" alt="rig" className="w-full h-full object-cover opacity-40" />
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/80 to-[#050505]" />
        </div>
        <div className="relative z-10 max-w-4xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="inline-flex items-center gap-2 border border-[#2A2A35] bg-black/40 px-3 py-1 mb-6 text-xs uppercase tracking-widest text-[#E5FF00]">
              <Gauge size={14} /> {t("landing.badge")}
            </div>
            <h1 className="font-display font-black text-4xl sm:text-5xl lg:text-6xl tracking-tighter leading-none mb-6">
              {t("landing.hero1")}<br /><span className="text-[#E5FF00]">{t("landing.hero2")}</span>
            </h1>
            <p className="text-zinc-400 text-base sm:text-lg max-w-2xl mx-auto mb-8 leading-relaxed">
              {t("landing.hero_sub")}
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/register" data-testid="hero-cta-btn" className="group inline-flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold px-6 py-3 hover:bg-[#D4EC00] transition-colors volt-glow btn-volt">
                {t("landing.cta")} <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link to="/login" className="inline-flex items-center justify-center gap-2 border border-[#2A2A35] px-6 py-3 hover:border-[#E5FF00] transition-colors">
                {t("landing.have_account")}
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">{t("landing.features_eyebrow")}</div>
        <h2 className="font-display font-bold text-2xl sm:text-3xl tracking-tight mb-12">{t("landing.features_title")}</h2>
        <div className="grid sm:grid-cols-2 gap-px bg-[#2A2A35] border border-[#2A2A35]">
          {FEATURES.map((f, i) => (
            <div key={i} className="bg-[#0F0F12] p-8 card-hover">
              <div className="w-11 h-11 border border-[#2A2A35] flex items-center justify-center mb-5 text-[#E5FF00] icon-pop">
                <f.icon size={22} />
              </div>
              <h3 className="font-display font-semibold text-xl mb-2">{t(`landing.f_${f.key}_t`)}</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">{t(`landing.f_${f.key}_d`)}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-[#2A2A35] py-8 text-center text-zinc-600 text-xs">
        {t("landing.footer")}
      </footer>
    </div>
  );
}
