"""Cosa si puo' spegnere all'avvio, e chi lo spegne davvero.

Due cose che vanno tenute insieme. La prima e' il verdetto: la lista delle voci
di avvio non e' una lista di cose da togliere — dentro ci sono l'antivirus, il
driver audio e il touchpad, e "disattiva tutto" e' il consiglio che lascia un
utente senza suono. La seconda e' l'esecuzione: il browser non scrive nel
registro del PC, quindi il clic diventa un'azione in attesa che l'agent ritira e
applica, e il verdetto va ricontrollato lato server perche' un payload si
modifica.

Il caso che ha guidato la forma delle regole: sotto `ASUS\\ArmouryDevice\\` ci
stanno sia la suite RGB, spegnibile, sia il motore di riduzione del rumore e
l'agente di alimentazione del mouse, che non lo sono. Finche' il match guardava
anche il percorso, bastava la cartella per dichiararli tutti sicuri.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent
from startup_kb import classify_startup, annotate_startup, summarize_startup

SCRIPT = ps_agent.PS_SCRIPT


def _corpo(firma: str) -> str:
    """Il corpo di una funzione dello script agent, dalla firma alla graffa di
    chiusura in colonna zero."""
    i = SCRIPT.index(firma)
    return SCRIPT[i:SCRIPT.index("\n}\n", i)]


def _voce(**kw):
    base = {"name": "Qualcosa", "display": "", "publisher": "", "path": "", "command": "", "source": "registry"}
    return {**base, **kw}


# --- il verdetto ---

def test_lo_sconosciuto_non_e_mai_sicuro():
    """Un default ottimista qui significa proporre di spegnere qualcosa che
    nessuno ha guardato."""
    v = classify_startup(_voce(name="QualcosaDiMaiVisto", publisher="Ditta Ignota"))
    assert v["safety"] == "valuta"
    assert v["can_disable"] is True


def test_un_updater_si_spegne():
    v = classify_startup(_voce(name="Update", display="Discord Updater", publisher="Discord Inc."))
    assert v["safety"] == "sicuro"


def test_driver_e_antivirus_non_si_toccano():
    for voce in (
        _voce(name="RtkAudUService", display="Realtek HD Audio Universal Service"),
        _voce(name="SecurityHealth", display="Windows Security notification icon"),
        _voce(name="XonarSE", display="Xear Audio Center"),
        _voce(name="NVIDIA LocalSystem Container", source="service",
              path=r"C:\Program Files\NVIDIA Corporation\NvContainer\nvcontainer.exe"),
    ):
        v = classify_startup(voce)
        assert v["safety"] == "critico", voce["name"]
        assert v["can_disable"] is False


def test_il_percorso_non_rende_sicuro_niente():
    """La regressione vera: un componente che sta nella cartella di una suite
    spegnibile non e' per questo spegnibile lui."""
    suite = classify_startup(_voce(name="Armoury Crate Service", source="service"))
    assert suite["safety"] == "sicuro"
    dentro_la_stessa_cartella = classify_startup(_voce(
        name="NoiseCancelingEngine", source="task",
        path=r"C:\Program Files (x86)\ASUS\ArmouryDevice\dll\MBLedSDK\NoiseCancelingEngine.exe"))
    assert dentro_la_stessa_cartella["safety"] != "sicuro"


def test_il_percorso_conta_quando_porta_a_essere_prudenti():
    """L'asimmetria e' voluta: verso il critico si guarda tutto, verso il sicuro
    solo l'identita'."""
    v = classify_startup(_voce(name="AsIO3", source="service",
                               path=r"C:\Program Files\ASUS\AsIO3 Driver\asio3.exe"))
    assert v["safety"] == "critico"


def test_la_sincronia_cloud_si_valuta_non_si_spegne_al_buio():
    v = classify_startup(_voce(name="OneDrive", display="Microsoft OneDrive"))
    assert v["safety"] == "valuta"
    assert v["condition"] and "sincronizzare" in v["condition"]["it"]


def test_un_servizio_con_dipendenti_scende_a_valuta():
    """Spegnendolo si spengono anche gli altri, e l'utente vede rompersi
    qualcosa che non ha toccato."""
    solo = classify_startup(_voce(name="Steam Client Service", source="service", dependents=0))
    con_dipendenti = classify_startup(_voce(name="Steam Client Service", source="service", dependents=3))
    assert solo["safety"] == "sicuro"
    assert con_dipendenti["safety"] == "valuta"
    assert "dipendono" in con_dipendenti["condition"]["it"]


