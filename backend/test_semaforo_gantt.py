"""
Test dell'INNESTO del semaforo su `GET /api/gantt/strutturato` — sotto-edit 3.

Richiede Postgres attivo (come `test_semaforo_aggregazione.py`; la suite pura
degli helper resta in `test_semaforo.py` e gira senza database).

Cosa presidia, in ordine di importanza:
  - NON-REGRESSIONE: l'innesto è ADDITIVO. Il payload deve avere esattamente i
    campi di prima, più `semaforo`. La lista dei campi attesi è scritta a mano
    qui sotto: se qualcuno ne toglie uno, o ne aggiunge uno senza accorgersene,
    il test lo dice. È l'unico modo di congelare un contratto che quattro pagine
    frontend consumano (Gantt, ElencoDettaglio, CantiereDettaglio, Archivio).
  - COERENZA: i colori nel payload sono quelli che `semaforo_progetti`
    restituisce chiamata da sola. Il payload non deve poter divergere dal
    calcolo.
  - COPERTURA: nessuna unità esce con `semaforo: null`. È il presidio che rende
    RUMOROSO l'unico rischio del `.get()` difensivo in `_semaforo_payload`.
  - NIENTE N+1: le query restano costanti al crescere dei progetti.
"""

from sqlalchemy import event

from data_db_impl import semaforo_progetti
from models import engine
from routes.gantt import gantt_strutturato


# ── Il contratto del payload, campo per campo ────────────────────────────
# Scritto a mano DOPO aver verificato il diff prima/dopo l'innesto: 0 campi
# persi, 0 valori cambiati, 1 solo campo nuovo (`semaforo`) ai tre livelli.
CAMPI_PROGETTO = {
    "id", "nome", "cliente", "stato", "stato_derivato", "tipologia",
    "data_inizio", "data_fine", "budget_ore", "pm_id",
    "ore_vendute_totali", "ore_consumate_totali", "n_fasi", "fasi",
    "semaforo",
}
CAMPI_FASE = {
    "id", "nome", "ordine", "stato", "data_inizio", "data_fine",
    "ore_vendute", "ore_pianificate", "ore_consumate", "n_task", "tasks",
    "semaforo",
}
CAMPI_TASK = {
    "id", "nome", "stato", "ore_stimate", "ore_pianificate", "ore_consumate",
    "scostamento", "data_inizio", "data_fine", "dipendente_id",
    "dipendente_nome", "profilo_richiesto", "predecessore", "dipendenze",
    "semaforo",
}
CAMPI_SEMAFORO = {"colore", "origine", "figli_rossi"}

COLORI = ("rosso", "giallo", "grigio", "verde")
ORIGINI = ("propria", "figli", "entrambe", None)


class ContaQuery:
    def __init__(self):
        self.n = 0

    def __enter__(self):
        self._h = lambda *a, **k: setattr(self, "n", self.n + 1)
        event.listen(engine, "before_cursor_execute", self._h)
        return self

    def __exit__(self, *exc):
        event.remove(engine, "before_cursor_execute", self._h)
        return False


def _payload(progetto_id=None):
    """Chiama la route direttamente. `_` è la dipendenza require_manager, che
    l'endpoint non usa nel corpo: qui si passa None e si testa il calcolo, non
    l'auth (che ha i suoi test)."""
    return gantt_strutturato(stato="all", progetto_id=progetto_id, _=None)


def _unita(payload):
    """Cammina il payload e produce (livello, id, nodo) per ogni unità."""
    for p in payload:
        yield "progetto", p["id"], p
        for f in p["fasi"]:
            yield "fase", f["id"], f
            for t in f["tasks"]:
                yield "task", t["id"], t


# ══════════════════════════════════════════════════════════════════════
# 1. NON-REGRESSIONE — additivo puro
# ══════════════════════════════════════════════════════════════════════

