"""Il giro completo dello spegnimento di una voce di avvio, via HTTP.

Le singole parti erano gia' coperte: il verdetto in `tests_unit`, la scrittura
nel registro provata a mano sul PC vero. Quello che mancava e' il collegamento,
che e' anche il punto dove le cose si rompono davvero:

    dashboard  ->  POST /startup/toggle        (azione in attesa)
               ->  GET  /agent/startup-actions (l'agent la ritira)
               ->  POST /agent/startup-actions/result (l'agent riferisce)
               ->  GET  /startup/actions       (la dashboard vede l'esito)

Qui l'agent non c'e': le sue due chiamate le fa il test col token dell'agent,
che e' esattamente quello che fa `Invoke-StartupActions` in `ps_agent.py`.
Quello che si verifica e' il contratto fra i quattro endpoint - che l'id
consegnato torni indietro riconoscibile, che l'azione si chiuda una volta sola,
che il verdetto critico non si aggiri modificando il payload.

La suite va lanciata in seriale e contro un database dedicato: questi test
scrivono nel `pc_specs` dell'account admin.
"""
import os

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@boostpc.io")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Due voci scelte per il verdetto che devono ricevere, non a caso: un updater e'
# "sicuro" per le regole di startup_kb, il pannello Realtek e' "critico" perche'
# e' un driver audio. Se quelle regole cambiassero, questi test lo dicono.
VOCE_SPEGNIBILE = {
    "name": "DiscordUpdate", "display": "Discord Updater",
    "publisher": "Discord Inc.", "source": "registry",
    "location": r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "path": r"C:\Users\tester\AppData\Local\Discord\Update.exe",
    "command": r"C:\Users\tester\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "enabled": True, "ram_mb": 120,
}
VOCE_CRITICA = {
    "name": "RTHDVCPL", "display": "Realtek HD Audio Manager",
    "publisher": "Realtek Semiconductor", "source": "registry",
    "location": r"HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
    "path": r"C:\Program Files\Realtek\Audio\HDA\RtkNGUI64.exe",
    "command": r"C:\Program Files\Realtek\Audio\HDA\RtkNGUI64.exe -s",
    "enabled": True, "ram_mb": 40,
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login {r.status_code}: {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def agent(agent_token):
    """Sessione che si presenta come l'agent, non come il browser."""
    s = requests.Session()
    s.headers.update({"X-Agent-Token": agent_token})
    return s


@pytest.fixture
def avvio_noto(session, agent):
    """Rimette il PC in uno stato noto: due voci, nessuna azione in sospeso.

    Non e' cortesia verso i test successivi: senza, il primo che lascia
    un'azione appesa fa fallire il secondo per un motivo che non c'entra.
    """
    r = agent.post(f"{BASE_URL}/api/agent/report-specs",
                   json={"startup": [dict(VOCE_SPEGNIBILE), dict(VOCE_CRITICA)]})
    assert r.status_code == 200, r.text
    session.delete(f"{BASE_URL}/api/startup/actions")
    # La dashboard e l'agent devono guardare lo stesso documento: se il filtro
    # per device li separasse, tutto il resto fallirebbe in modo incomprensibile.
    specs = session.get(f"{BASE_URL}/api/pc-specs")
    assert specs.status_code == 200, specs.text
    nomi = [v.get("name") for v in (specs.json() or {}).get("startup") or []]
    assert VOCE_SPEGNIBILE["name"] in nomi, (
        "l'agent e la dashboard non vedono lo stesso PC: " + str(nomi))
    yield
    session.delete(f"{BASE_URL}/api/startup/actions")


def _stato(session):
    r = session.get(f"{BASE_URL}/api/startup/actions")
    assert r.status_code == 200, r.text
    return r.json()


def _voce_a_schermo(session, nome):
    specs = session.get(f"{BASE_URL}/api/pc-specs")
    assert specs.status_code == 200, specs.text
    return next(v for v in specs.json()["startup"] if v["name"] == nome)


class TestGiroCompleto:
    def test_dal_clic_allesito(self, session, agent, avvio_noto):
        """Il percorso che fa un utente: clic, sync dell'agent, esito a schermo."""
        t = session.post(f"{BASE_URL}/api/startup/toggle",
                         json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                               "enable": False})
        assert t.status_code == 200, t.text
        assert t.json()["pending"] is True
        assert t.json()["safety"] == "sicuro"

        # In attesa: la scheda deve gia' mostrare il bottone spento, se no
        # sembra che il clic non abbia fatto niente.
        assert _voce_a_schermo(session, VOCE_SPEGNIBILE["name"]).get("pending_enable") is False

        # L'agent ritira l'azione: e' la stessa chiamata di Invoke-StartupActions.
        a = agent.get(f"{BASE_URL}/api/agent/startup-actions")
        assert a.status_code == 200, a.text
        azioni = a.json()["actions"]
        assert len(azioni) == 1, azioni
        azione = azioni[0]
        assert azione["enable"] is False
        # L'entry viaggia intera: l'agent decide dove scrivere leggendo `source`
        # e `location`, non ha altro modo di saperlo.
        assert azione["entry"]["name"] == VOCE_SPEGNIBILE["name"]
        assert azione["entry"]["location"] == VOCE_SPEGNIBILE["location"]

        r = agent.post(f"{BASE_URL}/api/agent/startup-actions/result",
                       json={"results": [{"id": azione["id"], "ok": True, "msg": ""}]})
        assert r.status_code == 200, r.text
        assert r.json()["updated"] == 1

        stato = _stato(session)
        assert stato["pending"] == []
        fatta = next(x for x in stato["recent"] if x["name"] == VOCE_SPEGNIBILE["name"])
        assert fatta["status"] == "done"

        # Chiusa l'azione, la scheda non deve piu' mostrare l'attesa.
        assert "pending_enable" not in _voce_a_schermo(session, VOCE_SPEGNIBILE["name"])

    def test_un_fallimento_arriva_a_schermo(self, session, agent, avvio_noto):
        """Il caso dell'elevazione mancante: l'agent non ce la fa e lo dice.

        Il messaggio deve arrivare all'utente: e' l'unica cosa che gli spiega
        perche' il programma e' ancora li'.
        """
        session.post(f"{BASE_URL}/api/startup/toggle",
                     json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                           "enable": False})
        azione = agent.get(f"{BASE_URL}/api/agent/startup-actions").json()["actions"][0]
        motivo = "servono i permessi di amministratore: rilancia FrameForge come amministratore"
        agent.post(f"{BASE_URL}/api/agent/startup-actions/result",
                   json={"results": [{"id": azione["id"], "ok": False, "msg": motivo}]})

        stato = _stato(session)
        assert stato["pending"] == []
        fallita = next(x for x in stato["recent"] if x["name"] == VOCE_SPEGNIBILE["name"])
        assert fallita["status"] == "failed"
        assert fallita["msg"] == motivo

        # E deve finire sulla scheda, non solo nel database: senza, il bottone
        # torna com'era e sembra che il clic non sia mai avvenuto.
        assert _voce_a_schermo(session, VOCE_SPEGNIBILE["name"])["last_error"] == motivo

    def test_un_errore_vecchio_non_resta_appeso(self, session, agent, avvio_noto):
        """Riprovato e riuscito: l'errore del tentativo prima esce di scena."""
        for esito in (False, True):
            session.post(f"{BASE_URL}/api/startup/toggle",
                         json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                               "enable": False})
            azione = agent.get(f"{BASE_URL}/api/agent/startup-actions").json()["actions"][0]
            agent.post(f"{BASE_URL}/api/agent/startup-actions/result",
                       json={"results": [{"id": azione["id"], "ok": esito,
                                          "msg": "" if esito else "serve l'amministratore"}]})
        assert "last_error" not in _voce_a_schermo(session, VOCE_SPEGNIBILE["name"])

    def test_lazione_si_chiude_una_volta_sola(self, session, agent, avvio_noto):
        """Un agent che rimanda lo stesso esito non deve confondere il conto."""
        session.post(f"{BASE_URL}/api/startup/toggle",
                     json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                           "enable": False})
        azione = agent.get(f"{BASE_URL}/api/agent/startup-actions").json()["actions"][0]
        corpo = {"results": [{"id": azione["id"], "ok": True, "msg": ""}]}
        assert agent.post(f"{BASE_URL}/api/agent/startup-actions/result",
                          json=corpo).json()["updated"] == 1
        assert agent.post(f"{BASE_URL}/api/agent/startup-actions/result",
                          json=corpo).json()["updated"] == 0
        # E l'azione chiusa non torna nella coda dell'agent.
        assert agent.get(f"{BASE_URL}/api/agent/startup-actions").json()["actions"] == []

    def test_ripensarci_non_accoda_due_azioni(self, session, agent, avvio_noto):
        """Spegni, riaccendi, rispegni: all'agent arriva l'ultima volonta'."""
        for enable in (False, True, False):
            r = session.post(f"{BASE_URL}/api/startup/toggle",
                             json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                                   "enable": enable})
            assert r.status_code == 200, r.text
        azioni = agent.get(f"{BASE_URL}/api/agent/startup-actions").json()["actions"]
        assert len(azioni) == 1, azioni
        assert azioni[0]["enable"] is False


