import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ListTodo, Check, Trash2, Loader2 } from "lucide-react";
import api from "@/lib/api";

/**
 * Lista delle azioni messe da parte con "Salva per dopo" nella diagnosi AI.
 *
 * Prima esisteva solo la scrittura: l'utente salvava un'azione, riceveva il toast
 * di conferma e non la rivedeva mai piu'. Gli endpoint per completarla ed
 * eliminarla erano gia' nel backend, senza nessuna interfaccia che li chiamasse.
 *
 * Si aggiorna anche in risposta all'evento `ff-planned-saved`, cosi' una nuova
 * azione salvata dal pannello di diagnosi compare qui senza ricaricare la pagina.
 */

const DIFFICULTY_STYLE = {
  facile: "text-[#00E0FF] border-[#00E0FF]/40",
  medio: "text-[#E5FF00] border-[#E5FF00]/40",
  avanzato: "text-[#FF3B30] border-[#FF3B30]/40",
};

export default function PlannedActionsCard() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language && i18n.language.startsWith("en") ? "en" : "it";
  const c = t("plannedactions", { returnObjects: true });
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    api.get("/advisor/planned-actions")
      .then(({ data }) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => {
    load();
    const onSaved = () => load();
    window.addEventListener("ff-planned-saved", onSaved);
    return () => window.removeEventListener("ff-planned-saved", onSaved);
  }, [load]);

  const act = async (id, kind) => {
    setBusy(id);
    try {
      if (kind === "done") await api.post(`/advisor/planned-actions/${id}/done`);
      else await api.delete(`/advisor/planned-actions/${id}`);
      setItems((prev) => (prev || []).filter((x) => x.id !== id));
      toast.success(kind === "done" ? c.markedDone : c.removed);
    } catch {
      toast.error(c.failed);
    } finally {
      setBusy("");
    }
  };

  // Finche' non si sa se ci sono azioni non si mostra nulla: una card vuota che
  // appare e sparisce a ogni caricamento e' peggio di nessuna card.
  if (items === null) return null;

  const label = (d) => ({ facile: c.easy, medio: c.medium, avanzato: c.hard }[d] || d);

  return (
    <div className="bg-[#0F0F12] border border-[#2A2A35] hud-tick p-6 mb-4" data-testid="planned-actions-card">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1 flex items-center gap-2">
        <ListTodo size={14} className="text-[#E5FF00]" /> {c.title}
        {items.length > 0 && (
          <span className="ml-1 text-[#E5FF00] font-mono" data-testid="planned-actions-count">
            {items.length}
          </span>
        )}
      </div>
      <p className="text-xs text-zinc-600 mb-4">{c.sub}</p>

      {items.length === 0 ? (
        <p className="text-sm text-zinc-600" data-testid="planned-actions-empty">{c.empty}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((a) => (
            <li
              key={a.id}
              className="border border-[#1A1A24] bg-black p-3 flex items-start justify-between gap-3"
              data-testid="planned-action-row"
            >
              <div className="min-w-0">
                <div className="text-sm text-zinc-200 break-words">{a.title}</div>
                {a.description && (
                  <p className="text-xs text-zinc-500 mt-1 break-words">{a.description}</p>
                )}
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  {a.difficulty && (
                    <span className={`text-[11px] uppercase tracking-wider border px-1.5 py-0.5 ${DIFFICULTY_STYLE[a.difficulty] || "text-zinc-500 border-[#2A2A35]"}`}>
                      {label(a.difficulty)}
                    </span>
                  )}
                  {a.impact && <span className="text-[11px] text-[#00E0FF]">{a.impact}</span>}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => act(a.id, "done")}
                  disabled={busy === a.id}
                  title={c.done}
                  aria-label={c.done}
                  data-testid="planned-action-done"
                  className="p-2 border border-[#2A2A35] text-zinc-400 hover:text-[#E5FF00] hover:border-[#E5FF00]/50 transition-colors disabled:opacity-40"
                >
                  {busy === a.id ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                </button>
                <button
                  onClick={() => act(a.id, "delete")}
                  disabled={busy === a.id}
                  title={c.remove}
                  aria-label={c.remove}
                  data-testid="planned-action-delete"
                  className="p-2 border border-[#2A2A35] text-zinc-500 hover:text-[#FF3B30] hover:border-[#FF3B30]/50 transition-colors disabled:opacity-40"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
