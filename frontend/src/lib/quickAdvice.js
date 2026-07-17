// Rule-based, zero-cost recommendations derived from real browser-detected hardware
// and the client-side network test. No AI, no account required.

const gpuVendor = (gpu = "") => {
  const g = gpu.toLowerCase();
  if (/nvidia|geforce|rtx|gtx/.test(g)) return "nvidia";
  if (/amd|radeon|rx /.test(g)) return "amd";
  if (/intel|arc|iris|uhd/.test(g)) return "intel";
  return "";
};

export function buildAdvice(specs = {}, net = null, lang = "it") {
  const it = lang !== "en";
  const out = [];
  const vendor = gpuVendor(specs.gpu);
  const threads = parseInt(specs.cpu_threads, 10) || 0;
  const isWin = /win/i.test(specs.os || "");

  // GPU / latency
  if (vendor === "nvidia") {
    out.push(it
      ? { t: "Attiva NVIDIA Reflex e Low Latency", d: "GPU NVIDIA rilevata: Reflex On+Boost e 'Low Latency Ultra' riducono l'input lag nei giochi competitivi." }
      : { t: "Enable NVIDIA Reflex & Low Latency", d: "NVIDIA GPU detected: Reflex On+Boost and 'Low Latency Ultra' cut input lag in competitive games." });
  } else if (vendor === "amd") {
    out.push(it
      ? { t: "Attiva AMD Anti-Lag e cap FPS", d: "GPU AMD rilevata: Anti-Lag + limite FPS sotto il refresh riducono la latenza e stabilizzano i frame." }
      : { t: "Enable AMD Anti-Lag & FPS cap", d: "AMD GPU detected: Anti-Lag + an FPS cap below your refresh reduce latency and stabilize frames." });
  } else if (vendor === "intel") {
    out.push(it
      ? { t: "Aggiorna i driver Intel Arc/Iris", d: "GPU Intel rilevata: i driver recenti migliorano molto le prestazioni di gioco." }
      : { t: "Update Intel Arc/Iris drivers", d: "Intel GPU detected: recent drivers significantly improve gaming performance." });
  } else {
    out.push(it
      ? { t: "Aggiorna i driver GPU", d: "Driver grafici aggiornati = più FPS e meno stutter. FrameForge trova la versione giusta per te." }
      : { t: "Update your GPU drivers", d: "Up-to-date graphics drivers mean more FPS and less stutter. FrameForge finds the right version for you." });
  }

  // CPU / RAM
  if (threads && threads <= 8) {
    out.push(it
      ? { t: "Chiudi le app in background", d: `Rilevati ${threads} thread CPU: la modalità 'Prima del match' libera CPU/RAM chiudendo Chrome, Discord e overlay.` }
      : { t: "Close background apps", d: `${threads} CPU threads detected: 'Pre-Match' mode frees CPU/RAM by closing Chrome, Discord and overlays.` });
  }
  if (specs.ram && /(^| )([1-7]) ?GB|≥8/.test(specs.ram) === false && /GB/.test(specs.ram)) {
    // generic RAM tip when detected
    out.push(it
      ? { t: "Ottimizza la RAM", d: "Disattiva le app all'avvio e la memoria in background per liberare RAM durante il gioco." }
      : { t: "Optimize RAM usage", d: "Disable startup apps and background memory to free up RAM while gaming." });
  }

  // Power plan (always relevant on Windows)
  if (isWin || !specs.os) {
    out.push(it
      ? { t: "Piano energetico 'Ultimate Performance'", d: "Sblocca il piano nascosto di Windows: niente throttling di CPU/USB, latenza più bassa." }
      : { t: "'Ultimate Performance' power plan", d: "Unlock Windows' hidden plan: no CPU/USB throttling, lower latency." });
  }

  // Network / bufferbloat
  if (net && net.grade) {
    const bad = ["C", "D", "F"].includes(net.grade);
    if (bad) {
      out.push(it
        ? { t: `Bufferbloat elevato (voto ${net.grade})`, d: `La latenza sale di ~${net.bufferbloatMs}ms sotto carico. Attiva SQM/fq_codel sul router ed evita upload in background durante il gioco.` }
        : { t: `High bufferbloat (grade ${net.grade})`, d: `Latency rises ~${net.bufferbloatMs}ms under load. Enable SQM/fq_codel on your router and avoid background uploads while gaming.` });
    } else {
      out.push(it
        ? { t: `Rete stabile (voto ${net.grade})`, d: `Ottimo: solo +${net.bufferbloatMs}ms sotto carico. Usa Ethernet e server di gioco vicini per il ping migliore.` }
        : { t: `Stable network (grade ${net.grade})`, d: `Great: only +${net.bufferbloatMs}ms under load. Use Ethernet and nearby game servers for the best ping.` });
    }
  } else {
    out.push(it
      ? { t: "Testa la rete con l'agent", d: "Il test bufferbloat completo (download+upload) è disponibile collegando FrameForge al PC." }
      : { t: "Test your network with the agent", d: "The full bufferbloat test (download+upload) is available by connecting FrameForge to your PC." });
  }

  return out.slice(0, 5);
}
