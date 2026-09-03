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
    # Urgenza (A1, 03/09/2026): sul progetto è un campo solo, sempre
    # valorizzato — è NOT NULL perché è la radice dell'eredità delle fasi.
    "urgenza",
}
CAMPI_FASE = {
    "id", "nome", "ordine", "stato", "data_inizio", "data_fine",
    "ore_vendute", "ore_pianificate", "ore_consumate", "n_task", "tasks",
    "semaforo",
    # Urgenza sulla fase: DUE campi, grezzo e risolto. `urgenza` null =
    # «eredita dal progetto»; `urgenza_risolta` è il valore effettivo. Servono
    # entrambi perché il Cantiere possa distinguere una scelta del PM da
    # un'eredità (vedi il commento in gantt_strutturato).
    "urgenza", "urgenza_risolta",
}
CAMPI_TASK = {
    "id", "nome", "stato", "ore_stimate", "ore_pianificate", "ore_consumate",
    "scostamento", "data_inizio", "data_fine", "dipendente_id",
    "dipendente_nome", "profilo_richiesto", "predecessore", "dipendenze",
    "semaforo",
}
# `sottotask` è l'unico campo OPZIONALE del task: c'è solo sui task scomposti.
# Non sta in CAMPI_TASK perché la sua assenza è il caso normale (e, oggi, l'unico
# in DB); sta qui perché la sua presenza non deve far fallire il contratto.
CAMPI_TASK_OPZIONALI = {"sottotask"}
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
        if livello == "task":
            extra -= CAMPI_TASK_OPZIONALI
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
          f"(uguali alle {c1.n} di un solo progetto) — 5 dell'endpoint, "
          f"2 del semaforo, 1 delle righe sottotask")


# ══════════════════════════════════════════════════════════════════════
# 8. SOTTOTASK ANNIDATI (lavoro B) — fixture, 0 pezzi in DB
# ══════════════════════════════════════════════════════════════════════

CAMPI_SOTTOTASK = {
    "id", "nome", "ordine", "stato", "ore_stimate",
    "dipendente_id", "dipendente_nome", "semaforo",
}