def test_payload_additivo():
    """1. Il payload ha i campi di prima + `semaforo`, a tutti e tre i livelli."""
    payload = _payload()
    assert payload, "nessun progetto serializzato"

    attesi = {"progetto": CAMPI_PROGETTO, "fase": CAMPI_FASE, "task": CAMPI_TASK}
    n = {"progetto": 0, "fase": 0, "task": 0}
    for livello, uid, nodo in _unita(payload):
        n[livello] += 1
        mancanti = attesi[livello] - set(nodo)
        extra = set(nodo) - attesi[livello]
        assert not mancanti, f"{livello} {uid}: campi PERSI {mancanti}"
        assert not extra, f"{livello} {uid}: campi INATTESI {extra}"

    print(f"✅ 1. payload additivo — {n['progetto']} progetti, {n['fase']} fasi, "
          f"{n['task']} task: 0 campi persi, 0 inattesi")


def test_forma_del_semaforo():
    """2. Il sotto-oggetto `semaforo` ha sempre e solo le tre chiavi, con
    valori nel vocabolario dichiarato."""
    for livello, uid, nodo in _unita(_payload()):
        sem = nodo["semaforo"]
        assert sem is not None, f"{livello} {uid}: semaforo null"
        assert set(sem) == CAMPI_SEMAFORO, f"{livello} {uid}: {set(sem)}"
        assert sem["colore"] in COLORI, (uid, sem["colore"])
        assert sem["origine"] in ORIGINI, (uid, sem["origine"])
        assert isinstance(sem["figli_rossi"], int) and sem["figli_rossi"] >= 0
        # In strato 1 il giallo non è emesso: se comparisse qui prima dello
        # strato 2, è un bug.
        assert sem["colore"] != "giallo", uid
        # Verde ⇔ nessuna origine da spiegare.
        assert (sem["colore"] == "verde") == (sem["origine"] is None), (uid, sem)

    print("✅ 2. forma del semaforo: 3 chiavi, vocabolario rispettato, "
          "verde ⇔ origine null")


# ══════════════════════════════════════════════════════════════════════
# 3. COERENZA col calcolo, e COPERTURA totale
# ══════════════════════════════════════════════════════════════════════

def test_payload_coerente_col_calcolo():
    """3. Ogni colore nel payload == quello di `semaforo_progetti` da sola.

    Il payload non deve poter divergere dal calcolo: se la traduzione in
    `_semaforo_payload` o il lookup nel loop sbagliassero livello, qui si vede.
    """
    payload = _payload()
    alberi = semaforo_progetti([p["id"] for p in payload])

    n = 0
    for p in payload:
        nodo_p = alberi[p["id"]]
        assert p["semaforo"]["colore"] == nodo_p["semaforo"], p["id"]
        assert p["semaforo"]["origine"] == nodo_p["origine"], p["id"]
        assert p["semaforo"]["figli_rossi"] == nodo_p["figli_rossi"], p["id"]
        n += 1
        for f in p["fasi"]:
            nodo_f = nodo_p["fasi"][f["id"]]
            assert f["semaforo"]["colore"] == nodo_f["semaforo"], f["id"]
            assert f["semaforo"]["origine"] == nodo_f["origine"], f["id"]
            assert f["semaforo"]["figli_rossi"] == nodo_f["figli_rossi"], f["id"]
            n += 1
            for t in f["tasks"]:
                nodo_t = nodo_f["task"][t["id"]]
                assert t["semaforo"]["colore"] == nodo_t["semaforo"], t["id"]
                assert t["semaforo"]["origine"] == nodo_t["origine"], t["id"]
                n += 1

    # `figli_rossi` di progetto conta le FASI rosse, non i task dei nipoti.
    for p in payload:
        fasi_rosse = sum(1 for f in p["fasi"] if f["semaforo"]["colore"] == "rosso")
        assert p["semaforo"]["figli_rossi"] == fasi_rosse, p["id"]

    print(f"✅ 3. {n} unità: colore/origine/figli_rossi identici al calcolo diretto")


