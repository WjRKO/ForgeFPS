// Best-effort hardware detection from the browser (no download required).
// Not as precise as the Desktop Agent, but enough to power advice/build/upgrade/FPS.

function detectGPU() {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) return "";
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    if (!dbg) return "";
    let r = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || "";
    // Chrome ANGLE format: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, ...)"
    const m = r.match(/ANGLE \(([^,]+),\s*([^,]+?)(?:\s+Direct3D|\s+\(|\s+vs_|\s+Vulkan|,|\))/i);
    if (m) r = m[2];
    return r.replace(/Direct3D.*$/i, "").replace(/\(.*$/, "").trim();
  } catch {
    return "";
  }
}

function detectOS() {
  const ua = navigator.userAgent || "";
  if (/Windows NT 10/.test(ua)) return "Windows 10/11";
  if (/Windows/.test(ua)) return "Windows";
  if (/Mac OS X/.test(ua)) return "macOS";
  if (/Linux/.test(ua)) return "Linux";
  return "";
}

export function detectBrowserSpecs() {
  const dpr = window.devicePixelRatio || 1;
  const w = Math.round((window.screen?.width || 0) * dpr);
  const h = Math.round((window.screen?.height || 0) * dpr);
  const mem = navigator.deviceMemory;
  return {
    gpu: detectGPU(),
    cpu_threads: navigator.hardwareConcurrency ? String(navigator.hardwareConcurrency) : "",
    ram: mem ? `${mem >= 8 ? "≥8" : mem} GB` : "",
    os: detectOS(),
    resolution: w && h ? `${w}x${h}` : "",
  };
}
