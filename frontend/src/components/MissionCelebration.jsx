import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Swords } from "lucide-react";
import { useTranslation } from "react-i18next";

// Overlay achievement-style al completamento di una missione.
// Ascolta l'evento globale "ff-mission-completed" (detail = array di missioni).
export const MissionCelebration = () => {
  const { t, i18n } = useTranslation();
  const en = (i18n.language || "it").startsWith("en");
  const [queue, setQueue] = useState([]);
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    const h = (e) => setQueue((q) => [...q, ...(e.detail || [])]);
    window.addEventListener("ff-mission-completed", h);
    return () => window.removeEventListener("ff-mission-completed", h);
  }, []);

  useEffect(() => {
    if (!current && queue.length) {
      setCurrent(queue[0]);
      setQueue((q) => q.slice(1));
    }
  }, [queue, current]);

  useEffect(() => {
    if (!current) return;
    const to = setTimeout(() => setCurrent(null), 3000);
    return () => clearTimeout(to);
  }, [current]);

  return (
    <div className="fixed top-20 inset-x-0 z-[100] flex justify-center pointer-events-none">
      <AnimatePresence>
        {current && (
          <motion.div
            key={current.code}
            initial={{ opacity: 0, y: -24, scale: 0.92 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.95 }}
            transition={{ duration: 0.35, ease: [0.2, 0.9, 0.3, 1.2] }}
            className="relative flex items-center gap-4 bg-[#0F0F12] border-2 border-[#E5FF00] px-6 py-4 shadow-[0_0_0_4px_rgba(229,255,0,0.15),0_16px_48px_rgba(0,0,0,0.7)]"
            data-testid="mission-celebration"
          >
            <div className="w-12 h-12 flex items-center justify-center border-2 border-[#E5FF00] text-[#E5FF00] bg-black/50">
              <Swords size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.3em] text-[#E5FF00]">
                <span className="w-2 h-2 bg-[#00FF66] rounded-full animate-pulse" />
                {t("missions.celebrate", "Missione completata")}
              </div>
              <div className="font-display font-black text-xl tracking-tight text-white mt-0.5">
                {en ? current.name_en : current.name_it}
              </div>
            </div>
            <div className="absolute -top-3 right-3 px-2.5 py-0.5 bg-black border-2 border-[#E5FF00] text-[#E5FF00] text-xs font-black tracking-widest">
              +{current.xp} XP
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