def test_sottotask_annidati():
    """8. I sottotask compaiono annidati nel task, con anagrafica e colore.

    Stampo di `test_semaforo_aggregazione.py::test_fixture_sottotask_eredita_
    la_data_del_padre`, spostato dal dict dell'aggregazione al payload della
    route. Due padri (uno verde, uno rosso) per verificare che il colore del
    pezzo segua la data EREDITATA dal task, più un pezzo «Annullato» che non
    deve comparire.
    """
    from datetime import date
    from models import get_session, Task, Sottotask
    from data_db_impl import colore_unita

    oggi = date.today()
    s = get_session()
    creati, ids_creati = [], []
    try:
        vivi = ("Completato", "Sospeso", "Annullato", "Eliminato")
        t_verde = next(t for t in s.query(Task).all()
                       if colore_unita(t.data_fine, t.stato, oggi) == "verde"
                       and t.stato not in vivi)
        t_rosso = next(t for t in s.query(Task).all()
                       if colore_unita(t.data_fine, t.stato, oggi) == "rosso")

        # ordine 2 PRIMA di ordine 1, per provare che l'order_by lavora.
        pezzi = [
            (t_verde, "verde-B", 2, "Da iniziare", 4, None),
            (t_verde, "verde-A", 1, "Da iniziare", 8, t_verde.dipendente_id),
            (t_rosso, "rosso-B", 2, "Sospeso", 3, None),
            (t_rosso, "rosso-A", 1, "Da iniziare", 6, None),
            (t_rosso, "rosso-ANNULLATO", 3, "Annullato", 5, None),
        ]
        for padre, nome, ordine, stato, ore, did in pezzi:
            st = Sottotask(task_id=padre.id, nome=f"[FIXTURE] {nome}",
                           ordine=ordine, stato=stato, ore_stimate=ore,
                           dipendente_id=did)
            s.add(st)
            creati.append(st)
        s.commit()
        ids_creati = [st.id for st in creati]

        payload = _payload()
        nodi = {tid: n for liv, tid, n in _unita(payload) if liv == "task"}

        # ── il task VERDE: 2 pezzi, verdi, ordinati, con anagrafica giusta
        tv = nodi[t_verde.id]
        assert "sottotask" in tv, "chiave sottotask assente sul task scomposto"
        assert len(tv["sottotask"]) == 2, tv["sottotask"]
        assert [p["ordine"] for p in tv["sottotask"]] == [1, 2], "order_by non rispettato"
        assert [p["nome"] for p in tv["sottotask"]] == \
            ["[FIXTURE] verde-A", "[FIXTURE] verde-B"]
        for p in tv["sottotask"]:
            assert set(p) == CAMPI_SOTTOTASK, set(p)
            assert p["semaforo"]["colore"] == "verde", (
                "il pezzo NON sta ereditando la data del padre")
            assert p["semaforo"]["origine"] is None
            assert p["semaforo"]["figli_rossi"] == 0
            assert "data_inizio" not in p and "data_fine" not in p
            assert "percentuale" not in p
        # anagrafica: stato, ore_stimate, override assegnatario
        a, b = tv["sottotask"]
        assert (a["stato"], a["ore_stimate"]) == ("Da iniziare", 8)
        assert (b["stato"], b["ore_stimate"]) == ("Da iniziare", 4)
        assert a["dipendente_id"] == t_verde.dipendente_id  # override esplicito
        assert b["dipendente_id"] is None                   # eredita → NULL, non ""
        assert b["dipendente_nome"] == ""
        # il task resta verde e senza origine: i pezzi non lo peggiorano
        assert tv["semaforo"]["colore"] == "verde"
        assert tv["semaforo"]["origine"] is None

        # ── il task ROSSO: l'annullato sparisce, i vivi ereditano il rosso
        tr = nodi[t_rosso.id]
        nomi = [p["nome"] for p in tr["sottotask"]]
        assert len(tr["sottotask"]) == 2, nomi
        assert "[FIXTURE] rosso-ANNULLATO" not in nomi, "pezzo Annullato serializzato"
        per_nome = {p["nome"]: p for p in tr["sottotask"]}
        vivo = per_nome["[FIXTURE] rosso-A"]
        sospeso = per_nome["[FIXTURE] rosso-B"]
        assert vivo["semaforo"]["colore"] == "rosso", (
            "il pezzo vivo deve ereditare la finestra chiusa del padre")
        assert vivo["semaforo"]["origine"] == "propria"
        # Un Sospeso è FERMO, non finito: grigio (01/09/2026, caso P006).
        assert sospeso["semaforo"]["colore"] == "grigio", "un Sospeso è fermo"
        assert sospeso["semaforo"]["origine"] == "propria"
        assert sospeso["stato"] == "Sospeso"
        # il task rosso di suo E dai pezzi
        assert tr["semaforo"]["colore"] == "rosso"
        assert tr["semaforo"]["origine"] == "entrambe"
        assert tr["semaforo"]["figli_rossi"] == 1, "il Sospeso non conta"

        # ── nessun pezzo con semaforo null, e i task non scomposti intatti
        for liv, tid, n in _unita(payload):
            if liv != "task" or "sottotask" not in n:
                continue
            for p in n["sottotask"]:
                assert p["semaforo"] is not None, (tid, p["id"])
        non_scomposti = [n for liv, _, n in _unita(payload)
                         if liv == "task" and "sottotask" not in n]
        assert len(non_scomposti) >= 100, "attesi molti task senza pezzi"

        print(f"✅ 8. sottotask annidati — {t_verde.id} (2 verdi, ordinati) e "
              f"{t_rosso.id} (1 rosso ereditato + 1 sospeso, annullato escluso); "
              f"{len(non_scomposti)} task senza chiave `sottotask`")
    finally:
        for st in creati:
            s.delete(st)
        s.commit()
        if ids_creati:
            assert s.query(Sottotask).filter(
                Sottotask.id.in_(ids_creati)).count() == 0, "fixture non ripulita"
        assert s.query(Sottotask).count() == 0, "residui in tabella sottotask"
        s.close()


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
    test_sottotask_annidati()
    test_endpoint_risponde_200()
    print()
    print("=" * 60)
    print("TUTTI I TEST PASSATI ✅")
