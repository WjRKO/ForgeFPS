"""lab_stats: statistica appaiata, Wilson e istogramma dei frametime."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lab_stats as L


# ---------- statistica appaiata ----------

def test_differenze_coerenti_sono_significative():
    """Tre coppie che vanno tutte nella stessa direzione bastano: e' esattamente
    il guadagno di potenza che lo schema appaiato porta rispetto ai blocchi."""
    out = L.paired_significance([2.0, 2.5, 1.8])
    assert out["significant"] is True
    assert out["p_value"] < 0.05
    assert out["n_pairs"] == 3


def test_differenze_che_cambiano_segno_non_lo_sono():
    assert L.paired_significance([0.2, -0.4, 0.1])["significant"] is False


def test_stessa_media_ma_piu_rumore_perde_significativita():
    """La media delle differenze non basta: conta quanto sono coerenti."""
    pulito = L.paired_significance([2.0, 2.0, 2.0])
    rumoroso = L.paired_significance([-8.0, 12.0, 2.0])
    assert pulito["p_value"] < rumoroso["p_value"]


def test_una_sola_coppia_non_decide():
    assert L.paired_t_test([1.0]) is None
    assert L.paired_significance([1.0])["significant"] is False


def test_intervallo_appaiato_contiene_la_media():
    diff, lo, hi = L.paired_ci([2.0, 2.5, 1.8])
    assert lo < diff < hi
    assert abs(diff - 2.1) < 1e-9


def test_alpha_piu_permissivo_con_poche_coppie():
    assert L.paired_significance([1.0, 1.1, 1.2])["alpha"] == 0.10
    assert L.paired_significance([1.0, 1.1, 1.2, 1.05])["alpha"] == 0.05


def test_appaiato_batte_i_blocchi_sulla_stessa_deriva():
    """Il punto di tutto lo schema: con una deriva comune ai due lati, il
    confronto a blocchi la scambia per rumore, quello appaiato la cancella."""
    deriva = [0.0, -3.0, -6.0]          # il PC si scalda durante la sessione
    off = [100.0 + d for d in deriva]
    on = [102.1, 99.0, 95.9]            # +2 FPS reali, con un filo di rumore
    blocchi = L.significance(on, off)
    appaiato = L.paired_significance([on[i] - off[i] for i in range(3)])
    assert blocchi["significant"] is False
    assert appaiato["significant"] is True


# ---------- Wilson ----------

def test_wilson_allarga_l_intervallo_sui_campioni_piccoli():
    lo3, hi3 = L.wilson_ci(2, 3)
    lo30, hi30 = L.wilson_ci(20, 30)
    assert (hi3 - lo3) > (hi30 - lo30)
    assert lo3 < 2 / 3 < hi3


def test_wilson_senza_campione_non_afferma_nulla():
    assert L.wilson_ci(0, 0) == (0.0, 1.0)


def test_wilson_resta_nei_limiti():
    lo, hi = L.wilson_ci(5, 5)
    assert 0.0 <= lo <= 1.0 and hi <= 1.0


# ---------- istogramma ----------

def test_bucket_e_centri_coerenti():
    for ms in (0.05, 3.3, 8.4, 16.6, 19.9, 21.0, 33.0, 55.0, 99.0, 150.0, 290.0):
        i = L.hist_bucket(ms)
        assert abs(L.hist_mid(i) - ms) <= 5.0


def test_confini_dei_segmenti():
    """Gli stessi confini sono replicati in Get-HistBucket nell'agent."""
    got = [L.hist_bucket(x) for x in (0, 19.99, 20, 49.9, 50, 99.9, 100, 299, 300, 9999)]
    assert got == [0, 199, 200, 259, 260, 284, 285, 304, 305, 305]


def test_risoluzione_fine_dove_i_frame_sono_veloci():
    """A 200 FPS (5 ms) due bucket contigui distano lo 0.1 ms: un bucket da 1 ms
    sarebbe stato il 20% del valore misurato."""
    assert L.hist_bucket(5.0) != L.hist_bucket(5.15)
    assert abs(L.hist_mid(L.hist_bucket(5.0)) - 5.0) < 0.1


def test_somma_di_istogrammi():
    a = L.build_hist([8.0] * 10)
    b = L.build_hist([8.0] * 5)
    assert L.hist_total(L.hist_add(L.hist_add(None, a), b)) == 15


