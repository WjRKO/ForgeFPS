import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { User, KeyRound, SlidersHorizontal, ShieldAlert, Loader2, Server, Mail, Save, Trash2, ShieldCheck, QrCode, HelpCircle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";

const T = {
  it: {
    eyebrow: "// account & sicurezza", title: "Account e sicurezza",
    profile: "Profilo", name: "Nome", email: "Email", save: "Salva", saved: "Salvato",
    pwd: "Cambia password", current: "Password attuale", newp: "Nuova password", change: "Aggiorna password", pwd_ok: "Password aggiornata",
    mfa_title: "Autenticazione a due fattori (2FA)", mfa_on: "Attiva", mfa_off: "Non attiva",
    mfa_desc_off: "Aggiungi un secondo livello di sicurezza con un'app authenticator (Google Authenticator, Authy...).",
    mfa_desc_on: "Il tuo account è protetto con 2FA. Al login ti verrà chiesto un codice.",
    mfa_enable: "Attiva 2FA", mfa_disable: "Disattiva 2FA", mfa_scan: "Scansiona il QR con la tua app authenticator, poi inserisci il codice a 6 cifre.",
    mfa_secret: "Oppure inserisci manualmente questa chiave:", mfa_code_ph: "Codice a 6 cifre", mfa_confirm: "Conferma e attiva",
    mfa_recovery_title: "Codici di recupero", mfa_recovery_desc: "Salvali in un posto sicuro: ti servono se perdi l'accesso all'app. Non verranno più mostrati.",
    mfa_done: "Ho salvato i codici", mfa_enabled_ok: "2FA attivata", mfa_disabled_ok: "2FA disattivata",
    mfa_disable_hint: "Inserisci un codice della tua app authenticator (o un codice di recupero) per disattivare la 2FA.",
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
    mfa_title: "Two-factor authentication (2FA)", mfa_on: "Enabled", mfa_off: "Disabled",
    mfa_desc_off: "Add a second layer of security with an authenticator app (Google Authenticator, Authy...).",
    mfa_desc_on: "Your account is protected with 2FA. You'll be asked for a code at login.",
    mfa_enable: "Enable 2FA", mfa_disable: "Disable 2FA", mfa_scan: "Scan the QR with your authenticator app, then enter the 6-digit code.",
    mfa_secret: "Or enter this key manually:", mfa_code_ph: "6-digit code", mfa_confirm: "Confirm & enable",
    mfa_recovery_title: "Recovery codes", mfa_recovery_desc: "Store them somewhere safe: you'll need them if you lose access to your app. They won't be shown again.",
    mfa_done: "I saved the codes", mfa_enabled_ok: "2FA enabled", mfa_disabled_ok: "2FA disabled",
    mfa_disable_hint: "Enter a code from your authenticator app (or a recovery code) to disable 2FA.",
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

const MfaCard = ({ c }) => {
  const [enabled, setEnabled] = useState(false);
  const [setup, setSetup] = useState(null); // {qr, secret}
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(null);
  const [busy, setBusy] = useState(false);
  const [disabling, setDisabling] = useState(false);
  const [disableCode, setDisableCode] = useState("");

  useEffect(() => { api.get("/auth/mfa/status").then(({ data }) => setEnabled(data.enabled)).catch(() => {}); }, []);

  const start = async () => {
    setBusy(true);
    try { const { data } = await api.post("/auth/mfa/setup"); setSetup(data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(false); }
  };
  const enable = async () => {
    setBusy(true);
    try { const { data } = await api.post("/auth/mfa/enable", { code: code.trim() }); setRecovery(data.recovery_codes); setSetup(null); setCode(""); setEnabled(true); toast.success(c.mfa_enabled_ok); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(false); }
  };
  const disable = async () => {
    const v = disableCode.trim(); if (!v) return;
    setBusy(true);
    try { await api.post("/auth/mfa/disable", { code: v }); setEnabled(false); setRecovery(null); setDisabling(false); setDisableCode(""); toast.success(c.mfa_disabled_ok); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(false); }
  };

  return (
    <Card icon={ShieldCheck} title={c.mfa_title} accent="#00FF66" testid="account-mfa">
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 border ${enabled ? "text-[#00FF66] border-[#00FF66]/40 bg-[#00FF66]/10" : "text-zinc-500 border-[#2A2A35]"}`} data-testid="mfa-badge">
          {enabled ? c.mfa_on : c.mfa_off}
        </span>
      </div>
      <p className="text-sm text-zinc-500 mb-4 max-w-lg">{enabled ? c.mfa_desc_on : c.mfa_desc_off}</p>

      {recovery && (
        <div className="mb-4 border border-[#E5FF00]/40 bg-[#E5FF00]/5 p-4" data-testid="mfa-recovery">
          <div className="text-sm font-semibold text-[#E5FF00] mb-1">{c.mfa_recovery_title}</div>
          <p className="text-xs text-zinc-400 mb-3">{c.mfa_recovery_desc}</p>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 font-mono text-xs">
            {recovery.map((r, i) => <code key={i} className="bg-black border border-[#2A2A35] px-2 py-1 text-center text-zinc-200">{r}</code>)}
          </div>
          <button onClick={() => setRecovery(null)} className="mt-3 text-xs border border-[#2A2A35] px-4 py-2 hover:border-white transition-colors uppercase tracking-wide" data-testid="mfa-recovery-done">{c.mfa_done}</button>
        </div>
      )}

      {!enabled && !setup && !recovery && (
        <button onClick={start} disabled={busy} data-testid="mfa-enable-btn"
          className="inline-flex items-center gap-2 border border-[#00FF66]/50 text-[#00FF66] px-5 py-2.5 hover:bg-[#00FF66]/10 transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <QrCode size={15} />} {c.mfa_enable}
        </button>
      )}

      {setup && (
        <div className="space-y-3 max-w-sm" data-testid="mfa-setup">
          <p className="text-sm text-zinc-400">{c.mfa_scan}</p>
          <img src={setup.qr} alt="QR" className="w-40 h-40 bg-white p-2" data-testid="mfa-qr" />
          <div className="text-xs text-zinc-500">{c.mfa_secret}</div>
          <code className="block bg-black border border-[#2A2A35] px-3 py-2 text-xs text-zinc-300 break-all" data-testid="mfa-secret">{setup.secret}</code>
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder={c.mfa_code_ph} inputMode="numeric" data-testid="mfa-code-input"
            className="w-full bg-black border-b border-[#2A2A35] focus:border-[#00FF66] outline-none py-2 text-sm tracking-widest transition-colors" />
          <button onClick={enable} disabled={busy || code.trim().length < 6} data-testid="mfa-confirm-btn"
            className="inline-flex items-center gap-2 bg-[#00FF66] text-black font-bold px-5 py-2.5 hover:bg-[#00e05c] transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />} {c.mfa_confirm}
          </button>
        </div>
      )}

      {enabled && !recovery && !disabling && (
        <button onClick={() => setDisabling(true)} disabled={busy} data-testid="mfa-disable-btn"
          className="inline-flex items-center gap-2 border border-[#FF3B30]/50 text-[#FF3B30] px-5 py-2.5 hover:bg-[#FF3B30]/10 transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <ShieldAlert size={15} />} {c.mfa_disable}
        </button>
      )}

      {enabled && !recovery && disabling && (
        <div className="space-y-3 max-w-sm" data-testid="mfa-disable-form">
          <p className="text-sm text-zinc-400">{c.mfa_disable_hint}</p>
          <input value={disableCode} onChange={(e) => setDisableCode(e.target.value)} placeholder={c.mfa_code_ph} inputMode="numeric" autoFocus data-testid="mfa-disable-code-input"
            className="w-full bg-black border-b border-[#2A2A35] focus:border-[#FF3B30] outline-none py-2 text-sm tracking-widest transition-colors" />
          <div className="flex items-center gap-2">
            <button onClick={disable} disabled={busy || disableCode.trim().length < 6} data-testid="mfa-disable-confirm-btn"
              className="inline-flex items-center gap-2 bg-[#FF3B30] text-white font-bold px-5 py-2.5 hover:bg-[#e02a20] transition-colors text-sm uppercase tracking-wide disabled:opacity-50">
              {busy ? <Loader2 size={15} className="animate-spin" /> : <ShieldAlert size={15} />} {c.mfa_disable}
            </button>
            <button onClick={() => { setDisabling(false); setDisableCode(""); }} data-testid="mfa-disable-cancel-btn"
              className="text-xs border border-[#2A2A35] px-4 py-2.5 hover:border-white transition-colors uppercase tracking-wide">{c.cancel || "Annulla"}</button>
          </div>
        </div>
      )}
    </Card>
  );
};

export default function Account() {
  const { user, setUser, logout } = useAuth();
  const { t, i18n } = useTranslation();
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

        <MfaCard c={c} />

        <Card icon={HelpCircle} title={t("tour.restart")} accent="#E5FF00" testid="account-tour">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="text-sm text-zinc-400 max-w-md">
              {t("tour.welcome_c")}
            </div>
            <button
              onClick={() => { try { window.localStorage.removeItem("ff_tour_done_v1"); } catch {} window.dispatchEvent(new Event("ff:tour:start")); }}
              data-testid="restart-tour-btn"
              className="inline-flex items-center gap-2 border border-[#E5FF00] text-[#E5FF00] px-5 py-2.5 hover:bg-[#E5FF00] hover:text-black transition-colors text-sm uppercase tracking-wide font-bold">
              <HelpCircle size={15} /> {t("tour.restart")}
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
