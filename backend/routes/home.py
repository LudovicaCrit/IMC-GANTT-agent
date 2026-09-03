"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/home.py — Router per endpoint /api/home (Home management)
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Aggrega le criticità dei progetti per la vista PM/manager (la "Home"
manageriale). Primo endpoint: lo sforamento ore (ore_consumate vs ore_vendute,
budget commerciale). È lavoro additivo: non tocca endpoint/modelli esistenti.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/home/criticita              │ GET      │ get_current_user (self-or-mgr)│
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/home/criticita
   - La route è sottile: delega tutto allo strato dati.
     • progetti_attivi_visibili(current_user): id dei progetti ATTIVI visibili
       (filtro self-or-manager — manager vede tutti, l'user solo i suoi via
       pm_id == dipendente_id).
     • criticita_sforamento_progetti(ids): calcolo sforamento col contratto
       fisso (liste-di-dict).
   - Tornano solo i progetti con almeno una criticità; i sani non compaiono.
   - Nessuna query SQL qui: la conoscenza del DB vive nello strato dati
     (coerente col Blocco 4 e con la futura conversione ORM).

PATTERN AUTH USATI
──────────────────
- `get_current_user`: l'endpoint è visibile sia agli user (filtrati ai propri
  progetti, nello strato dati) sia ai manager (tutti). Lo stile self-or-manager
  è quello di routes/dipendenti.py:dettaglio_dipendente.

DIPENDENZE
──────────
- `data` (modulo): `progetti_attivi_visibili`, `criticita_sforamento_progetti`.
- `deps`: `get_current_user`.
- `models`: `Utente` (solo type hint).

NOTE DI DIREZIONE
─────────────────
Il campo `tipo` delle criticità è una stringa-enum (oggi solo
"superamento_ore"), volutamente estendibile (futuri "slittamento_date",
"superamento_pianificato", ...). NON irrigidirlo a un booleano. Nessun
semaforo verde/giallo/rosso qui: arriverà col calcolo ritardabilità vero,
dopo il backend urgenza.

STORIA
──────
Aggiunto il 9 giugno 2026 come primo endpoint della Home management.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func

from deps import get_current_user
from models import (
    Utente, Progetto, Task, Dipendente, Azienda, get_session, LIVELLI_URGENZA,
)
from data import (
    progetti_attivi_visibili, criticita_sforamento_progetti,
    semaforo_progetti, carico_settimanale_dipendente, RANK_SEMAFORO,
)
from utils import get_oggi


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("/criticita")
def lista_criticita(current_user: Utente = Depends(get_current_user)):
    """Criticità di sforamento ore dei progetti attivi (vista PM/manager).

    Filtro identità (self-or-manager) e calcolo sono entrambi delegati allo
    strato dati: la route si limita a comporre le due funzioni.
    """
    ids = progetti_attivi_visibili(current_user)
    return criticita_sforamento_progetti(ids)


# ── Ordinamento dell'attenzione ──────────────────────────────────────────
# `LIVELLI_URGENZA` è ordinata dal meno al più urgente, quindi l'indice È il
# rango — non serve una seconda mappa che possa divergere dalla scala.
RANK_URGENZA = {liv: i for i, liv in enumerate(LIVELLI_URGENZA)}


def _peso_attenzione(voce):
    """Chiave di ordinamento: prima la GRAVITÀ, poi l'URGENZA, poi l'id.

    DUE ASSI DISTINTI, e l'ordine fra loro conta. Il semaforo dice «questo sta
    andando male», l'urgenza dice «questo non può aspettare»: sono cose diverse,
    e un progetto che va male viene prima di uno che va bene ma è urgente —
    l'urgenza ORDINA a parità di gravità, non la sostituisce.

    L'URGENZA È SCRITTA ORA ANCHE SE OGGI NON ORDINA NIENTE: tutti e 38 i
    progetti sono a 'Medio-Bassa' (il valore che la migration ha assegnato al
    default mai scelto), quindi il secondo criterio è piatto e i rossi restano
    pari fra loro. Diventa vivo il giorno in cui il PM differenzia, senza che
    nessuno debba ricordarsi di tornare qui.

    `progetto_id` come TERZO criterio: senza, due progetti con stessa gravità e
    stessa urgenza uscirebbero nell'ordine in cui Postgres li ha restituiti —
    che cambia dopo un UPDATE. È lo stesso spareggio, per la stessa ragione, di
    `Fase.task` (`order_by="Task.ordine, Task.id"`).

    Negativi sui primi due perché `sorted` è crescente e qui il PIÙ grave viene
    prima; l'id resta crescente.
    """
    return (
        -RANK_SEMAFORO.get(voce["semaforo"]["colore"], 0),
        -RANK_URGENZA.get(voce["urgenza"], 0),
        voce["progetto_id"],
    )


