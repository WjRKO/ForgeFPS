/**
 * I nomi dei campi sorvegliati da system_changes.py, nelle due lingue.
 *
 * Il backend manda `kind` (`gpu_driver_version`, `startup_added`, ...) e una
 * `label` italiana; il frontend traduce. Stava dentro WhatChangedCard, che era
 * l'unico a mostrarli: ora li nomina anche il toast del sync, e due mappe della
 * stessa cosa in due file e' il modo in cui iniziano a divergere.
 */
const LABELS = {
  it: {
    gpu_driver_version: "Driver GPU", ram_speed_mhz: "Velocità RAM", rebar_status: "Resizable BAR",
    cpu: "CPU", gpu: "GPU", ram: "RAM installata", ram_modules: "Moduli RAM",
    os_build: "Build di Windows", bios: "BIOS", motherboard: "Scheda madre",
    refresh_hz: "Refresh del monitor", resolution: "Risoluzione",
    gpu_secondary: "GPU secondaria", cpu_socket: "Socket CPU",
    startup_added: "Nuovi programmi all'avvio", startup_removed: "Programmi all'avvio rimossi",
  },
  en: {
    gpu_driver_version: "GPU driver", ram_speed_mhz: "RAM speed", rebar_status: "Resizable BAR",
    cpu: "CPU", gpu: "GPU", ram: "Installed RAM", ram_modules: "RAM modules",
    os_build: "Windows build", bios: "BIOS", motherboard: "Motherboard",
    refresh_hz: "Monitor refresh", resolution: "Resolution",
    gpu_secondary: "Secondary GPU", cpu_socket: "CPU socket",
    startup_added: "New startup programs", startup_removed: "Removed startup programs",
  },
};

export function changeLabel(kind, lang) {
  const mappa = LABELS[lang] || LABELS.it;
  return mappa[kind] || kind;
}

/**
 * Un cambiamento in una riga sola, per il toast: "Driver GPU: 566.36 → 572.16",
 * oppure "Nuovi programmi all'avvio: 2".
 */
export function changeSummary(change, lang) {
  const label = changeLabel(change.kind, lang);
  if (change.kind === "startup_added" || change.kind === "startup_removed") {
    return `${label}: ${change.count}`;
  }
  return `${label}: ${change.from} → ${change.to}`;
}

export default LABELS;
