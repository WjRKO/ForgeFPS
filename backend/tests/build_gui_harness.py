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
// Il piano arriva solo per i tweak che hanno qualcosa da cambiare, e porta le
// tre forme che la scheda deve saper disegnare: un prima letto sulla macchina,
// un valore che non si legge (solo il dopo), e una riga gia' a posto che non si
// conta fra le modifiche.
MOCK_TWEAKS.push(twk('g8','gaming','todo',false, { plan: [
  { what:'Game Mode', now:'0', next:'1', same:false, key:'HKCU:\\\\Software\\\\Microsoft\\\\GameBar::AllowAutoGameMode' },
  { what:'Hardware GPU Scheduling', now:'non impostata', next:'2', same:false, key:'HKLM:\\\\SYSTEM\\\\CCS\\\\Control::HwSchMode' },
  { what:'Parcheggio dei core CPU', now:'', next:'disattivato', same:false },
  { what:'Game DVR', now:'0', next:'0', same:true }
] }));
MOCK_TWEAKS.push(twk('g9','gaming','todo',false, { plan: [
  { what:'Accelerazione del puntatore', now:'1', next:'0', same:false, key:'HKCU:\\\\Control Panel\\\\Mouse::MouseSpeed' }
] }));
MOCK_TWEAKS.push(twk('g10','gaming','todo',false, { risk:'caution' }, '261 MB da pulire'));
MOCK_TWEAKS.push(twk('i1','input','todo',false));
MOCK_TWEAKS.push(twk('n1','network','ok',false,null,'gia su Cloudflare'));
MOCK_TWEAKS.push(twk('s1','system','todo',false));
const MOCK_STATE = {
  hw: { gpu:'NVIDIA', ram:32, ssd:true, laptop:false, win11:true },
  admin: location.search.indexOf('noadmin') < 0, backup: 1,
  backup_ids: 'g1', revertable: 'g1',
  agent: { installed:'0.7.9', latest:'0.7.9', dl:'' },
  tweaks: MOCK_TWEAKS,
  presets: { competitive:['g1','g8'], streaming:['g9'], complete: MOCK_TWEAKS.map(t=>t.id) }
};
// Journal: la cronologia su disco, per sessioni. Ogni forma che la schermata
// deve saper mostrare c'e' una volta sola - applicata e ancora attiva, non
// riuscita (nessuna chiave scritta), gia' annullata, e una chiave che prima
// non esisteva: sono i casi in cui il riquadro sbaglia se qualcuno lo tocca.
const MOCK_JOURNAL = { ok: true, file: 'C:\\\\Users\\\\tester\\\\AppData\\\\Roaming\\\\FrameForge\\\\journal.jsonl',
  live: ['g1','g8'],
  // L'unico numero misurato del prodotto: la Diagnosi lo mostra al posto
  // di una stima.
  bench: { ts:'2026-08-22T14:34:00+02:00', before:104, after:113, delta_pct:9 },
  sessions: [
    // Sessione con UNA voce e UNA chiave cambiata: dopo comePowerShell arrivano
    // come oggetti singoli, non come liste. E' esattamente cio' che ha rotto la
    // Diagnosi al primo avvio su una macchina vera.
    { id:'s-20260823-090000', started:'2026-08-23T09:00:00+02:00',
      applied:0, failed:0, reverted:1, revertable:[],
      entries:[
        { ts:'2026-08-23T09:00:00+02:00', event:'revert', tweak:'g9', name:'DNS veloci (Cloudflare)',
          cat:'network', ok:true, err:'', revertable:false, changes:[] }
      ] },
    { id:'s-20260822-143208', started:'2026-08-22T14:32:08+02:00',
      applied:3, failed:1, reverted:0, revertable:['g1','g8'],
      entries:[
        { ts:'2026-08-22T14:32:08+02:00', event:'apply', tweak:'g1', name:'Piano energetico prestazioni massime',
          cat:'gaming', ok:true, err:'', revertable:true,
          changes:[{key:'power_plan', previous:'Bilanciato', current:'Prestazioni elevate'},
                   {key:'HKLM:\\\\...\\\\Power::CPMINCORES', previous:'50', current:'100'}] },
        { ts:'2026-08-22T14:32:12+02:00', event:'apply', tweak:'gpu_msi', name:'GPU: MSI mode ON',
          cat:'gaming', ok:false, err:'accesso negato al ramo dei driver', revertable:false, changes:[] },
        { ts:'2026-08-22T14:32:14+02:00', event:'apply', tweak:'g8', name:'Timer resolution globale',
          cat:'input', ok:true, err:'', revertable:true,
          changes:[{key:'HKLM:\\\\SYSTEM\\\\...\\\\kernel::GlobalTimerResolutionRequests',
                    previous:'non esisteva', current:'1'}] },
        { ts:'2026-08-22T14:32:16+02:00', event:'apply', tweak:'g9', name:'DNS veloci (Cloudflare)',
          cat:'network', ok:true, err:'', revertable:false,
          changes:[{key:'dns::Ethernet', previous:'192.168.1.1', current:'1.1.1.1, 1.0.0.1'}] }
      ] }
  ] };
