"""
Test dell'AGGREGAZIONE del semaforo (`semaforo_progetti`) — sotto-edit 2.

A DIFFERENZA di `test_semaforo.py`, questi test RICHIEDONO il database: girano
su gantt_test, ricostruito da migration e seed dalla fixture `db_test` (vedi
conftest.py), e camminano la gerarchia che il seed crea. La suite pura degli helper
(`colore_unita`, `peggio_semaforo`, `_nodo_semaforo`) resta là e continua a
girare senza database — i due file sono separati per non perdere quella
proprietà.

I conteggi attesi sono confrontati con una query SQL INDIPENDENTE, scritta a
mano nel test: se l'aggregazione e la query divergono, uno dei due sbaglia e il
test lo dice. Non si asseriscono numeri hard-coded che il codice stesso ha
prodotto — sarebbe un test che si dà ragione da solo.

FIXTURE — due casi non esistono in DB (0 task senza data, 0 sottotask) e vanno
costruiti. Ogni fixture scrive, verifica e RIPULISCE nel `finally`: ripristina i
valori esatti che aveva letto prima, e cancella per chiave primaria le righe che
ha creato. Nessuna fixture lascia traccia.
"""

from datetime import timedelta

import pytest
from sqlalchemy import event, text

from data_db_impl import semaforo_progetti, colore_unita
from models import get_session, engine, Progetto, Fase, Task, Sottotask

pytestmark = pytest.mark.usefixtures("db_test")


# «Oggi» è la data del seed, dalla fixture `oggi_del_seed`: le date del seed
# sono assolute, e contro l'orologio vero i colori cambierebbero col calendario.


# ── conta-query, per la verifica «niente N+1» ────────────────────────────
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


def _tutti_i_progetti():
    s = get_session()
    try:
        return [p.id for p in s.query(Progetto).all()]
    finally:
        s.close()


def _conta_colori(alberi, livello):
    """Conta i colori a un livello, camminando il dict annidato."""
    out = {}
    for nodo_p in alberi.values():
        if livello == "progetto":
            nodi = [nodo_p]
        elif livello == "fase":
            nodi = list(nodo_p["fasi"].values())
        else:
            nodi = [t for f in nodo_p["fasi"].values() for t in f["task"].values()]
        for n in nodi:
            out[n["semaforo"]] = out.get(n["semaforo"], 0) + 1
    return out


# ══════════════════════════════════════════════════════════════════════
# 1. I CONTEGGI, contro una query SQL indipendente
# ══════════════════════════════════════════════════════════════════════

def test_conteggi_contro_sql_indipendente(oggi_del_seed):
    """1. Colori aggregati == quelli che l'SQL calcola per conto suo.

    L'SQL qui sotto NON usa il codice applicativo: replica la regola a mano
    (stati chiusi espliciti, `data_fine < :oggi` stretto) e fa il
    peggio-dei-figli con un EXISTS. Se i due divergono, il test fallisce senza
    dire chi ha ragione — ed è il punto: due strade indipendenti allo stesso
    numero.
    """
    alberi = semaforo_progetti(_tutti_i_progetti(), oggi=oggi_del_seed)

    chiusi = "('Completato','Completata','Sospeso','Sospesa','Annullato','Annullata','Eliminato')"
    s = get_session()
    try:
        # task rossi = vivi con la finestra chiusa
        sql_task_rossi = s.execute(text(
            f"SELECT count(*) FROM task WHERE stato NOT IN {chiusi} "
            f"AND data_fine < :oggi"
        ), {"oggi": oggi_del_seed}).scalar()

        # fase rossa = rossa di suo OPPURE con almeno un task rosso
        sql_fasi_rosse = s.execute(text(
            f"SELECT count(*) FROM fasi f WHERE "
            f"  (f.stato NOT IN {chiusi} AND f.data_fine < :oggi) "
            f"  OR EXISTS (SELECT 1 FROM task t WHERE t.fase_id = f.id "
            f"             AND t.stato NOT IN {chiusi} AND t.data_fine < :oggi)"
        ), {"oggi": oggi_del_seed}).scalar()

        # progetto rosso = rosso di suo OPPURE con almeno una fase rossa
        sql_prog_rossi = s.execute(text(
            f"SELECT count(*) FROM progetti p WHERE "
            f"  (p.stato NOT IN {chiusi} AND p.data_fine < :oggi) "
            f"  OR EXISTS (SELECT 1 FROM fasi f WHERE f.progetto_id = p.id AND ("
            f"     (f.stato NOT IN {chiusi} AND f.data_fine < :oggi) "
            f"     OR EXISTS (SELECT 1 FROM task t WHERE t.fase_id = f.id "
            f"                AND t.stato NOT IN {chiusi} AND t.data_fine < :oggi)))"
        ), {"oggi": oggi_del_seed}).scalar()
    finally:
        s.close()

    c_task = _conta_colori(alberi, "task")
    c_fase = _conta_colori(alberi, "fase")
    c_prog = _conta_colori(alberi, "progetto")

    assert c_task.get("rosso", 0) == sql_task_rossi, (c_task, sql_task_rossi)
    assert c_fase.get("rosso", 0) == sql_fasi_rosse, (c_fase, sql_fasi_rosse)
    assert c_prog.get("rosso", 0) == sql_prog_rossi, (c_prog, sql_prog_rossi)


