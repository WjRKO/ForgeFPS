"""Genera backend/tests/out/gui_test.html: la GUI locale dell'agent (estratta da
ps_agent.py) con API mockate, incluso un tweak CORROTTO per verificare che il render
non si svuoti mai (bug: griglia vuota all'avvio). Uso: python3 build_gui_harness.py"""
from pathlib import Path as _P
# Radice del repository calcolata dal file: i percorsi "/app/..." erano il
# layout di un vecchio container e non esistono ne' in locale ne' nell'immagine
# attuale, che monta il codice in /srv/app.
_BACKEND_DIR = _P(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ps_agent

# La GUI e' un file: si legge, non si ritaglia. Prima questo harness cercava i
# delimitatori della here-string dentro PS_SCRIPT e affettava per indice, il che
# funzionava finche' nessuno toccava i delimitatori.
html = ps_agent.GUI_HTML

MOCK = """<script>
// ---- TEST MOCK LAYER (solo harness, non nella GUI reale) ----
window.__errors = [];
window.__reported = [];
window.addEventListener('error', e => window.__errors.push(String(e.message)));
const MOCK_TWEAKS = [];
// Stessa forma che manda il backend: codice + etichetta composta dallo stato.
// Prima il mock inventava le proprie frasi ('Gia attivo', 'TRIM attivo') e
// l'anteprima mostrava un modello che non esiste piu' da nessuna parte.
const PAROLE = { ok:'Ottimale', todo:'Da applicare', na:'Non applicabile', unknown:'Sconosciuto' };
function twk(id, cat, code, fitskip, extra, dettaglio) {
  const label = PAROLE[code] + (dettaglio ? ' - ' + dettaglio : '');
  return Object.assign({ id: id, cat: cat, name: 'Tweak ' + id, problem: 'Problema x', reason: 'Motivo y',
    desc: 'Descrizione z', impact: '+3-8% FPS', risk: 'safe',
    state: label, state_code: code,
    fit: fitskip ? { ok:false, warn:false, note:false, skip:true, hint:'Solo GPU AMD (rilevata NVIDIA)' } : { ok:true, warn:false, note:false, skip:false, hint:'' } }, extra || {});
}
MOCK_TWEAKS.push(twk('g1','gaming','ok',false));
MOCK_TWEAKS.push(twk('g2','gaming','ok',false));
// DATO CORROTTO: fit mancante + state/impact null (simula il bug reale)
MOCK_TWEAKS.push({ id:'g3-broken', cat:'gaming', name:'Tweak corrotto (no fit)', problem:'p', reason:'r', desc:'d', impact:null, risk:'safe', state:null });
MOCK_TWEAKS.push(twk('g4','gaming','na',true,null,'solo su GPU AMD'));
MOCK_TWEAKS.push(twk('g5','gaming','ok',false));
MOCK_TWEAKS.push(twk('g6','gaming','ok',false,null,'nessuna app da rimuovere'));
MOCK_TWEAKS.push(twk('g7','gaming','ok',false));
MOCK_TWEAKS.push(twk('g8','gaming','todo',false));
MOCK_TWEAKS.push(twk('g9','gaming','todo',false));
MOCK_TWEAKS.push(twk('g10','gaming','todo',false, { risk:'caution' }, '261 MB da pulire'));
MOCK_TWEAKS.push(twk('i1','input','todo',false));
MOCK_TWEAKS.push(twk('n1','network','ok',false,null,'gia su Cloudflare'));
MOCK_TWEAKS.push(twk('s1','system','todo',false));
const MOCK_STATE = {
  hw: { gpu:'NVIDIA', ram:32, ssd:true, laptop:false, win11:true },
  admin: true, backup: 1,
  backup_ids: 'g1', revertable: 'g1',
  agent: { installed:'0.7.9', latest:'0.7.9', dl:'' },
  tweaks: MOCK_TWEAKS,
  presets: { competitive:['g1','g8'], streaming:['g9'], complete: MOCK_TWEAKS.map(t=>t.id) }
};
// Cronologia delle modifiche: una voce con valore precedente, una con chiave
// che prima non esisteva, una senza data (backup scritto da un agent vecchio).
const MOCK_CHANGES = { ok: true, backup_file: 'C:\\\\Users\\\\tester\\\\AppData\\\\Local\\\\Temp\\\\forgefps_backup.json', items: [
  { id:'g1', name:'Piano energetico prestazioni massime', cat:'gaming',
    applied_at:'2026-08-20T18:30:00+02:00',
    keys:[{key:'HKLM:\\\\SYSTEM\\\\...\\\\Power::Scheme', previous:'Bilanciato'}] },
  { id:'g8', name:'MPO off (fix stutter DWM)', cat:'gaming',
    applied_at:'2026-08-19T09:05:00+02:00',
    keys:[{key:'HKLM:\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\Dwm::OverlayTestMode', previous:'non esisteva'},
          {key:'HKLM:\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\Dwm::Other', previous:'2'}] },
  { id:'g9', name:'Tweak applicato da una versione precedente', cat:'network',
    applied_at:'', keys:[{key:'HKCU:\\\\Software\\\\X::Y', previous:'0'}] }
] };
window.fetch = function(url, opts) {
  const u = String(url);
  let body = { ok: true };
  let delay = 0;
  if (u.indexOf('/api/state') >= 0) { body = MOCK_STATE; delay = 4000; }
  else if (u.indexOf('/api/log') >= 0) body = { logs: [], total: 0, applying: false };
  else if (u.indexOf('/api/changes') >= 0) body = MOCK_CHANGES;
  else if (u.indexOf('/api/client-error') >= 0) { try { window.__reported.push(JSON.parse(opts.body).msg); } catch(e){} }
  return new Promise(res => setTimeout(() => res({ json: () => Promise.resolve(body), ok: true, status: 200 }), delay));
};
</script>
"""

anchor = "<script>\n(function(){"
assert anchor in html, "anchor script non trovato"
html = html.replace(anchor, MOCK + anchor, 1)
# Non in frontend/public/: quella cartella finisce integralmente nella build di
# produzione, e l'harness veniva pubblicato su internet come pagina raggiungibile.
_OUT_DIR = _P(__file__).resolve().parent / "out"
_OUT_DIR.mkdir(exist_ok=True)
out = str(_OUT_DIR / "gui_test.html")
open(out, "w", encoding="utf-8").write(html)
print("harness scritto:", out, len(html))
