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
        p = 1.0 if abs(m1 - m2) < 1e-12 else 0.0
        return {"method": "welch_t_test", "t": None, "df": None, "p_value": round(p, 4)}
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
    """Test di significativita' condiviso: Welch primario + Mann-Whitney secondario.

    Con n=3 run per lato (campione minimo del Lab) usiamo alpha adattivo 0.10;
    da n>=5 si scende a 0.05.
    """
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