# ══════════════════════════════════════════════════════════════════════
# 2. LA PROVENIENZA
# ══════════════════════════════════════════════════════════════════════

def test_provenienza(oggi_del_seed):
    """2. origine="figli" dove il calendario proprio regge; "propria"/"entrambe"
    dove il progetto è scaduto di suo.

    Non si codificano gli id: si deriva dal DB chi DEVE avere quale origine, e
    si verifica che l'aggregazione concordi. Così il test regge se i dati
    cambiano.
    """
    ids = _tutti_i_progetti()
    alberi = semaforo_progetti(ids, oggi=oggi_del_seed)

    s = get_session()
    try:
        progetti = {p.id: p for p in s.query(Progetto).all()}
    finally:
        s.close()

    visti = {"figli": [], "propria": [], "entrambe": []}
    for pid, nodo in alberi.items():
        if nodo["semaforo"] != "rosso":
            assert nodo["origine"] is None or nodo["semaforo"] == "grigio"
            continue
        p = progetti[pid]
        proprio = colore_unita(p.data_fine, p.stato, oggi_del_seed)
        da_figli = any(f["semaforo"] == "rosso" for f in nodo["fasi"].values())

        atteso = ("entrambe" if proprio == "rosso" and da_figli
                  else "propria" if proprio == "rosso" else "figli")
        assert nodo["origine"] == atteso, (pid, nodo["origine"], atteso)
        visti[atteso].append(pid)

        # figli_rossi = fasi rosse DIRETTE, non i task rossi dei nipoti.
        fasi_rosse = sum(1 for f in nodo["fasi"].values() if f["semaforo"] == "rosso")
        assert nodo["figli_rossi"] == fasi_rosse, pid
        task_rossi = sum(
            sum(1 for t in f["task"].values() if t["semaforo"] == "rosso")
            for f in nodo["fasi"].values()
        )
        # la somma dei figli_rossi delle fasi ricostruisce i task rossi:
        # i diretti danno i totali, il contrario non vale.
        assert sum(f["figli_rossi"] for f in nodo["fasi"].values()) == task_rossi

    assert visti["figli"], "atteso almeno un progetto rosso per colpa dei figli"


def test_progetto_verde_non_ha_origine(oggi_del_seed):
    """3. Progetto verde con tutti i figli verdi → origine None, figli_rossi 0."""
    alberi = semaforo_progetti(_tutti_i_progetti(), oggi=oggi_del_seed)
    verdi = [(pid, n) for pid, n in alberi.items() if n["semaforo"] == "verde"]
    assert verdi, "atteso almeno un progetto verde"
    for pid, n in verdi:
        assert n["origine"] is None, pid
        assert n["figli_rossi"] == 0, pid
        for f in n["fasi"].values():
            assert f["semaforo"] == "verde" and f["origine"] is None, pid


# ══════════════════════════════════════════════════════════════════════
# 4. FIXTURE GRIGIO — 0 casi reali, va costruito
# ══════════════════════════════════════════════════════════════════════

