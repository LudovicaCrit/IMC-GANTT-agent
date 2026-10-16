"""
Ciclo di vita del progetto (Fase 1, passo 5), su gantt_test.

Cosa presidia:
  - i progetti «Da iniziare» si vedono dove si pianifica (GANTT, Cantiere, la
    tendina del GANTT, l'aggiunta di task) e NON dove si sorveglia (Home);
  - completare una bozza scrive solo i campi che il Wizard manda;
  - un progetto ordinario o bando ha una società, un interno può non averla;
  - la Home distingue interni e commerciali per tipologia.

Le chiamate passano dall'HTTP (TestClient), perché due delle regole vivono lì:
«campo non inviato» esiste solo nel JSON, e il 422 è una risposta HTTP.
I progetti creati qui si cancellano per id alla fine di ogni test, così gli
altri test sul database ritrovano il seed com'era.
"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from deps import require_manager
from models import (Azienda, Progetto, STATI_PROGETTO_ATTIVI, LIVELLI_URGENZA,
                    URGENZA_DEFAULT, get_session)

pytestmark = pytest.mark.usefixtures("db_test")

FRA_UN_MESE = date.today() + timedelta(days=30)
FRA_DUE_MESI = date.today() + timedelta(days=60)
# Un'urgenza diversa dal default: se il completamento la riportasse al
# default, il test se ne accorgerebbe.
URGENZA_NON_DEFAULT = next(u for u in LIVELLI_URGENZA if u != URGENZA_DEFAULT)


@pytest.fixture
def client():
    main.app.dependency_overrides[require_manager] = lambda: None
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.pop(require_manager, None)


@pytest.fixture
def creati():
    """Gli id dei progetti creati dal test: cancellati alla fine, per chiave
    esatta (fasi e task vanno via in cascata)."""
    ids = []
    yield ids
    session = get_session()
    try:
        for pid in ids:
            p = session.get(Progetto, pid)
            if p is not None:
                session.delete(p)
        session.commit()
    finally:
        session.close()


@pytest.fixture
def una_societa():
    session = get_session()
    try:
        return session.query(Azienda).order_by(Azienda.id).first().id
    finally:
        session.close()


def _payload_wizard(pid, stato, azienda_id, tipologia="ordinario"):
    """Il body che manda il Wizard (WizardCreazioneProgetto.handleSubmit):
    né descrizione, né valore del contratto, né urgenza."""
    progetto = {
        "id": pid, "nome": f"[TEST] {pid}", "cliente": "Cliente di prova",
        "tipologia": tipologia, "stato": stato, "pm_id": None,
        "data_inizio": FRA_UN_MESE.isoformat(),
        "data_fine": FRA_DUE_MESI.isoformat(), "budget_ore": 40,
    }
    if azienda_id is not None:
        progetto["azienda_id"] = azienda_id
    return {
        "progetto": progetto,
        "fasi": [{"nome": "Analisi", "ordine": 1,
                  "data_inizio": FRA_UN_MESE.isoformat(),
                  "data_fine": FRA_DUE_MESI.isoformat(), "ore_vendute": 40}],
        "task_iniziali": [],
    }


def _ids(risposta):
    assert risposta.status_code == 200, risposta.text[:300]
    return {p["id"] for p in risposta.json()}


# ── TASK 1: i Da iniziare si vedono dove si pianifica ─────────────────────

def test_da_iniziare_nel_gantt_e_nella_tendina_non_negli_attivi(client, creati, una_societa):
    creati.append("PT501")
    r = client.post("/api/progetti/completo",
                    json=_payload_wizard("PT501", "Da iniziare", una_societa))
    assert r.status_code == 201, r.text

    assert "PT501" in _ids(client.get("/api/gantt/strutturato?stato=in piano"))
    assert "PT501" in _ids(client.get("/api/progetti?stato=in piano"))
    assert "PT501" in _ids(client.get("/api/gantt/strutturato?stato=da iniziare"))
    # Il default resta «attivi»: chi non chiede niente non vede cambiare nulla.
    assert "PT501" not in _ids(client.get("/api/gantt/strutturato"))
    assert "PT501" not in _ids(client.get("/api/progetti"))


def test_da_iniziare_fuori_dalla_home(creati, una_societa, client):
    """La Home sorveglia gli attivi: un progetto non ancora partito non entra
    nell'attenzione né negli sforamenti."""
    from data import progetti_attivi_visibili

    creati.append("PT502")
    client.post("/api/progetti/completo",
                json=_payload_wizard("PT502", "Da iniziare", una_societa))
    manager = SimpleNamespace(ruolo_app="manager", dipendente_id=None)
    assert "PT502" not in progetti_attivi_visibili(manager)
    assert "PT502" in progetti_attivi_visibili(manager, solo_attivi=False)
    assert "Da iniziare" not in STATI_PROGETTO_ATTIVI


