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
from models import Utente, Progetto, Task, Dipendente, get_session, LIVELLI_URGENZA
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


@router.get("/dashboard")
def dashboard(current_user: Utente = Depends(get_current_user)):
    """Lo stato delle cose, dal punto di vista di chi guarda (Home, Tappa 1).

    DUE BLOCCHI, e la coppia è il design:
      `polso`      — come stanno le cose in generale, comprese quelle che vanno
                     BENE. Non è decorazione: una Home che mostra solo problemi
                     diventa una pagina che si evita di aprire, e smette di
                     essere letta proprio quando servirebbe.
      `attenzione` — solo ciò che chiede una decisione, ordinato per quanto la
                     chiede.

    `get_current_user` e NON `require_manager`: la Home deve funzionare per un
    manager come per un PM o un membro. È lo stesso pattern self-or-manager di
    `/home/criticita`, e non è un dettaglio di permessi — la Home oggi vive su
    una rotta non protetta ma chiama endpoint manager-only, quindi per un
    dipendente si rompe con un 403.

    IL RUOLO SI APPLICA UNA VOLTA SOLA. `progetti_attivi_visibili` restituisce
    gli id che questa persona può vedere (manager → tutti gli attivi; altrimenti
    i progetti di cui è PM PIÙ quelli su cui ha almeno un task), e da lì in giù
    OGNI blocco si calcola su quella lista. Applicare il filtro per-blocco
    sarebbe la ricetta per una Home che mostra un conteggio su uno scope e una
    lista su un altro, senza che nessuno se ne accorga.

    SI COMPONE, NON SI RICALCOLA: i colori vengono da `semaforo_progetti`, lo
    sforamento ore da `criticita_sforamento_progetti`, il carico da
    `carico_settimanale_dipendente`. Nessuna regola nuova nasce qui — questa
    route è un punto di raccolta, e se un giorno un colore o una soglia
    cambiano, cambiano in un posto solo e la Home segue.

    DUE SCOPE, UNA SOLA REGOLA DI IDENTITÀ. I blocchi partono da due liste
    diverse, ed è la loro natura a chiederlo:
      polso      → `solo_attivi=False`: TUTTI gli stati. Un progetto COMPLETATO
                   è la vittoria più leggibile che ci sia, e tenerlo fuori
                   avrebbe reso il polso una seconda lista di problemi.
      attenzione → `solo_attivi=True` (default): un progetto chiuso non chiede
                   decisioni, e metterlo fra le cose da guardare vorrebbe dire
                   chiedere di guardare qualcosa su cui non c'è niente da fare.
    Il filtro di CHI-VEDE-COSA resta identico fra i due (`solo_attivi` tocca
    solo gli stati, vedi `progetti_attivi_visibili`), quindi l'attenzione è
    sempre un SOTTOINSIEME del polso: nessuna riga può comparire fra le cose da
    guardare senza essere contata anche nel quadro generale.
    """
    # Il polso: scope largo. L'attenzione: scope attivo. La seconda lista è
    # contenuta nella prima per costruzione — stessa identità, stati ristretti.
    ids_polso = progetti_attivi_visibili(current_user, solo_attivi=False)
    ids = progetti_attivi_visibili(current_user)

    # Nessun progetto visibile — un dipendente senza incarichi, o un PM di
    # progetti tutti chiusi. Si risponde 200 con la STESSA FORMA, non un 403 né
    # un 404: la Home non deve rompersi per nessuno, e «non hai progetti» è una
    # risposta legittima che il frontend rende come stato vuoto. Uscire qui
    # evita anche di interrogare il database per sapere che non c'è niente.
    if not ids_polso:
        return {
            "polso": {
                "progetti_per_stato": {},
                "semaforo": {"progetti": {}, "fasi": {}, "task": {}},
                "task_completati_totali": 0,
                "team": {"n_persone": 0, "sovraccarichi": 0},
            },
            "attenzione": [],
        }

    oggi = get_oggi()
    oggi = oggi.date() if hasattr(oggi, "date") else oggi

    session = get_session()
    try:
        # Due letture, due scopi. `progetti` (attivi) alimenta l'ATTENZIONE;
        # i conteggi del POLSO girano su `ids_polso`, che li comprende tutti.
        progetti = session.query(Progetto).filter(Progetto.id.in_(ids)).all() if ids else []

        # ── POLSO ────────────────────────────────────────────────────────
        progetti_per_stato = dict(
            session.query(Progetto.stato, func.count(Progetto.id))
            .filter(Progetto.id.in_(ids_polso))
            .group_by(Progetto.stato).all()
        )

        # Task completati: il SOSTITUTO ONESTO dei «completamenti recenti».
        # «Recenti» non è calcolabile — non esiste una data di completamento
        # effettiva, e le tre vie indirette sono state misurate e scartate
        # (`updated_at` sbaglia in media di 81 giorni). Si dice quindi quanti
        # sono in totale, che è vero, invece di inventare un quando.
        task_completati = session.query(func.count(Task.id)).filter(
            Task.progetto_id.in_(ids_polso), Task.stato == "Completato"
        ).scalar() or 0

        # Il TEAM è quello dei progetti visibili, non l'anagrafica intera: per
        # un PM «il team» sono le persone sui suoi progetti, e prenderle tutte
        # gli mostrerebbe il carico di gente che non gli compete.
        # Una query per gli id, poi il carico persona per persona.
        dip_ids = [
            d for (d,) in session.query(Task.dipendente_id)
            .filter(Task.progetto_id.in_(ids_polso), Task.dipendente_id.isnot(None))
            .distinct().all()
        ]
        persone = session.query(Dipendente).filter(
            Dipendente.id.in_(dip_ids), Dipendente.attivo == True  # noqa: E712
        ).all() if dip_ids else []
    finally:
        session.close()

    # SATURAZIONE — una chiamata per persona, ed è una scelta, non una svista.
    # `carico_settimanale_dipendente` è l'UNICO posto dove vive la regola di
    # distribuzione delle ore sulle settimane (il «debito uniforme» documentato
    # lì). Una GROUP BY qui sarebbe una query sola ma ricopierebbe quella
    # formula, e due copie di un calcolo approssimato divergono senza che nessun
    # test se ne accorga. Il costo è limitato dal numero di PERSONE (≈16), non
    # dai progetti o dai task, e la Home guarda UNA settimana — non le 12 della
    # heatmap di /risorse/carico.
    #
    # NB: la saturazione è quella TOTALE della persona, su tutti i suoi
    # progetti. È voluto: chi è sovraccarico lo è davvero, anche se il carico
    # gli arriva da un progetto che chi guarda non vede. Cappare il conto ai
    # soli progetti visibili darebbe un «tutto a posto» falso.
    lun = datetime.combine(oggi, datetime.min.time())
    sovraccarichi = sum(
        1 for d in persone
        if d.ore_sett and carico_settimanale_dipendente(d.id, lun) > d.ore_sett
    )

    # ── I COLORI, in una chiamata ────────────────────────────────────────
    # Sul polso: i colori contano anche i progetti chiusi (che escono verdi —
    # "Completato" è fra gli stati finiti del semaforo). L'attenzione riusa lo
    # stesso albero e ne pesca solo i suoi, senza una seconda chiamata.
    alberi = semaforo_progetti(ids_polso)

    def _conta(colori):
        out = {}
        for c in colori:
            out[c] = out.get(c, 0) + 1
        return out

    conteggi = {
        "progetti": _conta(n["semaforo"] for n in alberi.values()),
        "fasi": _conta(f["semaforo"] for n in alberi.values()
                       for f in n["fasi"].values()),
        "task": _conta(t["semaforo"] for n in alberi.values()
                       for f in n["fasi"].values()
                       for t in f["task"].values()),
    }

    # ── ATTENZIONE ───────────────────────────────────────────────────────
    # Sforamento ore: stessa funzione di `/criticita`, stessa lista di id.
    sforamenti = {c["progetto_id"]: c["criticita"]
                  for c in criticita_sforamento_progetti(ids)}

    attenzione = []
    for p in progetti:
        nodo = alberi.get(p.id)
        colore = nodo["semaforo"] if nodo else "verde"
        motivi = []

        # 1. Il semaforo è rosso. `origine` dice se il problema è del progetto
        #    o di qualcosa dentro: due situazioni diverse che meritano frasi
        #    diverse, e il dato c'è già.
        if colore == "rosso":
            motivi.append({
                "tipo": "semaforo_rosso",
                "origine": nodo["origine"],
                "figli_rossi": nodo["figli_rossi"],
            })

        # 2. La data di fine è passata e il progetto non è chiuso. Si tiene
        #    separato dal semaforo pur essendone spesso la causa: il semaforo
        #    dice il COLORE, questo dice DI QUANTO — e «scaduto da 32 giorni»
        #    è l'informazione su cui si decide.
        if p.data_fine and p.data_fine < oggi:
            motivi.append({
                "tipo": "scaduto",
                "giorni": (oggi - p.data_fine).days,
                "data_fine": p.data_fine.isoformat(),
            })

        # 3. Sforamento ore (consumate vs vendute). Forma invariata rispetto a
        #    `/criticita`, che resta esposto com'è: chi lo consuma già non deve
        #    imparare un secondo formato.
        if p.id in sforamenti:
            motivi.append({"tipo": "superamento_ore",
                           "dettaglio": sforamenti[p.id]})

        # Nessun motivo = il progetto sta bene: non entra in `attenzione`. È la
        # convenzione di `criticita_sforamento_progetti` («i progetti sani non
        # compaiono»), e ciò che tiene la lista corta abbastanza da leggerla.
        if not motivi:
            continue

        attenzione.append({
            "progetto_id": p.id,
            "nome": p.nome,
            "cliente": p.cliente,
            "pm_id": p.pm_id,
            "semaforo": {"colore": colore,
                         "origine": nodo["origine"] if nodo else None},
            "urgenza": p.urgenza,
            "data_fine": p.data_fine.isoformat() if p.data_fine else None,
            "motivi": motivi,
        })

    attenzione.sort(key=_peso_attenzione)

    return {
        "polso": {
            "progetti_per_stato": progetti_per_stato,
            "semaforo": conteggi,
            "task_completati_totali": task_completati,
            "team": {"n_persone": len(persone), "sovraccarichi": sovraccarichi},
        },
        "attenzione": attenzione,
    }
