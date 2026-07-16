import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { User, KeyRound, SlidersHorizontal, ShieldAlert, Loader2, Server, Mail, Save, Trash2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";

const T = {
  it: {
    eyebrow: "// account & sicurezza", title: "Account e sicurezza",
    profile: "Profilo", name: "Nome", email: "Email", save: "Salva", saved: "Salvato",
    pwd: "Cambia password", current: "Password attuale", newp: "Nuova password", change: "Aggiorna password", pwd_ok: "Password aggiornata",
    prefs: "Preferenze", local_only: "Modalità LOCAL ONLY", local_only_d: "Usa FrameForge senza inviare dati al cloud (analisi e ottimizzazioni restano in locale).",
    email_alerts: "Avvisi email", email_alerts_d: "Ricevi email quando un prezzo tracciato cala (in arrivo).",
    language: "Lingua", prefs_ok: "Preferenze salvate",
    danger: "Zona pericolosa", delete_t: "Elimina account", delete_d: "Elimina definitivamente il tuo account e tutti i dati (PC, prodotti, build, chat). Irreversibile.",
    delete_btn: "Elimina il mio account", delete_confirm: "Conferma con la password", delete_do: "Elimina definitivamente", delete_ok: "Account eliminato", cancel: "Annulla",
  },
  en: {
    eyebrow: "// account & security", title: "Account & security",
    profile: "Profile", name: "Name", email: "Email", save: "Save", saved: "Saved",
    pwd: "Change password", current: "Current password", newp: "New password", change: "Update password", pwd_ok: "Password updated",
    prefs: "Preferences", local_only: "LOCAL ONLY mode", local_only_d: "Use FrameForge without sending data to the cloud (analysis and optimizations stay local).",
    email_alerts: "Email alerts", email_alerts_d: "Get an email when a tracked price drops (coming soon).",
    language: "Language", prefs_ok: "Preferences saved",
    danger: "Danger zone", delete_t: "Delete account", delete_d: "Permanently delete your account and all data (PC, products, builds, chat). Irreversible.",
    delete_btn: "Delete my account", delete_confirm: "Confirm with your password", delete_do: "Delete permanently", delete_ok: "Account deleted", cancel: "Cancel",
  },
};

const Toggle = ({ on, onClick, testid }) => (
  <button type="button" onClick={onClick} data-testid={testid}
    className={`w-11 h-6 border transition-colors shrink-0 ${on ? "bg-[#E5FF00] border-[#E5FF00]" : "bg-black border-[#2A2A35]"}`}>
    <span className={`block w-5 h-5 bg-black transition-transform ${on ? "translate-x-5 bg-black" : "translate-x-0 bg-zinc-600"}`} />
  </button>
);

const Card = ({ icon: Icon, title, children, accent = "#E5FF00", testid }) => (
  <section className="bg-[#0F0F12] border border-[#2A2A35] p-6" data-testid={testid}>
    <div className="flex items-center gap-2.5 mb-5">
      <div className="w-9 h-9 border border-[#2A2A35] flex items-center justify-center" style={{ color: accent }}><Icon size={17} /></div>
      <h2 className="font-display font-bold text-lg">{title}</h2>
    </div>
    {children}
  </section>
);

const Field = ({ label, ...props }) => (
  <label className="block">
    <span className="text-xs uppercase tracking-widest text-zinc-500">{label}</span>
    <input {...props} className="w-full bg-black border-b border-[#2A2A35] focus:border-[#E5FF00] outline-none py-2 mt-1 text-sm transition-colors" />
  </label>
);

export default function Account() {
  const { user, setUser, logout } = useAuth();
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = (i18n.language || "it").startsWith("en") ? "en" : "it";
  const c = T[lang];

  const [name, setName] = useState(user?.name || "");
  const [cur, setCur] = useState(""); const [np, setNp] = useState("");
  const [prefs, setPrefs] = useState({ local_only: false, email_alerts: false, language: lang });
  const [busy, setBusy] = useState("");
  const [confirmDel, setConfirmDel] = useState(false); const [delPwd, setDelPwd] = useState("");

  useEffect(() => { api.get("/auth/preferences").then(({ data }) => setPrefs(data)).catch(() => {}); }, []);

  const saveProfile = async () => {
    setBusy("profile");
    try { const { data } = await api.patch("/auth/profile", { name }); setUser(data); toast.success(c.saved); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(""); }
  };
  const changePwd = async () => {
    setBusy("pwd");
    try { await api.post("/auth/change-password", { current_password: cur, new_password: np }); setCur(""); setNp(""); toast.success(c.pwd_ok); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(""); }
  };
  const savePrefs = async (next) => {
    setPrefs(next); setBusy("prefs");
    try { await api.put("/auth/preferences", next); toast.success(c.prefs_ok); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(""); }
  };
  const doDelete = async () => {
    setBusy("delete");
    try { await api.post("/auth/delete-account", { password: delPwd }); toast.success(c.delete_ok); await logout(); navigate("/"); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(""); }
  };

  return (
    <div className="max-w-3xl mx-auto fade-up" data-testid="account-page">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{c.eyebrow}</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">{c.title}</h1>
      </div>

      <div className="space-y-4">
        <Card icon={User} title={c.profile} testid="account-profile">
          <div className="space-y-4">
            <Field label={c.name} data-testid="account-name-input" value={name} onChange={(e) => setName(e.target.value)} />
            <div>
              <span className="text-xs uppercase tracking-widest text-zinc-500 flex items-center gap-1.5"><Mail size={12} /> {c.email}</span>
              <div className="text-sm text-zinc-400 py-2">{user?.email}</div>
            </div>
            <button onClick={saveProfile} disabled={busy === "profile"} data-testid="account-save-profile"
              className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-5 py-2.5 hover:bg-[#D4EC00] transition-colors btn-volt text-sm uppercase tracking-wide disabled:opacity-60">
              {busy === "profile" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} {c.save}
            </button>
          </div>
        </Card>

        <Card icon={KeyRound} title={c.pwd} accent="#00E0FF" testid="account-password">
          <div className="space-y-4 max-w-sm">
            <Field label={c.current} type="password" data-testid="account-current-pwd" value={cur} onChange={(e) => setCur(e.target.value)} />
            <Field label={c.newp} type="password" data-testid="account-new-pwd" value={np} onChange={(e) => setNp(e.target.value)} />
            <button onClick={changePwd} disabled={busy === "pwd" || !cur || np.length < 6} data-testid="account-change-pwd-btn"
              className="inline-flex items-center gap-2 border border-[#2A2A35] px-5 py-2.5 hover:border-[#00E0FF] hover:text-[#00E0FF] transition-colors text-sm uppercase tracking-wide disabled:opacity-40">
              {busy === "pwd" ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />} {c.change}
            </button>
          </div>
        </Card>

        <Card icon={SlidersHorizontal} title={c.prefs} accent="#00FF66" testid="account-prefs">
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Server size={16} className="text-[#00FF66] mt-0.5 shrink-0" />
                <div><div className="text-sm text-zinc-100 font-semibold">{c.local_only}</div><div className="text-xs text-zinc-500 max-w-md">{c.local_only_d}</div></div>
              </div>
              <Toggle on={prefs.local_only} testid="account-localonly-toggle" onClick={() => savePrefs({ ...prefs, local_only: !prefs.local_only })} />
            </div>
            <div className="flex items-start justify-between gap-4 border-t border-[#1A1A24] pt-4">
              <div className="flex items-start gap-3">
                <Mail size={16} className="text-zinc-400 mt-0.5 shrink-0" />
                <div><div className="text-sm text-zinc-100 font-semibold">{c.email_alerts}</div><div className="text-xs text-zinc-500 max-w-md">{c.email_alerts_d}</div></div>
              </div>
              <Toggle on={prefs.email_alerts} testid="account-emailalerts-toggle" onClick={() => savePrefs({ ...prefs, email_alerts: !prefs.email_alerts })} />
            </div>
          </div>
        </Card>

        <Card icon={ShieldAlert} title={c.danger} accent="#FF3B30" testid="account-danger">
          <p className="text-sm text-zinc-500 mb-4 max-w-lg">{c.delete_d}</p>
          {!confirmDel ? (
            <button onClick={() => setConfirmDel(true)} data-testid="account-delete-btn"
              className="inline-flex items-center gap-2 border border-[#FF3B30]/50 text-[#FF3B30] px-5 py-2.5 hover:bg-[#FF3B30]/10 transition-colors text-sm uppercase tracking-wide">
              <Trash2 size={15} /> {c.delete_btn}
            </button>
          ) : (
            <div className="space-y-3 max-w-sm border border-[#FF3B30]/30 bg-[#FF3B30]/5 p-4">
              <Field label={c.delete_confirm} type="password" data-testid="account-delete-pwd" value={delPwd} onChange={(e) => setDelPwd(e.target.value)} />
              <div className="flex gap-2">
                <button onClick={doDelete} disabled={busy === "delete" || !delPwd} data-testid="account-delete-confirm-btn"
                  className="inline-flex items-center gap-2 bg-[#FF3B30] text-white font-bold px-4 py-2.5 hover:bg-[#e02e24] transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
                  {busy === "delete" ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />} {c.delete_do}
                </button>
                <button onClick={() => { setConfirmDel(false); setDelPwd(""); }} className="px-4 py-2.5 border border-[#2A2A35] text-sm uppercase tracking-wide hover:border-white transition-colors">{c.cancel}</button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