def test_fixture_grigio(oggi_del_seed):
    """4. Task vivo senza data → grigio; ingrigisce la fase; ma un fratello
    rosso vince (rosso > grigio).

    Scrive su due task del seed, verifica, e ripristina i valori esatti letti prima.
    """
    s = get_session()
    # cerca una fase VERDE con almeno 2 task vivi e verdi: così il grigio e il
    # rosso che introduciamo sono l'unica causa di quello che vedremo.
    fase = None
    for f in s.query(Fase).all():
        vivi = [t for t in f.task
                if colore_unita(t.data_fine, t.stato, oggi_del_seed) == "verde"
                and t.stato not in ("Completato", "Sospeso", "Annullato", "Eliminato")]
        if colore_unita(f.data_fine, f.stato, oggi_del_seed) == "verde" and len(vivi) >= 2:
            fase, t_grigio, t_rosso = f, vivi[0], vivi[1]
            break
    assert fase is not None, "nessuna fase verde con 2 task vivi verdi"

    pid, fid = fase.progetto_id, fase.id
    orig_grigio = t_grigio.data_fine
    orig_rosso = t_rosso.data_fine
    id_grigio, id_rosso = t_grigio.id, t_rosso.id

    try:
        # ── (a) un solo task vivo senza data → grigio, e la fase lo eredita
        t_grigio.data_fine = None
        s.commit()

        albero = semaforo_progetti([pid], oggi=oggi_del_seed)
        nodo_fase = albero[pid]["fasi"][fid]
        assert nodo_fase["task"][id_grigio]["semaforo"] == "grigio"
        assert nodo_fase["semaforo"] == "grigio", nodo_fase
        assert nodo_fase["origine"] == "figli"
        assert nodo_fase["figli_rossi"] == 0
        assert albero[pid]["semaforo"] in ("grigio", "rosso")

        # ── (b) un fratello ROSSO vince sul grigio (rosso > grigio)
        t_rosso.data_fine = oggi_del_seed - timedelta(days=10)
        s.commit()

        albero = semaforo_progetti([pid], oggi=oggi_del_seed)
        nodo_fase = albero[pid]["fasi"][fid]
        assert nodo_fase["task"][id_grigio]["semaforo"] == "grigio"
        assert nodo_fase["task"][id_rosso]["semaforo"] == "rosso"
        assert nodo_fase["semaforo"] == "rosso", "il grigio ha nascosto il rosso"
        assert nodo_fase["origine"] == "figli"
        assert nodo_fase["figli_rossi"] == 1, "il grigio non deve contare"

    finally:
        t_grigio.data_fine = orig_grigio
        t_rosso.data_fine = orig_rosso
        s.commit()
        # ripristino verificato, non solo tentato
        s.refresh(t_grigio); s.refresh(t_rosso)
        assert t_grigio.data_fine == orig_grigio and t_rosso.data_fine == orig_rosso
        s.close()


# ══════════════════════════════════════════════════════════════════════
# 5. FIXTURE SOTTOTASK — l'eredità della data del padre
# ══════════════════════════════════════════════════════════════════════

