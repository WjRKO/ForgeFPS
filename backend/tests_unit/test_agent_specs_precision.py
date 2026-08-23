"""Precisione delle specs: prendere "il primo" non e' prendere quello giusto.

Tre campi venivano da tre insiemi diversi e nessuno li appaiava: la risoluzione
dal PRIMO Win32_VideoController della lista grezza, il refresh corrente dal
MASSIMO fra tutti i controller, il refresh massimo dal MASSIMO fra tutti i
monitor via EDID. Su una macchina con due schermi (240Hz primario + 165Hz
secondario, entrambi al loro massimo) il risultato memorizzato era
`refresh_hz=239, max_refresh_hz=75`: due numeri veri di due pannelli diversi,
che insieme non descrivono nessun computer esistente.

Stessa forma di errore per la RAM, dove velocita', tipo e produttore uscivano
tutti dal primo modulo - e un kit misto e' proprio il caso da segnalare.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT


def _get_specs():
    i = PS.index("function Get-Specs {")
    return PS[i:PS.index("\n  return $s\n}", i)]


# ---------- display ----------

def test_risoluzione_e_refresh_vengono_dallo_stesso_schermo():
    corpo = _get_specs()
    assert "Get-DisplayInfo" in corpo, "il blocco display unificato non c'e'"
    assert "$primario.hz" in corpo and "$primario.max_hz" in corpo, \
        "corrente e massimo devono uscire dallo stesso pannello"
    assert "$primario.width" in corpo, "anche la risoluzione viene dallo schermo primario"


def test_il_refresh_non_e_piu_il_massimo_fra_i_controller():
    """`Sort-Object CurrentRefreshRate -Descending | Select -First 1` prendeva il
    controller piu' veloce, che con due schermi non e' quello primario."""
    corpo = _get_specs()
    assert "Sort-Object CurrentRefreshRate" not in corpo


def test_la_risoluzione_non_esce_piu_dalla_lista_grezza():
    """`Win32_VideoController | Select -First 1` non filtra gli adattatori
    virtuali (Parsec, IDD) e non ordina: poteva dare la iGPU mentre `gpu`
    riportava la discreta. Il ripiego usa la lista gia' ordinata e filtrata."""
    corpo = _get_specs()
    assert not re.search(r"Get-CimInstance Win32_VideoController \| Select-Object -First 1", corpo)
    assert "$vcSorted | Where-Object { $_.CurrentHorizontalResolution -gt 0 }" in corpo


def test_il_massimo_si_cerca_alla_risoluzione_attuale():
    """Un pannello che fa 240Hz a 1080p ma 144Hz a 1440p non sta andando piano
    se e' a 1440p: confrontare col massimo assoluto darebbe un falso allarme."""
    disp = PS[PS.index("function Get-DisplayInfo"):PS.index("function Get-HwNameKey")]
    assert "$md.dmPelsWidth -eq $w -and [int]$md.dmPelsHeight -eq $h" in disp


def test_la_stringa_nulla_del_marshalling_e_gestita():
    """In PowerShell `$null` passato a un parametro string diventa una stringa
    VUOTA, ed EnumDisplayDevices con stringa vuota fallisce: senza
    [NullString]::Value la funzione trova zero schermi e non se ne accorge
    nessuno, perche' il ripiego copre il buco in silenzio."""
    disp = PS[PS.index("function Get-DisplayInfo"):PS.index("function Get-HwNameKey")]
    assert "[NullString]::Value" in disp


def test_l_edid_si_usa_solo_con_un_monitor_solo():
    """L'EDID da' un massimo su TUTTI i monitor: appaiarlo al refresh corrente di
    un altro pannello e' esattamente il difetto da cui si parte."""
    corpo = _get_specs()
    assert "$edid.Count -eq 1" in corpo


# ---------- RAM ----------

def test_la_ram_si_guarda_tutta_non_solo_il_primo_banco():
    corpo = _get_specs()
    assert "$pm1" not in corpo, "il primo modulo non e' piu' la fonte di niente"
    assert "$pmAll" in corpo
    assert "Measure-Object -Minimum" in corpo, \
        "il canale gira alla velocita' del modulo piu' lento, non del banco in slot 1"


def test_un_kit_misto_viene_dichiarato():
    corpo = _get_specs()
    assert "ram_mismatch" in corpo
    for atteso in ("frequenze diverse", "tipi diversi", "produttori diversi"):
        assert atteso in corpo


# ---------- confidenza ----------

def test_la_confidenza_dice_anche_se_le_fonti_erano_d_accordo():
    """Un conteggio non e' una confidenza: due fonti che si contraddicono
    valevano quanto due che confermano."""
    corpo = _get_specs()
    for campo in ("sources =", "agree =", "conflict ="):
        assert campo in corpo
    assert "$cpuAgree" in corpo and "$gpuAgree" in corpo and "$ramAgree" in corpo


def test_il_disaccordo_della_cpu_non_sparisce_piu():
    """Il conflitto veniva risolto prendendo la stringa piu' lunga, in silenzio."""
    corpo = _get_specs()
    assert "Get-HwNameKey $s.cpu" in corpo
    assert "$cpuConflict = " in corpo


def test_la_ram_confronta_davvero_le_due_fonti():
    """`$ramSources = 2  # le due fonti concordano` era un commento, non un
    controllo: la somma delle capacita' dei moduli non veniva mai confrontata
    col totale di sistema."""
    corpo = _get_specs()
    assert "$capSum" in corpo
    assert re.search(r"\$ramAgree = \(\[math\]::Abs\(\$capGb - \$ram\) -le 1\)", corpo)


def test_cio_che_non_si_puo_verificare_non_si_dichiara_concorde():
    """Lo storage non ha due fonti da confrontare sullo stesso valore: `agree`
    resta nullo, che e' diverso da "verificato e concorde"."""
    corpo = _get_specs()
    assert "storage = @{ sources = $storageSources; agree = $null;" in corpo


def test_il_nome_della_cpu_non_porta_con_se_il_padding():
    """ProcessorNameString arriva imbottito di spazi: finivano nella pagina, nei
    prompt dell'AI e nella chiave di aggregazione della flotta."""
    corpo = _get_specs()
    assert re.search(r"\$s\.cpu = \(\"\$\(\$s\.cpu\)\" -replace '\\s\+', ' '\)\.Trim\(\)", corpo)


# ---------- lato web ----------

def _mypc():
    percorso = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "frontend", "src", "pages", "MyPc.jsx")
    if not os.path.exists(percorso):
        import pytest
        pytest.skip("frontend non presente")
    with open(percorso, encoding="utf-8") as f:
        return f.read()


def test_il_web_accetta_anche_gli_agent_vecchi():
    """La forma vecchia di hw_confidence e' un numero. Gli agent in giro non si
    aggiornano tutti insieme, e un numero non puo' dire se le fonti erano
    d'accordo: vale "accordo non verificato", non "concordi"."""
    src = _mypc()
    assert "function hwConf" in src
    assert 'typeof valore === "number"' in src
    assert "agree: null" in src


def test_il_badge_mostra_il_disaccordo():
    src = _mypc()
    assert 'c?.agree === false' in src
    assert "hw_sources_conflict" in src


def test_il_clock_e_dichiarato_come_base():
    """MaxClockSpeed di WMI e' il clock base: scritto "3.4GHz" accanto al nome
    della CPU veniva letto come la frequenza in gioco."""
    assert "GHz base" in _mypc()
