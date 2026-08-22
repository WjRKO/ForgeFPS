"""Il piano di un tweak: cosa cambierebbe, prima di cambiarlo.

Una descrizione dice cosa fa un tweak; il piano dice cosa succede a QUESTA
macchina. "Disattiva l'accelerazione del mouse" e "MouseSpeed: 1 -> 0" dicono la
stessa cosa, ma solo la seconda si puo' controllare — e chi accetta che un
programma gli scriva nel registro ha diritto di controllare prima, non dopo.

Il rischio di un piano scritto a mano e' che dica una cosa e l'apply ne faccia
un'altra: un piano che mente e' peggio di nessun piano. Il test centrale qui
sotto (`test_ogni_scrittura_dichiarata_ha_la_sua_riga`) legge le chiamate a
Set-Reg dentro le funzioni di apply e verifica che ognuna abbia la propria riga
nel piano. Non copre le scritture costruite a runtime (cicli su tutte le schede
di rete, chiavi che dipendono dal PNP della GPU): quelle restano dichiarate a
mano, e il piano le racconta a parole.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML


def _tweaks():
    """Ogni voce dell'array dei tweak, come testo."""
    i = PS.index("$script:TWEAKS = @(")
    fine = PS.index("\n)\n", i)
    corpo = PS[i:fine]
    pezzi = corpo.split("\n  @{ cat=")[1:]
    return ["@{ cat=" + p for p in pezzi]


TWEAKS = _tweaks()


def _apply_di(voce):
    m = re.search(r"apply=\{ ([A-Za-z-]+)", voce)
    return m.group(1) if m else None


def _corpo_funzione(nome):
    i = PS.index("function %s" % nome)
    # la funzione finisce alla prima riga che comincia con '}' a colonna zero,
    # oppure e' tutta su una riga sola
    fine = PS.index("\n}", i)
    unaRiga = PS.index("\n", i)
    return PS[i:fine] if fine < PS.index("\nfunction ", i + 1) else PS[i:unaRiga]


_LIT = r"'([^']*)'"


def _scritture_risolte(corpo):
    """Le coppie path::name dei Set-Reg con argomenti risolvibili staticamente.

    Risolve le variabili assegnate a un letterale nella stessa funzione e le
    interpolazioni della forma "$var\\resto": sono le due forme che le apply
    usano davvero. Tutto il resto (PSPath di un ciclo, path costruiti dal PNP
    della GPU) resta fuori: e' dichiarato a mano nel piano.
    """
    var = {}
    for m in re.finditer(r"\$(\w+)\s*=\s*" + _LIT, corpo):
        var[m.group(1)] = m.group(2)
    for m in re.finditer(r'\$(\w+)\s*=\s*"\$(\w+)([^"]*)"', corpo):
        if m.group(2) in var:
            var[m.group(1)] = var[m.group(2)] + m.group(3)

    def risolvi(tok):
        tok = tok.strip()
        m = re.fullmatch(_LIT, tok)
        if m:
            return m.group(1)
        m = re.fullmatch(r"\$(\w+)", tok)
        if m:
            return var.get(m.group(1))
        m = re.fullmatch(r'"\$(\w+)([^"]*)"', tok)
        if m and m.group(1) in var:
            return var[m.group(1)] + m.group(2)
        return None

    fuori, dentro = 0, []
    for m in re.finditer(r"Set-Reg\s+(\S+|'[^']*')\s+'([^']+)'\s+'(\w+)'\s+(\S+)", corpo):
        path = risolvi(m.group(1))
        if path is None:
            fuori += 1
        else:
            valore = m.group(4).strip().rstrip("}").strip()
            if valore.startswith("'") and valore.endswith("'"):
                valore = valore[1:-1]
            dentro.append((path, m.group(2), valore))
    return dentro, fuori


# ---------- il legame fra piano e apply ----------

def test_ogni_tweak_ha_un_piano():
    """Un tweak senza piano ricade sulla descrizione: e' una via d'uscita per i
    casi difficili, non un'abitudine."""
    senza = [t.split("id='")[1].split("'")[0] for t in TWEAKS if "plan={" not in t]
    assert not senza, "tweak senza piano: %s" % senza


def test_ogni_scrittura_dichiarata_ha_la_sua_riga():
    """Il cuore: quello che l'apply scrive per certo, il piano lo dice. Se
    qualcuno aggiunge un Set-Reg e si dimentica la riga, l'utente vedrebbe un
    diff che promette meno di quello che succede."""
    mancanti = []
    for voce in TWEAKS:
        nome = _apply_di(voce)
        if not nome:
            continue
        scritture, _ = _scritture_risolte(_corpo_funzione(nome))
        for path, name, _valore in scritture:
            if ("'%s' '%s'" % (path, name)) not in voce:
                mancanti.append("%s -> %s::%s" % (nome, path, name))
    assert not mancanti, "scritture senza riga nel piano:\n  " + "\n  ".join(mancanti)