def test_a_un_da_iniziare_si_aggiungono_task(client, creati, una_societa):
    creati.append("PT503")
    client.post("/api/progetti/completo",
                json=_payload_wizard("PT503", "Da iniziare", una_societa))
    [prog] = client.get("/api/gantt/strutturato?progetto_id=PT503").json()
    r = client.post("/api/progetti/PT503/task-multipli", json={"task": [{
        "nome": "Primo task", "fase_id": prog["fasi"][0]["id"], "ore_stimate": 8,
        "data_inizio": FRA_UN_MESE.isoformat(), "data_fine": FRA_UN_MESE.isoformat(),
    }]})
    assert r.status_code == 201, r.text


def test_a_una_bozza_non_si_aggiungono_task(client, creati, una_societa):
    creati.append("PT504")
    client.post("/api/progetti/completo",
                json=_payload_wizard("PT504", "Bozza", una_societa))
    [prog] = client.get("/api/gantt/strutturato?progetto_id=PT504").json()
    r = client.post("/api/progetti/PT504/task-multipli", json={"task": [{
        "nome": "Primo task", "fase_id": prog["fasi"][0]["id"], "ore_stimate": 8,
    }]})
    assert r.status_code == 409


# ── TASK 2: completare una bozza non azzera i campi ───────────────────────

def test_completare_una_bozza_conserva_i_campi_che_il_wizard_non_manda(
        client, creati, una_societa):
    creati.append("PT510")
    r = client.post("/api/progetti", json={
        "id": "PT510", "nome": "[TEST] bozza ricca", "stato": "Bozza",
        "tipologia": "ordinario", "azienda_id": una_societa,
        "descrizione": "Descrizione scritta a mano", "valore_contratto": 12345.5,
        "urgenza": URGENZA_NON_DEFAULT, "priorita": "alta",
        "fase_corrente": "Analisi",
    })
    assert r.status_code == 201, r.text

    r = client.put("/api/progetti/PT510/completo",
                   json=_payload_wizard("PT510", "Da iniziare", una_societa))
    assert r.status_code == 200, r.text

    session = get_session()
    try:
        p = session.get(Progetto, "PT510")
        assert p.stato == "Da iniziare"               # i campi inviati si scrivono
        assert p.nome == "[TEST] PT510"
        assert p.descrizione == "Descrizione scritta a mano"   # gli altri restano
        assert p.valore_contratto == 12345.5
        assert p.urgenza == URGENZA_NON_DEFAULT
        assert p.priorita == "alta"
        assert p.fase_corrente == "Analisi"
    finally:
        session.close()


def test_completare_una_bozza_scrive_un_null_inviato(client, creati, una_societa):
    """«Non inviato» e «inviato vuoto» sono due cose: il secondo si scrive."""
    creati.append("PT511")
    client.post("/api/progetti", json={
        "id": "PT511", "nome": "[TEST] bozza", "stato": "Bozza",
        "tipologia": "ordinario", "azienda_id": una_societa, "cliente": "Vecchio",
    })
    payload = _payload_wizard("PT511", "Bozza", una_societa)
    payload["progetto"]["cliente"] = None
    assert client.put("/api/progetti/PT511/completo", json=payload).status_code == 200
    session = get_session()
    try:
        assert session.get(Progetto, "PT511").cliente is None
    finally:
        session.close()


