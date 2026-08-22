"""Nessun lavoro gira piu' dentro la richiesta.

Il server locale della GUI e' un HttpListener a thread singolo: qualsiasi cosa
duri, se gira dentro il gestore, tiene fermo tutto il resto — log compreso.
/api/apply era il caso piu' evidente e il primo sistemato, ma non era l'unico:
rimettere tutto com'era puo' voler dire venti tweak e servizi da riavviare,
Remove-AppxPackage ci mette secondi per app, e applicare un tweak solo puo'
comunque scandire tutte le schede di rete.

E c'e' una ragione in piu' che prima non c'era: da quando l'esito di un tweak si
verifica davvero, applicare puo' FALLIRE. Dentro la richiesta un tweak che non
passa diventava un 500; come job diventa un passo rosso con il suo motivo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML

LAVORI = ("/api/apply", "/api/apply-one", "/api/restore", "/api/restore-one",
          "/api/revert-session", "/api/bloatware/remove")


def _gestore(path):
    i = PS.index("$path -eq '%s'" % path)
    return PS[i:PS.index("\n        elseif ($path -eq", i)]


def _senza_commenti(testo):
    """Un commento che nomina Remove-AppxPackage per spiegare perche' NON gira
    piu' dentro la richiesta non e' Remove-AppxPackage che gira dentro la
    richiesta. I test qui sotto guardano il codice, non la prosa."""
    return "\n".join(r for r in testo.split("\n") if not r.lstrip().startswith("#"))


# ---------- tutti allo stesso modo ----------

def test_ogni_lavoro_registra_un_job_e_risponde_subito():
    for path in LAVORI:
        g = _gestore(path)
        assert "Start-GuiJob" in g, path
        assert "} 202" in g, path


def test_ogni_lavoro_rimbalza_se_ce_n_e_gia_uno():
    """Due lavori che scrivono insieme si mangiano il backup a vicenda."""
    for path in LAVORI:
        g = _gestore(path)
        assert "if ($script:JOB -and $script:JOB.state -eq 'running') {" in g, path
        assert "err = 'busy'" in g, path
        assert "} 409" in g, path


def test_nessun_gestore_lavora_prima_di_rispondere():
    """Il preambolo di ogni gestore: leggere il corpo e costruire i passi. Il
    lavoro vero lo fa il loop."""
    lavoro = ("Invoke-ApplyTracked", "Invoke-RestoreTweak", "Invoke-Restore",
              "Remove-AppxPackage", "Run-Benchmark", "Send-Data")
    for path in LAVORI:
        g = _senza_commenti(_gestore(path))
        preambolo = g[:g.index("New-JobStep") if "New-JobStep" in g else g.index("Start-GuiJob")]
        for l in lavoro:
            assert l not in preambolo, "%s esegue %s dentro la richiesta" % (path, l)


# ---------- i passi si costruiscono in un posto solo ----------

def test_i_passi_hanno_una_fabbrica_sola():
    """Applicare un tweak da /api/apply e applicarlo da /api/apply-one facevano
    cose leggermente diverse, e la differenza non la voleva nessuno."""
    for fabbrica in ("function New-TweakStep", "function New-RevertStep", "function New-StateStep"):
        assert fabbrica in PS, fabbrica
    assert "[void]$steps.Add((New-TweakStep $t))" in _gestore("/api/apply")
    assert "[void]$steps.Add((New-TweakStep $t))" in _gestore("/api/apply-one")
    assert "New-RevertStep" in _gestore("/api/restore")
    assert "New-RevertStep" in _gestore("/api/restore-one")
    assert "New-RevertStep" in _gestore("/api/revert-session")


def test_il_passo_di_chiusura_gira_anche_se_ci_si_ferma():
    """Fermarsi non deve lasciare la GUI a mostrare i valori di prima."""
    i = PS.index("function New-StateStep")
    assert "} $null $false $true)" in PS[i:PS.index("function Send-Json", i)]


# ---------- granularita' ----------

def test_il_ripristino_totale_e_un_passo_per_tweak():
    """Un solo passo lungo avrebbe dato una barra ferma e nessun modo di sapere
    a che punto fosse. La spazzata finale resta, per le chiavi che nessun tweak
    rivendica (backup scritti da versioni che non tracciavano)."""
    g = _gestore("/api/restore")
    assert "foreach ($id in @($script:TWKEYS.Keys)) { [void]$steps.Add((New-RevertStep $id)) }" in g
    assert "Ripristino il resto del backup." in g
    assert "Invoke-Restore" in g


def test_la_rimozione_bloatware_e_un_passo_per_app():
    g = _gestore("/api/bloatware/remove")
    assert "foreach ($n in @($body.names))" in g
    assert "Test-BloatProtected" in g, "la lista protetta non si tocca nemmeno come passo"


def test_anche_la_app_rimossa_si_verifica_guardando():
    """Remove-AppxPackage non alza la voce quando non riesce: si ricontrolla se
    la app c'e' ancora, invece di contare i tentativi."""
    g = _gestore("/api/bloatware/remove")
    assert "if (Get-AppxPackage -Name $a -ErrorAction SilentlyContinue) {" in g
    assert 'throw "la app risulta ancora installata"' in g


# ---------- il client ----------

def test_il_client_avvia_i_lavori_in_un_posto_solo():
    """Prima ogni chiamante ripeteva le stesse sei righe, e ognuno le ripeteva
    un po' diverse."""
    assert "async function runJob(path, corpo)" in GUI
    assert "function applicaRisultato(d)" in GUI
    for chiamata in ('runJob("/api/apply"', 'runJob("/api/apply-one"',
                     'runJob("/api/restore"', 'runJob("/api/restore-one"',
                     'runJob("/api/bloatware/remove"'):
        assert chiamata in GUI, chiamata


def test_il_client_riconosce_il_rimbalzo():
    assert 'started && started.err === "busy"' in GUI


def test_ogni_tipo_di_lavoro_si_presenta_col_proprio_nome():
    for kind in ("apply-one", "restore-one", "restore", "bloatware"):
        assert '"%s":' % kind in GUI, kind


def test_un_tweak_solo_che_non_passa_lo_dice():
    """Era il caso peggiore: dentro la richiesta diventava un 500 muto."""
    i = GUI.index("async function applyOne(id)")
    corpo = GUI[i:GUI.index("async function doRestore")]
    assert "if (err && !err.warn) {" in corpo
    assert "Non riuscito" in corpo
    assert "Applicato in parte" in corpo