def test_il_riepilogo_conta_solo_le_voci_attive_e_visibili():
    lista = [
        _voce(name="Update", display="Steam Update", enabled=True, ram_mb=40),
        _voce(name="Steam", enabled=True, ram_mb=100),          # sicuro
        _voce(name="OneDrive", enabled=True, ram_mb=90),        # valuta
        _voce(name="RtkAudUService", enabled=True),             # critico
        _voce(name="Spotify", enabled=False, ram_mb=300),       # gia' spenta
        _voce(name="SecurityHealth", enabled=True, noise=True),  # nascosta
    ]
    annotate_startup(lista)
    r = summarize_startup(lista)
    assert r["attive"] == 4
    assert r["sicuro"] == 2 and r["valuta"] == 1 and r["critico"] == 1
    assert r["ram_mb_sicuri"] == 140


# --- l'esecuzione ---

def test_il_backend_rifiuta_lo_spegnimento_di_una_voce_critica():
    """Il verdetto non e' un consiglio che il client possa ignorare: chi cambia
    il payload deve trovare il controllo anche dall'altra parte."""
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "pc.py"), encoding="utf-8").read()
    i = src.index('@r.post("/startup/toggle")')
    corpo = src[i:src.index('@r.get("/startup/actions")', i)]
    assert 'classify_startup(voce)' in corpo
    assert 'if not payload.enable and not verdetto["can_disable"]:' in corpo
    assert "raise HTTPException" in corpo


def test_l_agent_non_si_fida_della_lista_che_arriva_dalla_rete():
    """Difesa in profondita': l'agent scrive nel registro, e non lo fa su una
    voce di sicurezza qualunque cosa dica il backend."""
    assert "$script:STARTUP_INTOCCABILI" in SCRIPT
    assert "function Test-StartupIntoccabile($voce)" in SCRIPT
    i = SCRIPT.index("function Set-StartupEntry($voce, $enable) {")
    corpo = SCRIPT[i:SCRIPT.index("function Get-StartupActionEntry", i)]
    assert corpo.index("Test-StartupIntoccabile") < corpo.index("switch"), \
        "il controllo deve venire prima di qualunque scrittura"
    assert "Test-ForbiddenSvc" in corpo


def test_chi_serve_admin_lo_dice_prima_di_provarci():
    """Servizi, attivita' pianificate e cartella comune vivono in HKLM: senza
    elevazione Windows risponde "Accesso negato", che non dice all'utente cosa
    fare. Le voci sue - Run in HKCU, cartella personale, app dello Store - non
    chiedono niente a nessuno."""
    assert "function Test-StartupServeAdmin($voce) {" in SCRIPT
    i = SCRIPT.index("function Set-StartupEntry($voce, $enable) {")
    corpo = SCRIPT[i:SCRIPT.index("function Get-StartupActionEntry", i)]
    assert "(Test-StartupServeAdmin $voce) -and -not (Test-Admin)" in corpo
    assert corpo.index("Test-StartupServeAdmin") < corpo.index("switch")


def test_lo_spegnimento_usa_il_formato_del_task_manager():
    """Due byte diversi funzionano lo stesso, ma la voce apparirebbe 'mai
    toccata' a chi la guarda dal Task Manager."""
    i = SCRIPT.index("function Set-StartupApproved(")
    corpo = SCRIPT[i:SCRIPT.index("function Set-StartupEntry(", i)]
    assert "$b = New-Object byte[] 12" in corpo
    assert "$b[0] = $(if ($enable) { 2 } else { 3 })" in corpo
    assert "ToFileTimeUtc()" in corpo
    assert "-PropertyType Binary" in corpo


def test_ogni_fonte_ha_il_suo_modo_di_spegnersi():
    i = SCRIPT.index("function Set-StartupEntry($voce, $enable) {")
    corpo = SCRIPT[i:SCRIPT.index("function Get-StartupActionEntry", i)]
    for fonte, come in (("'service'", "Set-Service"), ("'task'", "Disable-ScheduledTask"),
                        ("'uwp'", "AppModel"), ("default", "Set-StartupApproved")):
        assert fonte in corpo and come in corpo, f"fonte {fonte} senza {come}"


