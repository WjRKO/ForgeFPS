/**
 * ProfileMenu — dropdown in alto a destra con account card + menu items.
 *
 * Sezione 1 (account card):
 *   - Avatar (iniziale + colore basato su email hash)
 *   - Name + email
 *   - Plan badge colorato (starter/pro/streamer/pro_trial con countdown)
 *
 * Sezione 2 (menu items):
 *   - Profilo & Sicurezza
 *   - Fatturazione (Stripe portal se paid)
 *   - Piani & Trial
 *   - Discord (connect / linked)
 *   - Feedback / bug
 *   - Logout
 *
 * Dropdown si chiude cliccando fuori (via ref + click-outside).
 * Su mobile potrebbe diventare bottom sheet, per ora popover uniforme.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  User, CreditCard, Sparkles, LogOut, Bug, Shield as ShieldIcon,
  ChevronDown, Gift, Zap, Video, Crown, AlertTriangle,
} from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import TrialUpgradeBanner from "@/components/TrialUpgradeBanner";

const DISCORD_ICON = ({ size = 16, ...props }) => (
  <svg {...props} width={size} height={size} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M20.317 4.369a19.79 19.79 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.865-.608 1.25a18.269 18.269 0 0 0-5.487 0 12.6 12.6 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.369a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.083.083 0 0 0 .031.056 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.372-.291a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.009c.12.099.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.055c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028z"/>
  </svg>
);

// Deterministic pastel color from email
function avatarColor(email) {
  if (!email) return "#3F3F46";
  let h = 0;
  for (const c of email) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
  const hue = Math.abs(h) % 360;
  return `hsl(${hue}, 55%, 45%)`;
}

function PlanBadge({ info }) {
  if (!info) return null;
  const eff = info.plan_effective;
  const days = info.trial_days_left;
  const grace = info.grace_days_left;

  if (eff === "starter") {
    return (
      <div className="mt-2 flex items-center gap-2 bg-black border border-zinc-700 px-2.5 py-1.5">
        <User size={13} className="text-zinc-500" />
        <span className="text-xs uppercase tracking-widest text-zinc-400 font-bold">Starter</span>
      </div>
    );
  }
  if (eff === "pro_trial" || eff === "streamer_trial") {
    const tier = eff === "streamer_trial" ? "Streamer" : "Pro";
    const urgent = days <= 3;
    return (
      <div className={`mt-2 flex items-center gap-2 border px-2.5 py-1.5 ${urgent ? "border-[#FFA500] bg-[#FFA500]/10" : "border-[#E5FF00] bg-[#E5FF00]/10"}`}>
        <Gift size={13} className={urgent ? "text-[#FFA500]" : "text-[#E5FF00]"} />
        <div className="min-w-0 text-xs">
          <div className={`uppercase tracking-widest font-bold ${urgent ? "text-[#FFA500]" : "text-[#E5FF00]"}`}>{tier} · trial</div>
          <div className="text-zinc-400 text-[10px] font-mono">{days} giorn{days === 1 ? "o" : "i"} rimasti</div>
        </div>
      </div>
    );
  }
  if (eff === "pro_expired" || eff === "streamer_expired") {
    return (
      <div className="mt-2 flex items-center gap-2 border border-[#FF3B30]/60 bg-[#FF3B30]/10 px-2.5 py-1.5">
        <AlertTriangle size={13} className="text-[#FF3B30]" />
        <div className="min-w-0 text-xs">
          <div className="uppercase tracking-widest font-bold text-[#FF3B30]">Scaduto</div>
          <div className="text-zinc-400 text-[10px] font-mono">Riattiva entro {grace}gg</div>
        </div>
      </div>
    );
  }
  if (eff === "pro") {
    return (
      <div className="mt-2 flex items-center gap-2 border border-[#E5FF00] bg-[#E5FF00]/10 px-2.5 py-1.5">
        <Zap size={13} className="text-[#E5FF00]" />
        <span className="text-xs uppercase tracking-widest font-bold text-[#E5FF00]">Pro · attivo</span>
      </div>
    );
  }
  if (eff === "streamer") {
    return (
      <div className="mt-2 flex items-center gap-2 border border-[#00E0FF] bg-[#00E0FF]/10 px-2.5 py-1.5">
        <Crown size={13} className="text-[#00E0FF]" />
        <span className="text-xs uppercase tracking-widest font-bold text-[#00E0FF]">Streamer · attivo</span>
      </div>
    );
  }
  return null;
}

export default function ProfileMenu() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState(null);
  const [discord, setDiscord] = useState({ linked: false, username: "" });
  const btnRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    api.get("/subscriptions/status").then(({ data }) => setInfo(data)).catch(() => {});
    api.get("/discord/status").then(({ data }) => {
      setDiscord({ linked: !!data?.linked, username: data?.username || "" });
    }).catch(() => {});
  }, [open]);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (menuRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onEsc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onEsc); };
  }, [open]);

  const doLogout = async () => { await logout(); navigate("/login"); };

  if (!user) return null;
  const initial = (user.name || user.email || "?").trim()[0]?.toUpperCase() || "?";
  const color = avatarColor(user.email);
  const isPaid = info?.plan_effective === "pro" || info?.plan_effective === "streamer";

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={() => setOpen((v) => !v)}
        data-testid="profile-menu-trigger"
        className="flex items-center gap-1.5 hover:opacity-90 transition-opacity"
        title={user.email}
      >
        <span className="w-8 h-8 flex items-center justify-center text-sm font-bold text-white" style={{ backgroundColor: color }}>
          {initial}
        </span>
        <ChevronDown size={14} className={`text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          ref={menuRef}
          data-testid="profile-menu-dropdown"
          className="absolute right-0 top-full mt-2 w-72 bg-[#0A0A0F] border border-[#2A2A35] shadow-2xl z-50"
        >
          {/* Sezione 1 — account card */}
          <div className="p-4 border-b border-[#2A2A35]">
            <div className="flex items-center gap-3">
              <span className="w-10 h-10 flex items-center justify-center text-base font-bold text-white shrink-0" style={{ backgroundColor: color }}>
                {initial}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-bold text-zinc-100 truncate">{user.name || user.email.split("@")[0]}</div>
                <div className="text-[11px] text-zinc-500 font-mono truncate">{user.email}</div>
              </div>
              {user.role === "admin" && (
                <span className="bg-[#E5FF00]/20 text-[#E5FF00] text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5" title="Admin">
                  <ShieldIcon size={10} className="inline" />
                </span>
              )}
            </div>
            <PlanBadge info={info} />
          </div>

          {/* Sezione 1b — banner upgrade dinamico (solo trial/expired) */}
          <TrialUpgradeBanner info={info} />

          {/* Sezione 2 — menu */}
          <div className="p-1.5">
            <MenuItem to="/app/settings" icon={User} label={t("profile.account", { defaultValue: "Profilo & Sicurezza" })} testid="menu-settings" />
            <MenuItem to="/app/billing" icon={CreditCard} label={t("profile.billing", { defaultValue: "Fatturazione" })} testid="menu-billing" />
            {!isPaid && (
              <MenuItem to="/pricing" icon={Sparkles} label={t("profile.plans", { defaultValue: "Piani & Trial" })} accent="#E5FF00" testid="menu-plans" />
            )}
            {discord.linked ? (
              <div className="flex items-center gap-2.5 px-3 py-2 text-sm text-zinc-300 opacity-80" data-testid="menu-discord-linked">
                <DISCORD_ICON size={15} className="text-[#5865F2] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs">Discord ✓ linkato</div>
                  {discord.username && <div className="text-[10px] text-zinc-500 truncate">@{discord.username}</div>}
                </div>
              </div>
            ) : (
              <MenuItem to="/app/settings#discord" icon={DISCORD_ICON} label={t("profile.discord_connect", { defaultValue: "Collega Discord" })} testid="menu-discord" />
            )}
            <MenuItem href="https://discord.gg/frameforge" external icon={Bug} label={t("profile.feedback", { defaultValue: "Segnala bug / feedback" })} testid="menu-feedback" />
            <div className="my-1 border-t border-[#2A2A35]" />
            <button
              onClick={doLogout}
              data-testid="menu-logout"
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-zinc-300 hover:bg-[#141419] hover:text-[#FF3B30] transition-colors"
            >
              <LogOut size={15} /> {t("profile.logout", { defaultValue: "Logout" })}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MenuItem({ to, href, external, icon: Icon, label, accent, testid }) {
  const body = (
    <>
      <Icon size={15} className="shrink-0" style={accent ? { color: accent } : {}} />
      <span className="flex-1">{label}</span>
    </>
  );
  const cls = "w-full flex items-center gap-2.5 px-3 py-2 text-sm text-zinc-300 hover:bg-[#141419] hover:text-zinc-100 transition-colors";
  if (href) {
    return <a href={href} target={external ? "_blank" : undefined} rel={external ? "noopener noreferrer" : undefined} className={cls} data-testid={testid}>{body}</a>;
  }
  return <Link to={to} className={cls} data-testid={testid}>{body}</Link>;
}
