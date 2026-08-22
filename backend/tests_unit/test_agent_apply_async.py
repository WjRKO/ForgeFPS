"""L'applicazione dei tweak non blocca piu' il server locale della GUI.

Il server della GUI e' un HttpListener a thread singolo: finche' /api/apply
faceva tutto il lavoro dentro la richiesta (benchmark PRIMA, N tweak, benchmark
DOPO, invio dati) nessun'altra richiesta veniva servita per minuti. La GUI
continuava a chiedere /api/log ogni 400 ms senza ricevere risposta, quindi
mostrava un log fermo e nessun avanzamento proprio mentre l'agent scriveva nel
registro: il momento in cui l'utente ha piu' bisogno di vedere che sta
succedendo qualcosa.

Ora la richiesta registra un job e torna subito, e il loop esegue un passo per
giro. Qui sotto ci sono le proprieta' che rendono vera quella frase: se una
salta, il log torna a congelarsi e nessuno se ne accorge finche' non lo vede un
utente su una macchina lenta.
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


HANDLER = _blocco("elseif ($path -eq '/api/apply' -and $method -eq 'POST') {",
                  "elseif ($path -eq '/api/job' -and $method -eq 'GET') {")
MOTORE = _blocco("# ---------------- Job cooperativi", "function Send-Json")
LOOP = _blocco("# Loop richieste (async", "try { $listener.Stop() } catch {}")


# ---------- la richiesta non fa piu' il lavoro ----------

def test_apply_registra_un_job_e_torna_subito():
    assert "Start-GuiJob 'apply' $steps" in HANDLER
    assert "Send-Json $ctx @{ ok = $true; job = (Get-JobDto) } 202" in HANDLER


def test_il_gestore_non_lavora_prima_di_rispondere():
    """Le due misure, i tweak e l'invio dati sono i pezzi che duravano minuti.
    Ora stanno tutti dentro scriptblock che esegue il loop: prima del primo
    passo il gestore non deve fare nient'altro che leggere il corpo."""
    preambolo = HANDLER[:HANDLER.index("New-JobStep")]
    for lavoro in ("Run-Benchmark", "Invoke-ApplyTracked", "Send-Data", "Save-Backup"):
        assert lavoro not in preambolo, lavoro


def test_prima_si_registra_il_job_poi_si_risponde():
    assert HANDLER.index("New-JobStep") < HANDLER.index("Start-GuiJob") < HANDLER.index("} 202")


def test_si_puo_seguire_il_job():
    """Il log racconta cosa e' successo, non a che punto e': senza questo
    endpoint il client non ha modo di sapere quando ha finito ne' quanto manca."""
    assert "elseif ($path -eq '/api/job' -and $method -eq 'GET') {" in PS
    assert "Send-Json $ctx (Get-JobDto)" in PS


def test_due_apply_insieme_non_si_sovrappongono():
    """Due job che scrivono nel registro contemporaneamente si mangerebbero il
    backup a vicenda: il secondo rimbalza invece di partire."""
    assert "if ($script:JOB -and $script:JOB.state -eq 'running') {" in HANDLER
    assert "err = 'busy'" in HANDLER
    assert "} 409" in HANDLER


# ---------- il loop e' quello che fa avanzare il lavoro ----------

def test_il_loop_esegue_un_passo_per_giro():
    assert "if ($script:JOB -and $script:JOB.state -eq 'running') { Step-GuiJob }" in LOOP


def test_con_un_job_in_corso_il_loop_non_sta_ad_aspettare():
    """180 ms di attesa per richiesta erano gratis quando il loop non aveva
    altro da fare; con un job in corso sono 180 ms aggiunti a ogni passo."""
    assert "$waitMs = 180; if ($jobRunning) { $waitMs = 5 }" in LOOP
    assert "$ar.AsyncWaitHandle.WaitOne($waitMs)" in LOOP


def test_un_job_in_corso_conta_come_attivita():
    """Il loop esce dopo 30 s senza richieste. Un benchmark dura di piu': senza
    questa riga l'ottimizzazione si interromperebbe da sola a meta'."""
    assert "if ($jobRunning) { $lastActivity = Get-Date }" in LOOP


def test_chiudere_la_finestra_non_interrompe_un_job_a_meta():
    """Uscire con il registro gia' modificato e' peggio che finire parlando a
    nessuno: i passi rimasti includono la scrittura del backup."""
    assert "if (-not $edgeAlive -and -not $jobRunning) { break }" in LOOP


def test_servire_una_richiesta_segnala_che_l_annuncio_e_arrivato():
    assert "if ($jobRunning) { $script:JOB.seen = $true }" in LOOP


# ---------- il motore dei passi ----------

