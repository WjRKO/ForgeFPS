import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Gamepad2, Plus, Trash2, Save, X, Zap } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { SecureRunBlock } from "@/components/SecureRunBlock";

function ProfileCard({ p, catalog, token, onDelete }) {
  const names = p.tweak_ids.map((id) => catalog.find((c) => c.id === id)?.name).filter(Boolean);
  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] p-5" data-testid={`profile-${p.id}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Gamepad2 size={18} className="text-[#E5FF00]" />
          <h3 className="font-display font-bold text-base">{p.game_name}</h3>
          {p.template && <span className="text-[10px] uppercase tracking-widest border border-[#2A2A35] px-1.5 py-0.5 text-zinc-500">{p.preset_label || "Preset"}</span>}
        </div>
        {!p.template && (
          <button data-testid={`delete-profile-${p.id}`} onClick={() => onDelete(p.id)} className="text-zinc-600 hover:text-[#FF3B30] transition-colors"><Trash2 size={16} /></button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5 mb-4">
        {names.slice(0, 8).map((n) => <span key={n} className="text-[11px] bg-black border border-[#1A1A24] px-2 py-0.5 text-zinc-400">{n}</span>)}
        {names.length > 8 && <span className="text-[11px] text-zinc-600 px-1 py-0.5">+{names.length - 8}</span>}
      </div>
      <SecureRunBlock token={token} mode="optimize" profile={p.id} testid={`profile-run-${p.id}`} />
    </div>
  );
}

export default function Profiles() {
  const { t } = useTranslation();
  const [templates, setTemplates] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [token, setToken] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState([]);

  const load = async () => { try { const { data } = await api.get("/profiles"); setProfiles(data); } catch (e) { console.error("load profiles failed", e); } };
  useEffect(() => {
    api.get("/profiles/templates").then(({ data }) => { setTemplates(data.templates); setCatalog(data.catalog); }).catch((e) => console.error("load templates failed", e));
    api.get("/agent/token").then(({ data }) => setToken(data.token)).catch((e) => console.error("load agent token failed", e));
    load();
  }, []);

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const save = async () => {
    if (!name.trim()) { toast.error(t("profiles.err_name")); return; }
    if (selected.length === 0) { toast.error(t("profiles.err_tweak")); return; }
    try {
      await api.post("/profiles", { game_name: name.trim(), tweak_ids: selected });
      toast.success(t("profiles.created"));
      setCreating(false); setName(""); setSelected([]); load();
    } catch { toast.error(t("profiles.err_create")); }
  };
  const del = async (id) => { await api.delete(`/profiles/${id}`); toast.success(t("profiles.deleted")); load(); };

  const cats = ["gaming", "input", "network", "system"];
  const CAT_LABELS = { gaming: t("profiles.cat_gaming"), input: t("profiles.cat_input"), network: t("profiles.cat_network"), system: t("profiles.cat_system") };
  // Group catalog once per catalog change so the create-profile form doesn't re-filter on every render.
  const catalogByCat = useMemo(() => {
    const map = { gaming: [], input: [], network: [], system: [] };
    for (const c of catalog) if (map[c.cat]) map[c.cat].push(c);
    return map;
  }, [catalog]);

  return (
    <div className="max-w-5xl mx-auto fade-up" data-testid="profiles-page">
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("profiles.eyebrow")}</div>
          <h1 className="font-display font-black text-3xl tracking-tighter">{t("profiles.title")}</h1>
          <p className="text-zinc-500 text-sm mt-1">{t("profiles.subtitle")}</p>
        </div>
        <button data-testid="new-profile-btn" onClick={() => setCreating((c) => !c)}
          className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2.5 text-sm hover:bg-[#c9e000] transition-colors">
          {creating ? <X size={16} /> : <Plus size={16} />} {creating ? t("common.cancel") : t("profiles.new")}
        </button>
      </div>

      {creating && (
        <div className="bg-[#0F0F12] border border-[#E5FF00]/40 p-5 mb-6" data-testid="create-profile-form">
          <input data-testid="profile-name-input" value={name} onChange={(e) => setName(e.target.value)}
            placeholder={t("profiles.name_ph")}
            className="w-full bg-black border border-[#2A2A35] px-3 py-2.5 text-sm mb-4 focus:border-[#E5FF00] outline-none" />
          {cats.map((cat) => (
            <div key={cat} className="mb-4">
              <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">{CAT_LABELS[cat]}</div>
              <div className="grid sm:grid-cols-2 gap-1.5">
                {(catalogByCat[cat] || []).map((c) => (
                  <label key={c.id} data-testid={`tweak-opt-${c.id}`} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer border border-[#1A1A24] px-2 py-1.5 hover:border-[#2A2A35]">
                    <input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggle(c.id)} className="accent-[#E5FF00]" />
                    {c.name}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button data-testid="save-profile-btn" onClick={save} className="inline-flex items-center gap-2 bg-[#E5FF00] text-black font-bold px-4 py-2.5 text-sm">
            <Save size={16} /> {t("profiles.save_profile")} ({selected.length})
          </button>
        </div>
      )}

      <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2"><Zap size={13} className="text-[#E5FF00]" /> {t("profiles.presets")}</div>
      <div className="grid md:grid-cols-2 gap-3 mb-8">
        {templates.map((tp) => <ProfileCard key={tp.id} p={tp} catalog={catalog} token={token} onDelete={del} />)}
      </div>

      {profiles.length > 0 && (
        <>
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3">{t("profiles.yours")}</div>
          <div className="grid md:grid-cols-2 gap-3">
            {profiles.map((p) => <ProfileCard key={p.id} p={p} catalog={catalog} token={token} onDelete={del} />)}
          </div>
        </>
      )}
    </div>
  );
}
