"""
Id dei progetti da una sequenza e ordinamento per numero (Fase 1, passo 6a),
su gantt_test.

Cosa presidia:
  - dopo la ricostruzione di gantt_test (migration + seed) la creazione senza
    id prende il numero dopo il più alto del seed, senza 409;
  - gli id di altra forma (PPROVA, PZ01) non disturbano la numerazione;
  - due creazioni di seguito prendono numeri consecutivi;
  - le liste mettono P999 prima di P1000 e gli id di altra forma in fondo.

I progetti si creano dall'HTTP come fa il Wizard, senza id. Alla fine di ogni
test si cancellano per id e la sequenza torna al numero più alto rimasto, così
gli altri test ritrovano gantt_test com'era dopo il seed.
"""

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from deps import require_manager
from models import (Azienda, Progetto, PREFISSO_ID_PROGETTO, formatta_id_progetto,
                    get_session, riallinea_numero_progetti)

pytestmark = pytest.mark.usefixtures("db_test")

FRA_UN_MESE = date.today() + timedelta(days=30)
FRA_DUE_MESI = date.today() + timedelta(days=60)
ID_GENERATO = re.compile(rf"^{PREFISSO_ID_PROGETTO}[0-9]+$")


@pytest.fixture
def client():
    main.app.dependency_overrides[require_manager] = lambda: None
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.pop(require_manager, None)


@pytest.fixture
def creati():
    """Gli id dei progetti creati dal test: cancellati alla fine per chiave
    esatta, poi la sequenza si riallinea a ciò che resta."""
    ids = []
    yield ids
    session = get_session()
    try:
        for pid in ids:
            p = session.get(Progetto, pid)
            if p is not None:
                session.delete(p)
        session.flush()
        riallinea_numero_progetti(session)
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


def _numero_piu_alto():
    session = get_session()
    try:
        numeri = [int(pid[len(PREFISSO_ID_PROGETTO):])
                  for (pid,) in session.query(Progetto.id)
                  if ID_GENERATO.match(pid)]
        return max(numeri)
    finally:
        session.close()


def _crea_dal_wizard(client, creati, azienda_id, nome="[TEST] id da sequenza"):
    """POST /completo senza id, come il Wizard. Restituisce l'id dato."""
    r = client.post("/api/progetti/completo", json={
        "progetto": {
            "nome": nome, "cliente": "Cliente di prova", "tipologia": "ordinario",
            "stato": "Da iniziare", "pm_id": None, "azienda_id": azienda_id,
            "data_inizio": FRA_UN_MESE.isoformat(),
            "data_fine": FRA_DUE_MESI.isoformat(), "budget_ore": 40,
        },
        "fasi": [{"nome": "Analisi", "ordine": 1,
                  "data_inizio": FRA_UN_MESE.isoformat(),
                  "data_fine": FRA_DUE_MESI.isoformat(), "ore_vendute": 40}],
        "task_iniziali": [{"nome": "Primo task", "fase_idx": 0, "ore_stimate": 8,
                           "data_inizio": FRA_UN_MESE.isoformat(),
                           "data_fine": FRA_UN_MESE.isoformat()}],
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    creati.append(pid)
    return pid


def _inserisci(creati, *ids):
    """Progetti con id espliciti, scritti direttamente: è ciò che fa il seed,
    e ciò che lascia la sequenza indietro finché non la si riallinea."""
    session = get_session()
    try:
        for pid in ids:
            session.add(Progetto(id=pid, nome=f"[TEST] {pid}", stato="Da iniziare",
                                 tipologia="interna"))
            creati.append(pid)
        session.commit()
    finally:
        session.close()


def test_formato_dell_id():
    assert formatta_id_progetto(12) == "P012"
    assert formatta_id_progetto(1000) == "P1000"


def test_creazione_dopo_la_ricostruzione_di_gantt_test(client, creati, una_societa):
    """Il seed inserisce id espliciti e riallinea la sequenza: il primo
    progetto del Wizard prende il numero dopo il più alto, non un 409."""
    atteso = formatta_id_progetto(_numero_piu_alto() + 1)
    assert _crea_dal_wizard(client, creati, una_societa) == atteso


def test_gli_id_di_altra_forma_non_disturbano(client, creati, una_societa):
    """PPROVA e PZ01 sono alfabeticamente dopo ogni «P» + cifre: il vecchio
    max(id) li prendeva per il massimo e ricadeva su P001."""
    _inserisci(creati, "PPROVA", "PZ01", "P450")
    session = get_session()
    try:
        assert riallinea_numero_progetti(session) == 451
        session.commit()
    finally:
        session.close()
    assert _crea_dal_wizard(client, creati, una_societa) == "P451"


def test_due_creazioni_di_seguito_hanno_numeri_consecutivi(client, creati, una_societa):
    primo = _crea_dal_wizard(client, creati, una_societa, "[TEST] primo")
    secondo = _crea_dal_wizard(client, creati, una_societa, "[TEST] secondo")
    assert ID_GENERATO.match(primo) and ID_GENERATO.match(secondo)
    assert int(secondo[1:]) == int(primo[1:]) + 1


def test_ordinamento_oltre_p999(client, creati, una_societa):
    """Come testo P1000 < P999 e PA01 < P999. Le liste vogliono i numeri in
    ordine di numero, poi gli id di altra forma in ordine alfabetico."""
    _inserisci(creati, "P999", "PA01", "PZ01")
    session = get_session()
    try:
        riallinea_numero_progetti(session)
        session.commit()
    finally:
        session.close()
    p1000 = _crea_dal_wizard(client, creati, una_societa)
    assert p1000 == "P1000"

    def atteso(ids):
        return sorted(ids, key=lambda pid: (0, int(pid[1:]), pid)
                      if ID_GENERATO.match(pid) else (1, 0, pid))

    progetti = [p["id"] for p in client.get("/api/progetti?stato=all").json()]
    assert progetti == atteso(progetti)
    assert progetti.index("P999") < progetti.index("P1000") < progetti.index("PA01")

    strutturato = [p["id"] for p in client.get("/api/gantt/strutturato?stato=all").json()]
    assert strutturato == atteso(strutturato)
    assert strutturato.index("P999") < strutturato.index("P1000") < strutturato.index("PA01")

    # Il foglio «GANTT Visivo» dell'export scorre i task nell'ordine di qui.
    from routes.gantt import _carica_task_export
    ordine_task = list(dict.fromkeys(r["progetto_id"]
                                     for r in _carica_task_export("all", None, None)))
    assert ordine_task == atteso(ordine_task)
    assert "P1000" in ordine_task