def test_copertura_totale():
    """4. Nessuna unità con `semaforo: null`.

    `_semaforo_payload` restituisce None su nodo assente invece di alzare, per
    non trasformare una divergenza di filtri in un 500 su quattro pagine.
    Questo test è il prezzo di quella scelta: la divergenza deve essere
    rumorosa QUI, non silenziosa in produzione.
    """
    buchi = [(liv, uid) for liv, uid, nodo in _unita(_payload())
             if nodo["semaforo"] is None]
    assert not buchi, f"unità senza semaforo: {buchi[:10]}"
    print("✅ 4. copertura totale: 0 unità con semaforo null")


def test_rossi_e_provenienza_nel_payload():
    """5. I progetti rossi escono rossi, con la provenienza giusta."""
    payload = _payload()
    rossi = {p["id"]: p["semaforo"] for p in payload
             if p["semaforo"]["colore"] == "rosso"}
    assert rossi, "atteso almeno un progetto rosso"

    for pid, sem in rossi.items():
        p = next(x for x in payload if x["id"] == pid)
        fasi_rosse = [f for f in p["fasi"] if f["semaforo"]["colore"] == "rosso"]
        if sem["origine"] in ("figli", "entrambe"):
            assert fasi_rosse, f"{pid} origine={sem['origine']} ma 0 fasi rosse"
        if sem["origine"] == "propria":
            assert not fasi_rosse, f"{pid} origine=propria ma ha fasi rosse"
        # ogni fase rossa ha un task rosso dentro, o è rossa di suo
        for f in fasi_rosse:
            task_rossi = [t for t in f["tasks"] if t["semaforo"]["colore"] == "rosso"]
            if f["semaforo"]["origine"] in ("figli", "entrambe"):
                assert task_rossi, f"fase {f['id']}: origine figli ma 0 task rossi"
            assert f["semaforo"]["figli_rossi"] == len(task_rossi)

    per_origine = {}
    for pid, sem in rossi.items():
        per_origine.setdefault(sem["origine"], []).append(pid)
    print(f"✅ 5. {len(rossi)} progetti rossi nel payload: {per_origine}")


# ══════════════════════════════════════════════════════════════════════
# 6. NIENTE N+1 AGGIUNTO
# ══════════════════════════════════════════════════════════════════════

def test_query_costanti():
    """6. Le query dell'endpoint non crescono col numero di unità.

    L'innesto aggiunge le 2 query fisse del semaforo. La proprietà che conta
    non è il numero assoluto (cambia se cambia l'endpoint) ma che sia lo STESSO
    su 1 progetto e su tutti: è ciò che esclude l'N+1.
    """
    payload = _payload()
    uno = payload[0]["id"]

    with ContaQuery() as c1:
        _payload(progetto_id=uno)
    with ContaQuery() as cN:
        tutti = _payload()

    unita = sum(1 for _ in _unita(tutti))
    assert c1.n == cN.n, f"{c1.n} query su 1 progetto, {cN.n} su {len(tutti)}"
    print(f"✅ 6. {cN.n} query per {len(tutti)} progetti / {unita} unità "
          f"(uguali alle {c1.n} di un solo progetto) — di cui 2 del semaforo")


def test_endpoint_risponde_200():
    """7. L'endpoint HTTP risponde 200 e il semaforo è nel JSON serializzato."""
    from fastapi.testclient import TestClient
    from deps import require_manager
    import main

    main.app.dependency_overrides[require_manager] = lambda: None
    try:
        r = TestClient(main.app).get("/api/gantt/strutturato?stato=all")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body and body[0]["semaforo"]["colore"] in COLORI
        assert body[0]["fasi"][0]["semaforo"]["colore"] in COLORI
    finally:
        main.app.dependency_overrides.pop(require_manager, None)
    print(f"✅ 7. GET /api/gantt/strutturato → 200, {len(body)} progetti col semaforo")


if __name__ == "__main__":
    test_payload_additivo()
    test_forma_del_semaforo()
    test_payload_coerente_col_calcolo()
    test_copertura_totale()
    test_rossi_e_provenienza_nel_payload()
    test_query_costanti()
    test_endpoint_risponde_200()
    print()
    print("=" * 60)
    print("TUTTI I TEST PASSATI ✅")
