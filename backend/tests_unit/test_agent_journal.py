"""Il journal: cosa FrameForge ha cambiato su questo PC, e come rimetterlo.

Il file di backup e' una fotografia del presente — quali chiavi sono modificate
adesso e con che valore rimetterle. Non sa raccontare cosa e' successo: un tweak
annullato ne sparisce, uno fallito non ci e' mai entrato. Il log della GUI, che
quella storia ce l'aveva, viveva in memoria e moriva con la finestra.

Cosi' "cosa mi hai fatto al PC?" non era rispondibile il giorno dopo, ed e' la
domanda da cui dipende la fiducia in uno strumento che scrive nel registro.
Ogni test qui sotto tiene ferma una delle proprieta' che rendono vera quella
risposta.
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


MOTORE = _blocco("# Journal: la storia, non solo lo stato",
                 "# v0.7.7: applica un tweak tracciando")


# ---------- dove vivono i dati ----------

def test_il_backup_non_sta_piu_in_temp():
    """%TEMP% lo svuota Windows, lo svuotano i pulitori e — soprattutto — lo
    cancella ricorsivamente Do-Cleanup, cioe' il tweak 'Pulizia temp' di questo
    stesso agent: bastava sceglierlo per ultimo perche' l'agent cancellasse il
    proprio backup e il PC non potesse piu' tornare indietro."""
    assert "$BACKUP  = Join-Path $FF_HOME 'backup.json'" in PS
    assert "$BACKUP  = Join-Path $env:TEMP" not in PS
    assert "Get-ChildItem $env:TEMP -Recurse -Force" in PS, \
        "se Do-Cleanup non svuota piu' %TEMP%, questo test ha perso il suo motivo"


def test_il_journal_sta_accanto_al_backup():
    assert "$JOURNAL = Join-Path $FF_HOME 'journal.jsonl'" in PS
    assert "if (-not (Test-Path $FF_HOME)) { New-Item -ItemType Directory -Path $FF_HOME -Force" in PS


def test_i_backup_vecchi_vengono_migrati_non_abbandonati():
    """Chi aggiorna ha il backup nel percorso di prima: se smettessimo di
    leggerlo, un PC gia' ottimizzato diventerebbe di colpo non ripristinabile."""
    assert "$BACKUP_OLD = @((Join-Path $env:TEMP 'forgefps_backup.json'), (Join-Path $env:TEMP 'boostpc_backup.json'))" in PS
    assert "function Get-BackupPath" in PS
    assert "$__bkFile = Get-BackupPath" in PS


def test_il_file_vecchio_si_cancella_solo_dopo_aver_scritto_il_nuovo():
    """Se il salvataggio fallisce, il backup di prima e' ancora l'unica via di
    ritorno: cancellarlo prima significa restare senza nessuno dei due."""
    i = PS.index("$__out | ConvertTo-Json -Depth 6 | Set-Content $BACKUP")
    j = PS.index("foreach ($__old in $BACKUP_OLD)", i)
    assert j > i


# ---------- cosa finisce nel journal ----------

def test_e_un_file_a_righe_scritto_in_coda():
    """Aggiungere in coda e' cio' che rende una riga corrotta un danno da una
    riga: riscrivere tutto il file a ogni evento no."""
    assert "Add-Content -Path $JOURNAL" in MOTORE
    assert "ConvertTo-Json -Depth 5 -Compress" in MOTORE


def test_una_riga_illeggibile_non_porta_via_il_file():
    i = MOTORE.index("function Read-Journal")
    corpo = MOTORE[i:MOTORE.index("function Get-JournalDto")]
    assert "try { $out += ($l | ConvertFrom-Json) } catch { }" in corpo


def test_anche_i_tweak_falliti_finiscono_nel_journal():
    """E' il pezzo di storia che il backup non puo' registrare: un tentativo
    fallito non lascia chiavi, quindi non lascia traccia. Ed e' la prima cosa
    che si cerca quando qualcosa non ha funzionato."""
    i = PS.index("function Invoke-ApplyTracked")
    corpo = PS[i:PS.index("function Get-RevertableIds", i)]
    assert "Write-Journal 'apply' $t @() $false" in corpo
    assert "throw" in corpo, "il fallimento va registrato E propagato, non inghiottito"
    assert "Write-Journal 'apply' $t $__new $true ''" in corpo


def test_anche_gli_annullamenti_finiscono_nel_journal():
    """Senza, la cronologia direbbe che un tweak annullato e' ancora attivo."""
    i = PS.index("function Invoke-RestoreTweak")
    assert "Write-Journal 'revert' (Get-TweakById $id)" in PS[i:PS.index("\n}", i)]


def test_il_ripristino_totale_registra_una_riga_per_tweak():
    i = PS.index("function Invoke-Restore {")
    corpo = PS[i:PS.index("\n}", i)]
    assert "foreach ($id in @($script:TWKEYS.Keys)) { Write-Journal 'revert'" in corpo
    # ...e prima di svuotare TWKEYS, altrimenti non c'e' piu' niente da scrivere
    assert corpo.index("Write-Journal") < corpo.index("$script:TWKEYS = @{}")