def test_fixture_sottotask_eredita_la_data_del_padre(oggi_del_seed):
    """5. I sottotask ereditano `data_fine` dal task padre, non None.

    È la mina: senza eredità ogni sottotask vivo sarebbe grigio, e ogni task
    scomposto diventerebbe grigio con lui. In DB ci sono 0 sottotask, quindi il
    guasto non si vedrebbe fino alla prima scomposizione vera.
    """
    s = get_session()
    creati = []
    try:
        # (a) padre VERDE (data futura) → i pezzi devono essere VERDI, non grigi
        t_verde = next(
            t for t in s.query(Task).all()
            if colore_unita(t.data_fine, t.stato, oggi_del_seed) == "verde"
            and t.stato not in ("Completato", "Sospeso", "Annullato", "Eliminato")
        )
        # (b) padre ROSSO (data passata) → i pezzi vivi ereditano il rosso
        t_rosso = next(
            t for t in s.query(Task).all()
            if colore_unita(t.data_fine, t.stato, oggi_del_seed) == "rosso"
        )

        for padre, nomi in ((t_verde, ["pezzo A", "pezzo B"]),
                            (t_rosso, ["pezzo C", "pezzo D"])):
            for nome in nomi:
                st = Sottotask(task_id=padre.id, nome=f"[FIXTURE] {nome}",
                               ore_stimate=4, stato="Da iniziare")
                s.add(st)
                creati.append(st)
        s.commit()
        ids_creati = [st.id for st in creati]

        fid_v, pid_v = t_verde.fase_id, t_verde.progetto_id
        fid_r, pid_r = t_rosso.fase_id, t_rosso.progetto_id

        alberi = semaforo_progetti(list({pid_v, pid_r}), oggi=oggi_del_seed)

        # ── padre verde: i pezzi NON sono grigi, e il task resta verde
        nodo_v = alberi[pid_v]["fasi"][fid_v]["task"][t_verde.id]
        assert "sottotask" in nodo_v, "chiave sottotask attesa sui task scomposti"
        assert len(nodo_v["sottotask"]) == 2
        for n in nodo_v["sottotask"].values():
            assert n["semaforo"] == "verde", (
                "sottotask grigio: NON sta ereditando la data del padre")
            assert n["figli_rossi"] == 0 and n["origine"] is None
        assert nodo_v["semaforo"] == "verde"
        assert nodo_v["origine"] is None

        # ── padre rosso: i pezzi vivi ereditano la finestra chiusa
        nodo_r = alberi[pid_r]["fasi"][fid_r]["task"][t_rosso.id]
        for n in nodo_r["sottotask"].values():
            assert n["semaforo"] == "rosso", n
            assert n["origine"] == "propria"
        assert nodo_r["semaforo"] == "rosso"
        assert nodo_r["origine"] == "entrambe", "rosso di suo E dai pezzi"
        assert nodo_r["figli_rossi"] == 2

        # ── un pezzo Sospeso è FERMO: grigio, non verde e non rosso.
        # Il semaforo si astiene su ciò che è stato messo in pausa (01/09/2026,
        # caso P006). Non conta fra i rossi, e non nasconde il fratello rosso.
        creati[2].stato = "Sospeso"   # pezzo C, sotto il padre rosso
        s.commit()
        alberi = semaforo_progetti([pid_r], oggi=oggi_del_seed)
        nodo_r = alberi[pid_r]["fasi"][fid_r]["task"][t_rosso.id]
        assert nodo_r["sottotask"][creati[2].id]["semaforo"] == "grigio"
        assert nodo_r["figli_rossi"] == 1
        # rosso > grigio: il pezzo fermo non attenua il pezzo in ritardo.
        assert nodo_r["semaforo"] == "rosso"
        assert nodo_r["origine"] == "entrambe"

        # ── i task NON scomposti non hanno la chiave `sottotask`
        altri = [t for t in alberi[pid_r]["fasi"][fid_r]["task"].items()
                 if t[0] != t_rosso.id]
        for tid, n in altri:
            assert "sottotask" not in n, tid

    finally:
        for st in creati:
            s.delete(st)
        s.commit()
        rimasti = (s.query(Sottotask)
                   .filter(Sottotask.id.in_(ids_creati)).count()
                   if creati else 0)
        assert rimasti == 0, "fixture sottotask non ripulita"
        assert s.query(Sottotask).count() == 0, "residui in tabella sottotask"
        s.close()


# ══════════════════════════════════════════════════════════════════════
# 6. NIENTE N+1
# ══════════════════════════════════════════════════════════════════════

