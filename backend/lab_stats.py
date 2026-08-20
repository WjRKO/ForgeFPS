"""Motore statistico condiviso del Laboratorio (Welch t-test + Mann-Whitney esatto).

Pure Python (niente scipy): CDF t di Student via funzione beta incompleta
regolarizzata (continued fraction, Numerical Recipes). Riusato da test loop,
synergy pass (fase 2) e validazione finale.
"""
import math
from itertools import combinations


def mean(xs):
    return sum(xs) / len(xs)


def sample_var(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def cv(xs):
    """Coefficiente di variazione (std campionaria / media)."""
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    if m == 0:
        return 0.0
    return math.sqrt(sample_var(xs)) / abs(m)


def _betacf(a, b, x, max_iter=200, eps=3e-12):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Beta incompleta regolarizzata I_x(a,b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_bt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    bt = math.exp(ln_bt)
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def t_sf(t, df):
    """P(T > t) per t >= 0, distribuzione t di Student con df gradi di liberta'."""
    if df <= 0:
        return 0.5
    x = df / (df + t * t)
    return 0.5 * betainc(df / 2.0, 0.5, x)


def welch_t_test(a, b):
    """Welch t-test bilaterale su due campioni indipendenti. Ritorna dict o None."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    m1, m2 = mean(a), mean(b)
    v1, v2 = sample_var(a), sample_var(b)
    se2 = v1 / n1 + v2 / n2
    if se2 <= 0:
        # Varianza nulla in entrambi i gruppi: nessuna stima dell'errore, e
        # p = 0 sarebbe certezza assoluta da due manciate di numeri identici.
        # Si usa il p piu' piccolo che un test di permutazione possa produrre
        # con queste numerosita': 2 / C(n1+n2, n1), cioe' 0.1 su 3 contro 3.
        p = 1.0 if abs(m1 - m2) < 1e-12 else min(1.0, 2.0 / math.comb(n1 + n2, n1))
        return {"method": "welch_t_test", "t": None, "df": None,
                "degenerate": True, "p_value": round(p, 4)}
    t = (m1 - m2) / math.sqrt(se2)
    denom = 0.0
    if n1 > 1:
        denom += (v1 / n1) ** 2 / (n1 - 1)
    if n2 > 1:
        denom += (v2 / n2) ** 2 / (n2 - 1)
    df = se2 ** 2 / denom if denom > 0 else (n1 + n2 - 2)
    p = 2.0 * t_sf(abs(t), df)
    return {"method": "welch_t_test", "t": round(t, 3), "df": round(df, 2), "p_value": round(min(1.0, p), 4)}


def mann_whitney_exact(a, b):
    """Mann-Whitney U esatto (permutazioni complete) per campioni piccoli (n1+n2 <= 14)."""
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0 or n1 + n2 > 14:
        return None

    def u_stat(xs, ys):
        u = 0.0
        for x in xs:
            for y in ys:
                if x > y:
                    u += 1.0
                elif x == y:
                    u += 0.5
        return u

    combined = list(a) + list(b)
    u_obs = u_stat(a, b)
    mu = n1 * n2 / 2.0
    idx = list(range(len(combined)))
    total = 0
    extreme = 0
    for comb in combinations(idx, n1):
        cs = set(comb)
        xs = [combined[i] for i in comb]
        ys = [combined[i] for i in idx if i not in cs]
        u = u_stat(xs, ys)
        total += 1
        if abs(u - mu) >= abs(u_obs - mu) - 1e-12:
            extreme += 1
    return {"method": "mann_whitney_exact", "u": u_obs, "p_value": round(extreme / total, 4)}


def significance(a, b, alpha=None):
    n = min(len(a), len(b))
    if alpha is None:
        alpha = 0.10 if n < 5 else 0.05
    w = welch_t_test(a, b)
    mw = mann_whitney_exact(a, b)
    p = w["p_value"] if w else (mw["p_value"] if mw else 1.0)
    out = {
        "method": (w or mw or {}).get("method", "n/a"),
        "p_value": p,
        "alpha": alpha,
        "significant": bool(p < alpha),
    }
    if w:
        out["welch"] = w
    if mw:
        out["mann_whitney"] = mw
    return out


def t_ppf(q, df):
    """Quantile t di Student (q > 0.5) via bisezione su t_sf."""
    lo, hi = 0.0, 200.0
    target = 1.0 - q
    for _ in range(80):
        mid = (lo + hi) / 2
        if t_sf(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def welch_ci(a, b, conf=0.95):
    """IC di Welch sulla differenza delle medie (a - b). Ritorna (diff, lo, hi) o None."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    m1, m2 = mean(a), mean(b)
    v1, v2 = sample_var(a), sample_var(b)
    se2 = v1 / n1 + v2 / n2
    diff = m1 - m2
    if se2 <= 0:
        return (diff, diff, diff)
    denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    df = se2 ** 2 / denom if denom > 0 else (n1 + n2 - 2)
    tcrit = t_ppf(1 - (1 - conf) / 2, df)
    half = tcrit * math.sqrt(se2)
    return (diff, diff - half, diff + half)


def cohens_d(a, b):
    """Effect size (pooled). None se varianza nulla."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    sp2 = ((n1 - 1) * sample_var(a) + (n2 - 1) * sample_var(b)) / (n1 + n2 - 2)
    if sp2 <= 0:
        return None
    return round((mean(a) - mean(b)) / math.sqrt(sp2), 2)


def holm_adjust(p_values):
    """Correzione Holm-Bonferroni: lista p -> lista p aggiustati (stesso ordine)."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * p_values[i]
        running = max(running, val)
        adj[i] = round(min(1.0, running), 4)
    return adj


# --------------------------------------------------------------------------
# Statistica appaiata (schema A/B/A/B)
# --------------------------------------------------------------------------
# Il confronto a blocchi (3 run di baseline, poi 3 run col tweak) mette nel
# confronto tutto cio' che cambia nel frattempo: temperatura, scena di gioco,
# shader cache, stato del driver. Con 3 run per lato e CV per-run del 3-5%
# l'effetto minimo rilevabile e' del 7-12%: uno strumento che non puo' vedere
# la soglia dell'1% che il Lab dichiara di misurare.
#
# Alternando ON/OFF e analizzando le DIFFERENZE di ogni coppia, la deriva
# comune si cancella: la varianza che conta diventa quella dentro la coppia,
# molto piu' piccola di quella tra blocchi distanti minuti.


def paired_t_test(diffs):
    """t-test appaiato (one-sample sulle differenze). Ritorna dict o None.

    `diffs` sono le differenze ON-OFF di ogni coppia: gia' depurate dalla
    deriva comune ai due run della coppia.
    """
    n = len(diffs)
    if n < 2:
        return None
    m = mean(diffs)
    v = sample_var(diffs)
    if v <= 0:
        # Differenze tutte identiche: il t non esiste (divisione per zero) e
        # dichiarare p = 0 sarebbe certezza assoluta ricavata da n numeri
        # uguali. Quello che i dati sostengono davvero e' soltanto che le
        # differenze hanno tutte lo stesso segno: il p esatto del test dei
        # segni, 2^-(n-1), che con tre coppie vale 0.25.
        p = 1.0 if abs(m) < 1e-12 else min(1.0, 2.0 ** -(n - 1))
        return {"method": "paired_t_test", "t": None, "df": n - 1, "n_pairs": n,
                "degenerate": True, "p_value": round(p, 4)}
    se = math.sqrt(v / n)
    t = m / se
    p = 2.0 * t_sf(abs(t), n - 1)
    return {"method": "paired_t_test", "t": round(t, 3), "df": n - 1, "n_pairs": n,
            "p_value": round(min(1.0, p), 4)}


def paired_ci(diffs, conf=0.95):
    """IC sulla media delle differenze appaiate. Ritorna (diff, lo, hi) o None."""
    n = len(diffs)
    if n < 2:
        return None
    m = mean(diffs)
    v = sample_var(diffs)
    if v <= 0:
        return (m, m, m)
    se = math.sqrt(v / n)
    half = t_ppf(1 - (1 - conf) / 2, n - 1) * se
    return (m, m - half, m + half)


def paired_significance(diffs, alpha=None):
    """Verdetto appaiato con la stessa forma di `significance` (chiavi omogenee)."""
    n = len(diffs)
    if alpha is None:
        alpha = 0.10 if n < 4 else 0.05
    t = paired_t_test(diffs)
    if not t:
        return {"method": "paired_t_test", "p_value": 1.0, "alpha": alpha,
                "significant": False, "n_pairs": n}
    return {"method": "paired_t_test", "p_value": t["p_value"], "alpha": alpha,
            "significant": bool(t["p_value"] < alpha), "n_pairs": n, "paired": t}


def wilson_ci(k, n, z=1.96):
    """IC di Wilson per una proporzione. (lo, hi) in 0-1; (0,1) se n == 0.

    Serve a non presentare '2 successi su 3' come un tasso del 67% secco: con
    Wilson quel 67% viene accompagnato da un intervallo 21%-94%, che e'
    l'informazione onesta.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - half) / d), min(1.0, (centre + half) / d))


# --------------------------------------------------------------------------
# Istogramma dei frametime
# --------------------------------------------------------------------------
# I percentili di una sessione non si ottengono mediando i percentili dei
# singoli run (la media di percentili non e' un percentile). L'agent manda
# quindi anche l'istogramma dei frametime: sommandolo tra run si ottiene la
# distribuzione dell'intero blocco, e da li' i percentili esatti.
#
# Risoluzione variabile perche' i millisecondi non contano tutti uguali: a 200
# FPS un frame dura 5 ms e un bucket da 1 ms sarebbe il 20% del valore, mentre
# sopra i 100 ms la precisione al millisecondo non interessa a nessuno.
#   [0,20)    -> 0.1 ms  (200 bucket)
#   [20,50)   -> 0.5 ms  ( 60 bucket)
#   [50,100)  -> 2 ms    ( 25 bucket)
#   [100,300) -> 10 ms   ( 20 bucket)
#   >=300     -> 1 bucket di coda
# La stessa suddivisione e' replicata nell'agent (Get-HistBucket in ps_agent.py):
# se cambia qui deve cambiare anche li'.
HIST_BUCKETS = 306
_HIST_SEGMENTS = ((0.0, 20.0, 0.1, 0), (20.0, 50.0, 0.5, 200),
                  (50.0, 100.0, 2.0, 260), (100.0, 300.0, 10.0, 285))
HIST_TAIL_MID = 350.0  # oltre 300 ms non e' un frame lento, e' uno stallo


def hist_bucket(ms):
    """Indice del bucket per un frametime in ms."""
    if ms < 0:
        ms = 0.0
    for lo, hi, step, base in _HIST_SEGMENTS:
        if ms < hi:
            return base + int((ms - lo) / step)
    return HIST_BUCKETS - 1


def hist_mid(i):
    """Frametime rappresentativo (centro) del bucket i."""
    if i >= HIST_BUCKETS - 1:
        return HIST_TAIL_MID
    for lo, hi, step, base in _HIST_SEGMENTS:
        n = int(round((hi - lo) / step))
        if i < base + n:
            return lo + (i - base) * step + step / 2
    return HIST_TAIL_MID


def build_hist(frametimes):
    """Istogramma da una lista di frametime."""
    h = [0] * HIST_BUCKETS
    for v in frametimes:
        h[hist_bucket(v)] += 1
    return h


def hist_add(acc, hist):
    """Somma di due istogrammi. `acc` puo' essere None (viene creato)."""
    if not hist:
        return acc
    if acc is None:
        acc = [0] * HIST_BUCKETS
    for i in range(min(HIST_BUCKETS, len(hist))):
        acc[i] += int(hist[i] or 0)
    return acc


def hist_total(hist):
    return sum(int(x or 0) for x in (hist or []))


def hist_low_mean_ms(hist, frac=0.01, min_frames=1):
    """Frametime medio del `frac` peggiore dei frame: il vero '1% low'.

    Il p99 puntuale usato finora e' un singolo frame in fondo alla coda, e
    soprattutto ignora tutto cio' che sta oltre: una sessione con esitazioni da
    30 ms e una con freeze da mezzo secondo possono avere lo stesso p99. La
    media della coda pesa l'intera coda, cioe' anche quanto sono gravi i frame
    peggiori — che e' la differenza che si sente giocando. E' anche la
    definizione di '1% low' usata dagli strumenti di benchmark.
    Ritorna None quando la coda richiesta non contiene abbastanza frame perche'
    il numero significhi qualcosa.
    """
    n = hist_total(hist)
    if n <= 0:
        return None
    want = n * frac
    if want < min_frames:
        return None
    acc = 0.0
    taken = 0.0
    for i in range(len(hist) - 1, -1, -1):
        c = int(hist[i] or 0)
        if c <= 0:
            continue
        use = min(float(c), want - taken)
        acc += hist_mid(i) * use
        taken += use
        if taken >= want - 1e-9:
            break
    if taken <= 0:
        return None
    return acc / taken


def hist_percentile_ms(hist, q):
    """Percentile del frametime (q in 0-1) dall'istogramma cumulativo."""
    n = hist_total(hist)
    if n <= 0:
        return None
    target = n * q
    cum = 0
    for i, c in enumerate(hist):
        cum += int(c or 0)
        if cum >= target:
            return hist_mid(i)
    return hist_mid(len(hist) - 1)


def hist_mean_ms(hist):
    n = hist_total(hist)
    if n <= 0:
        return None
    return sum(hist_mid(i) * int(c or 0) for i, c in enumerate(hist)) / n


def _fps(ms):
    return round(1000.0 / ms, 2) if ms and ms > 0 else None


def hist_fps_metrics(hist):
    """Metriche FPS di un blocco a partire dall'istogramma sommato dei suoi run.

    `fps_p1` / `fps_p01` sono medie della coda (1% e 0.1% peggiori), non il
    percentile puntuale: vedi `hist_low_mean_ms` per il perche'. `fps_p01`
    resta None quando lo 0.1% dei frame sarebbe meno di cinque campioni.
    """
    n = hist_total(hist)
    if n <= 0:
        return {}
    out = {"frames": n}
    m = hist_mean_ms(hist)
    if m:
        out["fps_avg"] = _fps(m)
        out["ft_avg_ms"] = round(m, 3)
    p1 = hist_low_mean_ms(hist, 0.01, min_frames=20)
    if p1:
        out["fps_p1"] = _fps(p1)
    p01 = hist_low_mean_ms(hist, 0.001, min_frames=5)
    if p01:
        out["fps_p01"] = _fps(p01)
    med = hist_percentile_ms(hist, 0.5)
    if med:
        out["ft_median_ms"] = round(med, 3)
    return out


def frame_cap_signature(hist, tol=0.02, min_share=0.6):
    """Rileva un frame cap / V-Sync dalla distribuzione dei frametime.

    Con un cap attivo la distribuzione collassa attorno a un solo valore: ogni
    tweak diventa per costruzione non significativo, e il Lab produrrebbe dieci
    'nessun effetto' che sembrano un risultato invece che uno strumento cieco.
    Ritorna dict con `capped` e, quando c'e', gli FPS del cap.
    """
    n = hist_total(hist)
    if n < 200:
        return {"capped": False}
    med = hist_percentile_ms(hist, 0.5)
    if not med or med <= 0:
        return {"capped": False}
    lo, hi = med * (1 - tol), med * (1 + tol)
    inside = 0
    for i, c in enumerate(hist):
        c = int(c or 0)
        if c and lo <= hist_mid(i) <= hi:
            inside += c
    share = inside / n
    if share < min_share:
        return {"capped": False, "peak_share": round(share, 3)}
    return {"capped": True, "peak_share": round(share, 3), "cap_fps": _fps(med)}
