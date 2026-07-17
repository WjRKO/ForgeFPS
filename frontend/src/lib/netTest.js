// Client-side network quality / bufferbloat test using Cloudflare's public speed endpoints.
// No backend, no account. Measures idle latency vs latency under download load.
// All fetches are tied to an AbortController so the test stops cleanly on timeout/unmount.
const DOWN = (bytes) => `https://speed.cloudflare.com/__down?bytes=${bytes}&r=${Math.random()}`;

async function ping(masterSignal, timeout = 3000) {
  if (masterSignal?.aborted) return null;
  const ctrl = new AbortController();
  const onAbort = () => ctrl.abort();
  masterSignal?.addEventListener("abort", onAbort);
  const to = setTimeout(() => ctrl.abort(), timeout);
  const t0 = performance.now();
  try {
    await fetch(DOWN(1), { cache: "no-store", signal: ctrl.signal });
    return performance.now() - t0;
  } catch {
    return null;
  } finally {
    clearTimeout(to);
    masterSignal?.removeEventListener("abort", onAbort);
  }
}

function median(arr) {
  const a = arr.filter((x) => x != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

async function idleLatency(signal, samples = 6) {
  const res = [];
  for (let i = 0; i < samples; i++) {
    if (signal?.aborted) break;
    res.push(await ping(signal));
  }
  return median(res);
}

async function loadedLatency(signal, durationMs = 4000, streams = 3) {
  let bytes = 0;
  const start = performance.now();
  const downloads = [];
  for (let i = 0; i < streams; i++) {
    downloads.push(
      (async () => {
        try {
          const resp = await fetch(DOWN(25000000), { cache: "no-store", signal });
          const reader = resp.body.getReader();
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            bytes += value.length;
            if (performance.now() - start > durationMs || signal?.aborted) break;
          }
          try { await reader.cancel(); } catch { /* ignore */ }
        } catch { /* aborted or blocked */ }
      })()
    );
  }
  const lat = [];
  while (performance.now() - start < durationMs && !signal?.aborted) {
    const p = await ping(signal, 3000);
    if (p != null) lat.push(p);
  }
  await Promise.allSettled(downloads);
  const elapsed = (performance.now() - start) / 1000;
  const mbps = elapsed > 0 && bytes > 0 ? (bytes * 8) / elapsed / 1e6 : null;
  return { median: median(lat), max: lat.length ? Math.max(...lat) : null, mbps };
}

export function gradeBufferbloat(increaseMs) {
  if (increaseMs == null) return null;
  if (increaseMs <= 5) return "A+";
  if (increaseMs <= 30) return "A";
  if (increaseMs <= 60) return "B";
  if (increaseMs <= 200) return "C";
  if (increaseMs <= 400) return "D";
  return "F";
}

async function _runNetTest(signal) {
  const idle = await idleLatency(signal);
  if (idle == null || signal?.aborted) return null;
  const loaded = await loadedLatency(signal);
  const inc = loaded.max != null ? Math.max(0, loaded.max - idle) : null;
  return {
    idleMs: Math.round(idle),
    loadedMs: loaded.max != null ? Math.round(loaded.max) : null,
    bufferbloatMs: inc != null ? Math.round(inc) : null,
    grade: gradeBufferbloat(inc),
    downloadMbps: loaded.mbps != null ? Math.round(loaded.mbps) : null,
  };
}

// Returns { idleMs, loadedMs, bufferbloatMs, grade, downloadMbps } or null.
// Aborts all in-flight fetches on timeout (maxMs) or when externalSignal aborts.
export function runNetTest(maxMs = 15000, externalSignal) {
  if (externalSignal?.aborted) return Promise.resolve(null);
  const ctrl = new AbortController();
  const onAbort = () => ctrl.abort();
  externalSignal?.addEventListener("abort", onAbort);
  const timer = setTimeout(() => ctrl.abort(), maxMs);
  return _runNetTest(ctrl.signal)
    .catch(() => null)
    .finally(() => {
      clearTimeout(timer);
      ctrl.abort();
      externalSignal?.removeEventListener("abort", onAbort);
    });
}
