"""Precisione del rilevamento di avvio e servizi.

La lista "app all'avvio" veniva costruita da quattro fonti e ne mancavano
altrettante, e il numero mostrato accanto (`health.startup_count`) era una
seconda rilevazione indipendente: sullo stesso PC i due numeri non tornavano.
Questi test fissano i punti che erano sbagliati, non l'implementazione:

  - le app UWP/Store (Teams, Xbox, Collegamento al telefono) esistono solo nel
    ramo AppModel del registro: senza quel ramo il Task Manager mostrava sette
    voci che noi non avevamo;
  - un servizio "Manuale" con avvio trigger parte quando serve e si ferma da
    solo: consigliarne la disattivazione rompe Bluetooth, stampa o VPN senza
    guadagnare un millisecondo all'avvio;
  - i servizi Defender arrivano col nome localizzato ("Servizio Microsoft
    Defender Antivirus"), che il filtro anti-rumore non intercettava;
  - quando cambia il rilevatore, la lista si muove per conto suo: senza un
    numero di revisione il backend legge quel movimento come "l'utente ha
    disattivato roba" e annuncia decine di cambiamenti mai avvenuti.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent
from models import SpecsInput
from services_kb import analyze_services, is_startup_noise
from system_changes import build_change_events

SCRIPT = ps_agent.PS_SCRIPT


# --- fonti di rilevamento presenti nello script servito ---

def test_le_fonti_che_mancavano_sono_nello_script():
    for fonte, perche in (
        (r"AppModel\SystemAppData", "app UWP/Store: Teams, Xbox, Collegamento al telefono"),
        (r"CurrentVersion\RunOnce", "voci RunOnce, macchina e utente"),
        (r"HKCU:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run", "Run a 32 bit dell'utente"),
        (r"Policies\Explorer\Run", "Run imposto da policy"),
    ):
        assert fonte in SCRIPT, f"fonte non rilevata: {perche}"


def test_lo_stato_startupapproved_e_letto_per_scope():
    """HKCU e HKLM finivano in un dizionario piatto: due voci con lo stesso nome
    in rami diversi si sovrascrivevano lo stato a vicenda."""
    assert "$approved[($sa.s + '|' + \"$n\".ToLower())]" in SCRIPT
    assert "function _approvedState($scope, $name)" in SCRIPT


def test_una_voce_senza_record_startupapproved_e_attiva():
    """Windows scrive StartupApproved solo dopo il primo toggle dal Task
    Manager: 'nessun record' significa attiva, non 'stato sconosciuto'."""
    assert SCRIPT.count("if ($null -eq $st) { $st = $true }") >= 2


def test_il_conteggio_deriva_dalla_lista():
    """Erano due rilevazioni separate, con fonti e chiavi di registro diverse."""
    i = SCRIPT.index("function Get-StartupCount {")
    corpo = SCRIPT[i:SCRIPT.index("\n}", i)]
    assert "Get-StartupListCached" in corpo
    codice = "\n".join(r for r in corpo.split("\n") if not r.lstrip().startswith("#"))
    for propria_rilevazione in ("HKCU:", "HKLM:", "Get-ScheduledTask", "GetFolderPath"):
        assert propria_rilevazione not in codice, "il conteggio e' tornato a rilevare per conto suo"


def test_i_servizi_trigger_start_vengono_rilevati():
    assert "function Get-ServiceTriggers {" in SCRIPT
    assert "TriggerInfo" in SCRIPT
    assert "trigger_start" in SCRIPT


def test_impatto_avvio_dal_registro_eventi():
    """Gli eventi 101/103 sono la fonte da cui il Task Manager ricava la colonna
    'Impatto all'avvio'. Il log 100 era gia' usato per il tempo di boot."""
    assert "function Get-StartupImpact {" in SCRIPT
    assert "Id      = @(101, 103)" in SCRIPT
    assert "impact_ms" in SCRIPT


def test_nessun_taglio_su_ordine_non_garantito():
    """Ogni fonte aveva il suo `Select -First 15` su un ordine che PowerShell non
    garantisce: la lista cambiava tra due sync senza che cambiasse il PC."""
    i = SCRIPT.index("function Get-StartupList {")
    corpo = SCRIPT[i:SCRIPT.index("function Get-StartupListCached", i)]
    assert "-First 15" not in corpo
    assert "$sorted = @($al | Sort-Object" in corpo


def test_la_firma_non_si_verifica_dentro_systemroot():
    """La verifica Authenticode e' la voce piu' cara della rilevazione e su un
    binario dentro %SystemRoot% non aggiunge niente: il publisher lo danno i
    metadati. Fuori di li' resta, perche' e' l'unica fonte attendibile su chi ha
    scritto un eseguibile che parte da solo a ogni logon."""
    i = SCRIPT.index("function _fileInfo([string]$exe)")
    corpo = SCRIPT[i:SCRIPT.index("function _add(", i)]
    assert "if (-not ($winRoot -and $k.StartsWith($winRoot))) {" in corpo
    # Col separatore finale, se no una cartella tipo C:\WindowsOld passerebbe
    # per parte di Windows e salterebbe la verifica.
    assert r'''$winRoot = ("$env:SystemRoot".TrimEnd('\') + '\').ToLower()''' in SCRIPT


def test_firma_non_controllata_e_firma_invalida_non_si_confondono():
    """`signed` resta $null quando non abbiamo guardato: chi legge il campo non
    deve poter scambiare 'non controllato' per 'controllato e non valido'."""
    i = SCRIPT.index("function _fileInfo([string]$exe)")
    corpo = SCRIPT[i:SCRIPT.index("function _add(", i)]
    assert "$pub = $null; $disp = $null; $signed = $null" in corpo
    assert corpo.count("$signed = (") == 1, "signed viene assegnato fuori dal ramo che verifica"


def test_niente_comobject_per_risolvere_i_collegamenti():
    """Il pattern WScript.Shell fa scattare l'euristica anti-persistenza di
    Defender: i .lnk si leggono a byte."""
    assert "ComObject" not in SCRIPT and "WScript" not in SCRIPT
    assert "function _lnkTarget([string]$lnk)" in SCRIPT


# --- revisione del rilevatore ---

def test_l_agent_dichiara_la_revisione_del_rilevatore():
    assert "$script:STARTUP_REV = 2" in SCRIPT
    assert "startup_rev = $script:STARTUP_REV" in SCRIPT


def test_il_payload_accetta_la_revisione():
    assert SpecsInput(startup=[{"name": "x"}], startup_rev=2).startup_rev == 2
    # I client vecchi non la mandano: resta assente, e il backend si comporta
    # come prima invece di credere a una revisione inventata.
    assert SpecsInput(startup=[{"name": "x"}]).startup_rev is None


def test_senza_lista_nessun_evento_di_avvio():
    """Il backend passa `None` al posto della lista quando la revisione cambia:
    e' il modo in cui un cambio di rilevatore non diventa 'nuovi programmi'."""
    prev = {"data": {}, "startup": [{"name": "vecchia", "enabled": True}]}
    nuovi = [{"name": "vecchia", "enabled": True}, {"name": "mai_vista", "enabled": True}]
    assert any(e["kind"] == "startup_added" for e in build_change_events(prev, {}, nuovi))
    assert not [e for e in build_change_events(prev, {}, None) if e["kind"].startswith("startup")]