def test_fixture_sospeso_in_aggregazione(oggi_del_seed):
    """4-bis. Un figlio SOSPESO (grigio) nel peggio-dei-figli.

    Due proprietà, e sono opposte fra loro — è il senso di mettere il grigio in
    mezzo all'ordinamento (rosso > grigio > verde):
      - un task sospeso INGRIGISCE la fase se è il peggio: se una parte del
        lavoro è ferma, la fase non può dire «tutto a posto»;
      - ma NON nasconde un fratello rosso: un dubbio non copre una certezza.
    In DB non ci sono task né fasi sospese (0 su 114, 0 su 71), quindi il caso
    va costruito. Scrive su due task del seed e ripristina i valori letti prima.
    """
    s = get_session()
    fase = None
    for f in s.query(Fase).all():
        vivi = [t for t in f.task
                if colore_unita(t.data_fine, t.stato, oggi_del_seed) == "verde"
                and t.stato not in ("Completato", "Sospeso", "Annullato", "Eliminato")]
        if colore_unita(f.data_fine, f.stato, oggi_del_seed) == "verde" and len(vivi) >= 2:
            fase, t_sosp, t_rosso = f, vivi[0], vivi[1]
            break
    assert fase is not None, "nessuna fase verde con 2 task vivi verdi"

    pid, fid = fase.progetto_id, fase.id
    id_sosp, id_rosso = t_sosp.id, t_rosso.id
    # Tre valori toccati, tre valori salvati — uno per riga, così il ripristino
    # non può appaiare la colonna sbagliata.
    orig_sosp_stato = t_sosp.stato
    orig_sosp_fine = t_sosp.data_fine
    orig_rosso_fine = t_rosso.data_fine

    try:
        # ── (a) un task sospeso → grigio, e la fase lo eredita
        t_sosp.stato = "Sospeso"
        s.commit()

        albero = semaforo_progetti([pid], oggi=oggi_del_seed)
        nodo_fase = albero[pid]["fasi"][fid]
        assert nodo_fase["task"][id_sosp]["semaforo"] == "grigio"
        assert nodo_fase["semaforo"] == "grigio", nodo_fase
        assert nodo_fase["origine"] == "figli"
        assert nodo_fase["figli_rossi"] == 0

        # ── (b) un fratello ROSSO vince sul grigio-sospeso
        t_rosso.data_fine = oggi_del_seed - timedelta(days=10)
        s.commit()

        albero = semaforo_progetti([pid], oggi=oggi_del_seed)
        nodo_fase = albero[pid]["fasi"][fid]
        assert nodo_fase["task"][id_sosp]["semaforo"] == "grigio"
        assert nodo_fase["task"][id_rosso]["semaforo"] == "rosso"
        assert nodo_fase["semaforo"] == "rosso", "il sospeso ha nascosto il rosso"
        assert nodo_fase["figli_rossi"] == 1, "il sospeso non deve contare"

        # ── (c) il sospeso resta grigio anche quando è LUI a essere scaduto
        t_sosp.data_fine = oggi_del_seed - timedelta(days=200)
        s.commit()
        albero = semaforo_progetti([pid], oggi=oggi_del_seed)
        assert albero[pid]["fasi"][fid]["task"][id_sosp]["semaforo"] == "grigio", (
            "un sospeso scaduto NON è rosso — è il caso P006")

    finally:
        t_sosp.stato = orig_sosp_stato
        t_sosp.data_fine = orig_sosp_fine
        t_rosso.data_fine = orig_rosso_fine
        s.commit()
        s.refresh(t_sosp); s.refresh(t_rosso)
        assert (t_sosp.stato, t_sosp.data_fine) == (orig_sosp_stato, orig_sosp_fine)
        assert t_rosso.data_fine == orig_rosso_fine
        s.close()


def test_niente_n_piu_uno(oggi_del_seed):
    """6. Le query sono costanti: non crescono col numero di unità."""
    ids = _tutti_i_progetti()

    with ContaQuery() as c1:
        semaforo_progetti(ids[:1], oggi=oggi_del_seed)
    with ContaQuery() as c2:
        alberi = semaforo_progetti(ids, oggi=oggi_del_seed)

    unita = sum(1 + len(p["fasi"]) + sum(len(f["task"]) for f in p["fasi"].values())
                for p in alberi.values())
    assert c2.n == c1.n, f"{c1.n} query su 1 progetto, {c2.n} su {len(ids)}"
    assert c2.n <= 3, f"{c2.n} query per {unita} unità: attese 2 (gerarchia + pezzi)"


def test_guardia_input_vuoto(oggi_del_seed):
    """Extra: lista vuota → {} senza toccare il database."""
    with ContaQuery() as c:
        assert semaforo_progetti([]) == {}
        assert semaforo_progetti(None) == {}
    assert c.n == 0, "la guardia deve precedere qualunque query"
    assert semaforo_progetti(["P-non-esiste"], oggi=oggi_del_seed) == {}
