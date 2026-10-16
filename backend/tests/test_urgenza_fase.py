"""
L'urgenza della fase: eredita dal progetto salvo un'eccezione (B3 bis).

Cosa presidia:
  - PATCH /api/fasi/{id} imposta un'urgenza propria, la toglie con `null`
    (si torna a ereditare) e rifiuta un livello non ammesso con 422;
  - i payload di /api/fasi/{progetto} e /api/gantt/strutturato espongono il
    valore che vale (`urgenza`) e se è ereditato (`urgenza_ereditata`), con
    la regola di `models.urgenza_fase_risolta`.

Si lavora su una fase del seed scelta con una query; alla fine urgenza e nota
tornano quelle di prima.
"""

import pytest
from fastapi.testclient import TestClient

import main
from deps import require_manager
from models import LIVELLI_URGENZA, Fase, Progetto, get_session

pytestmark = pytest.mark.usefixtures("db_test")


@pytest.fixture
def client():
    main.app.dependency_overrides[require_manager] = lambda: None
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.pop(require_manager, None)


@pytest.fixture
def una_fase():
    """La prima fase, per id, di un progetto in esecuzione, che erediti
    l'urgenza; a fine test urgenza e nota tornano com'erano."""
    session = get_session()
    try:
        f = (session.query(Fase).join(Progetto)
             .filter(Progetto.stato == "In esecuzione", Fase.urgenza.is_(None))
             .order_by(Fase.id).first())
        fase_id, progetto_id, del_progetto = f.id, f.progetto_id, f.progetto.urgenza
        nota = f.note
    finally:
        session.close()
    yield fase_id, progetto_id, del_progetto
    session = get_session()
    try:
        f = session.get(Fase, fase_id)
        f.urgenza, f.note = None, nota
        session.commit()
    finally:
        session.close()


def _urgenza_in_db(fase_id):
    session = get_session()
    try:
        return session.get(Fase, fase_id).urgenza
    finally:
        session.close()


def _nei_payload(client, fase_id, progetto_id):
    """(urgenza, urgenza_ereditata) della fase in /api/fasi e nel GANTT: i due
    payload devono dire la stessa cosa."""
    [da_fasi] = [f for f in client.get(f"/api/fasi/{progetto_id}").json() if f["id"] == fase_id]
    [prog] = client.get(f"/api/gantt/strutturato?progetto_id={progetto_id}&stato=all").json()
    [da_gantt] = [f for f in prog["fasi"] if f["id"] == fase_id]
    coppia = (da_fasi["urgenza"], da_fasi["urgenza_ereditata"])
    assert (da_gantt["urgenza"], da_gantt["urgenza_ereditata"]) == coppia
    return coppia


def test_di_norma_la_fase_eredita_dal_progetto(client, una_fase):
    fase_id, progetto_id, del_progetto = una_fase
    assert _nei_payload(client, fase_id, progetto_id) == (del_progetto, True)


def test_un_urgenza_propria_e_poi_il_ritorno_all_eredita(client, una_fase):
    fase_id, progetto_id, del_progetto = una_fase
    propria = next(u for u in LIVELLI_URGENZA if u != del_progetto)

    r = client.patch(f"/api/fasi/{fase_id}", json={"urgenza": propria})
    assert r.status_code == 200, r.text
    assert _urgenza_in_db(fase_id) == propria
    assert _nei_payload(client, fase_id, progetto_id) == (propria, False)

    # Un PATCH che non nomina l'urgenza non la tocca.
    r = client.patch(f"/api/fasi/{fase_id}", json={"note": "[TEST] nota"})
    assert r.status_code == 200, r.text
    assert _urgenza_in_db(fase_id) == propria

    # `null` esplicito: via l'eccezione, si torna a ereditare.
    r = client.patch(f"/api/fasi/{fase_id}", json={"urgenza": None})
    assert r.status_code == 200, r.text
    assert _urgenza_in_db(fase_id) is None
    assert _nei_payload(client, fase_id, progetto_id) == (del_progetto, True)


@pytest.mark.parametrize("valore", ["Altissima", "", "media"])
def test_un_livello_non_ammesso_e_un_422(client, una_fase, valore):
    fase_id, _, _ = una_fase
    r = client.patch(f"/api/fasi/{fase_id}", json={"urgenza": valore})
    assert r.status_code == 422, r.text
    assert "non ammessa sulla fase" in r.text
    assert _urgenza_in_db(fase_id) is None