# --- analisi dei servizi ---

def _servizio(**kw):
    base = {"name": "scardsvr", "display": "Smart Card", "state": "Running",
            "start_mode": "Manual", "dependents": 0, "ram_mb": 4}
    return {**base, **kw}


def test_un_trigger_start_non_va_disattivato():
    normale = analyze_services([_servizio()])["items"][0]
    trigger = analyze_services([_servizio(trigger_start=True)])["items"][0]
    assert normale["recommendation"] == "disattiva"
    assert trigger["recommendation"] == "valuta"
    assert "richiesta" in trigger["condition"]["it"]


def test_la_ram_di_un_trigger_start_non_e_risparmiabile():
    """Contarla prometteva MB che non si liberano: il servizio non gira a vuoto."""
    assert analyze_services([_servizio()])["summary"]["ram_mb_saveable"] == 4
    assert analyze_services([_servizio(trigger_start=True)])["summary"]["ram_mb_saveable"] == 0


def test_i_flag_arrivano_alla_ui():
    it = analyze_services([_servizio(trigger_start=True, delayed=True)])["items"][0]
    assert it["trigger_start"] is True and it["delayed"] is True


def test_defender_e_rumore_anche_col_nome_italiano():
    assert is_startup_noise("Servizio Microsoft Defender Antivirus")
    assert is_startup_noise("Servizio di base di Microsoft Defender")
    # Le voci su cui l'utente puo' davvero intervenire restano visibili.
    assert not is_startup_noise("Razer Synapse Service")
    assert not is_startup_noise("MongoDB Server (MongoDB)")
