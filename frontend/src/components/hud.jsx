import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import { LineChart, Line } from "recharts";

const EASE = [0.16, 1, 0.3, 1];

export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};
export const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

export function PageHeader({ eyebrow, title, subtitle, actions }) {
  return (
    <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8 pb-5 border-b border-[#1A1A24]">
      <div>
        {eyebrow && <div className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500 mb-2">{eyebrow}</div>}
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter">{title}</h1>
        {subtitle && <p className="text-zinc-500 text-sm mt-2 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

const BADGE = {
  volt: "bg-[#E5FF00]/10 text-[#E5FF00] border-[#E5FF00]/30",
  green: "bg-[#00FF66]/10 text-[#00FF66] border-[#00FF66]/30",
  cyan: "bg-[#00E0FF]/10 text-[#00E0FF] border-[#00E0FF]/30",
  red: "bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30",
  neutral: "bg-[#1A1A24] text-zinc-400 border-[#2A2A35]",
};
export function Badge({ tone = "neutral", icon: Icon, children, testid }) {
  return (
    <span data-testid={testid} className={`inline-flex items-center gap-1 px-2 py-0.5 border font-mono text-[10px] uppercase tracking-widest ${BADGE[tone]}`}>
      {Icon && <Icon size={11} />}{children}
    </span>
  );
}

export function StatCard({ icon: Icon, label, value, accent = "text-[#E5FF00]", testid }) {
  return (
    <motion.div variants={item} data-testid={testid}
      className="group bg-[#0F0F12] border border-[#1A1A24] hover:border-[#2A2A35] hud-tick p-5 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">{label}</span>
        {Icon && <Icon size={16} className={`${accent} icon-pop`} />}
      </div>
      <div className="font-display font-black text-3xl tracking-tighter group-hover:text-glow-volt transition-all">{value}</div>
    </motion.div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 border border-dashed border-[#2A2A35] bg-[#0F0F12]/40 gap-3">
      {Icon && <div className="p-4 bg-[#1A1A24] border border-[#2A2A35] text-zinc-500 mb-1"><Icon size={26} /></div>}
      {title && <div className="font-display font-bold text-lg">{title}</div>}
      {description && <p className="text-zinc-500 text-sm max-w-sm">{description}</p>}
      {action}
    </div>
  );
}

export function SkeletonCard({ className = "h-28" }) {
  return <div className={`skeleton ${className}`} />;
}
export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 p-4 border-b border-[#1A1A24]">
      <div className="skeleton w-12 h-12 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-3 w-2/3" />
        <div className="skeleton h-2.5 w-1/3" />
      </div>
      <div className="skeleton h-5 w-16" />
    </div>
  );
}

export function Sparkline({ data, color = "#00FF66", height = 36, width = 96 }) {
  const d = (data || []).map((v, i) => ({ i, v }));
  if (d.length < 2) return <div style={{ height, width }} />;
  return (
    <LineChart width={width} height={height} data={d} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
      <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.8} dot={false} isAnimationActive />
    </LineChart>
  );
}

export function HealthRing({ score = 0, size = 128, label }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const r = 54; const c = 2 * Math.PI * r;
  const color = score >= 80 ? "#00FF66" : score >= 55 ? "#E5FF00" : "#FF3B30";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg ref={ref} width={size} height={size} viewBox="0 0 128 128" className="-rotate-90">
        <circle cx="64" cy="64" r={r} fill="none" stroke="#1A1A24" strokeWidth="9" />
        <motion.circle cx="64" cy="64" r={r} fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={inView ? { strokeDashoffset: c - (Math.min(score, 100) / 100) * c } : {}}
          transition={{ duration: 1.4, ease: EASE }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display font-black text-4xl tracking-tighter" style={{ color }}>{score}</span>
        {label && <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{label}</span>}
      </div>
    </div>
  );
}


export function PageContainer({ children, className = "" }) {
  return <div className={`max-w-7xl mx-auto w-full space-y-8 ${className}`}>{children}</div>;
}

export function Section({ title, hint, actions, children, className = "" }) {
  return (
    <section className={`space-y-4 ${className}`}>
      {(title || actions) && (
        <div className="flex items-end justify-between gap-3">
          <div>
            {title && <h2 className="font-display font-bold text-lg tracking-tight text-zinc-100">{title}</h2>}
            {hint && <p className="text-xs text-zinc-500 mt-0.5">{hint}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function HUDCard({ children, className = "", featured = false, testid }) {
  return (
    <div data-testid={testid}
      className={`relative overflow-hidden bg-[#0F0F12] border border-[#2A2A35] p-5 flex flex-col ${className}`}>
      {featured && <span className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-[#E5FF00]/60 to-transparent" />}
      {children}
    </div>
  );
}

export function DataMetric({ label, value, unit, accent = "text-zinc-100", testid }) {
  return (
    <div data-testid={testid} className="flex flex-col gap-1 p-4 bg-[#0A0A0C] border border-[#2A2A35]">
      <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-[0.2em]">{label}</span>
      <div className="flex items-baseline gap-1.5">
        <span className={`text-2xl font-display font-black tabular-nums ${accent}`}>{value ?? "--"}</span>
        {unit && value != null && <span className="text-xs text-zinc-500 font-mono">{unit}</span>}
      </div>
    </div>
  );
}
