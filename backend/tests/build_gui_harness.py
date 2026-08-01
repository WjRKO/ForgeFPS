"""Genera /app/frontend/public/gui_test.html: la GUI locale dell'agent (estratta da
ps_agent.py) con API mockate, incluso un tweak CORROTTO per verificare che il render
non si svuoti mai (bug: griglia vuota all'avvio). Uso: python3 build_gui_harness.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ps_agent

s = ps_agent.PS_SCRIPT
i = s.index("$html = @'")
j = s.index("\n'@", i)
html = s[i + len("$html = @'") + 1:j]

MOCK = """<script>
// ---- TEST MOCK LAYER (solo harness, non nella GUI reale) ----
window.__errors = [];
window.__reported = [];
window.addEventListener('error', e => window.__errors.push(String(e.message)));
const MOCK_TWEAKS = [];
function twk(id, cat, state, fitskip, extra) {
  return Object.assign({ id: id, cat: cat, name: 'Tweak ' + id, problem: 'Problema x', reason: 'Motivo y',
    desc: 'Descrizione z', impact: '+3-8% FPS', risk: 'safe',
    state: state, fit: fitskip ? { ok:false, warn:false, note:false, skip:true, hint:'Solo GPU AMD (rilevata NVIDIA)' } : { ok:true, warn:false, note:false, skip:false, hint:'' } }, extra || {});
}
MOCK_TWEAKS.push(twk('g1','gaming','Gia attivo',false));
MOCK_TWEAKS.push(twk('g2','gaming','Gia attivo',false));
// DATO CORROTTO: fit mancante + state/impact null (simula il bug reale)
MOCK_TWEAKS.push({ id:'g3-broken', cat:'gaming', name:'Tweak corrotto (no fit)', problem:'p', reason:'r', desc:'d', impact:null, risk:'safe', state:null });
MOCK_TWEAKS.push(twk('g4','gaming','Solo GPU AMD',true));
MOCK_TWEAKS.push(twk('g5','gaming','Disabilitato correttamente',false));
MOCK_TWEAKS.push(twk('g6','gaming','Nessun bloat rilevato',false));
MOCK_TWEAKS.push(twk('g7','gaming','TRIM attivo',false));
MOCK_TWEAKS.push(twk('g8','gaming','(da attivare)',false));
MOCK_TWEAKS.push(twk('g9','gaming','(da disattivare)',false));
MOCK_TWEAKS.push(twk('g10','gaming','(da ottimizzare)',false, { risk:'caution' }));
MOCK_TWEAKS.push(twk('i1','input','(da attivare)',false));
MOCK_TWEAKS.push(twk('n1','network','Gia attivo',false));
MOCK_TWEAKS.push(twk('s1','system','(da attivare)',false));
const MOCK_STATE = {
  hw: { gpu:'NVIDIA', ram:32, ssd:true, laptop:false, win11:true },
  admin: true, backup: 1,
  backup_ids: 'g1', revertable: 'g1',
  agent: { installed:'0.7.9', latest:'0.7.9', dl:'' },
  tweaks: MOCK_TWEAKS,
  presets: { competitive:['g1','g8'], streaming:['g9'], complete: MOCK_TWEAKS.map(t=>t.id) }
};
window.fetch = function(url, opts) {
  const u = String(url);
  let body = { ok: true };
  let delay = 0;
  if (u.indexOf('/api/state') >= 0) { body = MOCK_STATE; delay = 4000; }
  else if (u.indexOf('/api/log') >= 0) body = { logs: [], total: 0, applying: false };
  else if (u.indexOf('/api/client-error') >= 0) { try { window.__reported.push(JSON.parse(opts.body).msg); } catch(e){} }
  return new Promise(res => setTimeout(() => res({ json: () => Promise.resolve(body), ok: true, status: 200 }), delay));
};
</script>
"""

anchor = "<script>\n(function(){"
assert anchor in html, "anchor script non trovato"
html = html.replace(anchor, MOCK + anchor, 1)
out = "/app/frontend/public/gui_test.html"
open(out, "w").write(html)
print("harness scritto:", out, len(html))
