"""L'esito di un tweak si verifica guardando la macchina, non gli errori.

Lo script gira con `$ErrorActionPreference = 'SilentlyContinue'` dalla prima
riga, e non puo' non girarci: meta' delle sonde interroga cose che su molti PC
non esistono, e ogni cmdlet che fallisce in silenzio li' e' voluto. Il prezzo
era che un tweak che non scriveva niente — permessi negati, chiave protetta,
criterio di dominio — risultava applicato esattamente come uno riuscito, e
finiva cosi' nel journal, nel riepilogo e nel conteggio.

La domanda giusta non e' "il codice ha sollevato un errore?" ma "la macchina e'
cambiata?". La risposta c'era gia': il piano dichiara chiave per chiave quale
valore ci deve essere dopo. Si rilegge, e le righe che dovevano cambiare devono
risultare a posto.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML

APPLY = PS[PS.index("# L'esito di un tweak si verifica guardando la macchina"):
           PS.index("function Get-RevertableIds")]


# ---------- da dove viene il verdetto ----------

def test_il_verdetto_si_legge_sulla_macchina():
    """Il piano prima di toccare niente e' la specifica; il piano dopo e' la
    verifica. Nessuna delle due dipende dal fatto che un cmdlet abbia parlato."""
    assert "function Test-TweakApplied" in APPLY
    assert "foreach ($r in (Get-TwPlan $t)) { if ($r.key -and -not $r.same) { $__attesi += \"$($r.key)\" } }" in APPLY
    assert "$__restate = @(Test-TweakApplied $t $__attesi)" in APPLY


def test_il_piano_si_legge_prima_di_applicare():
    """Dopo non si puo' piu' sapere cosa doveva cambiare: le righe gia' a posto
    e quelle appena scritte si assomigliano troppo."""
    i = APPLY.index("function Invoke-ApplyTracked")
    corpo = APPLY[i:]
    assert corpo.index("$__attesi") < corpo.index("& $t.apply")


def test_niente_di_previsto_e_cambiato_vuol_dire_fallito():
    """E' il caso che prima passava per riuscito."""
    assert "if ($__attesi.Count -gt 0 -and $__restate.Count -eq $__attesi.Count) {" in APPLY
    assert "nessuna delle {0} modifiche previste risulta scritta" in APPLY
    assert "Write-Journal 'apply' $t @() $false $__msg" in APPLY
    assert "throw $__msg" in APPLY


def test_un_tweak_fallito_non_lascia_chiavi_da_annullare():
    """Backup-Reg registra il valore PRIMA di scrivere: se la scrittura non
    avviene, resta una riga di backup per una modifica mai fatta, e 'Annulla'
    rimetterebbe un valore che nessuno ha toccato."""
    assert "foreach ($k in $__new) { $script:BK.Remove($k) }" in APPLY


def test_applicato_in_parte_non_e_fallito():
    """Qualcosa e' passato ed e' annullabile: dichiararlo fallito direbbe che
    non e' successo niente, ed e' falso quanto il contrario."""
    assert "if ($__restate.Count -gt 0) { $__extra['partial'] = @($__restate) }" in APPLY
    assert "Write-Journal 'apply' $t $__new $true '' $__extra" in APPLY


def test_quello_che_non_si_verifica_non_si_spaccia_per_verificato():
    """powercfg, netsh e fsutil non lasciano una chiave da rileggere: il piano
    non li conta fra gli attesi, e il journal registra QUANTE modifiche erano
    verificabili invece di un 'ok' senza qualita'."""
    assert "if (@($attesi).Count -eq 0) { return @() }" in APPLY
    assert "$__extra = @{ checked = $__attesi.Count }" in APPLY


# ---------- come arriva alla schermata ----------

def test_il_passo_puo_dire_da_se_com_e_andato():
    """'ok' e' il default, non un verdetto: se il pump lo scrivesse sempre,
    promuoverebbe a pieno successo un passo riuscito a meta'."""
    assert 'if (-not $j.outcome["$($j.i)"]) { $j.outcome["$($j.i)"] = \'ok\' }' in PS


def test_il_riuscito_a_meta_arriva_alla_schermata():
    assert "$j.outcome[\"$($j.i)\"] = 'warn'" in PS
    assert "$j.errors += @{ i = $j.i; step = \"$($a.name)\"; warn = $true" in PS
    assert 'RUN_TAG = { failed: "NON RIUSCITO", current: "in corso", skipped: "SALTATO", warn: "IN PARTE" }' in GUI
    assert ".run-step.warn" in GUI


def test_il_riepilogo_non_conta_i_parziali_fra_i_falliti():
    assert "const failed = tuttiErr.filter(e => !e.warn).length;" in GUI
    assert "const parziali = tuttiErr.filter(e => e.warn).length;" in GUI
    assert "riuscito/i solo in parte" in GUI


def test_il_journal_ricorda_cosa_non_e_passato():
    """Il giorno dopo, 'applicato' e 'applicato a meta'' devono restare due cose
    diverse."""
    assert "checked = [int]$r.checked; partial = @($r.partial)" in PS
    assert "Applicato in parte:" in GUI
    assert ".jr-row.parziale" in GUI
