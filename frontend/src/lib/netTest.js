// Client-side network quality / bufferbloat test using Cloudflare's public speed endpoints.
// No backend, no account. Measures idle latency vs latency under download load.
const DOWN = (bytes) => `https://speed.cloudflare.com/__down?bytes=${bytes}&r=${Math.random()}`;

async function ping(timeout = 4000) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), timeout);
  const t0 = performance.now();
  try {
    await fetch(DOWN(1), { cache: "no-store", signal: ctrl.signal });
    return performance.now() - t0;
  } catch {
    return null;
  } finally {
    clearTimeout(to);
  }
}

function median(arr) {
  const a = arr.filter((x) => x != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

async function idleLatency(samples = 6) {
  const res = [];
  for (let i = 0; i < samples; i++) res.push(await ping());
  return median(res);
}

async function loadedLatency(durationMs = 5000, streams = 4) {
  const ctrl = new AbortController();
  let bytes = 0;
  const start = performance.now();
  const downloads = [];
  for (let i = 0; i < streams; i++) {
    downloads.push(
      (async () => {
        try {
          const resp = await fetch(DOWN(50000000), { cache: "no-store", signal: ctrl.signal });
          const reader = resp.body.getReader();
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            bytes += value.length;
            if (performance.now() - start > durationMs) break;
          }
        } catch {
          /* aborted or blocked */
        }
      })()
    );
  }
  const lat = [];
  while (performance.now() - start < durationMs) {
    const p = await ping(3000);
    if (p != null) lat.push(p);
  }
  ctrl.abort();
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

// Returns { idleMs, loadedMs, bufferbloatMs, grade, downloadMbps } or null if the test can't run.
async function _runNetTest() {
  const idle = await idleLatency();
  if (idle == null) return null;
  const loaded = await loadedLatency();
  const inc = loaded.max != null ? Math.max(0, loaded.max - idle) : null;
  return {
    idleMs: Math.round(idle),
    loadedMs: loaded.max != null ? Math.round(loaded.max) : null,
    bufferbloatMs: inc != null ? Math.round(inc) : null,
    grade: gradeBufferbloat(inc),
    downloadMbps: loaded.mbps != null ? Math.round(loaded.mbps) : null,
  };
}

// Overall guard: on very slow/blocked links, resolve to null (graceful fallback) within maxMs.
export function runNetTest(maxMs = 15000) {
  return Promise.race([
    _runNetTest().catch(() => null),
    new Promise((resolve) => setTimeout(() => resolve(null), maxMs)),
  ]);
}