class TestQuelloCheNonDevePassare:
    def test_una_voce_critica_non_si_spegne(self, session, avvio_noto):
        """Il verdetto non e' un consiglio che il client puo' ignorare."""
        r = session.post(f"{BASE_URL}/api/startup/toggle",
                         json={"name": VOCE_CRITICA["name"], "source": "registry",
                               "enable": False})
        assert r.status_code == 400, r.text
        assert _stato(session)["pending"] == []

    def test_una_voce_critica_si_puo_riaccendere(self, session, avvio_noto):
        """Il divieto e' sullo spegnere, non sul rimettere le cose com'erano."""
        r = session.post(f"{BASE_URL}/api/startup/toggle",
                         json={"name": VOCE_CRITICA["name"], "source": "registry",
                               "enable": True})
        assert r.status_code == 200, r.text

    def test_una_voce_che_non_esiste(self, session, avvio_noto):
        r = session.post(f"{BASE_URL}/api/startup/toggle",
                         json={"name": "MaiVistoPrima", "source": "registry",
                               "enable": False})
        assert r.status_code == 404, r.text

    def test_una_fonte_inventata_non_passa(self, session, avvio_noto):
        r = session.post(f"{BASE_URL}/api/startup/toggle",
                         json={"name": VOCE_SPEGNIBILE["name"], "source": "kernel",
                               "enable": False})
        assert r.status_code == 422, r.text

    def test_senza_token_lagent_non_vede_niente(self, avvio_noto):
        r = requests.get(f"{BASE_URL}/api/agent/startup-actions",
                         headers={"X-Agent-Token": "non-e-un-token"})
        assert r.status_code == 401, r.text

    def test_la_dashboard_vuole_il_login(self):
        r = requests.post(f"{BASE_URL}/api/startup/toggle",
                          json={"name": VOCE_SPEGNIBILE["name"], "enable": False})
        assert r.status_code in (401, 403), r.text

    def test_un_id_non_valido_non_rompe_niente(self, session, agent, avvio_noto):
        """L'id arriva dalla rete: spazzatura e id altrui devono cadere nel vuoto."""
        session.post(f"{BASE_URL}/api/startup/toggle",
                     json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                           "enable": False})
        r = agent.post(f"{BASE_URL}/api/agent/startup-actions/result",
                       json={"results": [{"id": "non-un-objectid", "ok": True},
                                         {"id": "ffffffffffffffffffffffff", "ok": True}]})
        assert r.status_code == 200, r.text
        assert r.json()["updated"] == 0
        # L'azione vera e' ancora li' ad aspettare.
        assert len(_stato(session)["pending"]) == 1


class TestAnnullare:
    def test_annullare_svuota_la_coda(self, session, agent, avvio_noto):
        session.post(f"{BASE_URL}/api/startup/toggle",
                     json={"name": VOCE_SPEGNIBILE["name"], "source": "registry",
                           "enable": False})
        d = session.delete(f"{BASE_URL}/api/startup/actions")
        assert d.status_code == 200, d.text
        assert d.json()["removed"] == 1
        assert agent.get(f"{BASE_URL}/api/agent/startup-actions").json()["actions"] == []
        assert "pending_enable" not in _voce_a_schermo(session, VOCE_SPEGNIBILE["name"])