// L'applicazione dei tweak e' un job: /api/apply lo registra e torna subito,
// poi il client segue /api/job. Il finto job avanza di un passo a ogni poll,
// come quello vero avanza a ogni giro del loop del listener. Il DTO porta la
// LISTA dei passi col proprio esito: e' quella che la schermata di lavoro
// disegna, e ci sono dentro tutti gli stati che deve saper mostrare.
let MOCK_JOB = null;
function mockJob(kind, etichette) {
  return { id:'j1', kind:kind, state:'running', step:0, total:etichette.length, pct:0,
           current:etichette[0], cancel:false, errors:[], result:{},
           steps: etichette.map((l, i) => ({ i:i, label:l, slow: /Benchmark|Invio/.test(l), state:'pending', err:'' })) };
}
function mockJobAvanza() {
  const j = MOCK_JOB;
  // fermato: i passi rimasti si saltano, quelli di chiusura no
  const finale = (i) => i >= j.total - 1;
  if (j.step < j.total) {
    const s = j.steps[j.step];
    if (j.cancel && !finale(j.step)) s.state = 'skipped';
    else if (s.label.indexOf('MSI') >= 0) { s.state = 'failed'; s.err = 'accesso negato al ramo dei driver';
                                            j.errors.push({ i:j.step, step:s.label, err:s.err }); }
    else s.state = 'ok';
    j.step++;
  }
  j.pct = Math.round(100 * j.step / j.total);
  if (j.step >= j.total) {
    j.state = j.cancel ? 'cancelled' : 'done';
    j.current = '';
    j.result = j.rimozione
      ? { ok:true, removed:2, apps:[] }
      : { ok:true, tweaks:MOCK_TWEAKS, backup:3, backup_ids:['g1'], revertable:['g1'] };
  } else {
    j.steps[j.step].state = 'current';
    j.current = j.steps[j.step].label;
  }
  return j;
}
const PASSI_APPLY = ['Benchmark PRIMA in corso...', '-> Piano energetico prestazioni massime',
                     '-> GPU: MSI mode ON', '-> DNS veloci (Cloudflare)', '-> Timer resolution globale',
                     'Salvo il backup delle impostazioni.', 'Benchmark DOPO in corso...',
                     'Invio i dati aggiornati a FrameForge...'];
// ConvertTo-Json (PS 5.1) serializza un array di UN elemento come scalare.
// L'harness lo riproduce su ogni risposta: e' il difetto piu' sottile che
// l'agent vero possa presentare — la GUI esplodeva sul primo PC con una sola
// sessione nel journal — e un mock che manda sempre array non lo vedrebbe mai.
function comePowerShell(v) {
  if (Array.isArray(v)) return v.length === 1 ? comePowerShell(v[0]) : v.map(comePowerShell);
  if (v && typeof v === 'object') {
    const o = {};
    for (const k of Object.keys(v)) o[k] = comePowerShell(v[k]);
    return o;
  }
  return v;
}
window.fetch = function(url, opts) {
  const u = String(url);
  let body = { ok: true };
  let delay = 0;
  if (u.indexOf('/api/state') >= 0) { body = MOCK_STATE; delay = 4000; }
  // Anche questi sono job adesso: prima erano richieste che rispondevano dopo
  // aver fatto tutto, e il server locale restava fermo per tutto il tempo.
  else if (u.indexOf('/api/apply-one') >= 0) {
    MOCK_JOB = mockJob('apply-one', ['-> Tweak g8', 'Fatto.']);
    body = { ok: true, job: MOCK_JOB };
  }
  else if (u.indexOf('/api/restore-one') >= 0) {
    MOCK_JOB = mockJob('restore-one', ['<- Tweak g1', 'Ripristinato.']);
    body = { ok: true, job: MOCK_JOB };
  }
  else if (u.indexOf('/api/restore') >= 0) {
    MOCK_JOB = mockJob('restore', ['<- Tweak g1', '<- Tweak g8',
                                   'Ripristino il resto del backup.', 'Tutto rimesso com era.']);
    body = { ok: true, job: MOCK_JOB };
  }
  else if (u.indexOf('/api/bloatware/remove') >= 0) {
    MOCK_JOB = mockJob('bloatware', ['-> Microsoft.BingNews', '-> Microsoft.GetHelp', 'App aggiornate.']);
    MOCK_JOB.rimozione = true;
    body = { ok: true, job: MOCK_JOB };
  }
  else if (u.indexOf('/api/apply') >= 0) { MOCK_JOB = mockJob('apply', PASSI_APPLY); body = { ok: true, job: MOCK_JOB }; }
  else if (u.indexOf('/api/job/cancel') >= 0) {
    if (MOCK_JOB) MOCK_JOB.cancel = true;
    body = { ok: true, job: MOCK_JOB };
  }
  else if (u.indexOf('/api/job') >= 0) body = MOCK_JOB ? mockJobAvanza() : { state: 'idle' };
  else if (u.indexOf('/api/log') >= 0) body = { logs: [], total: 0, applying: !!(MOCK_JOB && MOCK_JOB.state === 'running') };
  else if (u.indexOf('/api/bloatware') >= 0) body = { apps: [
    { name:'Microsoft.BingNews', label:'Notizie', size_mb: 34 },
    { name:'Microsoft.GetHelp', label:'Richiesta supporto', size_mb: 12 },
    { name:'Microsoft.ZuneMusic', label:'Groove Musica', size_mb: 58 } ] };
  else if (u.indexOf('/api/journal') >= 0) body = MOCK_JOURNAL;
  else if (u.indexOf('/api/revert-session') >= 0) {
    MOCK_JOURNAL.sessions[1].revertable = [];
    MOCK_JOURNAL.sessions[1].entries.forEach(e => { e.revertable = false; });
    MOCK_JOB = mockJob('revert-session', ['<- Piano energetico prestazioni massime',
                                          '<- Timer resolution globale', 'Sessione annullata.']);
    body = { ok: true, job: MOCK_JOB };
  }
  else if (u.indexOf('/api/client-error') >= 0) { try { window.__reported.push(JSON.parse(opts.body).msg); } catch(e){} }
  const servito = comePowerShell(body);
  return new Promise(res => setTimeout(() => res({ json: () => Promise.resolve(servito), ok: true, status: 200 }), delay));
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