def _voce_attenzione(p, nodo, sforamenti, oggi):
    """La riga di `attenzione` per un progetto, o None se non ne ha bisogno.

    `motivi` è una LISTA e non un campo singolo perché le ragioni si sommano: un
    progetto può essere in ritardo E aver sforato le ore, e sapere che sono due
    cose insieme cambia la decisione. Ogni motivo ha un `tipo` stringa-enum,
    estendibile come quello di `criticita_sforamento_progetti`.

    Nessun motivo → None → il progetto NON entra nella lista. È la convenzione
    di `criticita_sforamento_progetti` («i progetti sani non compaiono»), ed è
    ciò che tiene l'elenco corto abbastanza da essere letto.
    """
    colore = nodo["semaforo"] if nodo else "verde"
    motivi = []

    # 1. Semaforo rosso. `origine` distingue «il problema è di questo progetto»
    #    da «il problema è dentro»: due situazioni che si raccontano diverse, e
    #    il dato lo abbiamo già.
    if colore == "rosso":
        motivi.append({"tipo": "semaforo_rosso",
                       "origine": nodo["origine"],
                       "figli_rossi": nodo["figli_rossi"]})

    # 2. Scadenza passata. Separato dal semaforo pur essendone spesso la causa:
    #    il semaforo dice il COLORE, questo dice DI QUANTO — e «scaduto da 32
    #    giorni» è il numero su cui si decide.
    if p.data_fine and p.data_fine < oggi:
        motivi.append({"tipo": "scaduto",
                       "giorni": (oggi - p.data_fine).days,
                       "data_fine": p.data_fine.isoformat()})

    # 3. Sforamento ore. Forma invariata rispetto a `/criticita`, che resta
    #    esposto: chi lo consuma già non deve imparare un secondo formato.
    if p.id in sforamenti:
        motivi.append({"tipo": "superamento_ore", "dettaglio": sforamenti[p.id]})

    if not motivi:
        return None

    return {
        "progetto_id": p.id,
        "nome": p.nome,
        "cliente": p.cliente,
        "pm_id": p.pm_id,
        # `stato` e `figli_rossi` servono al SOLO consumatore di questa voce, e
        # senza di loro direbbe il falso. `PastigliaSemaforo` (frontend) li
        # legge per costruire il tooltip:
        #   - `stato` distingue i DUE GRIGI. P006 è grigio perché SOSPESO, non
        #     perché gli manchi la data (ce l'ha, 2026-03-31): senza lo stato il
        #     tooltip direbbe «manca la data di fine», che è falso.
        #   - `figli_rossi` dentro il sotto-oggetto `semaforo`, dove la
        #     pastiglia lo cerca: con `origine="figli"` e il campo assente
        #     scriverebbe «0 fasi sono in ritardo».
        # Sono entrambi già in mano qui: non costano una query.
        "stato": p.stato,
        "semaforo": {"colore": colore,
                     "origine": nodo["origine"] if nodo else None,
                     "figli_rossi": nodo["figli_rossi"] if nodo else 0},
        "urgenza": p.urgenza,
        "data_fine": p.data_fine.isoformat() if p.data_fine else None,
        "motivi": motivi,
    }


def _conta(colori):
    out = {}
    for c in colori:
        out[c] = out.get(c, 0) + 1
    return out