def test_la_media_dei_percentili_non_e_il_percentile():
    """Il motivo per cui l'istogramma viaggia fino al backend.

    Run A tutto liscio, run B con un decimo dei frame lentissimi. L'1% peggiore
    del blocco sta tutto dentro B: mediare i due 1% low per-run da' un numero
    che non corrisponde a nessuna misura reale, e per giunta ottimista.
    """
    a = L.build_hist([8.0] * 10000)
    b = L.build_hist([8.0] * 9000 + [40.0] * 1000)
    p1_a = 1000 / L.hist_low_mean_ms(a, 0.01, 20)
    p1_b = 1000 / L.hist_low_mean_ms(b, 0.01, 20)
    pooled = L.hist_fps_metrics(L.hist_add(L.hist_add(None, a), b))["fps_p1"]
    media_dei_percentili = (p1_a + p1_b) / 2
    assert round(pooled) == 25            # tutti i frame peggiori vengono da B
    assert media_dei_percentili > 70      # la media inventa una fluidita' che non c'e'


def test_il_percentile_puntuale_ignora_quanto_sono_gravi_i_frame_peggiori():
    """Due sessioni con lo STESSO p99 ma code diverse: una ha esitazioni da 30
    ms, l'altra freeze da mezzo secondo. Il percentile puntuale le dichiara
    identiche perche' guarda un solo frame e butta via tutto quello che c'e'
    oltre; la media della coda le distingue, ed e' la differenza che l'utente
    sente davvero."""
    lieve = L.build_hist([8.0] * 9900 + [30.0] * 100)
    grave = L.build_hist([8.0] * 9900 + [30.0] * 50 + [500.0] * 50)
    assert L.hist_percentile_ms(lieve, 0.99) == L.hist_percentile_ms(grave, 0.99)
    m_lieve = L.hist_low_mean_ms(lieve, 0.01, 20)
    m_grave = L.hist_low_mean_ms(grave, 0.01, 20)
    assert m_grave > m_lieve * 3


def test_coda_troppo_corta_non_produce_un_numero():
    """Lo 0.1% di 100 frame e' un decimo di frame: meglio None che un valore
    che sembra una statistica."""
    h = L.build_hist([8.0] * 100)
    assert L.hist_low_mean_ms(h, 0.001, min_frames=5) is None


def test_metriche_fps_dall_istogramma():
    random.seed(1)
    fr = [8.0 + random.gauss(0, 0.4) for _ in range(20000)] + [40.0] * 50
    m = L.hist_fps_metrics(L.build_hist(fr))
    assert m["frames"] == 20050
    assert 120 < m["fps_avg"] < 128
    assert m["fps_p1"] < m["fps_avg"]          # l'1% peggiore e' sempre piu' lento
    assert m["fps_p01"] <= m["fps_p1"]


def test_istogramma_vuoto():
    assert L.hist_fps_metrics([0] * L.HIST_BUCKETS) == {}
    assert L.hist_total(None) == 0


# ---------- frame cap ----------

def test_frame_cap_riconosciuto():
    random.seed(5)
    capped = [16.66 + random.gauss(0, 0.05) for _ in range(5000)]
    out = L.frame_cap_signature(L.build_hist(capped))
    assert out["capped"] is True
    assert 59 <= out["cap_fps"] <= 61


def test_gioco_libero_non_e_cappato():
    random.seed(6)
    libero = [8.0 + random.gauss(0, 1.5) for _ in range(5000)]
    assert L.frame_cap_signature(L.build_hist(libero))["capped"] is False


def test_pochi_frame_non_bastano_per_dichiarare_un_cap():
    assert L.frame_cap_signature(L.build_hist([16.6] * 50))["capped"] is False


def test_differenze_identiche_non_producono_certezza_assoluta():
    """Tre differenze uguali al centesimo non sono una prova schiacciante: senza
    varianza il t non esiste, e dichiarare p=0 sarebbe certezza da tre numeri.
    Resta quello che i dati dicono davvero, cioe' il test dei segni."""
    out = L.paired_t_test([0.6, 0.6, 0.6])
    assert out["degenerate"] is True
    assert out["p_value"] == 0.25          # 2^-(n-1) con n = 3
    assert L.paired_significance([0.6, 0.6, 0.6])["significant"] is False
    assert L.paired_t_test([0.6] * 5)["p_value"] == 0.0625


def test_differenze_tutte_nulle_sono_il_massimo_del_p():
    assert L.paired_t_test([0.0, 0.0, 0.0])["p_value"] == 1.0


def test_gruppi_costanti_nel_welch_non_danno_p_zero():
    """Stesso problema nel confronto a blocchi: il limite e' il p minimo che un
    test di permutazione puo' produrre con quelle numerosita'."""
    out = L.welch_t_test([100.3] * 3, [99.7] * 3)
    assert out["degenerate"] is True
    assert out["p_value"] == 0.1           # 2 / C(6,3)
    assert L.significance([100.3] * 3, [99.7] * 3)["significant"] is False