def test_le_azioni_si_applicano_prima_di_rilevare():
    """Al contrario, la dashboard riceverebbe la fotografia di prima e la voce
    appena spenta risulterebbe ancora accesa fino al sync successivo."""
    i = SCRIPT.index("# default: sync (safe)")
    coda = SCRIPT[i:]
    assert coda.index("Invoke-StartupActions") < coda.index("$specs = Get-Specs")


def test_la_cache_della_lista_scade_dopo_un_azione():
    i = SCRIPT.index("function Invoke-StartupActions {")
    corpo = SCRIPT[i:SCRIPT.index("\n}\n", i)]
    assert "$script:__ffStartupAt = $null" in corpo


def test_l_azione_finisce_nel_journal():
    """"Cosa mi hai fatto al PC" e' la domanda da cui dipende la fiducia: una
    modifica decisa dal browser ha piu' bisogno di essere registrata, non meno."""
    corpo = _corpo("function Invoke-StartupBatch($azioni) {")
    assert "Write-Journal" in corpo
    assert "startup-off" in corpo and "startup-on" in corpo


# --- l'elevazione ---
#
# Meta' delle voci di avvio di un PC vero (servizi, attivita' pianificate,
# cartella comune) stanno in HKLM. Senza elevazione la dashboard le mostrava,
# lasciava cliccare e poi falliva: l'agent adesso si rilancia elevato per
# quelle, e solo per quelle.

def test_le_voci_utente_non_aspettano_il_prompt():
    """Una sola voce di sistema in coda non deve tenere in ostaggio le altre
    dietro una finestra di Windows che l'utente magari non guarda nemmeno."""
    corpo = _corpo("function Invoke-StartupActions {")
    assert "$subito" in corpo and "$daElevare" in corpo
    assert corpo.index("Invoke-StartupBatch @($subito)") < corpo.index("Start-StartupElevato"), \
        "le voci dell'utente vanno applicate prima di chiedere l'elevazione"


def test_una_voce_intoccabile_non_fa_comparire_il_prompt():
    """Chiedere l'amministratore per poi rifiutare comunque la voce sarebbe un
    prompt chiesto per niente."""
    corpo = _corpo("function Invoke-StartupActions {")
    assert "(Test-StartupServeAdmin $voce) -and -not (Test-StartupIntoccabile $voce)" in corpo


def test_se_lutente_nega_il_permesso_la_dashboard_lo_scopre():
    """Un'azione appesa per sempre e' peggio di un fallimento spiegato: se
    l'elevazione non c'e' stata, si prova lo stesso e l'errore torna indietro."""
    corpo = _corpo("function Invoke-StartupActions {")
    i = corpo.index("if (Start-StartupElevato)")
    assert "Invoke-StartupBatch @($daElevare)" in corpo[i:]


def test_la_copia_elevata_non_puo_richiamarne_unaltra():
    """Se la copia elevata non risultasse elevata (UAC spento, criteri di
    gruppo) senza questo si rilancerebbe all'infinito."""
    assert "param([switch]$NoElevate)" in SCRIPT
    corpo = _corpo("function Invoke-StartupActions {")
    assert "$possoElevare = (-not $NoElevate) -and (-not (Test-Admin))" in corpo
    modo = SCRIPT[SCRIPT.index("if ($MODE -eq 'startup') {"):]
    modo = modo[:modo.index("\n}\n")]
    assert "Invoke-StartupActions -NoElevate" in modo


def test_la_copia_elevata_fa_solo_le_azioni():
    """E' una finestra che si apre da sola: deve chiudersi subito, non mettersi
    a rilevare hardware."""
    modo = SCRIPT[SCRIPT.index("if ($MODE -eq 'startup') {"):]
    modo = modo[:modo.index("\n}\n")]
    for roba in ("Get-Specs", "Get-Health", "Send-Data"):
        assert roba not in modo, f"la modalita' startup non deve fare {roba}"
    assert "return" in modo


def test_il_sync_aspetta_la_finestra_elevata():
    """Se no fotografa il PC di prima e la voce appena spenta risulta accesa."""
    corpo = _corpo("function Start-StartupElevato {")
    assert "-Verb RunAs" in corpo and "-PassThru" in corpo
    assert "WaitForExit(" in corpo
    assert "'-Mode','startup'" in corpo