def test_il_piano_promette_lo_stesso_valore_che_l_apply_scrive():
    """La chiave giusta col valore sbagliato e' peggio della chiave mancante: e'
    il piano che dice "diventera 1" mentre l'apply scrive 5. E da quando l'esito
    di un tweak si verifica RILEGGENDO il piano, un valore sbagliato qui fa
    dichiarare fallito un tweak riuscito."""
    sbagliati = []
    for voce in TWEAKS:
        nome = _apply_di(voce)
        if not nome:
            continue
        scritture, _ = _scritture_risolte(_corpo_funzione(nome))
        for path, name, valore in scritture:
            m = re.search(r"PlReg\s+'%s'\s+'%s'\s+'([^']*)'" % (re.escape(path), re.escape(name)), voce)
            if m and m.group(1) != valore:
                sbagliati.append("%s %s::%s -> apply scrive '%s', il piano promette '%s'"
                                 % (nome, path, name, valore, m.group(1)))
    assert not sbagliati, "valori divergenti fra piano e apply:\n  " + "\n  ".join(sbagliati)


def test_il_piano_non_promette_chiavi_che_l_apply_non_tocca():
    """La direzione opposta, dove si puo' controllare: se l'apply e' fatta di
    sole scritture risolvibili, il piano non deve avere righe in piu'."""
    inventate = []
    for voce in TWEAKS:
        nome = _apply_di(voce)
        if not nome:
            continue
        scritture, fuori = _scritture_risolte(_corpo_funzione(nome))
        if fuori or not scritture:
            continue  # apply con scritture costruite a runtime: non confrontabile
        attese = {"'%s' '%s'" % (p, n) for p, n, _v in scritture}
        for m in re.finditer(r"PlReg\s+('[^']*')\s+('[^']*')", voce):
            coppia = "%s %s" % (m.group(1), m.group(2))
            if coppia not in attese:
                inventate.append("%s: %s" % (nome, coppia))
    assert not inventate, "righe di piano senza scrittura corrispondente:\n  " + "\n  ".join(inventate)


# ---------- come e' fatto un piano ----------

def test_il_prima_non_si_dichiara_mai():
    """Il valore attuale si legge sulla macchina. Dichiararlo vorrebbe dire
    scrivere nel piano quello che ci si aspetta di trovare, che e' esattamente
    il modo in cui un diff comincia a mentire."""
    i = PS.index("function PlReg")
    corpo = PS[i:PS.index("function PlSvc")]
    assert "$cur = Get-RegVal $path $name" in corpo
    assert "'non impostata'" in corpo


def test_una_riga_che_non_cambia_niente_lo_dice():
    """Lo stato di un tweak lo decide una chiave sola, ma il tweak ne scrive
    parecchie: senza questo, il piano prometteva '0 -> 0'."""
    assert 'same = ($null -ne $cur -and "$cur" -eq "$next")' in PS
    assert "function planChanging(p) { return p.filter(r => !r.same); }" in GUI
    assert "gia a posto" in GUI


def test_il_piano_si_calcola_solo_per_chi_deve_cambiare():
    """Per un tweak gia' ottimale sarebbe una lista vuota pagata con letture di
    registro; per uno non applicabile una promessa che non si mantiene."""
    assert "plan = $(if ($st.code -eq 'todo' -and -not $skip) { @(Get-TwPlan $t) } else { @() })" in PS


def test_un_piano_che_esplode_non_porta_via_la_scheda():
    i = PS.index("function Get-TwPlan")
    corpo = PS[i:PS.index("function Get-TwState")]
    assert "try { return @(& $t.plan) } catch { return @() }" in corpo


# ---------- la scheda ----------

def test_il_diff_prende_il_posto_della_descrizione():
    """La descrizione vale per tutti i PC, il diff per questo. Dove il diff
    c'e', la riga 'Modifica' non serve piu'."""
    assert "${planRows(t) || `<div class=\"row\">" in GUI


def test_dove_il_prima_manca_si_mostra_solo_il_dopo():
    """Valori che non si leggono a buon mercato: meglio meta' vera che una
    freccia inventata."""
    i = GUI.index("function planDiff(r)")
    corpo = GUI[i:GUI.index("function planRows")]
    assert 'if (!now) return `<span class="plan-arrow">' in corpo


def test_la_lista_compatta_mostra_una_riga_sola():
    assert "function planSummary(t)" in GUI
    assert ".card.compact .plan { display: none; }" in GUI
    assert ".card.compact.expanded .plan { display: block; }" in GUI