@router.get("/dashboard")
def dashboard(current_user: Utente = Depends(get_current_user)):
    """Lo stato delle cose, dal punto di vista di chi guarda (Home, Tappa 1).

    TRE BLOCCHI, e la loro asimmetria è il design:
      `rami`    — un blocco PARITARIO per società (IMC-Improve, Innovation
                  Plaza), ciascuno col proprio polso e la propria attenzione.
      `interne` — DUE CONTATORI e nient'altro.
      `team`    — un numero solo, trasversale.

    Ogni blocco porta il POLSO accanto all'ATTENZIONE, e la coppia non è
    decorativa: una Home che mostra solo problemi diventa una pagina che si
    evita di aprire, e smette di essere letta proprio quando servirebbe.

    ── PERCHÉ SI SEGMENTA PER `azienda_id` E NON PER `tipologia` ─────────
    Oggi i due campi COINCIDONO al 100% (ordinario↔Improve 9, bando↔Innovation
    Plaza 2, interna↔NULL 27), quindi segmentare per l'uno o per l'altro dà lo
    stesso risultato — ma non è la stessa domanda, e la differenza si vedrà il
    giorno in cui un progetto rompe la corrispondenza (il modello lo permette:
    le due colonne sono indipendenti).
    `azienda_id` risponde a «DI CHI è questo lavoro», che è la domanda di una
    Home divisa per società; `tipologia` risponde a «CHE TIPO di lavoro è». Un
    bando è tale perché lo fa Innovation Plaza, non viceversa. È anche il
    criterio di `margini_economia`, che espone `totali_per_azienda`: due pagine
    che segmentano lo stesso perimetro devono farlo sullo stesso campo, o i
    conti non torneranno fra loro.

    ── LE ATTIVITÀ INTERNE SONO FUORI DAI RAMI, E RIDOTTE A DUE NUMERI ──
    Sono 27 progetti su 38 — la maggioranza — e in tre colonne pari
    schiaccerebbero i due rami che portano fatturato.
    Ma la ragione vera è che il loro «sforamento ore» è rumore di NATURA
    diversa. Misurato: PC02 «Aggiornamento strumenti IA» ha 64h vendute e 103
    consumate, PC03 «Corso Excel avanzato» 60 contro 142. Su un progetto-cliente
    quel rapporto è un contratto eroso; su un corso interno `ore_vendute` è una
    stima di monte-ore e nessun cliente paga la differenza. Metterli nella
    stessa lista dei ritardi-cliente insegna a ignorare la lista.
    `margini_economia` fa la stessa scelta da tempo (`tipologia != "interna"`).
    Restano due contatori, che il frontend linka alla loro pagina: visibili, non
    confusi coi clienti.

    ── I RAMI SONO QUELLI CHE CHI GUARDA HA DAVVERO ─────────────────────
    Non due blocchi fissi: si costruiscono dalle aziende presenti nei progetti
    visibili. Un manager li vede entrambi; un PM con soli progetti Improve vede
    un ramo solo, e non una colonna vuota che gli chiede perché è vuota.

    ── IL FILTRO RUOLO PRIMA, LA SEGMENTAZIONE DOPO ─────────────────────
    `progetti_attivi_visibili` decide COSA questa persona può vedere; la
    divisione per azienda è una presentazione di quel risultato. L'ordine non è
    invertibile: segmentare prima e filtrare poi vorrebbe dire calcolare su
    progetti che non si possono mostrare.
    Due scope di stato, una sola regola d'identità: il polso usa
    `solo_attivi=False` (i progetti COMPLETATI sono la vittoria più leggibile
    che ci sia), l'attenzione il default (un progetto chiuso non chiede
    decisioni). L'attenzione è quindi sempre un SOTTOINSIEME del polso.

    ── `team` È GLOBALE, E NON PER RAMO ─────────────────────────────────
    Sembrerebbe naturale spezzarlo (`Dipendente.azienda_id` è NOT NULL: 13
    Improve, 5 Innovation Plaza). Non si fa, per tre fatti misurati:
      1. La saturazione è una proprietà della PERSONA, non del ramo:
         `carico_settimanale_dipendente` somma TUTTI i suoi task — commerciali
         di entrambe le società E attività interne. Attribuirla a un ramo
         significherebbe imputargli un carico che in parte nasce altrove.
      2. Le persone ATTRAVERSANO i rami: Innovation Plaza ha 7 task su progetti
         IMC-Improve, e D009 lavora su entrambi. Contarla in ciascun ramo la
         conterebbe DUE volte, e la somma dei rami non sarebbe più il totale.
      3. Tutti lavorano anche sulle interne (47 task), che dai rami sono
         escluse: un numero per ramo si misurerebbe contro un carico generato
         in parte da lavoro che la Home non mostra in nessun ramo.
    Un numero solo, onesto, senza doppi conteggi.
    """
    ids_polso = progetti_attivi_visibili(current_user, solo_attivi=False)
    ids_attivi = progetti_attivi_visibili(current_user)

    # Nessun progetto visibile — un dipendente senza incarichi, o un PM di
    # progetti tutti chiusi. Si risponde 200 con la STESSA FORMA (rami vuoti,
    # contatori a zero): la Home non deve rompersi per nessuno, e «non hai
    # progetti» è una risposta legittima che il frontend rende come stato vuoto.
    if not ids_polso:
        return {"rami": [], "interne": {"n_totali": 0, "n_in_attenzione": 0},
                "team": {"n_persone": 0, "sovraccarichi": 0}}

    oggi = get_oggi()
    oggi = oggi.date() if hasattr(oggi, "date") else oggi

    # I COLORI, una chiamata sola per tutto lo scope largo. L'attenzione ne
    # pesca i suoi senza una seconda invocazione.
    alberi = semaforo_progetti(ids_polso)
    # Lo sforamento ore, sui soli ATTIVI: è materia di attenzione, non di polso.
    sforamenti = {c["progetto_id"]: c["criticita"]
                  for c in criticita_sforamento_progetti(ids_attivi)}

    session = get_session()
    try:
        aziende = {a.id: a.nome for a in session.query(Azienda).all()}
        progetti = session.query(Progetto).filter(Progetto.id.in_(ids_polso)).all()

        # Task completati per progetto, in UNA query: serve per il polso di ogni
        # ramo, e chiederli progetto per progetto sarebbe un N+1.
        completati = dict(
            session.query(Task.progetto_id, func.count(Task.id))
            .filter(Task.progetto_id.in_(ids_polso), Task.stato == "Completato")
            .group_by(Task.progetto_id).all()
        )

        # Il TEAM: le persone con task sui progetti visibili — non l'anagrafica
        # intera. Per un PM «il team» sono le persone sui suoi progetti.
        dip_ids = [d for (d,) in session.query(Task.dipendente_id)
                   .filter(Task.progetto_id.in_(ids_polso),
                           Task.dipendente_id.isnot(None)).distinct().all()]
        persone = session.query(Dipendente).filter(
            Dipendente.id.in_(dip_ids), Dipendente.attivo == True  # noqa: E712
        ).all() if dip_ids else []
    finally:
        session.close()

    # SATURAZIONE — una chiamata per persona, ed è una scelta.
    # `carico_settimanale_dipendente` è l'UNICO posto dove vive la regola di
    # distribuzione delle ore sulle settimane (il «debito uniforme» documentato
    # lì). Una GROUP BY qui sarebbe una query sola ma ricopierebbe quella
    # formula, e due copie di un calcolo approssimato divergono senza che nessun
    # test se ne accorga. Il costo è limitato dalle PERSONE (≈18), non dai
    # progetti, e la Home guarda UNA settimana — non le 12 della heatmap.
    lun = datetime.combine(oggi, datetime.min.time())
    sovraccarichi = sum(
        1 for d in persone
        if d.ore_sett and carico_settimanale_dipendente(d.id, lun) > d.ore_sett
    )

    # ── SMISTAMENTO: ogni progetto nel suo ramo, o fra le interne ────────
    # `azienda_id is None` ⇔ attività interna. Oggi la corrispondenza con
    # `tipologia='interna'` è totale; se un giorno si rompesse, questo blocco
    # segue l'azienda — che è il criterio dichiarato sopra.
    per_ramo = {}
    interne_totali = 0
    interne_attenzione = 0
    attivi = set(ids_attivi)

    for p in progetti:
        nodo = alberi.get(p.id)
        if p.azienda_id is None:
            interne_totali += 1
            # In attenzione solo se ATTIVA e con almeno un motivo: si conta la
            # stessa soglia dei rami, così il numero è confrontabile.
            if p.id in attivi and _voce_attenzione(p, nodo, sforamenti, oggi):
                interne_attenzione += 1
            continue

        r = per_ramo.setdefault(p.azienda_id, {
            "azienda_id": p.azienda_id,
            "azienda": aziende.get(p.azienda_id, f"(azienda {p.azienda_id})"),
            "_progetti": [], "_colori_prog": [], "_colori_fasi": [],
            "_colori_task": [], "_stati": {}, "_completati": 0, "attenzione": [],
        })
        r["_progetti"].append(p)
        r["_stati"][p.stato] = r["_stati"].get(p.stato, 0) + 1
        r["_completati"] += completati.get(p.id, 0)

        if nodo:
            r["_colori_prog"].append(nodo["semaforo"])
            for f in nodo["fasi"].values():
                r["_colori_fasi"].append(f["semaforo"])
                for t in f["task"].values():
                    r["_colori_task"].append(t["semaforo"])

        # L'ATTENZIONE guarda i soli attivi: un progetto chiuso non chiede
        # decisioni. Il polso invece l'ha già contato qui sopra.
        if p.id in attivi:
            voce = _voce_attenzione(p, nodo, sforamenti, oggi)
            if voce:
                r["attenzione"].append(voce)

    # ── COMPOSIZIONE FINALE ──────────────────────────────────────────────
    rami = []
    for r in per_ramo.values():
        r["attenzione"].sort(key=_peso_attenzione)
        rami.append({
            "azienda_id": r["azienda_id"],
            "azienda": r["azienda"],
            "polso": {
                "n_progetti": len(r["_progetti"]),
                "progetti_per_stato": r["_stati"],
                "semaforo": {"progetti": _conta(r["_colori_prog"]),
                             "fasi": _conta(r["_colori_fasi"]),
                             "task": _conta(r["_colori_task"])},
                "task_completati": r["_completati"],
            },
            "attenzione": r["attenzione"],
        })
    # Ordine STABILE per azienda_id: due rami paritari non hanno una gerarchia,
    # ma la loro posizione non deve ballare fra due caricamenti della pagina.
    rami.sort(key=lambda x: x["azienda_id"])

    return {
        "rami": rami,
        "interne": {"n_totali": interne_totali,
                    "n_in_attenzione": interne_attenzione},
        "team": {"n_persone": len(persone), "sovraccarichi": sovraccarichi},
    }