def test_i_passi_lenti_vengono_annunciati_prima_di_partire():
    """Un passo lungo blocca il loop mentre gira: annunciarlo ed eseguirlo nello
    stesso giro farebbe arrivare la riga 'sto misurando' a misura finita."""
    assert "if ($st.slow) { return }" in MOTORE
    assert "$j.announced = $true" in MOTORE


def test_l_annuncio_ha_un_tetto():
    """Una GUI chiusa o bloccata non deve fermare un'ottimizzazione iniziata."""
    assert "-not $j.seen -and ((Get-Date) - $j.announce_ts).TotalMilliseconds -lt 1500" in MOTORE


def test_un_passo_che_fallisce_non_ferma_gli_altri_ma_si_vede():
    """Era gia' cosi' che si tirava dritto ($ErrorActionPreference =
    'SilentlyContinue'), ma il fallimento era indistinguibile dal successo."""
    assert "$j.errors += @{ i = $j.i; step = " in MOTORE
    assert 'WebLog ("[ERR ] {0}: {1}" -f $st.label, $_.Exception.Message)' in MOTORE
    assert "$j.i++" in MOTORE


def test_i_dati_del_passo_arrivano_come_argomento():
    """Le variabili del loop vengono sovrascritte dalla richiesta successiva,
    quindi un passo non puo' leggerle quando gli tocca. E GetNewClosure() qui e'
    vietato (vedi tests/test_agent_script.py)."""
    assert "& $st.run $j $st.arg" in MOTORE
    assert "GetNewClosure" not in MOTORE
    assert "param($j, $a)" in HANDLER


def test_il_lavoro_finito_libera_il_flag_applying():
    """/api/log espone `applying`: e' quello che tiene i bottoni disabilitati.
    Un job finito che non lo rilascia lascia la GUI inservibile."""
    assert "function Complete-GuiJob" in MOTORE
    assert "$script:APPLYING = $false" in MOTORE


def test_il_risultato_viaggia_solo_a_job_finito():
    """Il payload completo (tutti i tweak + i due benchmark) rispedito a ogni
    poll sarebbe una serializzazione grossa ogni 400 ms."""
    assert "if ($j.state -ne 'running') { $res = $j.result }" in MOTORE


# ---------- quello che il client si aspetta di ricevere ----------

def test_il_payload_finale_e_quello_di_prima():
    """Il risultato del job ha gli stessi campi della vecchia risposta sincrona:
    e' cio' che permette al client di consumarlo con lo stesso codice."""
    for campo in ("$j.result.ok = $true", "$j.result.tweaks = Get-TweakDto",
                  "$j.result.backup = $script:BK.Count",
                  "$j.result.backup_ids = (Get-BackupIds)",
                  "$j.result.revertable = (Get-RevertableIds)"):
        assert campo in HANDLER, campo


def test_il_backup_viene_scritto_dopo_ogni_tweak():
    """Ora il lavoro e' interrompibile (finestra chiusa, PC spento): un tweak
    applicato con sul disco il backup di prima e' un tweak che l'utente non puo'
    piu' annullare."""
    passo = _blocco("function New-TweakStep", "function New-RevertStep")
    i = passo.index("Invoke-ApplyTracked $a")
    assert "Save-Backup" in passo[i:i + 400]


def test_tutti_i_gestori_costruiscono_i_passi_allo_stesso_modo():
    """Applicare un tweak da /api/apply e applicarlo da /api/apply-one facevano
    cose leggermente diverse, e la differenza non la voleva nessuno."""
    for fabbrica in ("function New-TweakStep", "function New-RevertStep", "function New-StateStep"):
        assert fabbrica in PS, fabbrica
    assert "[void]$steps.Add((New-TweakStep $t))" in HANDLER


# ---------- la GUI ----------

def test_la_gui_aspetta_il_job_invece_della_risposta():
    assert "function waitForJob()" in GUI
    assert 'await api("/api/job")' in GUI
    assert "const job = await waitForJob();" in GUI


def test_la_gui_dice_a_che_punto_e():
    """Il log dice cosa e' successo; la schermata di lavoro dice quanto manca
    (i suoi test stanno in test_agent_run_screen.py)."""
    assert "function renderRun(j)" in GUI
    assert "${j.step}<span>/${j.total}</span>" in GUI


def test_la_gui_non_nasconde_i_passi_falliti():
    assert "const failedTweaks =" in GUI
    assert "Applicati in parte" in GUI


def test_la_gui_gestisce_il_rimbalzo():
    """Il 409 arriva con un corpo JSON valido: senza questo controllo verrebbe
    letto come un successo con zero tweak."""
    assert "started.ok === false" in GUI