def test_un_journal_che_non_si_scrive_non_ferma_l_ottimizzazione():
    """E' un registratore, non un partecipante."""
    i = MOTORE.index("function Write-Journal")
    corpo = MOTORE[i:MOTORE.index("function Read-Journal")]
    assert corpo.strip().startswith("function Write-Journal(")
    # il try apre subito: non c'e' niente prima che possa esplodere fuori
    assert corpo[corpo.index("{"):].lstrip("{ \n").startswith("try {")
    assert "} catch {" in corpo


# ---------- il valore precedente, in chiaro ----------

def test_il_valore_precedente_e_leggibile():
    """Nel backup le chiavi stanno come 'Tipo|Valore' e le assenti come
    '__ABSENT__': sono dettagli di come si rimette a posto, non risposte."""
    assert "if ($s -eq '__ABSENT__') { return 'non esisteva' }" in MOTORE
    assert "if ($p.Count -eq 2 -and ($p[0] -eq 'DWord' -or $p[0] -eq 'String')) { return $p[1] }" in MOTORE


def test_il_piano_energetico_non_si_racconta_col_guid():
    """Il backup salva il GUID perche' e' l'unica cosa con cui si rimette a
    posto, ma '381b4222-f694-...' nella cronologia non dice niente a nessuno."""
    assert "function Get-PowerPlanName" in MOTORE
    assert "Format-BkValue $script:BK[$k] $k" in MOTORE


def test_il_valore_attuale_manca_invece_di_essere_inventato():
    """Dove non si rilegge a buon mercato, Get-KeyNow torna stringa vuota e la
    GUI mostra solo il prima: meglio una meta' vera che una freccia finta."""
    i = MOTORE.index("function Get-KeyNow")
    corpo = MOTORE[i:MOTORE.index("function Write-Journal")]
    assert "catch { return '' }" in corpo
    assert "if (!now) return prevHtml;" in GUI


# ---------- cosa e' ancora annullabile ----------

def test_l_annullabilita_la_decide_il_backup_non_il_journal():
    """Il journal e' cronologia e non cambia; lo stato di adesso e' il backup.
    Senza questo incrocio, un tweak gia' annullato continuerebbe a offrire
    'Annulla' — e il secondo click rimetterebbe un valore che non c'e' piu'."""
    i = MOTORE.index("function Get-JournalDto")
    corpo = MOTORE[i:]
    assert "foreach ($id in @($script:TWKEYS.Keys)) { $live[\"$id\"] = $true }" in corpo
    assert 'revertable = ([bool]$r.ok -and "$($r.event)" -eq \'apply\' -and $live.ContainsKey("$($r.tweak)"))' in corpo


def test_le_sessioni_escono_dalla_piu_recente():
    """E' l'ordine in cui si cerca 'cosa e' successo poco fa', che e' il motivo
    per cui si apre questa schermata."""
    i = MOTORE.index("function Get-JournalDto")
    assert "for ($i = $ordine.Count - 1; $i -ge 0; $i--)" in MOTORE[i:]


def test_ogni_giro_di_ottimizzazione_e_una_sessione():
    i = PS.index("function Start-GuiJob")
    assert "$script:SESSION = 's-' + (Get-Date).ToString('yyyyMMdd-HHmmss')" in PS[i:PS.index("function Get-JobDto", i)]


def test_annullare_una_sessione_e_un_job_come_gli_altri():
    """N revert possono durare quanto N apply: dentro la richiesta bloccherebbero
    il server locale esattamente come faceva /api/apply."""
    i = PS.index("$path -eq '/api/revert-session'")
    corpo = PS[i:PS.index("elseif ($path -eq '/api/apply-one'", i)]
    assert "Start-GuiJob 'revert-session' $steps" in corpo
    assert "New-RevertStep $id" in corpo
    assert "Invoke-RestoreTweak $a" in PS[PS.index("function New-RevertStep"):]
    assert "} 202" in corpo
    assert "err = 'busy'" in corpo


# ---------- la schermata ----------

def test_la_schermata_dice_dove_sta_il_file():
    """La reversibilita' va mostrata, non promessa: il file e' verificabile."""
    assert 'data-testid="journal-file"' in GUI
    assert "resta anche se chiudi la finestra" in GUI


def test_la_schermata_distingue_i_quattro_casi():
    """Applicata e attiva, gia' annullata, annullamento, fallita: sono le
    quattro forme che una riga puo' avere, e si confondono facilmente."""
    for caso in ('e.event === "revert"', "!e.ok", "e.revertable", "GIA' ANNULLATO"):
        assert caso in GUI, caso
    assert "NULLA DA ANNULLARE" in GUI


def test_una_chiave_che_non_esisteva_lo_dice_a_parole():
    assert 'la chiave non esisteva' in GUI


def test_il_bottone_di_sessione_appare_solo_se_c_e_qualcosa_da_annullare():
    assert "${nRev ? `<button" in GUI