# ── TASK 3: società del progetto ──────────────────────────────────────────

@pytest.mark.parametrize("tipologia", ["ordinario", "bando"])
def test_un_commerciale_senza_societa_e_rifiutato(client, creati, tipologia):
    creati.append("PT520")
    r = client.post("/api/progetti/completo",
                    json=_payload_wizard("PT520", "Da iniziare", None, tipologia))
    assert r.status_code == 422
    assert "società" in r.json()["detail"]
    r = client.post("/api/progetti", json={"id": "PT520", "nome": "x",
                                           "tipologia": tipologia})
    assert r.status_code == 422
    session = get_session()
    try:
        assert session.get(Progetto, "PT520") is None
    finally:
        session.close()


def test_un_interno_puo_non_avere_societa(client, creati):
    creati.append("PT521")
    r = client.post("/api/progetti/completo",
                    json=_payload_wizard("PT521", "Da iniziare", None, "interna"))
    assert r.status_code == 201, r.text


def test_una_societa_inesistente_e_rifiutata(client, creati):
    creati.append("PT522")
    r = client.post("/api/progetti/completo",
                    json=_payload_wizard("PT522", "Da iniziare", 999999))
    assert r.status_code == 422
    assert "non esiste" in r.json()["detail"]


def test_il_progetto_creato_ha_la_societa_scelta(client, creati, una_societa):
    creati.append("PT523")
    client.post("/api/progetti/completo",
                json=_payload_wizard("PT523", "Da iniziare", una_societa))
    [prog] = client.get("/api/gantt/strutturato?progetto_id=PT523").json()
    assert prog["azienda_id"] == una_societa


def test_completare_una_bozza_commerciale_senza_societa_e_rifiutato(client, creati):
    """Una bozza nata prima della regola, senza società: il completamento la
    chiede, e la bozza resta com'era."""
    creati.append("PT524")
    session = get_session()
    try:
        session.add(Progetto(id="PT524", nome="[TEST] bozza vecchia",
                             stato="Bozza", tipologia="ordinario"))
        session.commit()
    finally:
        session.close()
    r = client.put("/api/progetti/PT524/completo",
                   json=_payload_wizard("PT524", "Da iniziare", None))
    assert r.status_code == 422
    session = get_session()
    try:
        assert session.get(Progetto, "PT524").stato == "Bozza"
    finally:
        session.close()


# ── TASK 3: la Home distingue per tipologia ───────────────────────────────

def _dashboard_manager():
    from routes.home import dashboard
    return dashboard(current_user=SimpleNamespace(ruolo_app="manager",
                                                  dipendente_id=None))


def test_home_conta_gli_interni_per_tipologia_sui_dati_del_seed():
    session = get_session()
    try:
        interni = session.query(Progetto).filter(Progetto.tipologia == "interna").count()
        commerciali = session.query(Progetto).filter(Progetto.tipologia != "interna").count()
    finally:
        session.close()
    d = _dashboard_manager()
    assert d["interne"]["n_totali"] == interni
    assert sum(r["polso"]["n_progetti"] for r in d["rami"]) == commerciali


def test_home_un_commerciale_senza_societa_non_e_un_interno(creati):
    """Il caso che la regola ora impedisce, ma che può esistere da prima:
    resta fra i commerciali, in un ramo a parte, e non gonfia gli interni."""
    prima = _dashboard_manager()
    creati.append("PT530")
    session = get_session()
    try:
        session.add(Progetto(id="PT530", nome="[TEST] senza società",
                             stato="In esecuzione", tipologia="ordinario"))
        session.commit()
    finally:
        session.close()
    dopo = _dashboard_manager()
    assert dopo["interne"]["n_totali"] == prima["interne"]["n_totali"]
    [ramo] = [r for r in dopo["rami"] if r["azienda_id"] is None]
    assert ramo["azienda"] == "Società non indicata"
    assert ramo["polso"]["n_progetti"] == 1
    assert dopo["rami"][-1] is ramo


