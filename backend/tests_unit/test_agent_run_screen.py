"""Il lavoro in corso e' una schermata, e si puo' fermare.

Prima l'unico segno che l'agent stesse scrivendo nel registro erano due bottoni
disabilitati e un riquadro di log alto 140px in fondo alla finestra: nessun
elenco di cosa stava per succedere, nessun modo di sapere a che punto fosse, e
nessun modo di fermarlo. Ora il job espone i propri passi con l'esito di
ciascuno, e l'utente puo' dire basta.

Fermarsi e' la parte delicata: e' legittimo interrompere un'ottimizzazione, non
lo e' uscire dal lavoro senza aver salvato il backup di quello che si e' gia'
applicato. Meta' dei test qui sotto stanno su quel confine.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML


def _blocco(inizio, fine):
    i = PS.index(inizio)
    return PS[i:PS.index(fine, i + len(inizio))]


MOTORE = _blocco("# ---------------- Job cooperativi", "function Send-Json")
HANDLER = _blocco("elseif ($path -eq '/api/apply' -and $method -eq 'POST') {",
                  "elseif ($path -eq '/api/job' -and $method -eq 'GET') {")


# ---------- fermarsi ----------

def test_fermare_non_interrompe_il_passo_in_corso():
    """Interrompere a meta' una scrittura nel registro sarebbe il modo peggiore
    di dare all'utente il controllo: si alza una bandiera che il loop legge fra
    un passo e l'altro."""
    assert "$path -eq '/api/job/cancel'" in PS
    assert "$script:JOB.cancel = $true" in PS
    assert "if ($j.cancel -and -not $st.final)" in MOTORE


def test_i_passi_di_chiusura_girano_anche_se_ci_si_ferma():
    """Salvare il backup e rileggere lo stato non sono parte
    dell'ottimizzazione: sono cio' che la lascia in un punto sano. Fermarsi
    prima significherebbe uscire con il registro modificato e nessun modo di
    tornare indietro."""
    assert "[bool]$final = $false" in MOTORE
    assert "final = $final" in MOTORE
    # il salvataggio del backup e l'invio dati sono dichiarati finali
    assert "} $null $false $true))" in HANDLER
    assert "} $null $true $true))" in HANDLER


def test_il_benchmark_dopo_non_e_un_passo_di_chiusura():
    """Misurare 'dopo' un'ottimizzazione fermata a meta' produce un confronto
    che non descrive niente."""
    i = HANDLER.index("Benchmark DOPO in corso...")
    coda = HANDLER[i:HANDLER.index("New-JobStep", i + 10)]
    assert "} $null $true))" in coda, "il passo del benchmark DOPO non deve essere final"


def test_un_lavoro_fermato_non_si_chiama_finito():
    """Altrimenti la GUI direbbe 'applicate 12 modifiche' dopo che l'utente ne
    ha fermate 8."""
    assert "$script:JOB.state = if ($script:JOB.cancel) { 'cancelled' } else { 'done' }" in MOTORE
    assert 'job.state === "cancelled"' in GUI


def test_fermare_quando_non_c_e_niente_da_fermare_non_e_un_successo():
    assert "err = 'no_job' } 409" in PS


# ---------- l'esito di ogni passo ----------

def test_il_job_tiene_l_esito_di_ogni_passo():
    """Un contatore dice quanti; per dire QUALE passo non e' riuscito mentre gli
    altri andavano avanti serve l'esito per indice."""
    assert "outcome = @{}; cancel = $false" in MOTORE
    for esito in ("$j.outcome[\"$($j.i)\"] = 'ok'",
                  "$j.outcome[\"$($j.i)\"] = 'failed'",
                  "$j.outcome[\"$($j.i)\"] = 'skipped'"):
        assert esito in MOTORE, esito


def test_l_errore_sa_a_quale_passo_appartiene():
    """Associarlo per etichetta significa sbagliare il giorno in cui due passi
    si chiamano uguale."""
    assert "$j.errors += @{ i = $j.i; step =" in MOTORE


def test_il_dto_porta_la_lista_dei_passi_non_solo_il_contatore():
    i = MOTORE.index("function Get-JobDto")
    corpo = MOTORE[i:MOTORE.index("function Step-GuiJob")]
    assert "for ($n = 0; $n -lt $j.total; $n++)" in corpo
    assert 'steps += @{ i = $n; label = "$($j.steps[$n].label)"' in corpo
    assert "if ($n -eq $j.i -and $j.state -eq 'running') { $stato = 'current' }" in corpo


# ---------- la schermata ----------

def test_il_lavoro_prende_la_finestra():
    """E' una modalita', non un posto: la occupa finche' dura e la restituisce."""
    assert 'id="run" data-testid="run-overlay" hidden' in GUI
    assert "function openRun()" in GUI and "function closeRun()" in GUI
    assert ".run {\n    position: fixed; inset: 0;" in GUI


def test_la_schermata_mostra_tutti_gli_stati_di_un_passo():
    for stato in ("ok", "failed", "current", "skipped", "pending"):
        assert f".run-step.{stato}" in GUI or f"RUN_ICONE = {{" in GUI, stato
    for stato in ("ok:", "failed:", "current:", "skipped:", "pending:"):
        assert stato in GUI.split("RUN_ICONE")[1][:1600], stato


def test_la_barra_ha_una_tacca_per_passo():
    """La percentuale di un lavoro fatto di pezzi disuguali e' un numero che si
    inventa: due benchmark da 40s e dieci tweak da mezzo secondo non sono
    dodicesimi uguali."""
    assert 'steps.map(s => `<div class="run-tick ${s.state}"></div>`)' in GUI


def test_il_passo_lento_lo_dice():
    """Senza, dieci secondi di riga ferma sembrano un blocco."""
    assert "corrente && corrente.slow" in GUI
    assert "Ci vuole qualche decina di secondi" in GUI


def test_il_passo_fallito_resta_a_schermo_col_motivo():
    assert "Nulla e' stato scritto per questo passo." in GUI
    assert 'RUN_TAG = { failed: "NON RIUSCITO"' in GUI


def test_il_log_e_lo_stesso_nei_due_riquadri():
    """Stessa sorgente e stesso contatore: due log che divergono sono peggio di
    un log solo."""
    assert 'document.querySelectorAll("[data-log]")' in GUI
    assert 'id="log" data-log' in GUI
    assert 'id="runLog" data-log' in GUI


def test_gli_errori_si_vedono_dentro_il_log_verde():
    assert "if (/^\\s*\\[(ERR|STOP)/.test(l.msg)) div.className = \"err\";" in GUI
    assert ".log .err { color: var(--danger); }" in GUI


def test_la_schermata_compare_anche_se_il_lavoro_non_l_ha_avviato_questa_pagina():
    """La finestra puo' essere stata ricaricata a lavoro in corso: /api/log dice
    gia' che qualcosa sta girando, e la schermata deve comparire lo stesso."""
    assert "if (v && !runWatching) waitForJob()" in GUI


def test_il_riepilogo_finale_distingue_saltati_e_falliti():
    assert 'const saltati = lista(job.steps).filter(s => s.state === "skipped").length;' in GUI
    assert "saltati > 0" in GUI
    assert "Fermato a meta'" in GUI
