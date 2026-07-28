
(function(){
  const TOKEN = "__TOKEN__";
  const CATS = [
    { key: "gaming",  label: "Gaming & FPS" },
    { key: "input",   label: "Latenza & Input" },
    { key: "network", label: "Rete & Streaming" },
    { key: "system",  label: "Sistema & Debloat" },
    { key: "bloatware", label: "Bloatware" },
    { key: "monitor", label: "Monitor Live" },
    { key: "profiles", label: "Profili Cloud" }
  ];
  let state = { tweaks: [], hw: {}, admin: false, backup: 0, backup_ids: [], presets: {}, profiles: null, revertable: [], agent: {} };
  let selected = new Set();
  let activeCat = "gaming";
  let searchQ = "";
  let logSince = 0;
  let applying = false;
  // GUI v2.5 — density mode (A), filters (H), sort (I)
  let density = (localStorage.getItem("ff_density") || "detailed"); // "compact" | "detailed"
  let expanded = new Set(); // per-card override in compact mode
  let activeFilters = new Set();
  let sortMode = "impact";

  function api(path, opts) {
    opts = opts || {};
    const url = path + (path.indexOf("?") >= 0 ? "&" : "?") + "tk=" + encodeURIComponent(TOKEN);
    return fetch(url, opts).then(r => r.json());
  }
  // GUI v3.1: errori JS -> log visibile in GUI + console (debug remoto senza rebuild)
  function reportClientError(msg) {
    try { console.error("[FF-GUI]", msg); } catch(_) {}
    try {
      fetch("/api/client-error?tk=" + encodeURIComponent(TOKEN), {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ msg: String(msg).slice(0, 600) })
      }).catch(()=>{});
    } catch(_) {}
  }
  window.addEventListener("error", e => reportClientError((e.message || "?") + " @riga " + (e.lineno || "?")));
  window.addEventListener("unhandledrejection", e => reportClientError("promise: " + (e.reason && (e.reason.stack || e.reason.message) || e.reason)));
  function safeRender(name, fn) {
    try { fn(); } catch (err) { reportClientError(name + ": " + (err && err.stack || err)); }
  }
  function toast(msg, cls) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast show" + (cls ? " " + cls : "");
    clearTimeout(t._h); t._h = setTimeout(() => t.className = "toast", 2400);
  }
  function esc(s) {
    return String(s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  }
  function stateClass(s) {
    const x = String(s || "").toLowerCase();
    if (!x || x === "n/d") return "na";
    // "(da attivare|disattivare|disabilitare|ottimizzare)" o "da attivare" ecc. -> azione richiesta
    if (/\(da (att|dis|ott)/i.test(x) || /^da (att|dis|ott)/i.test(x)) return "todo";
    // Solo GPU X (skip perche' altro vendor) -> non applicabile
    if (/^solo gpu /i.test(x)) return "na";
    // Stati positivi noti
    if (/attivo|attiva|disabilit|disattivat|gia |prestazioni|nessun|applicabile|libera ora|trim attivo/i.test(x)) return "ok";
    return "";
  }
  function isApplied(t) {
    if (t.fit.skip) return false;
    return stateClass(t.state) === "ok";
  }

  // ===== B. Impact meter — parse "+3-8% FPS", "meno stutter" ecc. -> 0..5 stars =====
  function parseImpact(t) {
    const s = String(t.impact || "").toLowerCase();
    // Numeric percentage range or single value
    const m = s.match(/\+?(\d+)\s*[-–]\s*(\d+)\s*%/) || s.match(/\+?(\d+)\s*%/);
    if (m) {
      const hi = parseInt(m[2] || m[1], 10);
      if (hi >= 20) return 5;
      if (hi >= 11) return 4;
      if (hi >= 6)  return 3;
      if (hi >= 3)  return 2;
      return 1;
    }
    // Qualitative
    if (/molto\s+meno\s+stutter|enorme|drastic/i.test(s)) return 4;
    if (/meno\s+stutter|pi[uù]\s+stabil|migliora\s+netta|pi[uù]\s+veloce/i.test(s)) return 3;
    if (/leggero|marginal|piccolo|minimo/i.test(s)) return 1;
    if (/latenza|input|frametime|reattiv/i.test(s)) return 2;
    return 2; // default
  }

  // Simple time/reboot detection from various text fields
  function needsReboot(t) {
    const s = ((t.desc || "") + " " + (t.impact || "") + " " + (t.problem || "") + " " + (t.reason || "")).toLowerCase();
    return /richiede\s+riavvio|require[s]?\s+reboot|riavvio\s+richiest/i.test(s);
  }

  // ===== H. Filter matching =====
  function matchFilters(t) {
    if (!activeFilters.size) return true;
    if (activeFilters.has("recommended") && parseImpact(t) < 3) return false;
    if (activeFilters.has("no-reboot") && needsReboot(t)) return false;
    if (activeFilters.has("reversible") && t.risk === "caution") return false;
    if (activeFilters.has("caution") && t.risk !== "caution") return false;
    if (activeFilters.has("pending") && (isApplied(t) || t.fit.skip)) return false;
    return true;
  }

  // ===== I. Sort =====
  function sortItems(items) {
    const arr = items.slice();
    if (sortMode === "impact") {
      arr.sort((a, b) => parseImpact(b) - parseImpact(a));
    } else if (sortMode === "name") {
      arr.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    } else if (sortMode === "pending") {
      arr.sort((a, b) => {
        const pa = isApplied(a) ? 1 : 0, pb = isApplied(b) ? 1 : 0;
        if (pa !== pb) return pa - pb;
        return parseImpact(b) - parseImpact(a);
      });
    }
    return arr;
  }

  // ===== C. Preset preview — which tweaks would this preset apply? =====
  function computePresetPreview(name) {
    const ids = (state.presets && state.presets[name]) ? new Set(state.presets[name]) : new Set();
    const picks = state.tweaks.filter(t => ids.has(t.id) && !t.fit.skip && !isApplied(t));
    const fpsBoost = picks.reduce((sum, t) => {
      const s = String(t.impact || "");
      const m = s.match(/\+(\d+)\s*[-–]\s*(\d+)\s*%\s*FPS/i);
      return sum + (m ? parseInt(m[2], 10) : 0);
    }, 0);
    const reboots = picks.filter(needsReboot).length;
    return { picks, count: picks.length, fpsBoost, reboots, ids };
  }

  function renderPresetPreview(name) {
    const el = document.getElementById("presetPreview");
    if (!name || name === "none") { el.classList.remove("show"); el.innerHTML = ""; return; }
    const p = computePresetPreview(name);
    if (!p.count) { el.classList.remove("show"); el.innerHTML = ""; return; }
    const parts = [`<b>${p.count}</b> tweak da applicare`];
    if (p.fpsBoost) parts.push(`<b>+${p.fpsBoost}%</b> FPS stimati max`);
    parts.push(p.reboots ? `<b>${p.reboots}</b> riavvi` : `<b>0</b> riavvi`);
    el.innerHTML = `Preset <b>${esc(name)}</b>: ` + parts.join(`<span class="preview-sep">·</span>`);
    el.classList.add("show");
    // Highlight cards
    document.querySelectorAll(".card").forEach(c => {
      const id = c.dataset.id;
      c.classList.toggle("preview-pick", p.ids.has(id) && !isApplied({ id, state: "", fit: { skip: false } }));
    });
  }
  function clearPresetPreview() {
    const el = document.getElementById("presetPreview");
    el.classList.remove("show"); el.innerHTML = "";
    document.querySelectorAll(".card.preview-pick").forEach(c => c.classList.remove("preview-pick"));
  }

  // ===== F. Progress ring =====
  function renderProgressRing() {
    const items = state.tweaks.filter(t => !t.fit.skip);
    const done = items.filter(t => isApplied(t)).length;
    const total = items.length || 1;
    const pct = Math.round((done / total) * 100);
    const circumference = 2 * Math.PI * 22; // r=22
    const offset = circumference * (1 - done / total);
    const fg = document.getElementById("progressRingFg");
    if (fg) fg.setAttribute("stroke-dashoffset", offset.toFixed(2));
    const pctEl = document.getElementById("progressRingPct");
    if (pctEl) pctEl.textContent = pct + "%";
    const info = document.getElementById("progressRingInfo");
    if (info) {
      const sub = pct >= 80 ? "Configurazione ottimale" : pct >= 50 ? "Buona strada" : "C'è margine di miglioramento";
      info.innerHTML = `<b>${done}/${total}</b> ottimizzato<br/><span style="color:var(--dim)">${sub}</span>`;
    }
  }

  // ===== J. Summary strip =====
  function updateSummaryStrip() {
    const strip = document.getElementById("summaryStrip");
    const btn = document.getElementById("applyBtn");
    const n = selected.size;
    if (!n) {
      strip.className = "summary-strip";
      strip.textContent = "Nessun tweak selezionato · scegli i tweak o clicca un preset";
      btn.disabled = true;
      btn.textContent = "Applica selezionati";
      return;
    }
    const picks = state.tweaks.filter(t => selected.has(t.id));
    const fpsMax = picks.reduce((sum, t) => {
      const m = String(t.impact || "").match(/\+(\d+)\s*[-–]\s*(\d+)\s*%\s*FPS/i);
      return sum + (m ? parseInt(m[2], 10) : 0);
    }, 0);
    const reboots = picks.filter(needsReboot).length;
    const cauts = picks.filter(t => t.risk === "caution").length;
    const parts = [`<b>${n}</b> selezionati`];
    if (fpsMax) parts.push(`<b>+${fpsMax}%</b> FPS stimati max`);
    if (reboots) parts.push(`<b>${reboots}</b> con riavvio`);
    if (cauts) parts.push(`<b>${cauts}</b> in cautela`);
    parts.push(`Backup automatico <b>ON</b>`);
    strip.innerHTML = parts.join(`<span class="sep">·</span>`);
    strip.className = cauts ? "summary-strip danger" : "summary-strip armed";
    btn.disabled = false;
    btn.textContent = `Applica ${n} tweak`;
  }

  // ===== K. Big toast (post-apply) =====
  function bigToast({ level, title, body, actions, autoDismiss }) {
    const host = document.getElementById("bigToastHost");
    const id = "bt-" + Date.now();
    const div = document.createElement("div");
    div.className = "big-toast " + (level || "");
    div.id = id;
    div.innerHTML = `
      <button class="big-toast-close" aria-label="Chiudi">&times;</button>
      <div class="big-toast-title">${esc(title || "")}</div>
      <div class="big-toast-body">${body || ""}</div>
      <div class="big-toast-actions"></div>`;
    const actsEl = div.querySelector(".big-toast-actions");
    (actions || []).forEach(a => {
      const b = document.createElement("button");
      b.className = a.primary ? "primary" : "";
      b.textContent = a.label;
      b.onclick = () => { try { a.onClick && a.onClick(); } finally { dismiss(); } };
      actsEl.appendChild(b);
    });
    if (!actions || !actions.length) actsEl.remove();
    const dismiss = () => {
      div.classList.remove("show");
      setTimeout(() => div.remove(), 300);
    };
    div.querySelector(".big-toast-close").onclick = dismiss;
    host.appendChild(div);
    requestAnimationFrame(() => div.classList.add("show"));
    if (autoDismiss !== false) setTimeout(dismiss, autoDismiss || 12000);
    return { dismiss };
  }

  function renderTabs() {
    const el = document.getElementById("tabs");
    el.innerHTML = CATS.map(c => {
      if (c.key === "profiles") {
        const count = state.profiles?.profiles?.length ?? "…";
        return `<button class="tab ${c.key === activeCat ? "active" : ""}" data-cat="${c.key}" data-testid="tab-${c.key}">${c.label}<span class="count">${count}</span></button>`;
      }
      if (c.key === "monitor") {
        return `<button class="tab ${c.key === activeCat ? "active" : ""}" data-cat="${c.key}" data-testid="tab-${c.key}"><span class="mon-live-dot"></span>${c.label}</button>`;
      }
      if (c.key === "bloatware") {
        const count = bloat ? (bloat.apps || []).length : "…";
        return `<button class="tab ${c.key === activeCat ? "active" : ""}" data-cat="${c.key}" data-testid="tab-${c.key}">${c.label}<span class="count">${count}</span></button>`;
      }
      const inCat = state.tweaks.filter(t => t.cat === c.key && !t.fit.skip);
      const todo = inCat.filter(t => !isApplied(t)).length;
      const total = inCat.length;
      return `<button class="tab ${c.key === activeCat ? "active" : ""}" data-cat="${c.key}" data-testid="tab-${c.key}">${c.label}<span class="count">${todo}/${total}</span></button>`;
    }).join("");
    [...el.querySelectorAll(".tab")].forEach(b => b.onclick = () => {
      activeCat = b.dataset.cat;
      if (activeCat === "profiles" && !state.profiles) loadProfiles();
      if (activeCat === "bloatware" && !bloat) loadBloat();
      if (activeCat === "monitor") startMonitor(); else stopMonitor();
      renderTabs();
      renderCards();
    });
  }

  function renderCards() {
    const el = document.getElementById("cards");
    if (activeCat === "profiles") { renderProfilesTab(el); return; }
    if (activeCat === "monitor") { renderMonitorTab(el); return; }
    if (activeCat === "bloatware") { renderBloatwareTab(el); return; }
    let items = state.tweaks.filter(t => t.cat === activeCat).filter(t => {
      if (!searchQ) return true;
      const q = searchQ.toLowerCase();
      return (t.name + " " + (t.problem||"") + " " + (t.impact||"")).toLowerCase().includes(q);
    });
    items = items.filter(matchFilters);
    items = sortItems(items);
    if (!items.length) { el.innerHTML = `<div class="empty">Nessun tweak in questa categoria.</div>`; return; }
    const cardHtml = (t) => {
      const applied = isApplied(t);
      t.applied = applied;
      const sel = selected.has(t.id);
      const skipCls = t.fit.skip ? " skip" : "";
      const appliedCls = applied ? " applied" : "";
      const riskCls = t.risk === "caution" ? " risk-caution" : "";
      const selCls = sel ? " selected" : "";
      const compactCls = density === "compact" ? " compact" : "";
      const expandedCls = expanded.has(t.id) ? " expanded" : "";
      let hint = "";
      if (t.fit.skip) hint = `<div class="hint skip">Non applicabile: ${esc(t.fit.hint)}</div>`;
      else if (t.fit.warn) hint = `<div class="hint">Attenzione: ${esc(t.fit.hint)}</div>`;
      else if (t.fit.note) hint = `<div class="hint">Nota: ${esc(t.fit.hint)}</div>`;
      const impactLvl = parseImpact(t);
      const impactPct = String(t.impact || "").match(/\+(\d+)\s*[-–]\s*(\d+)\s*%/);
      const impactLabel = impactPct ? `+${impactPct[2]}%` : (impactLvl >= 4 ? "high" : impactLvl >= 3 ? "med" : "low");
      const meterDots = Array.from({length: 5}, (_, i) => `<span class="impact-dot${i < impactLvl ? ` on-${impactLvl}` : ""}"></span>`).join("");
      const timePill = needsReboot(t) ? `<span class="time-pill reboot">&#128260; riavvio</span>` : `<span class="time-pill">&#9202; ~2s</span>`;
      const chevron = density === "compact" ? `<span class="chevron" data-toggle="${t.id}">&#9662;</span>` : "";
      return `
        <div class="card${skipCls}${riskCls}${selCls}${appliedCls}${compactCls}${expandedCls}" data-id="${t.id}" data-testid="card-${t.id}">
          <div class="card-head">
            <input type="checkbox" class="cb" data-id="${t.id}" ${sel?"checked":""} ${t.fit.skip?"disabled":""} data-testid="cb-${t.id}" />
            <div class="name">${esc(t.name)}</div>
            <span class="impact-meter" title="Impatto stimato">${meterDots}<span class="impact-label">${esc(impactLabel)}</span></span>
            ${timePill}
            ${chevron}
          </div>
          <div class="state ${stateClass(t.state)}">Stato: ${esc(t.state)}</div>
          <div class="desc-block">
            <div class="row"><div class="k" title="Problema">&#9888;</div><div class="v">${esc(t.problem)}</div></div>
            <div class="row"><div class="k motivo" title="Motivo">&#8505;</div><div class="v">${esc(t.reason)}</div></div>
            <div class="row"><div class="k mod" title="Modifica">&#9881;</div><div class="v">${esc(t.desc)}</div></div>
            <div class="row"><div class="k impatto" title="Impatto">&#128200;</div><div class="v impatto">${esc(t.impact)}</div></div>
          </div>
          ${hint}
          <div class="actions">
            ${applied
              ? `<span class="applied-note">&#10003; gia attivo</span>${(state.revertable||[]).indexOf(t.id) >= 0 ? `<button class="btn-revert-one" data-revert="${t.id}" data-testid="revert-one-${t.id}">&#8617; Ripristina</button>` : ""}`
              : `<button class="btn-apply-one" data-apply="${t.id}" ${t.fit.skip?"disabled":""} data-testid="apply-one-${t.id}">Applica</button>`}
          </div>
        </div>`;
    };
    // Una card corrotta non deve mai svuotare l'intera griglia: fallback per-card.
    el.innerHTML = items.map(t => {
      try { return cardHtml(t); }
      catch (err) {
        reportClientError("card '" + (t && t.id) + "': " + (err && err.stack || err));
        return `<div class="card" data-id="${esc(t && t.id || "")}"><div class="card-head"><div class="name">${esc((t && (t.name || t.id)) || "Tweak")}</div></div><div class="hint">Card non visualizzabile (dettagli nel log in basso)</div></div>`;
      }
    }).join("");
    el.querySelectorAll(".cb").forEach(cb => cb.onchange = e => {
      const id = e.target.dataset.id;
      if (e.target.checked) selected.add(id); else selected.delete(id);
      updateSelCount();
      const card = e.target.closest(".card");
      if (card) card.classList.toggle("selected", e.target.checked);
    });
    el.querySelectorAll(".btn-apply-one").forEach(b => b.onclick = () => applyOne(b.dataset.apply));
    el.querySelectorAll(".btn-revert-one").forEach(b => b.onclick = () => revertOne(b.dataset.revert));
    // Chevron expand/collapse in compact mode
    el.querySelectorAll(".chevron").forEach(ch => ch.onclick = (e) => {
      e.stopPropagation();
      const id = ch.dataset.toggle;
      if (expanded.has(id)) expanded.delete(id); else expanded.add(id);
      const card = ch.closest(".card");
      if (card) card.classList.toggle("expanded", expanded.has(id));
    });
  }

  function updateSelCount() {
    updateSummaryStrip();
    renderProgressRing();
  }

  // -------- Cloud profiles tab --------
  async function loadProfiles() {
    const el = document.getElementById("cards");
    if (activeCat === "profiles") el.innerHTML = `<div class="empty">Caricamento profili dal cloud…</div>`;
    try {
      const d = await api("/api/profiles-cloud");
      state.profiles = d && !d.err ? d : { profiles: [], templates: [], catalog: [], err: d?.err };
    } catch (e) {
      state.profiles = { profiles: [], templates: [], catalog: [], err: "network" };
    }
    if (activeCat === "profiles") { renderTabs(); renderCards(); }
  }

  function renderProfilesTab(el) {
    const p = state.profiles;
    if (!p) { el.innerHTML = `<div class="empty">Caricamento profili…</div>`; loadProfiles(); return; }
    if (p.err) { el.innerHTML = `<div class="empty">Cloud non raggiungibile. Verifica la connessione internet e riprova.</div>`; return; }
    const catalogMap = {};
    (p.catalog || []).forEach(c => { catalogMap[c.id] = c.name; });
    const cardHtml = (item, opts) => {
      const isTemplate = !!opts.template;
      const tweakIds = item.tweak_ids || [];
      const names = tweakIds.map(id => catalogMap[id]).filter(Boolean).slice(0, 6);
      const extra = tweakIds.length > 6 ? ` <span>+${tweakIds.length - 6}</span>` : "";
      const meta = isTemplate ? `📚 Template community · ${tweakIds.length} tweak` : `👤 Il tuo profilo · ${tweakIds.length} tweak`;
      const testid = isTemplate ? `profile-template-${item.id}` : `profile-${item.id}`;
      return `<div class="profile-card" data-testid="${testid}">
        <h3>${esc(item.name || item.game_name || 'Senza nome')}</h3>
        <div class="profile-meta">${meta}</div>
        <div class="profile-tweaks">${names.map(n => `<span>${esc(n)}</span>`).join("")}${extra}</div>
        <button class="profile-apply" data-testid="apply-${testid}" onclick='applyProfile(${JSON.stringify(tweakIds)})'>Applica profilo</button>
      </div>`;
    };
    let html = "";
    if ((p.profiles || []).length) {
      html += `<div class="profile-section-title" data-testid="section-my-profiles">// I MIEI PROFILI</div>`;
      html += p.profiles.map(pr => cardHtml(pr, { template: false })).join("");
    } else {
      html += `<div class="profile-section-title">// I MIEI PROFILI</div><div class="empty" style="grid-column: 1 / -1;">Nessun profilo personale ancora. Crea preset gaming su forgefps.dev &rarr; Gaming.</div>`;
    }
    if ((p.templates || []).length) {
      html += `<div class="profile-section-title" data-testid="section-templates">// TEMPLATE COMMUNITY</div>`;
      html += p.templates.map(t => cardHtml(t, { template: true })).join("");
    }
    el.innerHTML = html;
  }

  window.applyProfile = function(tweakIds) {
    if (!Array.isArray(tweakIds) || !tweakIds.length) return;
    // Select the tweaks in the local catalog matching this profile.
    selected.clear();
    let matched = 0;
    for (const id of tweakIds) {
      if (state.tweaks.find(t => t.id === id && !t.fit.skip)) { selected.add(id); matched++; }
    }
    if (!matched) { toast("Nessun tweak compatibile con il tuo hardware", "err"); return; }
    toast(`Profilo caricato: ${matched} tweak selezionati`, "ok");
    // Jump to Gaming tab so the user sees what got selected.
    activeCat = "gaming";
    renderTabs(); renderCards(); updateSelCount();
  };

  function renderHeader() {
    const hw = state.hw || {};
    const gpuTxt = hw.gpu || "?";
    const chassis = hw.laptop ? "Laptop" : "Desktop";
    const disk = hw.ssd ? "SSD" : "HDD";
    const win11 = hw.win11 ? " | Win 11" : "";
    document.getElementById("hwLine").innerHTML =
      `PC: <b>${chassis}</b> | GPU <b>${esc(gpuTxt)}</b> | RAM <b>${hw.ram||"?"} GB</b> | <b>${disk}</b>${win11} -> tweak adattati automaticamente`;
    const adm = document.getElementById("adminLine");
    if (state.admin) { adm.className = "admin-line ok"; adm.textContent = "Amministratore: SI - tutte le ottimizzazioni disponibili."; }
    else { adm.className = "admin-line no"; adm.textContent = "Amministratore: NO - alcune opzioni non verranno applicate."; }
    document.getElementById("backupBadge").textContent = `Backup: ${state.backup} modifiche reversibili`;
    renderBackupPanel();
  }

  // Populate the backup dropdown with the names of the tweaks currently reversible.
  function renderBackupPanel() {
    const badge = document.getElementById("backupBadge");
    const list = document.getElementById("backupList");
    if (!list) return;
    const ids = Array.isArray(state.backup_ids) ? state.backup_ids : [];
    // ID -> friendly name via existing tweaks catalog.
    const items = ids.map(id => {
      const tw = state.tweaks.find(t => t.id === id);
      return { id, name: tw ? tw.name : id };
    });
    list.innerHTML = "";
    if (items.length === 0) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Nessuna modifica applicata ancora.";
      list.appendChild(li);
      badge.classList.add("disabled");
    } else {
      badge.classList.remove("disabled");
      for (const it of items) {
        const li = document.createElement("li");
        li.setAttribute("data-testid", `backup-item-${it.id}`);
        li.textContent = it.name;
        list.appendChild(li);
      }
    }
  }

  function toggleBackupPanel(force) {
    const panel = document.getElementById("backupPanel");
    if (!panel) return;
    const willOpen = typeof force === "boolean" ? force : panel.hasAttribute("hidden");
    if (willOpen) panel.removeAttribute("hidden");
    else panel.setAttribute("hidden", "");
  }

  function applyPreset(key) {
    document.querySelectorAll(".preset-btn").forEach(b => b.classList.toggle("active", b.dataset.preset === key));
    selected.clear();
    if (key === "none") { renderCards(); updateSelCount(); return; }
    const list = key === "complete"
      ? state.tweaks.filter(t => !t.fit.skip && !isApplied(t)).map(t => t.id)
      : (state.presets[key] || []).filter(id => {
          const t = state.tweaks.find(x => x.id === id);
          return t && !t.fit.skip && !isApplied(t);
        });
    list.forEach(id => selected.add(id));
    renderCards(); updateSelCount();
  }

  function pollLog() {
    fetch(`/api/log?tk=${encodeURIComponent(TOKEN)}&since=${logSince}`)
      .then(r => r.json())
      .then(d => {
        if (d.logs && d.logs.length) {
          const el = document.getElementById("log");
          d.logs.forEach(l => {
            const div = document.createElement("div");
            div.innerHTML = `<span class="ts">${l.ts}</span>${esc(l.msg)}`;
            el.appendChild(div);
          });
          el.scrollTop = el.scrollHeight;
          logSince = d.total;
        }
        if (typeof d.applying === "boolean") setApplying(d.applying);
      }).catch(()=>{});
  }
  function setApplying(v) {
    applying = v;
    document.getElementById("applyBtn").disabled = v;
    document.getElementById("restoreBtn").disabled = v;
  }

  let _stateRetries = 0;
  async function refreshState(showToast) {
    let d;
    try {
      d = await api("/api/state");
      if (!d || !Array.isArray(d.tweaks)) throw new Error("payload /api/state non valido");
    } catch (e) {
      reportClientError("refreshState: " + (e && e.message || e));
      if (_stateRetries++ < 6) setTimeout(() => refreshState(showToast), 2500);
      return;
    }
    _stateRetries = 0;
    // Normalizza il payload: ConvertTo-Json (PS 5.1) puo' produrre scalari al posto
    // di array (1 elemento) o campi mancanti. Il render non deve MAI rompersi per
    // un dato inatteso (bug storico: griglia vuota all'avvio finche' non si
    // cliccava un filtro).
    state.tweaks = d.tweaks.filter(t => t && typeof t === "object").map(t => {
      if (!t.fit || typeof t.fit !== "object") t.fit = { ok: true, warn: false, note: false, skip: false, hint: "" };
      if (typeof t.state !== "string") t.state = t.state == null ? "n/d" : String(t.state);
      return t;
    });
    state.hw = d.hw || {}; state.admin = !!d.admin;
    state.backup = d.backup || 0;
    state.backup_ids = Array.isArray(d.backup_ids) ? d.backup_ids : (d.backup_ids ? [d.backup_ids] : []);
    state.presets = d.presets || {};
    state.revertable = Array.isArray(d.revertable) ? d.revertable : (d.revertable ? [d.revertable] : []);
    state.agent = d.agent || {};
    safeRender("renderHeader", renderHeader);
    safeRender("renderTabs", renderTabs);
    safeRender("renderCards", renderCards);
    safeRender("renderProgressRing", renderProgressRing);
    safeRender("updateSummaryStrip", updateSummaryStrip);
    safeRender("renderUpdateBanner", renderUpdateBanner);
    if (showToast) toast("\u21bb Aggiornato", "ok");
  }

  async function applySelected() {
    if (!selected.size) { toast("Seleziona almeno un tweak"); return; }
    setApplying(true);
    const bench = document.getElementById("benchToggle").checked;
    const appliedIds = Array.from(selected);
    const picks = state.tweaks.filter(t => selected.has(t.id));
    const rebootCount = picks.filter(needsReboot).length;
    const d = await api("/api/apply", { method: "POST", headers:{"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ ids: appliedIds, benchmark: bench }) });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = d.backup || state.backup; if (d.backup_ids) state.backup_ids = d.backup_ids; if (d.revertable) state.revertable = d.revertable; renderHeader(); renderCards(); renderProgressRing(); }
    selected.clear();
    updateSummaryStrip();
    setApplying(false);
    // K. Big toast post-apply
    appliedIds.forEach(id => {
      const c = document.querySelector(`.card[data-id="${id}"]`);
      if (c) { c.classList.add("just-applied"); setTimeout(() => c.classList.remove("just-applied"), 1000); }
    });
    const level = rebootCount > 0 ? "warn" : null;
    const parts = [`<b>${appliedIds.length}</b> tweak applicati`];
    if (rebootCount > 0) parts.push(`<b>${rebootCount}</b> richiede/richiedono riavvio`);
    bigToast({
      level,
      title: rebootCount > 0 ? "\u26a0 Applicati · Riavvio consigliato" : "\u2713 Ottimizzazioni applicate",
      body: parts.join(" \u00b7 ") + " \u00b7 Backup salvato",
      actions: rebootCount > 0 ? [
        { label: "Ricorda dopo", onClick: () => {} },
        { label: "Riavvia ora", primary: true, onClick: () => api("/api/reboot", { method: "POST", headers:{"X-FF-Token":TOKEN}}) },
      ] : [{ label: "OK", primary: true, onClick: () => {} }],
    });
  }
  async function applyOne(id) {
    setApplying(true);
    const t = state.tweaks.find(x => x.id === id);
    const d = await api("/api/apply-one", { method: "POST", headers:{"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ id }) });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = d.backup || state.backup; if (d.backup_ids) state.backup_ids = d.backup_ids; if (d.revertable) state.revertable = d.revertable; renderHeader(); renderCards(); renderProgressRing(); }
    setApplying(false);
    // Pulse animation on the just-applied card
    const c = document.querySelector(`.card[data-id="${id}"]`);
    if (c) { c.classList.add("just-applied"); setTimeout(() => c.classList.remove("just-applied"), 1000); }
    if (t && needsReboot(t)) {
      bigToast({
        level: "warn",
        title: "\u26a0 Applicato · Riavvio consigliato",
        body: `<b>${esc(t.name)}</b> richiede un riavvio per essere pienamente attivo.`,
        actions: [
          { label: "Pi\u00f9 tardi", onClick: () => {} },
          { label: "Riavvia ora", primary: true, onClick: () => api("/api/reboot", { method: "POST", headers:{"X-FF-Token":TOKEN}}) },
        ],
      });
    } else {
      toast("\u2713 Applicato", "ok");
    }
  }
  async function doRestore() {
    if (!confirm("Ripristinare TUTTE le modifiche dal backup?")) return;
    setApplying(true);
    const d = await api("/api/restore", { method: "POST", headers:{"X-FF-Token":TOKEN} });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = 0; state.backup_ids = []; state.revertable = []; renderHeader(); renderCards(); renderProgressRing(); }
    setApplying(false);
    toast("\u21a9 Ripristinato", "ok");
  }

  // ===== v0.7.7 — Revert singolo tweak =====
  async function revertOne(id) {
    const t = state.tweaks.find(x => x.id === id);
    if (!confirm(`Ripristinare "${t ? t.name : id}" al valore precedente?`)) return;
    setApplying(true);
    const d = await api("/api/restore-one", { method: "POST", headers:{"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ id }) });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = d.backup || 0; state.backup_ids = d.backup_ids || []; state.revertable = d.revertable || []; renderHeader(); renderTabs(); renderCards(); renderProgressRing(); }
    setApplying(false);
    toast("\u21a9 Tweak ripristinato", "ok");
  }

  // ===== v0.7.7 — Monitor Live locale =====
  const MON_METRICS = [
    { k: "cpu_util", label: "CPU", unit: "%", max: 100 },
    { k: "cpu_temp", label: "CPU Temp", unit: "\u00b0C", temp: true },
    { k: "gpu_util", label: "GPU", unit: "%", max: 100 },
    { k: "gpu_temp", label: "GPU Temp", unit: "\u00b0C", temp: true },
    { k: "ram_used_pct", label: "RAM", unit: "%", max: 100 },
    { k: "vram_used_pct", label: "VRAM", unit: "%", max: 100 },
    { k: "gpu_clock", label: "GPU Clock", unit: " MHz" },
    { k: "gpu_power", label: "GPU Power", unit: " W" },
  ];
  let monHist = {}; let monTimer = 0; let monBusy = false; let monFirst = true;
  function startMonitor() { if (!monTimer) { monPoll(); monTimer = setInterval(monPoll, 3000); } }
  function stopMonitor() { if (monTimer) { clearInterval(monTimer); monTimer = 0; } }
  async function monPoll() {
    if (activeCat !== "monitor") { stopMonitor(); return; }
    if (monBusy) return;
    monBusy = true;
    try {
      const s = await api("/api/telemetry-local");
      MON_METRICS.forEach(m => {
        if (typeof s[m.k] === "number") {
          (monHist[m.k] = monHist[m.k] || []).push(s[m.k]);
          if (monHist[m.k].length > 40) monHist[m.k].shift();
        }
      });
      monFirst = false;
      if (activeCat === "monitor") renderMonitorTiles();
    } catch (e) {}
    monBusy = false;
  }
  function sparkline(vals, color) {
    if (!vals || vals.length < 2) return "";
    const w = 150, h = 36;
    const mn = Math.min(...vals), mx = Math.max(...vals);
    const rng = (mx - mn) || 1;
    const pts = vals.map((v, i) => `${(i / (vals.length - 1) * w).toFixed(1)},${(h - 3 - ((v - mn) / rng) * (h - 6)).toFixed(1)}`).join(" ");
    return `<svg class="mon-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
  }
  function monColor(m, v) {
    if (v == null) return "var(--dim)";
    if (m.temp) return v >= 85 ? "var(--danger)" : v >= 72 ? "var(--warn)" : "var(--ok)";
    if (m.max) return v >= 92 ? "var(--danger)" : v >= 75 ? "var(--warn)" : "var(--info)";
    return "var(--info)";
  }
  function renderMonitorTab(el) {
    el.innerHTML = `
      <div class="mon-head">
        <div>
          <div class="mon-title">// MONITOR LIVE</div>
          <div class="mon-sub">Telemetria locale in tempo reale, aggiornata ogni 3 secondi. Attiva <b>Sync Cloud</b> in alto a destra per inviarla anche al Command Center di FrameForge.</div>
        </div>
      </div>
      <div class="mon-grid" id="monGrid" data-testid="monitor-grid"></div>`;
    renderMonitorTiles();
    startMonitor();
  }
  function renderMonitorTiles() {
    const grid = document.getElementById("monGrid");
    if (!grid) return;
    grid.innerHTML = MON_METRICS.map(m => {
      const hist = monHist[m.k] || [];
      const v = hist.length ? hist[hist.length - 1] : null;
      const col = monColor(m, v);
      const valTxt = v == null ? (monFirst ? "..." : "n/d") : `${v}<span class="mon-unit">${m.unit}</span>`;
      return `<div class="mon-tile" data-testid="mon-${m.k}">
        <div class="mon-label">${m.label}</div>
        <div class="mon-value" style="color:${col}">${valTxt}</div>
        ${sparkline(hist, col)}
      </div>`;
    }).join("");
  }

  // ===== v0.7.7 — Bloatware tab =====
  let bloat = null; let bloatSel = new Set(); let bloatBusy = false;
  async function loadBloat() {
    if (activeCat === "bloatware") document.getElementById("cards").innerHTML = `<div class="empty">Scansione app installate in corso...</div>`;
    try {
      const d = await api("/api/bloatware");
      bloat = { apps: d.apps || [] };
    } catch (e) { bloat = { apps: [], err: true }; }
    bloatSel = new Set();
    renderTabs();
    if (activeCat === "bloatware") renderCards();
  }
  function updateBloatBtn() {
    const b = document.getElementById("bloatRemoveBtn");
    if (b) { b.disabled = !bloatSel.size || bloatBusy; b.textContent = bloatSel.size ? `Rimuovi ${bloatSel.size} selezionate` : "Rimuovi selezionate"; }
  }
  function renderBloatwareTab(el) {
    if (!bloat) { el.innerHTML = `<div class="empty">Scansione app installate in corso...</div>`; return; }
    const apps = bloat.apps || [];
    if (bloat.err) { el.innerHTML = `<div class="empty">Errore durante la scansione. Riapri la tab per riprovare.</div>`; bloat = null; return; }
    if (!apps.length) { el.innerHTML = `<div class="empty">&#10003; Nessun bloatware rilevato: il tuo sistema e gia pulito.</div>`; return; }
    const rows = apps.map(a => `
      <label class="bloat-row${bloatSel.has(a.name) ? " selected" : ""}" data-testid="bloat-${esc(a.name)}">
        <input type="checkbox" class="cb bloat-cb" data-name="${esc(a.name)}" ${bloatSel.has(a.name) ? "checked" : ""} />
        <div class="bloat-info">
          <div class="bloat-name">${esc(a.name)}</div>
          <div class="bloat-meta">${a.curated ? `<span class="bloat-badge curated">lista curata</span>` : `<span class="bloat-badge">auto-rilevata</span>`}${a.size_mb ? ` <span>${a.size_mb} MB</span>` : ""}${a.version ? ` <span>v${esc(a.version)}</span>` : ""}</div>
        </div>
      </label>`).join("");
    el.innerHTML = `
      <div class="bloat-head">
        <div>
          <div class="mon-title">// BLOATWARE TROVATO: ${apps.length} APP</div>
          <div class="mon-sub">App preinstallate e promozionali rimovibili in sicurezza, tutte reinstallabili dal Microsoft Store. Store, Calculator, Photos e i runtime di sistema sono protetti e non compaiono mai in questa lista.</div>
        </div>
        <div class="bloat-actions">
          <button class="chip" id="bloatSelAll" data-testid="bloat-select-all">Seleziona tutte</button>
          <button class="btn-danger" id="bloatRemoveBtn" data-testid="bloat-remove-btn" disabled>Rimuovi selezionate</button>
        </div>
      </div>
      <div class="bloat-list">${rows}</div>`;
    el.querySelectorAll(".bloat-cb").forEach(cb => cb.onchange = () => {
      const n = cb.dataset.name;
      if (cb.checked) bloatSel.add(n); else bloatSel.delete(n);
      const row = cb.closest(".bloat-row");
      if (row) row.classList.toggle("selected", cb.checked);
      updateBloatBtn();
    });
    const selAll = document.getElementById("bloatSelAll");
    if (selAll) selAll.onclick = () => {
      if (bloatSel.size === apps.length) bloatSel.clear();
      else apps.forEach(a => bloatSel.add(a.name));
      el.querySelectorAll(".bloat-cb").forEach(cb => {
        cb.checked = bloatSel.has(cb.dataset.name);
        const row = cb.closest(".bloat-row");
        if (row) row.classList.toggle("selected", cb.checked);
      });
      updateBloatBtn();
    };
    const rmBtn = document.getElementById("bloatRemoveBtn");
    if (rmBtn) rmBtn.onclick = removeBloat;
    updateBloatBtn();
  }
  async function removeBloat() {
    if (!bloatSel.size || bloatBusy) return;
    if (!confirm(`Rimuovere ${bloatSel.size} app? Potrai reinstallarle dal Microsoft Store in qualsiasi momento.`)) return;
    bloatBusy = true;
    const btn = document.getElementById("bloatRemoveBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Rimozione in corso..."; }
    try {
      const d = await api("/api/bloatware/remove", { method: "POST", headers: {"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ names: Array.from(bloatSel) }) });
      bloat = { apps: (d && d.apps) || [] };
      bloatSel = new Set();
      bigToast({
        title: "\u2713 Bloatware rimosso",
        body: `<b>${(d && d.removed) || 0}</b> app rimosse dal sistema. Reinstallabili in qualsiasi momento dal Microsoft Store.`,
        actions: [{ label: "OK", primary: true, onClick: () => {} }],
      });
    } catch (e) { toast("Errore durante la rimozione", "err"); }
    bloatBusy = false;
    renderTabs();
    if (activeCat === "bloatware") renderCards();
  }

  // ===== v0.7.7 — Banner aggiornamento agent =====
  function verLt(a, b) {
    if (!b) return false;
    if (!a) return true;
    const pa = String(a).split(".").map(Number), pb = String(b).split(".").map(Number);
    for (let i = 0; i < 3; i++) {
      const x = pa[i] || 0, y = pb[i] || 0;
      if (x < y) return true;
      if (x > y) return false;
    }
    return false;
  }
  function renderUpdateBanner() {
    const el = document.getElementById("updateBanner");
    if (!el) return;
    const ag = state.agent || {};
    const latest = (ag.latest && ag.latest.indexOf("__") < 0) ? ag.latest : "";
    const installed = (ag.installed && ag.installed.indexOf("__") < 0) ? ag.installed : "";
    const show = latest && verLt(installed, latest) && !sessionStorage.getItem("ff_upd_dismiss");
    if (!show) { el.setAttribute("hidden", ""); return; }
    const cur = installed ? `hai la v${esc(installed)}` : "la tua versione e precedente alla 0.7.8";
    el.innerHTML = `
      <span class="upd-icon">&#8593;</span>
      <span class="upd-text"><b>FrameForge Agent v${esc(latest)}</b> disponibile (${cur}): auto-update, zero-flash console e nuovi tweak.</span>
      <a class="upd-btn" href="${esc(ag.dl || "#")}" target="_blank" rel="noopener" data-testid="update-download-btn">Scarica v${esc(latest)}</a>
      <button class="upd-dismiss" id="updDismiss" title="Nascondi per questa sessione" data-testid="update-dismiss-btn">&times;</button>`;
    el.removeAttribute("hidden");
    const d = document.getElementById("updDismiss");
    if (d) d.onclick = () => { sessionStorage.setItem("ff_upd_dismiss", "1"); el.setAttribute("hidden", ""); };
  }

  // events
  document.querySelectorAll(".preset-btn").forEach(b => {
    b.onclick = () => applyPreset(b.dataset.preset);
    // C. Preset hover preview
    b.addEventListener("mouseenter", () => renderPresetPreview(b.dataset.preset));
    b.addEventListener("mouseleave", clearPresetPreview);
    b.addEventListener("focus", () => renderPresetPreview(b.dataset.preset));
    b.addEventListener("blur", clearPresetPreview);
  });
  document.getElementById("applyBtn").onclick = applySelected;
  document.getElementById("restoreBtn").onclick = doRestore;
  document.getElementById("searchBox").oninput = e => { searchQ = e.target.value; renderCards(); };

  // A. Density toggle (Compact/Detailed)
  const _densityBtn = document.getElementById("densityToggle");
  const _densityLabel = document.getElementById("densityLabel");
  function _refreshDensityUI() {
    if (!_densityBtn) return;
    _densityBtn.classList.toggle("active", density === "compact");
    if (_densityLabel) _densityLabel.textContent = density === "compact" ? "Compatto" : "Dettagliato";
  }
  _refreshDensityUI();
  if (_densityBtn) _densityBtn.onclick = () => {
    density = (density === "compact") ? "detailed" : "compact";
    localStorage.setItem("ff_density", density);
    expanded.clear();
    _refreshDensityUI();
    renderCards();
  };

  // Cambia account: cancella token.dat + chiude GUI
  const _logoutBtn = document.getElementById("logoutBtn");
  if (_logoutBtn) _logoutBtn.onclick = async () => {
    if (!confirm("Rimuovere il token FrameForge da questo PC?\n\nAl prossimo avvio dell'agent verra' richiesto un nuovo token.\nUsalo se stai passando a un altro account.")) return;
    _logoutBtn.disabled = true;
    try {
      const r = await api("/api/logout", { method: "POST", headers:{"X-FF-Token":TOKEN} });
      toast(r && r.removed ? "\u2713 Token rimosso · chiusura in corso..." : "Chiusura in corso...", "ok");
      setTimeout(() => { try { window.close(); } catch(_){} }, 900);
    } catch (e) {
      _logoutBtn.disabled = false;
      toast("Errore: " + (e && e.message || e), "err");
    }
  };

  // H. Filter chips
  document.querySelectorAll("#filterChips .chip").forEach(chip => {
    chip.onclick = () => {
      const k = chip.dataset.filter;
      if (activeFilters.has(k)) activeFilters.delete(k); else activeFilters.add(k);
      chip.classList.toggle("active", activeFilters.has(k));
      renderCards();
    };
  });

  // I. Sort
  const _sortSel = document.getElementById("sortSelect");
  if (_sortSel) _sortSel.onchange = () => { sortMode = _sortSel.value; renderCards(); };

  // G. Keyboard Ctrl+K -> focus search; D -> toggle density
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      const s = document.getElementById("searchBox");
      if (s) { s.focus(); s.select(); }
    } else if (!e.ctrlKey && !e.metaKey && !e.altKey && (e.key === "d" || e.key === "D")) {
      const tag = (e.target && e.target.tagName || "").toLowerCase();
      if (tag !== "input" && tag !== "textarea" && tag !== "select") {
        if (_densityBtn) _densityBtn.click();
      }
    }
  });

  // Live Sync toggle: streams telemetry to cloud when ON.
  const _liveToggle = document.getElementById("liveSyncToggle");
  if (_liveToggle) {
    _liveToggle.addEventListener("change", async () => {
      try {
        const d = await api("/api/live-sync", { method: "POST", headers: {"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ enabled: _liveToggle.checked }) });
        if (d && d.ok) toast(d.enabled ? "Sync Cloud attivo · dati in streaming" : "Sync Cloud disattivato", d.enabled ? "ok" : null);
      } catch { _liveToggle.checked = !_liveToggle.checked; toast("Errore attivazione sync", "err"); }
    });
  }

  // Backup badge toggle: open panel with reversible tweaks list.
  const _backupBadge = document.getElementById("backupBadge");
  if (_backupBadge) {
    _backupBadge.addEventListener("click", () => toggleBackupPanel());
    _backupBadge.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleBackupPanel(); }
    });
    document.addEventListener("click", (e) => {
      const panel = document.getElementById("backupPanel");
      if (!panel || panel.hasAttribute("hidden")) return;
      if (!panel.contains(e.target) && e.target !== _backupBadge) toggleBackupPanel(false);
    });
  }
  window.addEventListener("beforeunload", () => {
    try { navigator.sendBeacon(`/api/close?tk=${encodeURIComponent(TOKEN)}`, ""); } catch(e){}
  });

  // -------- Mobile Handoff (Continua sul Telefono) --------
  const mh = {
    btn: document.getElementById("mobileHandoffBtn"),
    overlay: document.getElementById("mobileHandoffOverlay"),
    closeBtn: document.getElementById("mhClose"),
    regenBtn: document.getElementById("mhRegen"),
    loading: document.getElementById("mhLoading"),
    error: document.getElementById("mhError"),
    qr: document.getElementById("mhQr"),
    consumed: document.getElementById("mhConsumed"),
    deviceLabel: document.getElementById("mhDeviceLabel"),
    footer: document.getElementById("mhFooter"),
    time: document.getElementById("mhTime"),
    token: "",
    remaining: 0,
    tickId: 0,
    pollId: 0,
    open: false,
  };
  function mhSetVis(node, visible) {
    if (!node) return;
    if (visible) node.removeAttribute("hidden"); else node.setAttribute("hidden", "");
  }
  function mhStopTimers() {
    if (mh.tickId) { clearInterval(mh.tickId); mh.tickId = 0; }
    if (mh.pollId) { clearInterval(mh.pollId); mh.pollId = 0; }
  }
  function mhReset() {
    mhStopTimers();
    mh.token = ""; mh.remaining = 0;
    mhSetVis(mh.loading, true);
    mhSetVis(mh.error, false); mh.error.textContent = "";
    mhSetVis(mh.qr, false); mh.qr.innerHTML = "";
    mhSetVis(mh.consumed, false);
    mhSetVis(mh.footer, false);
  }
  function mhOpen() {
    mh.open = true; mhSetVis(mh.overlay, true); mhReset(); mhGenerate();
  }
  function mhClose() {
    mh.open = false; mhStopTimers(); mhSetVis(mh.overlay, false); mhReset();
  }
  function mhFmt(sec) {
    const m = String(Math.floor(sec/60)).padStart(2,"0");
    const s = String(sec%60).padStart(2,"0");
    return m+":"+s;
  }
  async function mhGenerate() {
    mhReset();
    try {
      const d = await api("/api/mobile-handoff/generate", { method: "POST", headers: {"X-FF-Token": TOKEN} });
      if (!d || d.err) throw new Error(d && d.err ? d.err : "unknown");
      mh.token = d.token;
      mh.remaining = d.expires_in_seconds || 300;
      // Fetch QR SVG (locally proxied to cloud) and inject.
      const qrResp = await fetch(`/api/mobile-handoff/qr?tk=${encodeURIComponent(TOKEN)}&token=${encodeURIComponent(mh.token)}`);
      if (!qrResp.ok) throw new Error("qr_fetch_failed");
      const svg = await qrResp.text();
      mhSetVis(mh.loading, false);
      mh.qr.innerHTML = svg;
      mhSetVis(mh.qr, true);
      mhSetVis(mh.footer, true);
      mh.time.textContent = mhFmt(mh.remaining);
      mh.time.classList.remove("low");
      mh.tickId = setInterval(() => {
        mh.remaining = Math.max(0, mh.remaining - 1);
        mh.time.textContent = mhFmt(mh.remaining);
        if (mh.remaining < 60) mh.time.classList.add("low");
        if (mh.remaining <= 0) { mhStopTimers(); mhShowError("Il QR e scaduto. Rigenera."); }
      }, 1000);
      mh.pollId = setInterval(mhPoll, 2000);
    } catch (e) {
      mhShowError((e && e.message === "rate_limited") ? "Troppi QR generati. Riprova tra un'ora." : "Errore nella generazione del QR");
    }
  }
  function mhShowError(msg) {
    mhStopTimers();
    mhSetVis(mh.loading, false);
    mhSetVis(mh.qr, false);
    mhSetVis(mh.footer, false);
    mh.error.textContent = msg;
    mhSetVis(mh.error, true);
  }
  async function mhPoll() {
    if (!mh.token || !mh.open) return;
    try {
      const d = await api(`/api/mobile-handoff/status?magic=${encodeURIComponent(mh.token)}`);
      if (!d || d.err) return;
      if (d.used) {
        mhStopTimers();
        const label = d.device_label || "Dispositivo";
        mh.deviceLabel.textContent = label + " ha effettuato l'accesso";
        mhSetVis(mh.qr, false);
        mhSetVis(mh.footer, false);
        mhSetVis(mh.error, false);
        mhSetVis(mh.consumed, true);
        toast("Nuovo device connesso: " + label, "ok");
        // Also trigger Windows native toast via local endpoint.
        try { fetch(`/api/mobile-handoff/notify?tk=${encodeURIComponent(TOKEN)}&device=${encodeURIComponent(label)}`, { method: "POST" }); } catch(e){}
        setTimeout(() => { if (mh.open) mhClose(); }, 2600);
      } else if (d.expired) {
        mhStopTimers();
        mhShowError("Il QR e scaduto. Rigenera.");
      }
    } catch(e) {}
  }
  if (mh.btn)      mh.btn.addEventListener("click", mhOpen);
  if (mh.closeBtn) mh.closeBtn.addEventListener("click", mhClose);
  if (mh.regenBtn) mh.regenBtn.addEventListener("click", mhGenerate);
  if (mh.overlay)  mh.overlay.addEventListener("click", (e) => { if (e.target === mh.overlay) mhClose(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && mh.open) mhClose(); });

  refreshState();
  setInterval(pollLog, 400);
})();