def test_home_un_interno_con_societa_resta_un_interno(creati, una_societa):
    prima = _dashboard_manager()
    creati.append("PT531")
    session = get_session()
    try:
        session.add(Progetto(id="PT531", nome="[TEST] interno con società",
                             stato="In esecuzione", tipologia="interna",
                             azienda_id=una_societa))
        session.commit()
    finally:
        session.close()
    dopo = _dashboard_manager()
    assert dopo["interne"]["n_totali"] == prima["interne"]["n_totali"] + 1
    assert ([r["polso"]["n_progetti"] for r in dopo["rami"]]
            == [r["polso"]["n_progetti"] for r in prima["rami"]])


def test_completare_una_bozza_con_una_societa_inesistente_e_un_422(
        client, creati, una_societa):
    """La società si valida PRIMA di toccare la bozza. Prima si scrivevano i
    campi sull'oggetto e poi si validava: la query di `_valida_societa` faceva
    l'autoflush dell'azienda inesistente, e la foreign key rispondeva con un
    IntegrityError, cioè un 500, invece del 422."""
    creati.append("PT525")
    client.post("/api/progetti", json={
        "id": "PT525", "nome": "[TEST] bozza", "stato": "Bozza",
        "tipologia": "ordinario", "azienda_id": una_societa,
    })
    r = client.put("/api/progetti/PT525/completo",
                   json=_payload_wizard("PT525", "Da iniziare", 999999))
    assert r.status_code == 422, r.text
    assert "non esiste" in r.json()["detail"]
    session = get_session()
    try:
        p = session.get(Progetto, "PT525")
        assert (p.stato, p.azienda_id) == ("Bozza", una_societa)
    finally:
        session.close()


def test_il_patch_valida_la_societa_sui_valori_risultanti(client, creati):
    """Un interno senza società che diventa ordinario dal PATCH resterebbe un
    commerciale senza società: il PATCH lo rifiuta e il progetto resta com'era."""
    creati.append("PT526")
    client.post("/api/progetti", json={
        "id": "PT526", "nome": "[TEST] interno", "stato": "Da iniziare",
        "tipologia": "interna",
    })
    r = client.patch("/api/progetti/PT526", json={"tipologia": "ordinario"})
    assert r.status_code == 422, r.text
    assert "società" in r.json()["detail"]
    session = get_session()
    try:
        assert session.get(Progetto, "PT526").tipologia == "interna"
    finally:
        session.close()


def test_il_patch_fa_diventare_ordinario_un_interno_con_la_societa(
        client, creati, una_societa):
    """Tipologia e società insieme: i valori risultanti sono un ordinario con
    una società valida, e il PATCH li scrive entrambi."""
    creati.append("PT527")
    client.post("/api/progetti", json={
        "id": "PT527", "nome": "[TEST] interno", "stato": "Da iniziare",
        "tipologia": "interna",
    })
    r = client.patch("/api/progetti/PT527",
                     json={"tipologia": "ordinario", "azienda_id": una_societa})
    assert r.status_code == 200, r.text
    session = get_session()
    try:
        p = session.get(Progetto, "PT527")
        assert (p.tipologia, p.azienda_id) == ("ordinario", una_societa)
    finally:
        session.close()


def test_il_patch_con_una_societa_inesistente_e_un_422(client, creati, una_societa):
    """Lo stesso caso del completamento: validata dopo i setattr, la società
    inesistente arriverebbe alla foreign key come 500."""
    creati.append("PT528")
    client.post("/api/progetti", json={
        "id": "PT528", "nome": "[TEST] ordinario", "stato": "Da iniziare",
        "tipologia": "ordinario", "azienda_id": una_societa,
    })
    r = client.patch("/api/progetti/PT528", json={"azienda_id": 999999})
    assert r.status_code == 422, r.text
    assert "non esiste" in r.json()["detail"]
    session = get_session()
    try:
        assert session.get(Progetto, "PT528").azienda_id == una_societa
    finally:
        session.close()
