"""
Data layer — implementazione database (unica: Postgres è obbligatorio).

Ri-esportata da `data.py`, che è la porta d'ingresso delle route.
"""

from datetime import datetime, timedelta, date
from models import (
    get_session, Dipendente, Progetto, Task,
    Consuntivo, Segnalazione,
)

# ══════════════════════════════════════════════════════════════════════
# UTILITY DI CONVERSIONE
# ══════════════════════════════════════════════════════════════════════

def _to_dt(d):
    """date → datetime per compatibilità con codice esistente."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return datetime.combine(d, datetime.min.time())
    return d


# ══════════════════════════════════════════════════════════════════════
# SEMAFORO RITARDABILITÀ — primitiva pura (strato 1)
# ══════════════════════════════════════════════════════════════════════
# Il colore di UNA unità di lavoro, dedotto dai soli fatti che le
# appartengono. Nessuna query, nessun modello ORM, nessuna gerarchia: qui vive
# la REGOLA, scritta una volta, che tutti i livelli — sottotask, task, fase,
# progetto — useranno identica.
#
# PERCHÉ UNA SOLA REGOLA PER QUATTRO LIVELLI. È lo stesso principio che
# `_baseline_percentuali` difende per le due tabelle dell'avanzamento: un
# semaforo che sbaglia colore non fa fallire nessuna query, non rompe nessun
# test di forma e non alza nessun 500 — è un guasto SILENZIOSO, e due copie
# della regola che divergono sono il modo più facile di produrlo. Chi legge il
# colore non ha alcun modo di accorgersi che è quello sbagliato.
#
# IL CAMPO SI CHIAMERÀ `semaforo`, NON `ritardabilita`. `Progetto.ritardabilita`
# esiste già come colonna STORED (models.py, `String(10)`, default "media"),
# scritta dal PM in `routes/progetti.py` ed esposta nello snapshot SAL: è la
# DICHIARAZIONE «quanto è rimandabile questo progetto», cioè un futuro input
# alla modulazione per urgenza. Il semaforo è calcolato e non è mai persistito.
# Riusare quel nome metterebbe due cose diverse con la stessa etichetta nello
# stesso payload.
#
# COSA NON STA QUI, PER SCELTA:
#   - l'aggregazione «il peggio dei figli» (sottotask → task → fase →
#     progetto): guarda i figli, non l'unità. Sotto-edit successivo.
#   - il rosso PROSPETTICO (un figlio scaduto dentro un genitore che chiude
#     presto): è aggregazione anche quello — richiede di vedere i figli.
#   - il giallo VERO (ore residue vs capacità residua): strato 2, vedi sotto.
#   - qualunque accesso al database.

# DUE INSIEMI, NON UNO. Fino al 01/09/2026 «Sospeso» stava insieme a
# «Completato» in un unico set di stati-chiusi, e usciva VERDE. Non è la stessa
# cosa, e la differenza si vede meglio dicendola col colore:
#   FINITO   → verde:  il lavoro è andato a termine, non c'è rischio di ritardo.
#   FERMO    → grigio: il semaforo SI ASTIENE. Un'unità sospesa non è «a posto»
#                      (il verde lo direbbe) e non è un allarme su cui agire
#                      (il rosso lo direbbe): è ferma per una decisione presa
#                      apposta, e il giudizio sul ritardo non si applica.
# Il caso che l'ha reso evidente è P006: progetto Sospeso con la data di fine
# passata da cinque mesi. Il semaforo lo dava verde — «tutto bene» su qualcosa
# che è fermo da marzo — mentre la criticità della tab Scenari lo segnalava in
# ritardo. Non aveva ragione nessuno dei due: la risposta giusta è «non giudico».
#
# I QUATTRO LIVELLI PARLANO QUATTRO VOCABOLARI DIVERSI, e la fase è al
# FEMMINILE — è la ragione per cui entrambi i set sono UNIONI e non una delle
# quattro liste di models.py:
#   Task      (STATI_TASK)                      → Completato, Sospeso, Annullato
#   Fase      (STATI_FASE)                      → Completata, Sospesa, Annullata
#   Progetto  (STATI_PROGETTO)                  → Completato, Sospeso, Annullato
#   Sottotask (STATI_PIANIFICAZIONE_SOTTOTASK)  → Sospeso, Annullato
#     (un sottotask non ha uno stato "Completato": la sua conclusione vive
#      nelle dichiarazioni, non sulla definizione condivisa del pezzo.)
# Un set al solo maschile colorerebbe ROSSO ogni fase «Completata» chiusa in
# ritardo — 25 fasi su 71 sono in quello stato oggi — e lo farebbe in silenzio.

# ── FINITI → verde ────────────────────────────────────────────────────
# Il semaforo SCEGLIE i propri stati, non li eredita:
#   - Completato/Completata: il lavoro è finito. Che sia finito dopo la data
#     prevista è un fatto STORICO, materia di consuntivo, non un rischio da
#     presidiare. Un semaforo che resta rosso su ciò che è chiuso accumula
#     rossi che nessuno può spegnere, e a quel punto smette di essere letto.
#     Stessa scelta di `_in_ritardo` in `task_settimana_dipendente`.
#   - Annullato/Annullata: tolto dal piano. Non è lavoro in ritardo, non è
#     lavoro. Qui il semaforo DIVERGE da `_in_ritardo`, che non lo esclude:
#     quella closure gira su una query che ha già filtrato gli annullati a
#     monte, il semaforo no e deve difendersi da sé.
#   - Eliminato: soft delete. NON è uno stato ammesso per i task (il CHECK
#     `ck_task_stato_ammessi` è costruito su STATI_TASK, che non lo contiene) e
#     `gantt_strutturato` lo filtra comunque prima di arrivare qui. Lo teniamo
#     per difesa: se rientrasse da un percorso non previsto dev'essere chiuso,
#     mai rosso.
# "Bozza" (progetto) e "Da iniziare" NON sono qui: sono lavoro vivo che non è
# ancora partito, e un lavoro non partito con la data di fine alle spalle è
# esattamente il caso che il rosso deve gridare.
STATI_FINITI_SEMAFORO = (
    "Completato", "Completata",
    "Annullato", "Annullata",
    "Eliminato",
)

# ── FERMI → grigio ────────────────────────────────────────────────────
# Sospeso/Sospesa: è una DECISIONE del PM, non uno scivolamento — e
# `_in_ritardo` lo dice bene: «segnalarlo accuserebbe del contrario». Ma non
# accusare non vuol dire assolvere: un lavoro fermo da mesi non è un lavoro che
# va bene, è un lavoro su cui il semaforo non ha niente da dire finché qualcuno
# non lo riprende in mano.
# Non c'è un colore dedicato ai fermi: il grigio è UNO, e lo condividono con le
# unità senza data. Le due ragioni («fermo» / «senza data») sono entrambe
# «non calcolabile», e distinguerle è compito del tooltip lato frontend, che ha
# lo `stato` sotto mano. Un quinto colore per una sfumatura che l'interfaccia
# può già spiegare a parole costringerebbe ogni consumatore e l'ordinamento
# dell'aggregazione a farci i conti.
STATI_FERMI_SEMAFORO = ("Sospeso", "Sospesa")


def colore_unita(data_fine, stato, oggi,
                 percentuale=None, ore_consumate=None, ore_pianificate=None):
    """Colore del semaforo di UNA unità di lavoro. Pura: nessuna query.

    Restituisce una fra "grigio", "rosso", "giallo", "verde". In STRATO 1 il
    giallo non viene MAI emesso — vedi «IL GIALLO» in fondo.

    `oggi` È UN PARAMETRO, non `date.today()` letto qui dentro. È ciò che rende
    la funzione pura e testabile senza congelare l'orologio: l'unica sorgente
    di tempo è l'argomento, e due chiamate con gli stessi input danno sempre lo
    stesso output. Non ha default di proposito — un default che legge il clock
    reintrodurrebbe di soppiatto l'impurità che questa firma esiste per evitare.

    L'ORDINE DI VALUTAZIONE È LA REGOLA, e non è riordinabile:

      1. FINITA → "verde". Vedi `STATI_FINITI_SEMAFORO` sopra per quali stati e
         perché. Viene PRIMA di tutto il resto — prima del rosso (è la ragione
         per cui un task completato in ritardo non è un allarme) e prima del
         grigio.
         PERCHÉ LA CHIUSURA BATTE IL GRIGIO (invertito nel sotto-edit 2
         dell'aggregazione, che ha reso il caso concreto). Le due domande sono
         in ordine, non in parità: «questo lavoro è ancora aperto?» viene prima
         di «riesco a collocarlo nel calendario?». Di un'unità FINITA sappiamo
         già la risposta che conta — non è a rischio — e non ci serve alcuna
         data per saperlo: il calendario risponderebbe a una domanda che non si
         pone più. «Finito» è informazione più forte di «non calcolabile».
         Chiamare grigia una chiusura senza data sarebbe dire «non so» di
         qualcosa che sappiamo, e in aggregazione (dove grigio > verde) quel
         falso «non so» si propagherebbe verso l'alto: una singola fase
         completata e priva di data ingrigirebbe il progetto. Il grigio deve
         restare il colore del dubbio VERO, altrimenti smette di segnalare
         qualcosa.

      2. FERMA → "grigio". `STATI_FERMI_SEMAFORO`: Sospeso/Sospesa.
         DEVE STARE PRIMA DEL ROSSO, ed è tutto il punto di questo ramo: un
         sospeso con la data passata NON è rosso. Se il controllo stesse dopo,
         P006 — Sospeso, scaduto da cinque mesi — uscirebbe rosso, e il
         semaforo accuserebbe di ritardo un lavoro che qualcuno ha fermato
         apposta. Metterlo prima non è un dettaglio di ordinamento: è la
         differenza fra «non giudico» e un'accusa.
         Sta invece DOPO il verde solo per leggibilità — gli stati sono
         mutuamente esclusivi (una stringa sola), quindi i due rami non possono
         mai contendersi la stessa unità.

      3. GRIGIO — `data_fine is None` su unità viva e non ferma → "grigio".
         Senza data di fine la famiglia A (calendario) non ha termine di
         confronto: non è «va tutto bene», è «non lo so», e le due cose non
         vanno confuse. Precede il rosso e il verde perché entrambi si leggono
         dalla data che manca.
         Oggi in DB i NULL sono ZERO (0 su 114 task, 0 su 71 fasi, 0 su 38
         progetti) e le colonne sono comunque `nullable=True` a tutti e tre i
         livelli: questo ramo è difesa di schema, non un caso osservato.
         Stesso colore del ramo 2 — vedi `STATI_FERMI_SEMAFORO` per il perché il
         grigio è uno solo e la distinzione la fa il tooltip.

      4. ROSSO retrospettivo — `data_fine < oggi` su unità viva → "rosso".
         Il confronto è STRETTO: un'unità che scade OGGI non è in ritardo, la
         giornata non è finita. Non è solo semantica — `_in_ritardo` usa
         `data_fine < oggi`, e divergere di un `=` farebbe dissentire il badge
         di /me e il semaforo per l'esattezza di un giorno, sullo stesso task,
         senza che nessuno possa capire perché.

      5. GIALLO — non emesso in strato 1. Vedi sotto.

      6. VERDE — tutto il resto: unità viva con la finestra ancora aperta.

    IL GIALLO — perché è spento e come si accende
    ---------------------------------------------
    Il giallo su base TEMPO ("mancano N giorni e non ho finito") sarebbe rumore,
    non segnale: è la condizione NORMALE di ogni lavoro in corso, e un semaforo
    che ingiallisce tutto ciò che è in corso non distingue più niente. Il giallo
    vero è dello STRATO 2 e confronta ORE RESIDUE con CAPACITÀ RESIDUA — quanto
    lavoro manca contro quanto tempo-persona resta per farlo — più la famiglia B
    («consumo ore più in fretta di quanto avanzo») come aggravante che peggiora
    di un gradino e mai migliora.
    Qui NON c'è un ramo morto né un flag da rovesciare: c'è un BUCO
    nell'ordinamento, marcato al punto esatto dove la condizione entrerà, fra il
    rosso e il verde. Accenderlo è aggiungere quel ramo e niente altro — nessuna
    firma da cambiare, nessun chiamante da toccare, nessun `if False` che finge
    di essere coperto dai test.

    `percentuale`, `ore_consumate`, `ore_pianificate` — IL GANCIO DELLO STRATO 2
    ----------------------------------------------------------------------------
    Sono nella firma perché il giallo e la famiglia B li useranno, e stanno qui
    DA ORA perché aggiungerli dopo significherebbe toccare ogni chiamante.
    In strato 1 sono ACCETTATI E IGNORATI: non influenzano il colore in nessun
    caso. Non è una svista, ed è verificato da un test.
    Vale la pena sapere che oggi sarebbero comunque inerti: in DB ci sono ZERO
    righe con `percentuale` non-NULL, in `consuntivi` come in
    `consuntivo_sottotask`. Lo slider dell'avanzamento uniforme è vivo ma non è
    ancora stato usato da nessuno, e finché non lo sarà la famiglia B non
    avrebbe nulla da dire nemmeno se fosse accesa.

    Nota su `stato`: si accetta la stringa grezza dell'entità, senza
    normalizzarla. Uno stato sconosciuto o `None` non è né finito né fermo,
    quindi ricade nella valutazione per data — che è il comportamento prudente:
    davanti a uno stato che non riconosciamo, la scadenza vale comunque.
    """
    # 1. FINITA — il lavoro è andato a termine (o è stato tolto dal piano):
    #    nessun allarme aperto. Precede tutto: di ciò che è finito sappiamo già
    #    che non è a rischio, senza guardare il calendario. «Finito» batte «non
    #    calcolabile».
    if stato in STATI_FINITI_SEMAFORO:
        return "verde"

    # 2. FERMA — sospesa per decisione: il semaforo si astiene. PRIMA del rosso,
    #    ed è il punto: un sospeso scaduto non è in ritardo, è fermo (caso P006).
    if stato in STATI_FERMI_SEMAFORO:
        return "grigio"

    # 3. GRIGIO — unità VIVA senza data: non calcolabile, e non è «va bene».
    if data_fine is None:
        return "grigio"

    # 4. ROSSO retrospettivo — finestra chiusa su lavoro ancora vivo.
    #    `<` stretto: chi scade oggi non è (ancora) in ritardo.
    if data_fine < oggi:
        return "rosso"

    # 5. GIALLO — STRATO 2, qui e non altrove.
    #    Entrerà in questo punto il confronto ORE RESIDUE vs CAPACITÀ RESIDUA,
    #    con la famiglia B (ritmo di consumo ore contro ritmo di avanzamento)
    #    come aggravante di un gradino. I tre parametri già in firma
    #    (`percentuale`, `ore_consumate`, `ore_pianificate`) sono i suoi
    #    ingressi. In strato 1 non si emette giallo: sul tempo soltanto,
    #    ingiallirebbe ogni lavoro in corso, cioè quasi tutto il DB.

    # 6. VERDE — viva, non ferma, con la finestra ancora aperta.
    return "verde"


# ── L'ORDINAMENTO DEI COLORI — una regola sola, condivisa ─────────────
# Serve ovunque si debba dire «il peggio fra questi»: l'aggregazione lungo la
# scala sottotask → task → fase → progetto, e chiunque altro debba confrontare
# due colori. Sta qui, in una funzione, per la stessa ragione di `colore_unita`:
# due ordinamenti che divergono producono un colore sbagliato senza che nulla
# fallisca.
#
# IL GIALLO È NELL'ORDINE PUR ESSENDO SPENTO. In strato 1 `colore_unita` non lo
# emette mai, quindi il rank 2 non viene mai usato — ed è deliberato: quando lo
# strato 2 lo accenderà, l'ordinamento non va toccato, e non c'è il rischio di
# infilarlo al posto sbagliato mesi dopo, quando la ragione dell'ordine sarà
# meno fresca.
#
# GRIGIO SOPRA VERDE, e non sotto: un'unità viva senza data è un DUBBIO, e un
# dubbio non deve essere assorbito da fratelli che stanno bene. La conseguenza
# — un solo figlio grigio ingrigisce il genitore se è il peggio — è voluta, non
# un effetto collaterale. Sotto il rosso, però: un dubbio non può nascondere una
# certezza, e un fratello rosso vince sempre su un fratello grigio.
RANK_SEMAFORO = {"rosso": 3, "giallo": 2, "grigio": 1, "verde": 0}


def peggio_semaforo(colori):
    """Il colore peggiore fra quelli dati, secondo RANK_SEMAFORO. Pura.

    Sequenza VUOTA → None, non "verde". La differenza conta: "verde" sarebbe
    un'affermazione («va tutto bene») su qualcosa che non abbiamo guardato,
    mentre None dice «non c'è nulla da confrontare». Una fase senza task non è
    verde-per-via-dei-suoi-task: semplicemente non ne ha, e il suo colore lo
    decide il proprio calendario. Il chiamante scarta i None prima di
    confrontare.

    Un colore non presente in RANK_SEMAFORO solleva KeyError, e va bene così:
    è un bug del chiamante, e un default silenzioso lo trasformerebbe in un
    colore sbagliato che nessuno può notare.
    """
    colori = [c for c in colori if c is not None]
    if not colori:
        return None
    return max(colori, key=lambda c: RANK_SEMAFORO[c])


def _nodo_semaforo(colore_proprio, colori_figli):
    """Il nodo dell'albero: colore aggregato + da dove viene. Puro.

    È la regola del punto 1 della scala, scritta UNA volta e applicata identica
    ai quattro livelli:

        colore = peggio(colore-proprio, peggio-dei-figli)

    Un livello non può essere più verde del proprio calendario, né più verde del
    peggio dei suoi figli. Nessun assorbimento, nessuna finestra di prossimità:
    un figlio rosso rende rosso il genitore, punto. Misurato sui dati veri, il
    rosso che sale produce 5 progetti rossi su 38 — leggibile, non un'inondazione
    — e l'alternativa («assorbi il rosso se il genitore ha margine») si è
    rivelata un no-op: avrebbe lasciato rossi esattamente i 2 progetti già rossi
    per data propria, nascondendo 8 task rossi su 11.

    `origine` — PERCHÉ È ROSSO, non solo che lo è
    ---------------------------------------------
    È la scomposizione di un fatto che l'aggregazione conosce già e che
    altrimenti butterebbe via. Non è un quinto colore e non tocca
    l'ordinamento: è un secondo campo, di natura diversa dal colore.
      "propria" → il colore viene dal calendario/stato DI QUESTO livello, e i
                  figli non arrivano a tanto (o non ci sono).
      "figli"   → questo livello per conto suo starebbe meglio; il colore glielo
                  passa un figlio. È il caso di P002: 60 giorni di margine e
                  dentro un task scaduto da 139.
      "entrambe"→ il colore-proprio E il peggio-dei-figli valgono ENTRAMBI il
                  colore finale. Non «sono uguali fra loro»: sono uguali AL
                  PEGGIO. Un livello rosso di suo con un figlio rosso è
                  "entrambe"; un livello rosso di suo con figli grigi è
                  "propria", perché il grigio non concorre al colore vinto.
      None      → il colore è verde: non c'è niente da spiegare, e inventare
                  un'origine per lo star bene sarebbe rumore.
    Serve al frontend per graduare la resa senza che il backend inventi soglie:
    «rosso proprio» pieno, «rosso ereditato» più leggero. È la gradazione che il
    giallo darà da solo in strato 2, ottenuta intanto senza inventare un gradino.

    `figli_rossi` — figli DIRETTI, non il sottoalbero
    -------------------------------------------------
    Il progetto conta le FASI rosse, non i task rossi dei nipoti; la fase conta
    i task. Due ragioni. La prima: è il numero che risponde alla domanda che si
    fa davvero guardando un drill-down — «dove clicco adesso» — e il totale del
    sottoalbero dice quanto è grosso il problema, non dove sta. La seconda: i
    diretti danno anche i totali (la somma dei `figli_rossi` delle fasi di un
    progetto è il numero dei task rossi), mentre dal totale non si torna
    indietro. Si espone il dato da cui si ricava l'altro.
    Sulle foglie (sottotask) vale sempre 0: la forma del nodo è identica a ogni
    livello, così chi cammina l'albero non ha casi speciali.
    """
    colore_figli = peggio_semaforo(colori_figli)
    colore = peggio_semaforo([colore_proprio, colore_figli])

    if colore == "verde":
        origine = None
    else:
        da_se = colore_proprio == colore
        da_figli = colore_figli == colore
        origine = "entrambe" if (da_se and da_figli) else ("propria" if da_se else "figli")

    return {
        "semaforo": colore,
        "origine": origine,
        "figli_rossi": sum(1 for c in colori_figli if c == "rosso"),
    }


# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS — lettura
# ══════════════════════════════════════════════════════════════════════

def get_dipendente(did):
    if not did or did == "":
        return {"id": "", "nome": "Non assegnato", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []}
    session = get_session()
    r = session.query(Dipendente).filter(
        Dipendente.id == did,
        Dipendente.attivo == True,
    ).first()
    session.close()
    if r is None:
        return {"id": did, "nome": f"Sconosciuto ({did})", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []}
    return {
        "id": r.id, "nome": r.nome, "profilo": r.profilo,
        "ore_sett": r.ore_sett, "costo_ora": r.costo_ora or 0,
        "competenze": r.competenze or [],
    }

def get_progetto(pid):
    if not pid or pid == "":
        return {"id": "", "nome": "Sconosciuto", "cliente": "", "stato": ""}
    session = get_session()
    r = session.query(Progetto).filter(Progetto.id == pid).first()
    session.close()
    if r is None:
        return {"id": pid, "nome": f"Sconosciuto ({pid})", "cliente": "", "stato": ""}
    return {
        "id": r.id, "nome": r.nome, "cliente": r.cliente, "stato": r.stato,
        "data_inizio": _to_dt(r.data_inizio), "data_fine": _to_dt(r.data_fine),
        "budget_ore": r.budget_ore or 0, "valore_contratto": r.valore_contratto or 0,
        "descrizione": r.descrizione or "", "fase_corrente": r.fase_corrente or "",
    }
def ore_consuntivate_progetto(pid):
    from sqlalchemy import func
    session = get_session()
    total = session.query(
        func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0.0)
    ).join(Task, Consuntivo.task_id == Task.id).filter(
        Task.progetto_id == pid
    ).scalar()
    session.close()
    return total or 0

def progetti_attivi_visibili(current_user, solo_attivi=True):
    """Id dei progetti visibili a `current_user` (filtro self-or-manager).

    Confina nello strato dati la conoscenza del DB del filtro di visibilità,
    così lo stesso filtro è riusabile identico dalla Home management, dalla Home
    dipendente e dalla Consuntivazione (coerente col Blocco 4 e con la futura
    conversione ORM).

    DUE DOMANDE, NON UNA — ed è la ragione del parametro (03/09/2026)
    ----------------------------------------------------------------
    «Chi può vedere questo progetto?» e «quali stati mi interessano?» sono
    indipendenti, ma stavano annodate: la funzione rispondeva solo per gli
    attivi, e chi voleva un altro scope avrebbe dovuto riscrivere la regola
    d'identità. Il parametro le separa senza sdoppiare nulla.

    `solo_attivi=True`  (DEFAULT) — solo STATI_PROGETTO_ATTIVI. È il
        comportamento storico, invariato: i chiamanti che non passano il
        parametro non cambiano di una virgola.
    `solo_attivi=False` — TUTTI gli stati, stessa identica regola di identità.

    LA REGOLA DI CHI-VEDE-COSA È UNA SOLA, e il parametro non la sfiora: sotto,
    `filtro_stato` è una lista di condizioni che si aggiunge o resta vuota,
    mentre i due rami dell'identità (manager / PM+membro) sono scritti una volta
    e valgono per entrambi gli scope. Se un domani cambiasse chi vede cosa,
    cambierebbe in un punto. È la stessa disciplina di `_baseline_percentuali`,
    dove l'`if` sceglie SOLO la coppia (tabella, colonna) e il resto è comune.

    CHI USA `False`, e perché: il POLSO della Home (`/home/dashboard`). Un
    progetto COMPLETATO non chiede decisioni — quindi resta fuori
    dall'«attenzione», che continua a usare il default — ma è la vittoria più
    leggibile che ci sia, e una Home che mostra solo ciò che va male diventa una
    pagina che si smette di aprire. Il polso conta anche le chiusure; le cose da
    guardare no.

    NOTA SUL NOME. Con `solo_attivi=False` il nome della funzione è
    imperfetto — restituisce i visibili, non gli «attivi visibili». Rinominarla
    toccherebbe i chiamanti e il vocabolario di tre docstring: si è preferito il
    parametro con default esplicito, che non muove nulla di ciò che già funziona.

    Identità (identica nei due scope — dove qui si legge «attivi», con
    `solo_attivi=False` si legge «di qualunque stato»):
      - manager → tutti;
      - altrimenti → UNIONE (senza duplicati) di:
          a) progetti di cui è PM (Progetto.pm_id == dipendente_id);
          b) progetti con almeno un task assegnato a lui
             (Task.dipendente_id == dipendente_id), anche se il PM è un altro.
             Così un membro vede i progetti su cui lavora, non solo quelli che
             dirige.

    NB: il confronto è con `dipendente_id` (FK a dipendenti), NON con
    `current_user.id` (PK di utenti, dominio diverso): sbagliarlo darebbe un
    filtro che non matcha mai, silenziosamente.

    Step 4 sottotask (06/08/2026) — il ramo (b) leggeva la tabella
    `Assegnazione` con un secondo join. Ora legge `Task.dipendente_id`, che è
    l'UNICA verità sull'assegnazione. Erano due sorgenti per lo stesso fatto e
    solo una veniva mantenuta: `modifica_task` aggiorna `Task.dipendente_id` e
    non tocca `Assegnazione`, quindi ogni riassegnazione dal Cantiere faceva
    divergere il mirror — un dipendente continuava a "vedere" il progetto da
    cui era stato tolto, e non vedeva quello su cui era stato messo. Al momento
    del taglio le due sorgenti erano ancora allineate (114 coppie identiche):
    il drift era latente, non ancora materializzato. Il rischio si chiude
    togliendo il secondo termine, non riparando il mirror.

    La tabella resta in schema ma è fuori dal giro: nessuno la legge più,
    nessuno la scrive più. Il DROP è rimandato a una sessione di pulizia
    monconi dedicata.

    Ritorna list[str] (gli id progetto sono String(10)).
    """
    from models import STATI_PROGETTO_ATTIVI

    session = get_session()
    try:
        # L'UNICO punto in cui `solo_attivi` interviene: una lista di condizioni
        # da spalmare sui tre rami. Vuota = nessun filtro sugli stati. Da qui in
        # giù non si sa più quale scope sia stato chiesto, e non deve importare —
        # la regola di CHI VEDE COSA è la stessa per entrambi.
        filtro_stato = (
            [Progetto.stato.in_(STATI_PROGETTO_ATTIVI)] if solo_attivi else []
        )

        if current_user.ruolo_app == "manager":
            q = session.query(Progetto.id).filter(*filtro_stato)
            return [pid for (pid,) in q.all()]

        did = current_user.dipendente_id
        # a) progetti di cui è PM
        pm_q = session.query(Progetto.id).filter(
            *filtro_stato,
            Progetto.pm_id == did,
        )
        # b) progetti con almeno un task assegnato a lui
        membro_q = (
            session.query(Progetto.id)
            .join(Task, Task.progetto_id == Progetto.id)
            .filter(
                *filtro_stato,
                Task.dipendente_id == did,
            )
        )
        # Unione senza duplicati (un progetto può matchare entrambi i rami).
        ids = {pid for (pid,) in pm_q.all()} | {pid for (pid,) in membro_q.all()}
        return list(ids)
    finally:
        session.close()


def criticita_sforamento_progetti(progetti_ids):
    """Criticità di sforamento ore (consumate vs vendute) per i progetti dati.

    Home management — vista PM/manager. Restituisce SOLO i progetti che hanno
    almeno una criticità; i progetti sani non compaiono. `progetti_ids` è già
    la lista filtrata a monte (attivi + filtro identità); qui non si filtra per
    stato né per identità, si calcola e basta.

    DIREZIONE — "superamento_ore" confronta ore_consumate vs ore_vendute (budget
    commerciale, contratto col cliente). Il confronto con ore_pianificate (piano
    interno del PM) è una criticità di tipo DIVERSO, prevista in futuro come
    tipo: "superamento_pianificato", da affiancare a questa SENZA ridisegnare il
    payload (tipo è una stringa-enum, non un booleano). NON implementarlo ora.

    Calcolo unico (vincolante): un solo metodo di aggregazione applicato sia
    alle fasi sia al totale. ore_consumate di fase = SUM(Consuntivo.ore_dichiarate)
    sui task della fase (stesso pattern di routes/fasi.py:lista_fasi_progetto,
    concentrato qui). Il totale di progetto è la SOMMA delle ore_consumate di
    fase appena calcolate — NON una query separata, NON ore_consuntivate_progetto.
    Così fase e progetto sono coerenti per costruzione: il progetto sfora se e
    solo se la somma delle sue fasi sfora.

    ore_vendute di fase NULL/0: la fase non genera criticità di fase (nessun
    budget, niente /0), MA le sue ore_consumate entrano comunque nel totale di
    progetto (sottostimare il consumo nasconderebbe una criticità). Progetto con
    somma_vendute 0/NULL: saltato (non calcolabile, non è errore).
    """
    from sqlalchemy import func
    from models import Fase

    if not progetti_ids:
        return []

    session = get_session()
    try:
        progetti = (
            session.query(Progetto)
            .filter(Progetto.id.in_(progetti_ids))
            .all()
        )
        out = []
        for p in progetti:
            fasi = (
                session.query(Fase)
                .filter(Fase.progetto_id == p.id)
                .order_by(Fase.ordine)
                .all()
            )
            criticita = []
            somma_consumate = 0.0
            somma_vendute = 0.0
            for f in fasi:
                # Stessa aggregazione di routes/fasi.py: SUM(ore_dichiarate)
                # sui consuntivi dei task agganciati a questa fase.
                ore_consumate = float(
                    session.query(
                        func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0.0)
                    ).join(Task, Consuntivo.task_id == Task.id)
                    .filter(Task.fase_id == f.id)
                    .scalar() or 0.0
                )
                # Contributo al totale: SEMPRE, anche se la fase non ha budget.
                somma_consumate += ore_consumate
                ore_vendute = f.ore_vendute
                if ore_vendute:  # non None e non 0 → fase con budget
                    somma_vendute += ore_vendute
                    if ore_consumate > ore_vendute:
                        criticita.append({
                            "tipo": "superamento_ore",
                            "livello": "fase",
                            "fase_id": f.id,
                            "fase_nome": f.nome,
                            "dimensione_pct": round(ore_consumate / ore_vendute, 2),
                            "ore_consumate": ore_consumate,
                            "ore_vendute": float(ore_vendute),
                            "focus": f"fase-{f.id}",
                        })

            # Progetto senza budget complessivo: non calcolabile, si salta.
            if not somma_vendute:
                continue
            if somma_consumate > somma_vendute:
                criticita.append({
                    "tipo": "superamento_ore",
                    "livello": "progetto",
                    "fase_id": None,
                    "fase_nome": None,
                    "dimensione_pct": round(somma_consumate / somma_vendute, 2),
                    "ore_consumate": somma_consumate,
                    "ore_vendute": somma_vendute,
                    "focus": None,
                })

            if criticita:
                out.append({
                    "progetto_id": p.id,
                    "progetto_nome": p.nome,
                    "pm_id": p.pm_id,
                    "criticita": criticita,
                })
        return out
    finally:
        session.close()


def semaforo_progetti(progetti_ids, oggi=None):
    """Semaforo ritardabilità su tutta la gerarchia dei progetti dati.

    STRATO 1, sotto-edit 2. Cammina progetto → fase → task → sottotask,
    calcola il colore-proprio di ogni unità con `colore_unita` e lo aggrega
    verso l'alto col peggio-dei-figli (`_nodo_semaforo`). Il colore non è MAI
    persistito: si ricalcola a ogni richiesta, e `oggi` è l'unico ingresso che
    lo fa cambiare da solo.

    FIRMA BATCH SU SCOPE-PROGETTO, come `criticita_sforamento_progetti` — la
    stessa forma per la stessa ragione: `progetti_ids` è già la lista filtrata a
    monte (attivi + filtro identità), qui non si filtra per stato né per
    identità, si calcola e basta. Il chiamante più esigente è
    `gantt_strutturato`, che gira su tutti i progetti attivi: una chiamata per
    unità sarebbe un N+1 su ~110 task. Chi ne vuole uno solo passa [pid].

    `oggi` INIETTABILE. `colore_unita` è pura e non conosce l'orologio; questa
    funzione è il confine dove il tempo entra nel calcolo, UNA volta, e resta
    un parametro perché i test possano fissarlo. Il default `date.today()` è
    letto qui e passato a tutte le unità: senza questo, una richiesta a cavallo
    di mezzanotte potrebbe valutare due rami dello stesso albero in due giorni
    diversi.

    OUTPUT — dict annidato, chiave = id dell'unità a ogni livello:

      {progetto_id: {semaforo, origine, figli_rossi,
         "fasi": {fase_id: {semaforo, origine, figli_rossi,
            "task": {task_id: {semaforo, origine, figli_rossi,
               "sottotask": {sottotask_id: {semaforo, origine, figli_rossi}}}}}}}}

    La forma del NODO è identica ai quattro livelli (`semaforo`, `origine`,
    `figli_rossi`): chi cammina l'albero non ha casi speciali, e sulle foglie
    `figli_rossi` vale 0 e `origine` è "propria" o None.
    `fasi` e `task` ci sono sempre, anche vuoti — sono la struttura.
    `sottotask` compare SOLO sui task scomposti: la chiave assente è essa stessa
    l'informazione «questo task non ha pezzi», ed è la convenzione della casa
    (`task_settimana_dipendente`, `scostamento_stime_sottotask`).
    Progetto inesistente → chiave assente, nessun raise: le route validano a
    monte, qui non si alza.

    IL SOTTOTASK EREDITA LA DATA DEL TASK PADRE — è la riga da non sbagliare.
    `Sottotask` non ha date proprie PER SCELTA (models.py: «eredita la finestra
    temporale del task padre»). Passare `sottotask.data_fine` — che non esiste —
    o `None` renderebbe GRIGIO ogni sottotask vivo, e siccome grigio > verde
    ogni task scomposto diventerebbe grigio, e con lui la sua fase. Il guasto
    non si vedrebbe oggi: in DB ci sono ZERO sottotask, quindi si accenderebbe
    alla prima scomposizione reale, lontano da qui. Vedi la riga marcata
    «EREDITÀ» nel corpo.

    STATI DEL SOTTOTASK: sono `STATI_PIANIFICAZIONE_SOTTOTASK` («Da iniziare»,
    «Sospeso», «Annullato») e NON includono «Completato» — la conclusione di un
    pezzo vive nelle dichiarazioni, non sulla definizione condivisa.
    «Annullato» sta in `STATI_FINITI_SEMAFORO` → verde: un pezzo tolto dal piano
    non tinge il task. «Sospeso» sta in `STATI_FERMI_SEMAFORO` → GRIGIO, e
    siccome grigio > verde un pezzo sospeso dentro un task altrimenti verde
    ingrigisce il task. È voluto e coerente con gli altri livelli: se una parte
    del lavoro è ferma, il semaforo del task non può dire «tutto a posto».
    Un pezzo «Da iniziare» dentro un task scaduto è invece rosso, e deve
    esserlo: è lavoro vivo con la finestra chiusa.

    TASK «Eliminato» ESCLUSI, come in `gantt_strutturato` (soft delete, non
    devono comparire nel drill-down). Sarebbero comunque verdi — «Eliminato» è
    fra gli stati chiusi — ma escluderli qui tiene le CHIAVI di questo dict
    allineate a quelle del payload che lo ospiterà: un semaforo su un task che
    la pagina non mostra è un orfano che qualcuno prima o poi cercherà di
    renderizzare.

    QUERY: due, indipendenti dal numero di unità. Una per la gerarchia
    (joinedload fasi → task, lo stesso di `gantt_strutturato`) e una per tutti i
    sottotask dei task in scope. Nessun N+1, ed è verificato da un test che
    conta le query.
    """
    from sqlalchemy.orm import joinedload
    from models import Fase, Sottotask

    if not progetti_ids:
        return {}

    oggi = oggi or date.today()

    session = get_session()
    try:
        progetti = (
            session.query(Progetto)
            .options(joinedload(Progetto.fasi).joinedload(Fase.task))
            .filter(Progetto.id.in_(list(progetti_ids)))
            .all()
        )
        if not progetti:
            return {}

        task_ids = [
            t.id for p in progetti for f in p.fasi for t in f.task
            if t.stato != "Eliminato"
        ]

        # Tutti i pezzi in UNA query, poi lookup nel loop. Stesso pattern di
        # `ore_per_task` in routes/gantt.py.
        pezzi_per_task = {}
        if task_ids:
            for st in (session.query(Sottotask)
                       .filter(Sottotask.task_id.in_(task_ids))
                       .all()):
                pezzi_per_task.setdefault(st.task_id, []).append(st)

        out = {}
        for p in progetti:
            fasi_out = {}
            for f in p.fasi:
                task_out = {}
                for t in f.task:
                    if t.stato == "Eliminato":
                        continue

                    sottotask_out = {}
                    for st in pezzi_per_task.get(t.id, []):
                        # EREDITÀ — `t.data_fine`, NON `None`: il sottotask non
                        # ha date proprie e vive nella finestra del task padre.
                        # Vedi il docstring: sbagliare qui ingrigisce in
                        # silenzio ogni task scomposto.
                        sottotask_out[st.id] = _nodo_semaforo(
                            colore_unita(t.data_fine, st.stato, oggi), []
                        )

                    nodo_task = _nodo_semaforo(
                        colore_unita(t.data_fine, t.stato, oggi),
                        [n["semaforo"] for n in sottotask_out.values()],
                    )
                    if sottotask_out:
                        nodo_task["sottotask"] = sottotask_out
                    task_out[t.id] = nodo_task

                nodo_fase = _nodo_semaforo(
                    colore_unita(f.data_fine, f.stato, oggi),
                    [n["semaforo"] for n in task_out.values()],
                )
                nodo_fase["task"] = task_out
                fasi_out[f.id] = nodo_fase

            nodo_progetto = _nodo_semaforo(
                colore_unita(p.data_fine, p.stato, oggi),
                [n["semaforo"] for n in fasi_out.values()],
            )
            nodo_progetto["fasi"] = fasi_out
            out[p.id] = nodo_progetto

        return out
    finally:
        session.close()


def scostamento_stime_sottotask(task_ids):
    """Scostamento tra la scomposizione in sottotask e il piano del task.

    Step 2.3 sottotask (30/07/2026). SEGNALA, NON IMPONE: espone tre numeri e
    basta. Nessun vincolo, nessun blocco alla creazione o modifica di un
    sottotask se la somma sfora, nessun ribilanciamento automatico — il PM
    guarda e decide. (`routes/progetti.py`, che rifiuta con 422 se la somma
    delle ore di fase non quadra col budget di progetto, è il CONTRO-esempio:
    lì è un vincolo di creazione, qui è informazione.)

    FIRMA BATCH — accetta una LISTA di task_id e restituisce un dict
    {task_id: {...}}. È la forma che serve al chiamante più esigente
    (gantt_strutturato, che serializza tutti i task dei progetti attivi e non
    può permettersi una query per task). Chi ne vuole uno solo passa [task_id] e
    fa `.get(task_id)`. Stesso pattern di `ore_per_task` in routes/gantt.py:
    una GROUP BY, poi lookup con default.

    I TRE NUMERI, per ogni task calcolabile:
      - somma_stime_sottotask : SUM(Sottotask.ore_stimate) dei sottotask che
                                contano (vedi sotto)
      - ore_pianificate_task  : Task.ore_pianificate, il piano CORRENTE
      - differenza            : ore_pianificate_task − somma_stime_sottotask

    Segno della differenza: POSITIVA = il piano del task è più grande della
    somma delle stime, c'è piano non ancora coperto dalla scomposizione;
    NEGATIVA = i sottotask sforano il piano. Stessa convenzione di
    `ore_rimanenti` in routes/fasi.py (ore_vendute − ore_consumate), dove il
    positivo è il margine che resta e il negativo lo sforo: il PM legge i due
    scostamenti nello stesso verso.

    RIFERIMENTO = ore_pianificate e non ore_stimate. Sono due grandezze vive
    che si confrontano: le stime dei sottotask si aggiornano, il piano si
    rivede. `Task.ore_stimate` è il budget storico congelato (convenzione R1,
    non si tocca dopo l'avvio): confrontarci una somma che cambia darebbe uno
    scostamento che cresce da solo senza che nessuno abbia sbagliato piano.

    QUALI SOTTOTASK CONTANO — tutti tranne gli "Annullato" (i "Sospeso" SÌ).
    La domanda a cui questo numero risponde è «il piano di questo task quadra?»,
    ed è una domanda sul PIANO: un sottotask sospeso è in pausa ma resta nel
    piano, un annullato ne è stato tolto e le sue ore non sono più lavoro
    previsto. Precedente affine: `task_settimana_dipendente` filtra
    `Task.stato != "Annullato"` per la stessa ragione (cosa c'è nel piano di
    quella persona), mentre i filtri del carico/saturazione in routes/risorse.py
    escludono anche i Sospesi — ma quelli rispondono a «quanto lavoro c'è ORA»,
    che è un'altra domanda.

    QUANDO NON SI SEGNALA (la chiave manca dal dict, il chiamante legge None):
      - `Task.ore_pianificate` NULL: manca il termine di confronto. Non è un
        errore, non è calcolabile — come il "progetto senza budget complessivo:
        saltato" di `criticita_sforamento_progetti`.
      - task senza NESSUN sottotask che conta (mai scomposto, o scomposto e poi
        annullato tutto): la domanda non si pone. Senza questa esclusione ogni
        task non scomposto del sistema — cioè tutti e 114 quelli in DB oggi —
        risulterebbe "scostante" dell'intero piano: un falso positivo di massa
        che renderebbe la segnalazione inutile. Coerente con «i progetti sani
        non compaiono» di criticita_sforamento_progetti.
    NB: un task CON sottotask attivi ma tutti senza `ore_stimate` compare invece
    con somma 0 — lì la scomposizione esiste ma non è stimata, ed è
    informazione buona da mostrare, non un caso da nascondere. La GROUP BY
    distingue i due casi da sola: nessuna riga contro una riga che somma 0.
    """
    from sqlalchemy import func
    from models import Sottotask

    if not task_ids:
        return {}

    session = get_session()
    try:
        # Somma delle stime per task, in UNA query. I sottotask annullati sono
        # esclusi qui, non dopo: non devono nemmeno entrare nell'aggregato.
        somme = dict(
            session.query(
                Sottotask.task_id,
                func.coalesce(func.sum(Sottotask.ore_stimate), 0.0),
            )
            .filter(
                Sottotask.task_id.in_(task_ids),
                Sottotask.stato != "Annullato",
            )
            .group_by(Sottotask.task_id)
            .all()
        )
        if not somme:
            return {}

        # Il piano corrente dei soli task che hanno una scomposizione.
        piani = dict(
            session.query(Task.id, Task.ore_pianificate)
            .filter(Task.id.in_(list(somme.keys())))
            .all()
        )

        out = {}
        for tid, somma in somme.items():
            piano = piani.get(tid)
            if piano is None:  # niente piano corrente → non calcolabile
                continue
            somma = float(somma or 0.0)
            piano = float(piano)
            out[tid] = {
                "somma_stime_sottotask": round(somma, 1),
                "ore_pianificate_task": round(piano, 1),
                "differenza": round(piano - somma, 1),
            }
        return out
    finally:
        session.close()


TIPI_UNITA = ("task", "sottotask")


def _baseline_percentuali(session, tipo, ids, settimana):
    """{id: percentuale} dell'ultima dichiarazione PRECEDENTE a `settimana`.

    Step 4 (06/08/2026, generalizzata il 07/08). È la definizione — unica — di
    «da dove riparte l'avanzamento», e sta in una funzione a sé perché la usano
    in due: `ore_derivate_sottotask`, che ci calcola il Δ, e
    `task_settimana_dipendente`, che la manda al frontend come punto di partenza
    dello slider. Se le due copie divergessero, il dipendente vedrebbe un
    cursore che parte da un valore e ore calcolate da un altro — e non avrebbe
    alcun modo di accorgersene.

    UNITÀ DI LAVORO, NON SOLO SOTTOTASK
    -----------------------------------
    `tipo` dice su cosa si cerca:
      "sottotask" → ConsuntivoSottotask.percentuale, per sottotask_id
      "task"      → Consuntivo.percentuale, per task_id  (task NON scomposto,
                    che dichiara l'avanzamento come farebbe un pezzo)

    Due tabelle, ma UNA regola. Nel codice sotto l'`if` sceglie SOLO la coppia
    (tabella, colonna-che-identifica-l'unità): il filtro e la riduzione sono
    scritti una volta e attraversati da entrambi i tipi. È deliberato, ed è la
    ragione per cui non ci sono due funzioni: se la regola che decide QUALE
    riga vince divergesse fra task e sottotask, il bug sarebbe invisibile —
    nessuna query fallirebbe, nessun test di forma se ne accorgerebbe, e le ore
    derivate sarebbero semplicemente sbagliate per metà del sistema.

    `tipo` è obbligatorio e senza default di proposito. Un default "sottotask"
    sarebbe comodo e pericoloso: un chiamante nuovo che se lo dimentica non
    prende un errore, prende la semantica sbagliata in silenzio — che è
    esattamente il modo in cui questa funzione può fare danno.

    LE REGOLE, identiche per entrambi i tipi
    ----------------------------------------
    Le unità senza storia NON compaiono nel dict: il chiamante usa
    `.get(id, 0)`, cioè «prima dichiarazione, si parte da zero».

    PER UNITÀ, NON PER DIPENDENTE. La percentuale descrive il LAVORO («a che
    punto è»), non la persona. Entrambe le tabelle hanno il dipendente nella
    grana perché la DICHIARAZIONE ha un autore, ma il fatto dichiarato è del
    lavoro: cercando la baseline per (unità, dipendente) ogni passaggio di
    consegne produrrebbe una falsa prima dichiarazione, e su un pezzo già
    portato al 60% il nuovo assegnatario rideriverebbe da zero.

    Le righe con `percentuale` NULL non fanno baseline: sono di chi si è
    espresso sullo stato e non sull'avanzamento. Senza il filtro diventerebbero
    una baseline fantasma a 0.

    Se nella settimana-baseline ci sono più dichiarazioni non-NULL (possibile:
    la UNIQUE include il dipendente in entrambe le tabelle), vince la
    percentuale PIÙ ALTA — il lavoro è avanzato almeno quanto la dichiarazione
    più avanti, e una baseline più alta dà un Δ più piccolo: sbaglia dalla parte
    di derivare MENO ore, mai di più.

    Una query sola, ridotta in Python. Non una per unità (N+1); e non una
    window function pur essendo ora possibile — Postgres è obbligatorio dal
    07/08/2026 e il vincolo SQLite che la sconsigliava è caduto — perché su un
    punto di fallimento SILENZIOSO due rami leggibili a occhio valgono più di
    una query più elegante. Le righe in gioco sono comunque poche: una per
    persona per settimana, sulla vita di un'unità di lavoro.
    """
    from models import ConsuntivoSottotask

    if not ids:
        return {}

    # ── L'UNICO punto in cui i due tipi divergono ────────────────────────
    # Da qui in giù non si sa più se si stia parlando di task o di sottotask,
    # e non deve importare: la regola è la stessa.
    if tipo == "sottotask":
        Dichiarazione = ConsuntivoSottotask
        colonna_unita = ConsuntivoSottotask.sottotask_id
    elif tipo == "task":
        Dichiarazione = Consuntivo
        colonna_unita = Consuntivo.task_id
    else:
        raise ValueError(
            f"tipo '{tipo}' non ammesso per la baseline: attesi {TIPI_UNITA}."
        )

    storiche = (
        session.query(
            colonna_unita,
            Dichiarazione.settimana,
            Dichiarazione.percentuale,
        )
        .filter(
            colonna_unita.in_(list(ids)),
            Dichiarazione.settimana < settimana,
            Dichiarazione.percentuale.isnot(None),
        )
        .all()
    )

    # ── La riduzione: scritta UNA volta, per entrambi i tipi ─────────────
    migliore = {}      # id unità → (settimana, percentuale)
    for unita_id, sett_storica, pct in storiche:
        corrente = migliore.get(unita_id)
        if corrente is None or sett_storica > corrente[0]:
            migliore[unita_id] = (sett_storica, pct)
        elif sett_storica == corrente[0] and pct > corrente[1]:
            migliore[unita_id] = (sett_storica, pct)

    return {unita_id: pct for unita_id, (_sett, pct) in migliore.items()}


def _nota_ereditata_payload(coppia):
    """(settimana, nota) → i due campi del payload. Sempre presenti, anche None.

    Scritto una volta perché i due punti che lo usano — i sottotask e i
    task-unità — devono produrre la stessa forma: sono la stessa informazione su
    due entità, e il frontend li legge con lo stesso codice.

    Le chiavi ci sono SEMPRE, anche quando non c'è nulla da ereditare. Qui non
    vale la convenzione «chiave assente = niente da dire» di `scostamento` e
    `sottotask`: quelle segnalano al frontend di cambiare RENDER, questa è un
    valore da mostrare o no, e `null` lo dice già. Chiavi che appaiono e
    scompaiono a seconda della storia costringerebbero ogni lettore a
    difendersi con un `?.`.
    """
    sett, nota = coppia if coppia else (None, None)
    return {
        "nota_ereditata": nota,
        "nota_ereditata_da": sett.isoformat() if sett else None,
    }


def _note_ereditate(session, tipo, ids, settimana):
    """{id: (settimana, nota)} dell'ultima NOTA non vuota PRECEDENTE a `settimana`.

    Nodo F-2 (02/09/2026), parte (b). Il perché di un fermo non cambia ogni
    lunedì: chi aspetta le credenziali del cliente da tre settimane non deve
    ridigitare «aspetto le credenziali» tre volte. Questa funzione va a
    riprendere l'ultima spiegazione scritta e la rende disponibile alla
    settimana corrente.

    GEMELLA DI `_baseline_percentuali`, e non per somiglianza: stessa domanda
    («qual è l'ultima cosa detta su questa unità prima d'ora»), stessa forma
    (batch, una query, riduzione in Python), stesso `if` che sceglie SOLO la
    coppia (tabella, colonna-che-identifica-l'unità). Da lì in giù non si sa più
    se si parli di task o di sottotask, e non deve importare: se la regola che
    decide QUALE riga vince divergesse fra i due tipi, il bug sarebbe invisibile
    — nessuna query fallirebbe e nessun test di forma se ne accorgerebbe.

    EREDITÀ A LETTURA, NON COPIA — è la scelta (b2) fatta in ricognizione. La
    nota vecchia NON viene duplicata sulla riga della settimana nuova: resta
    dov'è, e la si va a leggere. Copiarla avrebbe significato scrivere una riga
    che l'utente non ha toccato, con `compilato=True` e `data_compilazione`
    valorizzati — e il contatore di F-1 l'avrebbe contata come dichiarata,
    dicendo «5/5 compilati» a chi non ha aperto la pagina.

    PER UNITÀ, NON PER DIPENDENTE, come la baseline. Il fatto raccontato è del
    LAVORO («questo pezzo è fermo perché mancano le credenziali»), non della
    persona che l'ha scritto: se il pezzo passa di mano, il motivo del fermo
    deve seguirlo. È la scelta meno ovvia delle due — la nota è firmata, la
    percentuale no — e va guardata di nuovo al sotto-edit della SCRITTURA: una
    nota ereditata non deve mai finire salvata come nota PROPRIA di chi la
    legge, o si ritroverebbe a firmare le parole di un collega.

    NOTE VUOTE ESCLUSE due volte, in SQL e in Python. In DB la nota assente è
    NULL — `_nota_task` normalizza "" e i soli spazi — ma il filtro `IS NOT
    NULL` da solo si fiderebbe di quella normalizzazione per ogni riga mai
    scritta, comprese quelle del seed e di eventuali import futuri. Lo `strip()`
    nella riduzione costa nulla e rende la funzione vera per costruzione invece
    che per convenzione.

    IL PAREGGIO — se due righe della stessa settimana hanno entrambe una nota
    (possibile: la UNIQUE include il dipendente), vince quella scritta DOPO,
    cioè con l'`id` più alto. La baseline in questo caso prende la percentuale
    più ALTA, che è una regola di merito; qui il merito non esiste — due
    spiegazioni non si ordinano — e l'unica cosa sensata è l'ultima parola detta
    sull'argomento. Serve comunque una regola: senza, l'esito dipenderebbe
    dall'ordine in cui Postgres restituisce le righe, che cambia da solo dopo un
    UPDATE.

    RESTITUISCE LA COPPIA (settimana, nota) e non la sola nota — a differenza
    della baseline, che torna il solo valore. La provenienza serve: «aspetto le
    credenziali» scritto la settimana scorsa e scritto due mesi fa non si
    leggono allo stesso modo, e il payload la espone come `nota_ereditata_da`.

    NESSUN FILTRO su «l'unità è ferma» o «ha già una nota sua»: qui si
    restituisce il fatto, non la decisione di mostrarlo. Vedi
    `task_settimana_dipendente` per il perché.
    """
    from models import ConsuntivoSottotask

    if not ids:
        return {}

    # ── L'UNICO punto in cui i due tipi divergono ────────────────────────
    if tipo == "sottotask":
        Dichiarazione = ConsuntivoSottotask
        colonna_unita = ConsuntivoSottotask.sottotask_id
    elif tipo == "task":
        Dichiarazione = Consuntivo
        colonna_unita = Consuntivo.task_id
    else:
        raise ValueError(
            f"tipo '{tipo}' non ammesso per le note ereditate: attesi {TIPI_UNITA}."
        )

    storiche = (
        session.query(
            colonna_unita,
            Dichiarazione.settimana,
            Dichiarazione.nota,
            Dichiarazione.id,
        )
        .filter(
            colonna_unita.in_(list(ids)),
            Dichiarazione.settimana < settimana,
            Dichiarazione.nota.isnot(None),
        )
        .all()
    )

    # ── La riduzione: scritta UNA volta, per entrambi i tipi ─────────────
    migliore = {}      # id unità → (settimana, nota, id_riga)
    for unita_id, sett_storica, nota, riga_id in storiche:
        if not (nota or "").strip():
            continue
        corrente = migliore.get(unita_id)
        if corrente is None or sett_storica > corrente[0]:
            migliore[unita_id] = (sett_storica, nota, riga_id)
        elif sett_storica == corrente[0] and riga_id > corrente[2]:
            migliore[unita_id] = (sett_storica, nota, riga_id)

    return {
        unita_id: (sett, nota)
        for unita_id, (sett, nota, _riga_id) in migliore.items()
    }


def _prima_settimana_dopo(session, tipo, ids, settimana):
    """{id: settimana} della PRIMA dichiarazione con percentuale dopo `settimana`.

    Serve al ricalcolo a valle: scrivere un avanzamento a W cambia la baseline
    di chi viene dopo, e la sola settimana da rifare è la prima dichiarata dopo
    W (le successive hanno per baseline quella, il cui VALORE non cambia).

    Generalizzata all'unità di lavoro come le sorelle `_baseline_percentuali` e
    `percentuali_successive`: stesso `if` che sceglie solo (tabella, colonna),
    stessa riduzione scritta una volta.
    """
    from models import ConsuntivoSottotask

    ids = list(ids)
    if not ids:
        return {}

    if tipo == "sottotask":
        Dichiarazione = ConsuntivoSottotask
        colonna_unita = ConsuntivoSottotask.sottotask_id
    elif tipo == "task":
        Dichiarazione = Consuntivo
        colonna_unita = Consuntivo.task_id
    else:
        raise ValueError(
            f"tipo '{tipo}' non ammesso per il ricalcolo: attesi {TIPI_UNITA}."
        )

    righe = (
        session.query(colonna_unita, Dichiarazione.settimana)
        .filter(
            colonna_unita.in_(ids),
            Dichiarazione.settimana > settimana,
            Dichiarazione.percentuale.isnot(None),
        )
        .all()
    )

    prima = {}
    for unita_id, sett in righe:
        if unita_id not in prima or sett < prima[unita_id]:
            prima[unita_id] = sett
    return prima


def percentuali_successive(session, tipo, ids, settimana):
    """{id: (settimana, percentuale)} della dichiarazione SUCCESSIVA più bassa.

    Gemella in avanti di `_baseline_percentuali`, e come quella generalizzata
    all'unità di lavoro (Step 4, 07/08/2026): "sottotask" guarda
    ConsuntivoSottotask, "task" guarda Consuntivo, e l'`if` sceglie SOLO la
    coppia (tabella, colonna) — filtro e riduzione sono scritti una volta.

    Serve alla MONOTONIA: recuperare una settimana passata è ammesso, ma non
    può risultare più avanti di una successiva già dichiarata. La regola guarda
    quindi in AVANTI, ed è per questo che non può stare né nel DTO né dentro il
    calcolo del Δ, che guarda solo all'indietro.

    Si tiene il MINIMO fra le percentuali successive: se anche solo una è più
    indietro di quella in arrivo, la sequenza non è monotòna. Le unità senza
    dichiarazioni successive non compaiono nel dict — nessun tetto.

    Come per la baseline: solo percentuali non-NULL, e la ricerca è per UNITÀ e
    non per dipendente (la percentuale descrive il lavoro, non la persona).
    """
    from models import ConsuntivoSottotask

    ids = list(ids)
    if not ids:
        return {}

    if tipo == "sottotask":
        Dichiarazione = ConsuntivoSottotask
        colonna_unita = ConsuntivoSottotask.sottotask_id
    elif tipo == "task":
        Dichiarazione = Consuntivo
        colonna_unita = Consuntivo.task_id
    else:
        raise ValueError(
            f"tipo '{tipo}' non ammesso per la monotonia: attesi {TIPI_UNITA}."
        )

    righe = (
        session.query(colonna_unita, Dichiarazione.settimana, Dichiarazione.percentuale)
        .filter(
            colonna_unita.in_(ids),
            Dichiarazione.settimana > settimana,
            Dichiarazione.percentuale.isnot(None),
        )
        .all()
    )

    minimo_dopo = {}
    for unita_id, sett, pct in righe:
        if unita_id not in minimo_dopo or pct < minimo_dopo[unita_id][1]:
            minimo_dopo[unita_id] = (sett, pct)
    return minimo_dopo


def ore_derivate_unita(tipo, avanzamenti, settimana=None, session=None):
    """Ore derivate dall'avanzamento dichiarato su una o più UNITÀ DI LAVORO.

    Un'unità di lavoro è un SOTTOTASK (pezzo di un task scomposto) oppure un
    TASK non scomposto, che dichiara l'avanzamento come farebbe un pezzo. Le due
    cose si derivano con la stessa formula e differiscono in due soli punti,
    entrambi nell'anagrafica qui sotto: dove sta la percentuale e quale colonna
    è la stima.

    Step 4 sottotask — STRATO 1 del motore ore-derivate (06/08/2026,
    generalizzata alle unità il 07/08). Calcola e
    basta: NON scrive niente, né su ConsuntivoSottotask né su Consuntivo. Dato
    lo stato del database ritorna dei numeri, e chi la chiama decide cosa
    farne. Isolarla così la rende testabile senza montare un salvataggio
    completo, ed è la ragione per cui esiste come funzione a sé.

    LA FORMULA
    ----------
        Δpct  = percentuale − baseline
        ore   = (Δpct / 100) × Sottotask.ore_stimate       [clamp Δ<0 → 0 ore]

    La `baseline` è l'ultima percentuale non-NULL dichiarata su QUEL SOTTOTASK
    in una settimana PRECEDENTE — non il lunedì-calendario prima: l'ultima
    settimana in cui qualcuno si è espresso. Se non esiste, è 0 (prima
    dichiarazione: Δ = percentuale intera).

    BASELINE PER SOTTOTASK, NON PER DIPENDENTE — è la scelta che regge tutto.
    La percentuale descrive il PEZZO DI LAVORO («a che punto è questo
    sottotask»), non la persona. La grana di ConsuntivoSottotask include il
    dipendente perché la DICHIARAZIONE ha un autore, ma il fatto dichiarato è
    del pezzo. Cercando la baseline per (sottotask, dipendente) ogni passaggio
    di consegne produrrebbe una falsa prima dichiarazione: riassegnato il
    sottotask da X a Y (override cambiato, o task riassegnato — vedi
    Sottotask.dipendente_id), Y non ha storia propria, la sua baseline sarebbe
    0, e su un pezzo già portato al 60% da X una dichiarazione al 70% di Y
    deriverebbe il 70% delle ore invece del 10%. Si ri-deriverebbe lavoro già
    derivato, e proprio nel momento in cui sbagliare costa di più.

    Se nella settimana-baseline ci sono PIÙ dichiarazioni non-NULL (grana
    unique per sottotask+dipendente+settimana: possibile se due collaboratori
    si esprimono entrambi, anche se la regola vuole che scriva solo
    l'assegnatario), si prende la percentuale PIÙ ALTA. Il pezzo è avanzato
    almeno quanto la dichiarazione più avanti, e una baseline più alta produce
    un Δ più piccolo: sbaglia dalla parte di derivare MENO ore, mai di più.

    INPUT
    -----
    avanzamenti: dict {sottotask_id: percentuale}. La percentuale può essere
                 None — è il caso «slider fermo» previsto dal design: il
                 dipendente si è espresso sullo stato ma non sull'avanzamento,
                 e da lì non si deriva nessuna ora. NON si inventa un default.
    settimana:   la settimana della dichiarazione. Normalizzata al lunedì con
                 `_lunedi`, come ovunque. Una sola per chiamata: in un
                 salvataggio la settimana è una, e il ricalcolo di una settimana
                 diversa (quella la cui baseline è stata invalidata) è una
                 SECONDA chiamata, non un caso da infilare qui.
    session:     se fornita, si riusa quella e NON la si chiude — pattern di
                 `genera_id_task_multipli`. Serve al caso transazionale: dentro
                 `salva_consuntivo` le righe ConsuntivoSottotask appena scritte
                 non sono ancora committate, e una sessione nuova (cioè
                 un'altra connessione) non le vedrebbe. Il Δ si calcolerebbe
                 sulla storia com'era PRIMA del salvataggio, in silenzio.

    FIRMA BATCH, come `scostamento_stime_sottotask` — una chiamata, due query,
    nessun N+1. Il motore vero processerà tutti i sottotask di un salvataggio in
    un colpo; chi ne vuole uno solo passa un dict di un elemento.

    OUTPUT — {sottotask_id: {...}}, una voce per ogni sottotask ESISTENTE:
      task_id      : il task padre. Lo restituisce questa funzione perché lo ha
                     già in mano: il chiamante deve aggregare le ore per task
                     (su Consuntivo.ore_dichiarate) e senza questo dovrebbe
                     rifare la stessa query.
      ore          : float, le ore derivate. Oppure **None = NON DERIVABILE**,
                     vedi sotto.
      baseline_pct : la percentuale da cui si è partiti (0 se prima dichiarazione)
      delta_pct    : Δ GREZZO, col segno. Un negativo resta visibile qui anche
                     se `ore` è già 0: è il sintomo, e va potuto leggere.
      ore_stimate  : la stima usata, per ricostruire il conto a posteriori.

    `ore = None` È IL SENTINELLA, E NON È 0.0 — la distinzione è il punto.
      - `ore = 0.0`  → derivato, e fa zero ore: nessun avanzamento (Δ=0), o
                       regressione clampata, o slider non mosso. È un numero.
      - `ore = None` → NON derivabile: il sottotask non ha `ore_stimate`, quindi
                       Δpct × NULL non è definito. Il chiamante deve SEGNALARLO
                       («sottotask non stimato, ore non derivate»), non sommare
                       zero in silenzio: chi ha dichiarato ha lavorato davvero, e
                       far sparire quelle ore senza dirlo è il modo peggiore di
                       gestire una stima che manca al PM, non a lui.
      Qui si diverge da `scostamento_stime_sottotask`, che il NULL lo tratta con
      `coalesce(..., 0.0)` — e giustamente: lì la domanda è «il piano quadra?» e
      0 è una risposta informativa («non stimato»). Qui la domanda è «quante ore
      ha prodotto questo avanzamento?», e 0 sarebbe una bugia.

    PRECEDENZA DEI CONTROLLI — `percentuale is None` viene PRIMA di
    `ore_stimate is None`. Su un pezzo su cui nessuno ha dichiarato avanzamento
    la stima mancante non è un problema di nessuno: segnalarla produrrebbe un
    avviso per ogni sottotask non stimato toccato di striscio dal salvataggio,
    cioè rumore che nasconde i pochi casi veri.

    CHIAVE ASSENTE dal risultato = sottotask inesistente (stessa convenzione di
    `scostamento_stime_sottotask`, dove la chiave manca quando non c'è niente da
    dire). Le route validano l'esistenza a monte, come fa `_task_o_404` in
    routes/sottotask.py; qui non si alza, si omette.

    NON FA — e non per dimenticanza: la validazione della MONOTONIA (dipende
    anche dalla dichiarazione SUCCESSIVA, è regola del data layer/route, non di
    un calcolo puro), il ricalcolo della settimana la cui baseline è stata
    invalidata, l'aggregazione per task, l'innesto in `salva_consuntivo`. Questa
    funzione calcola una fotografia, non gestisce il tempo.
    """
    from models import Sottotask

    if not avanzamenti:
        return {}

    sett = _lunedi(settimana)
    ids = list(avanzamenti)

    propria = session is None
    session = session or get_session()
    try:
        # 1) ANAGRAFICA — l'unico punto, con la baseline, in cui i due tipi
        # divergono. Per ciascuna unità serve la coppia (task a cui le ore
        # vanno attribuite, stima su cui calcolare il Δ).
        if tipo == "sottotask":
            righe = (
                session.query(Sottotask.id, Sottotask.task_id, Sottotask.ore_stimate)
                .filter(Sottotask.id.in_(ids))
                .all()
            )
            anagrafica = {r[0]: (r[1], r[2]) for r in righe}
        elif tipo == "task":
            # Il task È la propria unità: il «task a cui attribuire» è se
            # stesso, e le ore che ne derivano stanno già sulla riga giusta —
            # è la ragione per cui più avanti l'aggregazione non ha nulla da
            # sommare.
            #
            # LA STIMA È `ore_pianificate`, NON `ore_stimate`. Quest'ultima
            # porta la convenzione R1 («non si modifica dopo l'avvio»): è il
            # budget storico congelato, e derivarci sopra vorrebbe dire
            # calcolare le ore di oggi su un piano di mesi fa. `ore_pianificate`
            # è il piano vivo, ed è la stessa base che usano già
            # `scostamento_stime_sottotask` (che ci confronta la somma delle
            # stime dei pezzi) e la barra `progress` del GANTT.
            # NB: sul SOTTOTASK il ruolo è invertito — `Sottotask.ore_stimate`
            # è l'unica colonna-ore che il pezzo ha, quindi lì è quella viva.
            righe = (
                session.query(Task.id, Task.ore_pianificate)
                .filter(Task.id.in_(ids))
                .all()
            )
            anagrafica = {r[0]: (r[0], r[1]) for r in righe}
        else:
            raise ValueError(
                f"tipo '{tipo}' non ammesso per la derivazione: attesi {TIPI_UNITA}."
            )
        if not anagrafica:
            return {}

        # 2) Baseline — la regola vive in `_baseline_percentuali`, condivisa con
        # `task_settimana_dipendente`: il frontend deve mostrare allo slider
        # ESATTAMENTE il punto da cui il motore calcolerà il Δ, e due copie
        # della stessa riduzione finirebbero per rispondere due cose diverse.
        baseline = _baseline_percentuali(session, tipo, list(anagrafica), sett)

        out = {}
        for sid in ids:
            if sid not in anagrafica:
                continue                      # inesistente: chiave omessa
            task_id, stima = anagrafica[sid]
            pct = avanzamenti[sid]
            base = baseline.get(sid, 0)

            # Slider fermo: nessuna derivazione, e la stima mancante non si
            # segnala (vedi PRECEDENZA DEI CONTROLLI).
            if pct is None:
                out[sid] = {
                    "task_id": task_id, "ore": 0.0, "baseline_pct": base,
                    "delta_pct": None, "stima_usata": stima,
                }
                continue

            delta = pct - base

            if stima is None:
                out[sid] = {
                    "task_id": task_id, "ore": None, "baseline_pct": base,
                    "delta_pct": delta, "stima_usata": None,
                }
                continue

            # Clamp sul Δ, non sulle ore: «l'avanzamento può tornare indietro,
            # le ore no». Con la monotonia imposta a monte non dovrebbe mai
            # scattare — se scatta, `delta_pct` resta negativo nel risultato ed
            # è il sintomo di una dichiarazione entrata da un'altra porta.
            ore = (max(delta, 0) / 100.0) * stima
            out[sid] = {
                "task_id": task_id,
                # round a 1 decimale: è la precisione di TUTTE le ore di questo
                # modulo (ore_settimanali_task, ore_dichiarate_settimana,
                # lista_fasi_progetto...). Serve anche a tagliare il rumore
                # float, che qui è tutt'altro che raro: un Δ del 10% su una
                # stima da 3h vale 0.30000000000000004 senza arrotondamento, e
                # le stime piccole sono la norma sui sottotask.
                "ore": round(ore, 1),
                "baseline_pct": base,
                "delta_pct": delta,
                "stima_usata": stima,
            }
        return out
    finally:
        # Solo se l'abbiamo aperta noi: chiudere la sessione del chiamante
        # farebbe scadere i suoi oggetti a metà transazione.
        if propria:
            session.close()


def tipo_unita_per_task(session, task_ids):
    """{task_id: "sottotask" | "task"} — quale unità di lavoro governa ogni task.

    È IL PUNTO DI MUTUA ESCLUSIONE del motore ore-derivate (Step 4, 07/08/2026).
    Un task ha pezzi OPPURE una percentuale propria, MAI entrambi:

      ha almeno un sottotask non-Annullato  → "sottotask"
          le ore vengono dai pezzi, e una eventuale `Consuntivo.percentuale`
          sulla riga del task viene IGNORATA.
      nessun sottotask                      → "task"
          le ore vengono dalla percentuale del task.

    PERCHÉ ESISTE, e perché è una funzione e non un `if` sparso. Le due sorgenti
    risponderebbero alla stessa domanda — quante ore è costato questo task
    questa settimana — e sommarle conterebbe due volte lo stesso lavoro. È lo
    stesso conflitto già risolto una volta fra ore derivate e ore manuali
    (`salva_consuntivo`, dove le derivate vincono): lì la regola sta in un punto
    solo, e qui deve stare in un punto solo. Un task con pezzi che si porti
    dietro una percentuale propria — residuo di prima della scomposizione, o di
    un client distratto — non deve poter far comparire ore dal nulla.

    LA DOMANDA È SULLA STRUTTURA, NON SULLE DICHIARAZIONI. Si guarda se il
    task è scomposto, non se qualcuno ha dichiarato: un task scomposto su cui
    nessuno ha ancora toccato i pezzi resta di tipo "sottotask" e deriva zero,
    che è la verità. Decidere in base a «dove ci sono dichiarazioni» farebbe
    cambiare tipo allo stesso task da una settimana all'altra.

    Gli ANNULLATI non contano: sono pezzi tolti dal piano (la via che il
    Cantiere offre per cancellarli conservando le dichiarazioni), e
    `salva_consuntivo` rifiuta con 400 un avanzamento su di essi. Un task i cui
    pezzi sono stati tutti annullati torna a essere un task-unità. Stessa
    asimmetria di `scostamento_stime_sottotask`, che esclude gli Annullati e
    tiene i Sospesi.

    Una query aggregata per tutti i task insieme, non una per task.
    """
    from models import Sottotask

    task_ids = list(task_ids)
    if not task_ids:
        return {}

    scomposti = {
        r[0]
        for r in session.query(Sottotask.task_id)
        .filter(
            Sottotask.task_id.in_(task_ids),
            Sottotask.stato != "Annullato",
        )
        .distinct()
        .all()
    }
    return {
        tid: ("sottotask" if tid in scomposti else "task")
        for tid in task_ids
    }


def _aggrega_ore_unita(session, tipo, righe, settimana):
    """Ore per task da un insieme di dichiarazioni-sottotask di una settimana.

    Step 4 STRATO 2 (06/08/2026). È il punto — l'UNICO — dove si applica la
    regola «le ore effettive sostituiscono la derivata». Sta in una funzione a
    sé perché serve in due posti dentro `salva_consuntivo` (l'aggregazione
    della settimana in corso e il ricalcolo di quella a valle) e una regola
    scritta due volte è una regola che prima o poi diverge: basterebbe
    correggere un ramo solo e le ore di una settimana ricalcolata comincerebbero
    a raccontare una storia diversa da quelle appena salvate.

    righe: iterabile di (sottotask_id, percentuale, ore_effettive) — le
           dichiarazioni di UNA settimana, già lette dal DB.
    settimana: quella delle righe. Serve al calcolo del Δ per cercare la
           baseline all'indietro.

    LA PRECEDENZA, e perché è in quest'ordine:
      1. `ore_effettive` non NULL  → vince, sempre. È un dato esplicito
         scritto da chi ha lavorato; la derivata è una stima calcolata da una
         percentuale. Non si sommano: sono due risposte alla stessa domanda.
      2. altrimenti la derivata (Δpct × ore_stimate).
      3. derivata non calcolabile (manca `ore_stimate`) → il sottotask finisce
         fra i `non_derivabili` e NON contribuisce: sommare 0 farebbe sparire
         lavoro vero in silenzio.

    Il controllo su `ore_effettive` viene PRIMA di quello sulla derivabilità, e
    non è un dettaglio: un pezzo NON STIMATO ma con ore dichiarate a mano è uno
    dei casi per cui lo strato 2 esiste. Segnalarlo come «non derivabile»
    sarebbe un avviso su un problema che il dipendente ha già risolto — gli si
    direbbe che le sue ore non sono state contate proprio mentre vengono
    contate.

    Ritorna (per_task, non_derivabili):
      per_task       : {task_id: ore}, già arrotondate a 1 decimale
      non_derivabili : [sottotask_id] su cui il chiamante costruisce gli avvisi
    """
    righe = list(righe)
    if not righe:
        return {}, []

    effettive = {
        unita_id: ore
        for unita_id, _pct, ore in righe
        if ore is not None
    }
    derivate = ore_derivate_unita(
        tipo,
        {unita_id: pct for unita_id, pct, _ore in righe},
        settimana,
        session=session,
    )

    # LA SOMMA NON HA UN RAMO PER TIPO, e non è una svista. Per i sottotask
    # accumula i pezzi sul task padre; per un task-unità `task_id` È l'unità
    # stessa e le righe di quel task sono una sola (UNIQUE task+dipendente+
    # settimana), quindi lo stesso accumulo diventa un passaggio diretto: il
    # caso «nessuna aggregazione» è quello degenere dell'aggregazione con un
    # elemento. Scriverci sopra un `if tipo ==` aggiungerebbe un ramo che
    # calcola la stessa cosa, cioè un posto in più dove divergere.
    per_task = {}
    non_derivabili = []
    for unita_id, calcolo in derivate.items():
        task_id = calcolo["task_id"]
        if unita_id in effettive:
            per_task[task_id] = per_task.get(task_id, 0.0) + effettive[unita_id]
            continue
        if calcolo["ore"] is None:
            non_derivabili.append(unita_id)
            continue
        per_task[task_id] = per_task.get(task_id, 0.0) + calcolo["ore"]

    return {t: round(o, 1) for t, o in per_task.items()}, non_derivabili


def tasso_compilazione_progetto(pid):
    session = get_session()
    base = session.query(Consuntivo).join(
        Task, Consuntivo.task_id == Task.id
    ).filter(Task.progetto_id == pid)
    n_tot = base.count()
    if n_tot == 0:
        session.close()
        return 0
    n_comp = base.filter(Consuntivo.compilato == True).count()
    session.close()
    return n_comp / n_tot * 100

def carico_settimanale_dipendente(did, settimana):
    """Carico di un dipendente in una settimana (in ore).

    ⚠ DEBITO DI DESIGN — distribuzione uniforme (decisione 18 mag, vedi handoff):
    Il calcolo assume che `ore_stimate` di un task siano distribuite
    UNIFORMEMENTE su tutte le settimane della sua durata. Questa è una
    semplificazione provvisoria: in realtà il PM dovrebbe poter dichiarare
    una distribuzione settimanale esplicita (es. "20h la prima settimana,
    5h le successive" per un task con setup iniziale concentrato).

    Step 2.7-pre del handoff v17 affronterà:
      1) Chiarimento semantica ore_stimate / ore_vendute / ore_pianificate /
         ore_consumate / ore_mancanti (storia: ore_pianificate ha avuto un
         significato bisecato durante l'evoluzione della specifica)
      2) Eventuale aggiunta campo Task.distribuzione_ore_per_settimana
      3) UI nel modale Task per dichiarare la distribuzione (default = uniforme)

    Fino allo Step 2.7-pre i numeri di saturazione mostrati sono onesti
    rispetto alla logica attuale, ma rappresentano una media uniformata
    della realtà operativa. NON costruire sopra logiche di redistribuzione
    automatica IA prima dello Step 2.7-pre.

    Filtri (iso-comportamento col vecchio DataFrame loader):
      - task del dipendente, stato NON in ("Completato", "Sospeso")
      - sovrapposizione con la settimana lunedì–venerdì
      - task senza data_inizio/data_fine (NULL): esclusi (in SQL WHERE)

    ⚠ NON UNIFICARE QUESTA FINESTRA CON QUELLA DI `task_settimana_dipendente`.
    Sono due copie della stessa condizione e la somiglianza invita a fonderle,
    ma rispondono a domande opposte: là «cosa posso ancora dichiarare», qui
    «quanto pesa questa settimana». Dal 04/09/2026 la prima ha un ramo in più
    (il task SCADUTO ma ancora vivo, che resta consuntivabile); portarlo anche
    qui farebbe consumare capacità a un task scaduto in OGNI settimana futura,
    per sempre — il carico di ogni dipendente crescerebbe di un fantasma a ogni
    scadenza mancata. E questa funzione ha una decina di chiamanti (Risorse,
    Home, agent, contesto, dipendenti): l'errore si vedrebbe lontano da qui.
    """
    lun = settimana - timedelta(days=settimana.weekday())
    ven = lun + timedelta(days=4)

    session = get_session()
    try:
        tasks_dip = (
            session.query(Task)
            .filter(
                Task.dipendente_id == did,
                Task.stato.notin_(["Completato", "Sospeso"]),
                Task.data_inizio <= ven,
                Task.data_fine >= lun,
            )
            .all()
        )
    finally:
        session.close()

    ore = 0
    for t in tasks_dip:
        # Distribuzione uniforme: ore_pianificate (piano corrente) / durata.
        # Migrazione #3 passo 2 (#1): il carico usa il PIANO CORRENTE, non la
        # stima storica. Post-backfill pianificate == stimate → oracolo invariato.
        # weeks = max(1, ...) per task brevi (< 1 settimana).
        weeks = max(1, (t.data_fine - t.data_inizio).days / 7)
        ore += (t.ore_pianificate or 0) / weeks
    return round(ore, 1)

def get_progetti_dipendente(did):
    session = get_session()
    rows = session.query(Task.progetto_id, Progetto.nome).join(
        Progetto, Task.progetto_id == Progetto.id
    ).filter(
        Task.dipendente_id == did,
        Task.stato.in_(["In corso", "Da iniziare"]),
    ).order_by(Task.id).all()
    session.close()
    seen, out = set(), []
    for pid, nome in rows:
        if pid not in seen:
            seen.add(pid)
            out.append(nome)
    return out


def _lunedi(d=None):
    """Normalizza una data al lunedì della sua settimana ISO.

    Regola UNICA condivisa da lettura (task_settimana_dipendente) e scrittura
    (salva_consuntivo): la colonna `settimana` di Consuntivo / Presenza /
    Spesa contiene SEMPRE un lunedì. Se la scrittura ci mette un giorno
    qualsiasi (era `datetime.now()`), la UNIQUE task+dip+settimana non
    intercetta il doppione e la stessa settimana si sdoppia in righe diverse:
    è l'origine del bug duplicati.

    Accetta date, datetime, stringa ISO 'YYYY-MM-DD' o None (= oggi).
    Solleva ValueError se la stringa non è una data ISO valida.
    """
    if d is None:
        d = date.today()
    if isinstance(d, str):
        d = date.fromisoformat(d)      # ValueError se malformata
    if isinstance(d, datetime):
        d = d.date()
    return d - timedelta(days=d.weekday())


def task_settimana_dipendente(dipendente_id, settimana=None):
    """I task schedulati sul dipendente per una settimana, con le ore già
    consuntivate da LUI in QUELLA settimana attaccate sopra.

    Riusabile: alimenta sia GET /api/consuntivi/me sia la futura Home-utente
    («su cosa sto lavorando, come procedono i progetti»). La logica sta qui,
    non nella route, così un secondo endpoint la riusa senza duplicare la query.

    Parte dai Task assegnati (NON dai Consuntivi): il dipendente vede «cosa era
    previsto per lui quella settimana» anche se non ha ancora compilato
    (ore_consumate = 0 in quel caso, non lista vuota).

    Criterio di inclusione: PURAMENTE TEMPORALE — il task compare se la sua
    finestra data_inizio..data_fine interseca la settimana richiesta. Lo stato
    NON filtra (si esclude solo 'Annullato'): «schedulato» e «stato» sono assi
    indipendenti — un task può essere schedulato per questa settimana ed essere
    Bloccato, o schedulato per la scorsa e ancora In corso perché in ritardo.
    Il criterio precedente (stato IN 'In corso','Da iniziare') era
    settimana-cieco: guardando la settimana scorsa mostrava i task attivi
    OGGI, così un task chiuso venerdì spariva e le ore fatte su di esso
    diventavano indichiarabili.
    I task con date NULL restano inclusi (non si può dire che NON intersecano,
    e vanno comunque consuntivati). Assegnazione via Task.dipendente_id.

    Una query con joinedload(Task.progetto) per nome/tipologia progetto (niente
    N+1); una seconda query indicizzata prende i Consuntivi del dip/settimana e
    li attacca per task_id.

    Ritorna list[dict] ordinata per task_id:
      task_id, task_nome, progetto_id, progetto_nome, interna (bool),
      ore_iniziale (= ore_stimate congelata), ore_pianificate (totale del task),
      ore_pianificate_settimana (quota della settimana corrente: ore_pianificate
        spalmate sulla durata del task; None se date NULL, 0 se la finestra non
        tocca la settimana), ore_consumate (dichiarate dal dip in settimana),
      ore_rimanenti (residuo del task = ore_pianificate − consumato TOTALE del
        task su tutti i dipendenti/settimane, calcolato al volo), stato,
      in_ritardo (bool), nota (str|None: «a che punto sono», scritta dal dip in
        QUELLA settimana — è il round-trip di note_per_task in scrittura),
      dichiarato (bool: esiste una riga Consuntivo compilata di QUESTO dip su
        QUESTO task in QUELLA settimana),
      stato_dichiarato (str|None: lo stato che il dipendente ha dichiarato in
        QUELLA settimana; None se non si è espresso).
    `stato`, `dichiarato` e `stato_dichiarato` sono tre assi indipendenti: a che
    punto è il task oggi, se il dipendente ha compilato, e cosa ha dichiarato.
    Solo il terzo è attribuibile a lui — `stato` può essere stato scritto dal PM
    in Cantiere e non dice né chi né quando.

    `in_ritardo` NON è uno stato: è DERIVATO da data_fine e stato, ricalcolato
    a ogni lettura. Non è nella lista di ciò che il dipendente può dichiarare e
    non ha una colonna — il ritardo non si «dichiara», succede: la finestra del
    task si è chiusa e il task non è chiuso. Il frontend lo rende come
    segnalazione automatica accanto al task, non come opzione della tendina.

    NODO F-2 (02/09/2026) — tre campi nuovi su OGNI UNITÀ, cioè sui sottotask e
    sui task NON scomposti, gemelli esatti fra i due:
      presa_visione (bool)        «l'ho guardato, è ancora fermo». False quando
                                  la riga non c'è: la domanda ha risposta, ed è
                                  no. Vedi migration e7f8a9b0c1d2 per il perché
                                  è una colonna sua e non `compilato`.
      nota_ereditata (str|None)   l'ultima nota non vuota scritta su quell'unità
                                  PRIMA di questa settimana.
      nota_ereditata_da (str|None) la settimana da cui viene, in ISO.

    EREDITÀ A LETTURA, NON COPIA: la nota vecchia resta dov'è ed è `/me` che va
    a prenderla (`_note_ereditate`). Nessuna riga viene scritta per l'utente,
    quindi il contatore di F-1 non conta come dichiarato chi non ha aperto la
    pagina.

    `nota_ereditata` È SEPARATA DA `nota` E NON VA FUSA. `nota` è ciò che il
    dipendente ha scritto QUESTA settimana ed è una dichiarazione;
    `nota_ereditata` è un promemoria di ciò che era già stato detto e non lo è.
    Fonderle farebbe leggere a `unitaDichiarata` (contatore F-1) una traccia che
    non esiste, e ogni unità con una nota vecchia risulterebbe dichiarata: lo
    stesso guasto silenzioso dell'accessor che cade sulla baseline.

    QUI NON SI FILTRA, SI ESPONE IL FATTO. La nota ereditata si restituisce
    sempre che esista, anche quando l'unità ha già una nota propria o è
    avanzata. Decidere SE mostrarla è resa, e le due condizioni — «non ha una
    nota sua questa settimana» (`nota is None`) e «è ferma» (`percentuale` nulla
    oppure uguale a `baseline_pct`) — si calcolano interamente da campi che il
    payload porta già. Filtrare qui significherebbe scrivere la definizione di
    «ferma» in un secondo posto, dopo che il semaforo ha già mostrato cosa
    costa una regola in due copie; e farebbe apparire e sparire un campo a
    seconda di cosa l'utente ha appena digitato, che è più difficile da leggere
    di un campo stabile.
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func, or_, and_
    from models import Sottotask, ConsuntivoSottotask

    lun = _lunedi(settimana)
    fine_sett = lun + timedelta(days=6)  # lun..dom, come /me e /settimana
    # `oggi` sale QUI perché da ora serve a DUE cose: al ramo-4 del filtro e
    # alla closure `_in_ritardo` più sotto. Un solo riferimento al presente per
    # entrambe, invece di due `date.today()` che in teoria possono cadere a
    # cavallo della mezzanotte e far divergere filtro e etichetta.
    oggi = date.today()

    # Gli stati che NON sono un ritardo del dipendente. Vocabolario definito una
    # volta e usato in DUE forme — la condizione SQL del ramo-4 e `_in_ritardo`
    # — perché un'espressione SQLAlchemy e un `in` su un oggetto Python non
    # possono essere la stessa riga di codice. Il vocabolario però sì, ed è la
    # sola parte che può davvero divergere: se un domani si decidesse che anche
    # "Bloccato" non è un ritardo, cambiarlo qui cambierebbe insieme chi COMPARE
    # e chi viene ETICHETTATO. Sono la stessa domanda e devono restare allineate.
    STATI_NON_IN_RITARDO = ("Completato", "Sospeso")

    session = get_session()
    try:
        # ── I rami della visibilità ───────────────────────────────────────
        # 1-2. task senza date: non si può dire che NON intersecano.
        # 3.   intersezione finestra-task × settimana (il criterio storico).
        rami_finestra = [
            Task.data_inizio.is_(None),
            Task.data_fine.is_(None),
            and_(Task.data_inizio <= fine_sett, Task.data_fine >= lun),
        ]

        # 4. SCADUTO MA ANCORA VIVO — la finestra è chiusa e il lavoro no.
        #
        # Prima di questo ramo un task con `data_fine` passata usciva dalla
        # Consuntivazione e le ore fatte su di esso diventavano INDICHIARABILI:
        # il dipendente doveva aspettare che il PM spostasse la data. Ma la
        # scadenza di un piano non è la fine di un lavoro, e chi ci sta ancora
        # lavorando deve poter scrivere le sue ore senza chiedere il permesso.
        #
        # NON È UNA REGOLA NUOVA: è la stessa di `_in_ritardo`, che vive venti
        # righe più sotto e finora decideva solo l'ETICHETTA nel payload. Qui
        # viene promossa a decidere anche l'ESISTENZA della riga — perché
        # etichettare come «in ritardo» una riga che non si vede è una
        # contraddizione che il codice portava senza accorgersene.
        #
        # «Sospeso» resta fuori, con «Completato»: è un parcheggio deciso dal
        # PM, non un lavoro in corso, e riaprirlo ogni settimana per anni
        # riempirebbe la Consuntivazione di righe su cui nessuno deve scrivere.
        # «Bloccato» invece rientra: è la parola del DIPENDENTE per «sono fermo
        # ma è ancora lavoro mio» (è in STATI_DICHIARABILI, dove "Sospeso" non
        # c'è), ed è esattamente il caso che il nodo F-2 esiste per registrare.
        #
        # ⚠ IL CANCELLO `lun <= oggi` NON È ORNAMENTALE. La condizione del ramo
        # non nomina la settimana richiesta: da sola scatterebbe identica per
        # QUALSIASI settimana, comprese quelle future, e un task scaduto
        # comparirebbe da qui all'infinito. Il confronto con `oggi` garantisce
        # che il ramo non guardi la settimana visualizzata, non che si fermi —
        # a fermarlo è questo `if`. La guardia della route
        # (`/api/consuntivi/me` accetta solo corrente e precedente) copre già
        # il caso, ma vive in un ALTRO file: questa funzione è pubblica nello
        # strato dati e il suo docstring ne promette un secondo consumatore
        # («la userà anche la Home-utente»). Deve difendersi da sé.
        if lun <= oggi:
            rami_finestra.append(
                and_(
                    Task.data_fine < oggi,
                    Task.stato.notin_(STATI_NON_IN_RITARDO),
                )
            )

        tasks = (
            session.query(Task)
            .options(joinedload(Task.progetto))
            .filter(
                Task.dipendente_id == dipendente_id,
                # «Eliminato» accanto ad «Annullato»: il soft-delete scrive
                # quello stato e la riga resta in tabella, quindi un task
                # cancellato con la finestra ancora aperta compariva nella
                # Consuntivazione di chi ce l'aveva assegnato. In DB non ce n'è
                # nemmeno uno oggi — era un buco latente, non un bug osservato —
                # ma il ramo-4 allarga la visibilità e un latente allargato
                # prima o poi si vede. `gantt_strutturato` filtra già entrambi.
                Task.stato.notin_(("Annullato", "Eliminato")),
                or_(*rami_finestra),
            )
            .order_by(Task.id)
            .all()
        )
        task_ids = [t.id for t in tasks]

        # Ore dichiarate e nota scritta da QUESTO dip in QUESTA settimana, per
        # task_id. (UNIQUE task+dip+settimana → di norma una riga per task;
        # sommiamo comunque per robustezza.)
        cons_rows = (
            session.query(Consuntivo.task_id, Consuntivo.ore_dichiarate,
                          Consuntivo.nota, Consuntivo.compilato,
                          Consuntivo.stato_dichiarato,
                          # Step 4 (07/08/2026): la dichiarazione del task come
                          # UNITÀ di lavoro. Due colonne in più sulla query che
                          # c'era già, non una query nuova.
                          Consuntivo.percentuale, Consuntivo.ore_effettive,
                          # Nodo F-2 (02/09/2026): una colonna in più sulla
                          # stessa query, come sopra.
                          Consuntivo.presa_visione,
                          # Consuntivazione A (04/09/2026): idem. Serve a
                          # RIPOPOLARE il campo quando si riapre una settimana
                          # già compilata — senza, il residuo scritto lunedì
                          # apparirebbe vuoto martedì, e un ri-salvataggio lo
                          # lascerebbe intatto (chiave assente = non toccare)
                          # facendo credere di averlo cancellato.
                          Consuntivo.ore_stimate_residue)
            .filter(
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana >= lun,
                Consuntivo.settimana <= fine_sett,
            )
            .all()
        )
        # Consumato TOTALE per task (tutti i dipendenti, tutte le settimane):
        # serve per ore_rimanenti. La colonna Task.ore_rimanenti è denormalizzata
        # e stale (il seed non la aggiorna dopo i consuntivi) → la ricalcolo al
        # volo, stesso principio del serializzatore SAL su ore_consumate.
        tot_rows = []
        if task_ids:
            tot_rows = (
                session.query(Consuntivo.task_id, func.sum(Consuntivo.ore_dichiarate))
                .filter(Consuntivo.task_id.in_(task_ids))
                .group_by(Consuntivo.task_id)
                .all()
            )

        # ── SOTTOTASK (Step 4, 06/08/2026) ───────────────────────────────
        # Tre query per TUTTI i task insieme, non tre per task: la pagina di un
        # dipendente con dieci task farebbe altrimenti trenta round-trip. Stesso
        # pattern dell'aggregata `tot_rows` qui sopra e di
        # `scostamento_stime_sottotask`.
        #
        # Gli ANNULLATI restano fuori dalla lista: `salva_consuntivo` rifiuta con
        # 400 un avanzamento su un pezzo annullato, e mostrarlo nel form vorrebbe
        # dire offrire uno slider che al salvataggio esplode. I SOSPESI invece
        # restano — la sospensione è una decisione di piano del PM, ma se il
        # dipendente ci ha lavorato le sue ore vanno dichiarabili (stessa
        # asimmetria di `scostamento_stime_sottotask` e della validazione).
        sottotask_rows = []
        dich_sottotask = {}
        baseline_sottotask = {}
        note_ered_sottotask = {}
        task_unita = []
        baseline_task = {}
        note_ered_task = {}
        if task_ids:
            sottotask_rows = (
                session.query(Sottotask)
                .filter(
                    Sottotask.task_id.in_(task_ids),
                    Sottotask.stato != "Annullato",
                )
                .order_by(Sottotask.ordine, Sottotask.id)
                .all()
            )
            sottotask_ids = [s.id for s in sottotask_rows]

            if sottotask_ids:
                # Dichiarazioni di QUESTO dipendente in QUESTA settimana: è ciò
                # che ri-popola il form quando si riapre una settimana già
                # compilata. Per dipendente e non per pezzo, a differenza della
                # baseline: qui la domanda è «cosa ho scritto io», non «a che
                # punto è il pezzo».
                for r in (
                    session.query(ConsuntivoSottotask)
                    .filter(
                        ConsuntivoSottotask.sottotask_id.in_(sottotask_ids),
                        ConsuntivoSottotask.dipendente_id == dipendente_id,
                        ConsuntivoSottotask.settimana >= lun,
                        ConsuntivoSottotask.settimana <= fine_sett,
                    )
                    .all()
                ):
                    dich_sottotask[r.sottotask_id] = r

                # Baseline: stessa identica funzione che il motore userà per
                # calcolare il Δ al salvataggio. Il cursore deve partire dal
                # punto da cui partirà il conto, non da un numero che gli
                # somiglia.
                baseline_sottotask = _baseline_percentuali(
                    session, "sottotask", sottotask_ids, lun
                )
                # Nodo F-2 (b): il perché di un fermo, ripescato all'indietro.
                # Stessa forma della baseline qui sopra — una query, batch — e
                # per la stessa ragione: sono la stessa domanda su due colonne
                # diverse.
                note_ered_sottotask = _note_ereditate(
                    session, "sottotask", sottotask_ids, lun
                )

            # ── Baseline dei TASK-UNITÀ (Step 4, 07/08/2026) ──────────────
            # Solo per i task NON scomposti: su un task con pezzi la
            # percentuale vive sui pezzi, e una percentuale-task sarebbe la
            # doppia verità che il motore già ignora (`tipo_unita_per_task`).
            # Il discriminante NON richiede una query: `sottotask_rows` sopra ha
            # già filtrato i non-Annullati, quindi i task che vi compaiono sono
            # esattamente gli scomposti — stesso criterio, dato già in mano.
            task_scomposti = {s.task_id for s in sottotask_rows}
            task_unita = [tid for tid in task_ids if tid not in task_scomposti]
            if task_unita:
                # Stessa funzione della baseline dei pezzi, con tipo="task": il
                # cursore deve partire dal punto da cui partirà il conto.
                baseline_task = _baseline_percentuali(
                    session, "task", task_unita, lun
                )
                # Nodo F-2 (b), gemella per i task-unità. Solo per i NON
                # scomposti: su un task con pezzi la nota-del-perché sta sui
                # pezzi, come tutto il resto della dichiarazione.
                note_ered_task = _note_ereditate(
                    session, "task", task_unita, lun
                )
    finally:
        session.close()

    # Sottotask raggruppati per task padre, nell'ordine già stabilito dalla
    # query (ordine, id): il dict conserva l'ordine di inserimento.
    sottotask_per_task = {}
    for s in sottotask_rows:
        d = dich_sottotask.get(s.id)
        sottotask_per_task.setdefault(s.task_id, []).append({
            "id": s.id,
            "nome": s.nome,
            "ore_stimate": s.ore_stimate,
            "ordine": s.ordine,
            # stato di PIANIFICAZIONE (Da iniziare/Sospeso), non l'avanzamento:
            # quello è `stato_dichiarato`, che sta due righe sotto ed è un asse
            # diverso. Vedi il commento su Sottotask.stato in models.
            "stato": s.stato,
            # Assegnatario RISOLTO — `sottotask.dipendente_id or task.dipendente_id`.
            # Si espone il risolto e non l'override grezzo perché la domanda del
            # form è una sola: «questo pezzo è mio?». Chi ha l'override viene
            # riempito nel ciclo sotto, dove il task padre è a portata di mano.
            "assegnatario_id": s.dipendente_id,
            # Dichiarazione di questa settimana, o None se non pervenuta.
            "percentuale": d.percentuale if d else None,
            "stato_dichiarato": d.stato_dichiarato if d else None,
            "nota": d.nota if d else None,
            "ore_effettive": d.ore_effettive if d else None,
            # Consuntivazione A: «quante ore mancano ancora su questo pezzo».
            # None quando la riga non c'è O quando c'è ma nessuno ha stimato —
            # i due casi collassano di proposito: per il form sono la stessa
            # cosa, un campo vuoto da compilare. La distinzione conterebbe solo
            # per chi analizza le dichiarazioni, e quel consumatore leggerà la
            # colonna, non questo payload.
            "ore_stimate_residue": d.ore_stimate_residue if d else None,
            # Nodo F-2 (a): «l'ho guardato, è ancora fermo». È una traccia
            # SENZA avanzamento, e sta accanto agli altri campi della
            # dichiarazione perché è una dichiarazione anche lei. False — non
            # None — quando la riga non c'è: la domanda «l'ha preso in visione?»
            # ha risposta, ed è no.
            "presa_visione": bool(d.presa_visione) if d else False,
            # Da dove riparte l'avanzamento: 0 = mai dichiarato prima.
            "baseline_pct": baseline_sottotask.get(s.id, 0),
            # Nodo F-2 (b): l'ultima nota scritta su questo pezzo PRIMA di
            # questa settimana, con la settimana da cui viene.
            # DUE CAMPI DISTINTI DA `nota`, e la separazione non è cosmetica: se
            # la nota ereditata finisse dentro `nota`, `unitaDichiarata` del
            # contatore F-1 la leggerebbe come traccia e conterebbe come
            # dichiarata ogni unità con una nota vecchia. È la stessa trappola
            # dell'accessor `valoreSottotask`, che cade sulla baseline e
            # renderebbe ogni percentuale non-nulla.
            **_nota_ereditata_payload(note_ered_sottotask.get(s.id)),
        })

    consumate_per_task = {}
    note_per_task = {}
    dichiarati = set()
    stato_dichiarato_per_task = {}
    percentuale_per_task = {}
    ore_effettive_per_task = {}
    residuo_per_task = {}
    presa_visione_per_task = set()
    for (tid, ore, nota, compilato, stato_dich,
         pct, ore_eff, presa_vis, residuo) in cons_rows:
        consumate_per_task[tid] = consumate_per_task.get(tid, 0.0) + float(ore or 0)
        # Come lo stato e la nota: non si sommano, vince la prima valorizzata.
        if pct is not None and tid not in percentuale_per_task:
            percentuale_per_task[tid] = pct
        if ore_eff is not None and tid not in ore_effettive_per_task:
            ore_effettive_per_task[tid] = ore_eff
        # Stessa regola: NON si somma. Due stime residue sulla stessa settimana
        # non fanno «55 ore mancanti», fanno due opinioni sullo stesso lavoro, e
        # sommarle produrrebbe un numero che nessuno ha detto. `is not None` e
        # non un test di verità, perché 0.0 — «non manca più niente» — è una
        # dichiarazione da preservare e un `if residuo:` la scarterebbe.
        if residuo is not None and tid not in residuo_per_task:
            residuo_per_task[tid] = residuo
        # Nodo F-2 (a). Un set e non un dict: se nel range ci fossero due righe,
        # basta che UNA porti la presa-visione perché il task risulti guardato —
        # «l'ho visto» non si annulla per il fatto che un'altra riga taccia.
        if presa_vis:
            presa_visione_per_task.add(tid)
        if compilato:
            dichiarati.add(tid)
        # Come la nota: non si somma, e la prima valorizzata vince.
        if stato_dich and not stato_dichiarato_per_task.get(tid):
            stato_dichiarato_per_task[tid] = stato_dich
        # La nota NON si somma: è testo. Se per qualche ragione ci fossero due
        # righe nel range, vince la prima non vuota — meglio mostrare una nota
        # vecchia che perderla e costringere a riscriverla.
        if nota and not note_per_task.get(tid):
            note_per_task[tid] = nota

    consumato_totale_task = {tid: float(s or 0) for tid, s in tot_rows}

    def _quota_settimana(t):
        """Quota di ore per la settimana corrente: ore_pianificate spalmate
        uniformemente sulle settimane di durata del task. Riusa la stessa logica
        di carico_settimanale_dipendente, così le due viste restano coerenti.
        Casi limite: date NULL → None; finestra fuori settimana → 0; durata < 1
        settimana → tutte le ore nella settimana (weeks = max(1, ...))."""
        if t.data_inizio is None or t.data_fine is None:
            return None
        if t.data_inizio > fine_sett or t.data_fine < lun:
            return 0.0
        weeks = max(1, (t.data_fine - t.data_inizio).days / 7)
        return round((t.ore_pianificate or 0) / weeks, 1)

    def _in_ritardo(t):
        """Finestra chiusa (data_fine passata) e task non chiuso.
        Il confronto è con OGGI, non con la settimana visualizzata: un task
        scaduto resta in ritardo anche riaprendo la settimana scorsa.
        Date NULL → non si può dire che sia scaduto, quindi False.
        'Sospeso' è escluso con 'Completato': è una decisione del PM, non un
        ritardo del dipendente — segnalarlo accuserebbe del contrario.

        STESSA REGOLA DEL RAMO-4 del filtro, in cima alla funzione: là decide
        se la riga ESISTE, qui se va ETICHETTATA. Il vocabolario degli stati è
        letteralmente lo stesso oggetto (`STATI_NON_IN_RITARDO`) proprio perché
        le due risposte non possono divergere: una riga che compare per il
        ramo-4 esce da qui con `in_ritardo=True`, sempre e per costruzione."""
        if t.data_fine is None:
            return False
        return t.data_fine < oggi and t.stato not in STATI_NON_IN_RITARDO

    out = []
    for t in tasks:
        prog = t.progetto
        pianificate = float(t.ore_pianificate or 0)
        out.append({
            "task_id": t.id,
            "task_nome": t.nome,
            "progetto_id": t.progetto_id,
            "progetto_nome": prog.nome if prog else "?",
            # interna = tipologia progetto, NON id P010 (vedi economia: il
            # filtro per id era un hack morto). Per il badge blu/grigio.
            "interna": bool(prog and prog.tipologia == "interna"),
            "ore_iniziale": int(t.ore_stimate or 0),
            "ore_pianificate": pianificate,             # totale del task (contesto)
            "ore_pianificate_settimana": _quota_settimana(t),  # quota settimana
            "ore_consumate": round(consumate_per_task.get(t.id, 0.0), 1),
            # residuo del TASK (non del singolo/settimana): piano − consumato tot.
            "ore_rimanenti": round(pianificate - consumato_totale_task.get(t.id, 0.0), 1),
            "stato": t.stato,
            # La SCADENZA del task (Tappa 2, 04/09/2026). `in_ritardo` qui
            # accanto dice SE la finestra è chiusa; questa dice QUANDO si
            # chiude — e finché è aperta è l'unica delle due che informa:
            # «scade fra 3 giorni» è ciò che fa decidere, «non è in ritardo»
            # no. Serve a «le mie cose» nella Home per evidenziare le scadenze
            # imminenti, che senza questo campo non erano calcolabili.
            # `data_inizio` non si espone: nella settimana corrente un task già
            # cominciato non aggiunge nulla, e il payload cresce per niente.
            "data_fine": t.data_fine.isoformat() if t.data_fine else None,
            "in_ritardo": _in_ritardo(t),
            # «A che punto sono», come l'ha scritta il dipendente in QUESTA
            # settimana (None se non ha scritto nulla). Serve a riaprire una
            # settimana già compilata senza perdere il testo: su un task
            # Bloccato la nota è obbligatoria in scrittura, quindi senza
            # rileggerla un ri-salvataggio verrebbe rifiutato con 400.
            "nota": note_per_task.get(t.id),
            # Il dipendente ha dichiarato qualcosa su questo task IN QUESTA
            # settimana? È un asse diverso da `stato`: `stato` è Task.stato,
            # che esiste da quando il PM ha creato il task e vale "Da iniziare"
            # o "In corso" anche se nessuno ha mai compilato nulla. Senza
            # questo flag la pagina non può distinguere «non dichiarato» da
            # «dichiarato In corso», e il salvataggio non lascia traccia
            # visibile. Le righe del seed hanno compilato=True e risultano
            # dichiarate: è corretto, sono consuntivi a tutti gli effetti.
            "dichiarato": t.id in dichiarati,
            # CHE COSA ha dichiarato il dipendente in questa settimana (None se
            # non si è espresso). Terzo asse, distinto dagli altri due: `stato`
            # è il task oggi, `dichiarato` è se ha compilato, questo è la sua
            # dichiarazione. Solo questo può essere attribuito a lui.
            "stato_dichiarato": stato_dichiarato_per_task.get(t.id),
        })

        # ── Il task come UNITÀ DI LAVORO (Step 4, 07/08/2026) ────────────
        # I tre campi che il frontend serve per rendere lo slider del task,
        # gemelli di quelli che ogni pezzo porta già. Compaiono SOLO sui task
        # non scomposti: sulla voce di un task con pezzi sarebbero la doppia
        # verità che il motore rifiuta, e il payload di quei task resta
        # identico a prima — nessun consumatore esistente vede campi nuovi.
        #
        # `baseline_pct` è None e non 0 quando non c'è storia: 0 direbbe «il
        # lavoro è a zero», None dice «non c'è un punto di partenza», e sono
        # due cose diverse per uno slider che deve decidere il proprio minimo.
        if t.id not in task_scomposti:
            out[-1].update({
                "percentuale": percentuale_per_task.get(t.id),
                "baseline_pct": baseline_task.get(t.id),
                "ore_effettive": ore_effettive_per_task.get(t.id),
                # Consuntivazione A, gemella di quella sui pezzi. Dentro questo
                # ramo come tutte le altre: su un task SCOMPOSTO il residuo vive
                # sui pezzi, e una stima-del-task accanto alle stime-dei-pezzi
                # sarebbe la doppia verità che il motore rifiuta per le ore.
                "ore_stimate_residue": residuo_per_task.get(t.id),
                # Nodo F-2 (a) e (b), gemelli esatti di quelli sui pezzi — e
                # stanno qui, dentro il ramo dei NON scomposti, per la stessa
                # ragione degli altri tre: su un task con pezzi sarebbero la
                # doppia verità che il motore rifiuta, e il payload di quei task
                # deve restare identico a prima.
                "presa_visione": t.id in presa_visione_per_task,
                **_nota_ereditata_payload(note_ered_task.get(t.id)),
            })

        # `sottotask` compare SOLO sui task scomposti — la chiave assente è essa
        # stessa l'informazione «questo task si compila come sempre», e il
        # frontend distingue i due render dalla sua presenza. È la convenzione
        # di `scostamento_stime_sottotask` (chiave assente = niente da dire), e
        # tiene il payload dei task non scomposti IDENTICO a prima: nessun
        # consumatore esistente vede comparire un campo nuovo.
        pezzi = sottotask_per_task.get(t.id)
        if pezzi:
            # Risoluzione dell'assegnatario, qui e non nella comprehension
            # sopra: serve `Task.dipendente_id`, che è disponibile solo dentro
            # questo ciclo. `or` e non `if is None`: un override a stringa vuota
            # (FK invalida per Postgres, ma scrivibile da un client distratto)
            # deve ricadere sull'eredità come farebbe un NULL.
            out[-1]["sottotask"] = [
                {**p, "assegnatario_id": p["assegnatario_id"] or t.dipendente_id}
                for p in pezzi
            ]
    return out


def lunedi_settimana(d=None):
    """Alias PUBBLICO di `_lunedi`. Non è una seconda regola: delega, punto.

    Esiste solo per attraversare il confine di `data.py`, che fa
    `from data_db_impl import *` — e `import *` non porta con sé i nomi che
    iniziano con underscore. Le route devono poter normalizzare la settimana
    richiesta (query param / body) con la STESSA regola usata qui dentro,
    invece di ricalcolare il lunedì per conto loro: è esattamente la
    duplicazione che ha generato il bug dei duplicati.
    """
    return _lunedi(d)


def note_consuntivi_settimana(dipendente_id, settimana=None):
    """{task_id: nota} delle note NON VUOTE già scritte dal dipendente in quella
    settimana. I task senza nota non compaiono nel dict.

    Serve alla validazione «Bloccato richiede una nota», che deve guardare ciò
    che ESISTE e non solo ciò che è arrivato nella richiesta: il form manda solo
    le note MODIFICATE, quindi ridichiarare Bloccato senza ritoccare la nota è
    il caso normale, non un errore. La lettura sta qui e non nella route perché
    è una domanda sul DB, e le route non fanno SQL.

    Query indicizzata su (dipendente_id, settimana), le stesse colonne del resto
    del modulo; il range lun..dom è quello di /me e /settimana.
    """
    lun = _lunedi(settimana)
    fine_sett = lun + timedelta(days=6)

    session = get_session()
    try:
        rows = (
            session.query(Consuntivo.task_id, Consuntivo.nota)
            .filter(
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana >= lun,
                Consuntivo.settimana <= fine_sett,
                Consuntivo.nota.isnot(None),
            )
            .all()
        )
    finally:
        session.close()

    # Lo strip finale: in DB una nota vuota è NULL (vedi _nota_task), ma righe
    # scritte da altri percorsi potrebbero portare spazi — «vuota» resta vuota.
    return {tid: nota for tid, nota in rows if (nota or "").strip()}


def note_sottotask_settimana(dipendente_id, settimana=None):
    """{sottotask_id: nota} delle note NON VUOTE già scritte dal dipendente su
    un SOTTOTASK in quella settimana. I sottotask senza nota non compaiono.

    Gemella di `note_consuntivi_settimana`, stessa forma e stesso scopo un
    livello più giù: serve alla validazione «un sottotask Bloccato richiede una
    nota», che deve guardare ciò che ESISTE e non solo ciò che è arrivato nel
    body. Il form manda le sole note modificate, quindi ridichiarare bloccato un
    pezzo che è fermo da tre settimane — senza ritoccarne il testo — è il caso
    normale, non un errore da rifiutare.

    Query sulla UNIQUE (sottotask, dipendente, settimana); il range lun..dom è
    la stessa rete di sicurezza della gemella per righe con data non
    normalizzata.
    """
    from models import ConsuntivoSottotask

    lun = _lunedi(settimana)
    fine_sett = lun + timedelta(days=6)

    session = get_session()
    try:
        rows = (
            session.query(ConsuntivoSottotask.sottotask_id, ConsuntivoSottotask.nota)
            .filter(
                ConsuntivoSottotask.dipendente_id == dipendente_id,
                ConsuntivoSottotask.settimana >= lun,
                ConsuntivoSottotask.settimana <= fine_sett,
                ConsuntivoSottotask.nota.isnot(None),
            )
            .all()
        )
    finally:
        session.close()

    return {sid: nota for sid, nota in rows if (nota or "").strip()}


_MESI_ABBR = ["gen", "feb", "mar", "apr", "mag", "giu",
              "lug", "ago", "set", "ott", "nov", "dic"]


def _etichetta_intervallo(lun):
    """'13–19 lug' se la settimana sta in un mese solo, '29 giu – 5 lug' se
    scavalca. Solo presentazione: il frontend mostra la stringa così com'è."""
    dom = lun + timedelta(days=6)
    if lun.month == dom.month:
        return f"{lun.day}–{dom.day} {_MESI_ABBR[dom.month - 1]}"
    return (f"{lun.day} {_MESI_ABBR[lun.month - 1]} – "
            f"{dom.day} {_MESI_ABBR[dom.month - 1]}")


def ore_dichiarate_settimana(dipendente_id, settimana=None):
    """Ore COPERTE dal dipendente in una settimana (float): ore dichiarate sui
    task + ore di assenza. È l'input del criterio di completezza.

    Le assenze contano. Chi è in ferie tutta la settimana HA compilato
    correttamente — ha dichiarato l'assenza. Se contassimo solo i Consuntivi
    resterebbe a 0 ore, quindi «incompleto», e il sistema gli chiederebbe in
    eterno di fare una cosa che ha già fatto.

    Indipendente dai task: somma TUTTI i Consuntivi del dip in quella
    settimana, anche quelli su task che non intersecano più la finestra.
    `task_settimana_dipendente` invece somma solo i task che vede — va bene
    per il totale mostrato accanto alla lista, non per decidere se una
    settimana è «compilata» (un task chiuso e uscito dalla finestra
    renderebbe la settimana incompleta per sempre).

    Range lun..dom, non `== lunedì`: rete di sicurezza per righe storiche o
    scritte da altre fonti con una data non normalizzata. Sommarle è il
    comportamento corretto in quel caso.
    """
    from sqlalchemy import func
    from models import PresenzaSettimanale

    lun = _lunedi(settimana)
    dom = lun + timedelta(days=6)
    session = get_session()
    try:
        ore_task = (
            session.query(func.sum(Consuntivo.ore_dichiarate))
            .filter(
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana >= lun,
                Consuntivo.settimana <= dom,
            )
            .scalar()
        )
        # Due query invece di un join: le presenze stanno su una tabella
        # separata con cardinalità 1-per-settimana, un join produrrebbe
        # righe moltiplicate e una somma gonfiata.
        ore_assenza = (
            session.query(func.sum(PresenzaSettimanale.ore_assenza))
            .filter(
                PresenzaSettimanale.dipendente_id == dipendente_id,
                PresenzaSettimanale.settimana >= lun,
                PresenzaSettimanale.settimana <= dom,
            )
            .scalar()
        )
    finally:
        session.close()
    return round(float(ore_task or 0) + float(ore_assenza or 0), 1)


def settimane_selezionabili(dipendente_id):
    """Le settimane che il dipendente può aprire in consuntivazione: la
    corrente e la precedente. Nient'altro — non si compila in anticipo, e il
    recupero all'indietro si ferma a una settimana.

    Ogni voce: {lunedi (ISO), etichetta, compilabile}.

    `compilabile` sulla settimana corrente è sempre True. Sulla precedente è
    True solo se INCOMPLETA: il recupero serve a chi non ha compilato, non a
    rivedere ciò che è chiuso. Criterio di completezza: ore dichiarate >= ore
    contrattuali del dipendente.

    Nota: la voce resta nella lista anche quando `compilabile` è False — il
    frontend la mostra disabilitata («già compilata») invece di farla sparire,
    così l'utente capisce perché non può tornarci.
    """
    corrente = _lunedi()
    precedente = corrente - timedelta(days=7)

    ore_sett = int(get_dipendente(dipendente_id).get("ore_sett") or 0)
    dichiarate_prec = ore_dichiarate_settimana(dipendente_id, precedente)

    return [
        {
            "lunedi": corrente.isoformat(),
            "etichetta": "Questa settimana",
            "compilabile": True,
        },
        {
            "lunedi": precedente.isoformat(),
            "etichetta": f"Settimana scorsa ({_etichetta_intervallo(precedente)})",
            "compilabile": dichiarate_prec < ore_sett,
        },
    ]


# ══════════════════════════════════════════════════════════════════════
# FUNZIONI DI MODIFICA — scrittura (scrivono nel db + ricaricano cache)
# ══════════════════════════════════════════════════════════════════════

def _next_task_id():
    session = get_session()
    from sqlalchemy import func
    max_id = session.query(func.max(Task.id)).scalar()
    session.close()
    if max_id and max_id.startswith("T") and max_id[1:].isdigit():
        return f"T{int(max_id[1:]) + 1:03d}"
    return "T001"


def genera_id_task_multipli(n, session=None):
    """Genera `n` id task consecutivi (formato T###) in un colpo solo.

    Step 2.7 (20/05/2026) — chiude la triplicazione del debito #22.
    Serve quando si creano PIÙ task nella stessa transazione: chiamare
    _next_task_id() in loop darebbe id duplicati, perché legge sempre lo
    stesso max() finché la transazione non è committata. Questa funzione
    legge il max UNA volta e poi incrementa un contatore locale.

    Parametri:
      n: quanti id servono (>= 0).
      session: se fornita, riusa quella sessione (caso transazionale: il
        chiamante sta già dentro una transazione aperta). Se None, ne apre
        e chiude una propria.

    Ritorna: lista di `n` stringhe id, es. ["T071", "T072", "T073"].

    NOTA (debito #22, forma residua): la generazione resta applicativa
    (max+1). La soluzione definitiva è una sequence lato DB — rimandata al
    ridisegno DB pilota (handoff §5.9). Questa utility elimina la
    triplicazione del pattern, non la sua natura applicativa.
    """
    if n <= 0:
        return []
    from sqlalchemy import func
    proprietaria = session is None
    if proprietaria:
        session = get_session()
    try:
        max_id = session.query(func.max(Task.id)).scalar()
        if max_id and max_id.startswith("T") and max_id[1:].isdigit():
            partenza = int(max_id[1:]) + 1
        else:
            partenza = 1
        return [f"T{partenza + i:03d}" for i in range(n)]
    finally:
        if proprietaria:
            session.close()


def _next_progetto_id():
    session = get_session()
    from sqlalchemy import func
    max_id = session.query(func.max(Progetto.id)).scalar()
    session.close()
    if max_id and max_id.startswith("P") and max_id[1:].isdigit():
        return f"P{int(max_id[1:]) + 1:03d}"
    return "P001"


def aggiungi_task(progetto_id, nome, fase, ore_stimate, data_inizio, data_fine,
                  stato="Da iniziare", profilo_richiesto="", dipendente_id="",
                  dipendenze=None):
    """Crea un task. Step 2.1 D1: il parametro `fase` (stringa) viene risolto
    a `fase_id` cercando la `Fase` del progetto col nome corrispondente.

    Step 3.1 (25/05/2026): il vecchio parametro `predecessore` (stringa singola)
    è sostituito da `dipendenze`: lista di dict
    `{task_predecessore_id, tipo_dipendenza}`. Le righe corrispondenti vengono
    create nella tabella `dipendenza_task` dopo l'INSERT del task.

    Parametri:
      dipendenze: lista (opzionale) di dict con chiavi:
        - task_predecessore_id (str, obbligatorio): id del task predecessore
        - tipo_dipendenza (str, opzionale, default 'FS'): uno di TIPI_DIPENDENZA

    Errori:
      ValueError se:
        - la stringa `fase` non matcha nessuna Fase del progetto;
        - `stato` è "In corso" e `dipendente_id` è vuoto (Step 4, 06/08/2026:
          un task non entra in lavorazione senza assegnatario);
        - una delle dipendenze punta a un task inesistente (FK orfana);
        - una delle dipendenze ha task_predecessore_id == new_id (self-loop);
        - tipo_dipendenza non è in TIPI_DIPENDENZA;
        - la lista `dipendenze` contiene predecessori duplicati.
      Il chiamante (router) deve catturarle e convertirle in HTTP 4xx.

    Timing degli id e sequenza transazionale:
      `new_id` è generato applicativamente (`_next_task_id()` → "T###"), quindi
      è noto PRIMA dell'add — non serve aspettare il DB. La sequenza è:
        1. genera new_id (applicativo);
        2. valida `dipendenze` (predecessori esistenti, no self-loop, no
           duplicati, tipo ammesso) — errori chiari, niente FK violation grezza;
        3. session.add(task);
        4. session.flush() ← rende il task visibile alle FK delle
           DipendenzaTask successive (anche se SQLAlchemy ordina gli INSERT
           correttamente, il flush rende la sequenza esplicita);
        5. per ogni d in dipendenze: session.add(DipendenzaTask(...));
        6. session.commit() → INSERT cumulativo, transazione singola.

      Il passo «eventuale assegnazione dipendente» che stava fra il 5 e il 6 è
      stato rimosso (Step 4, 06/08/2026): l'assegnatario è già su
      `Task.dipendente_id`, unica sorgente. Vedi il commento a fine funzione.
    """
    from models import Fase, DipendenzaTask, TIPI_DIPENDENZA  # import locale per evitare cicli

    new_id = _next_task_id()
    session = get_session()

    # Step 2.1 D1: risolvi fase stringa → fase_id (NOT NULL)
    fase_row = session.query(Fase).filter(
        Fase.progetto_id == progetto_id,
        Fase.nome == fase
    ).first()
    if not fase_row:
        session.close()
        raise ValueError(
            f"Fase '{fase}' non trovata nel progetto '{progetto_id}'. "
            f"Le fasi vanno create prima dei task."
        )

    # Step 4 sottotask (06/08/2026): un task NON entra in lavorazione senza
    # assegnatario. `stato` è client-settable (NuovoTask.stato, DTO dei router),
    # quindi un task può NASCERE "In corso" saltando del tutto `modifica_task`:
    # senza questo check la regola avrebbe una porta di servizio aperta.
    #
    # L'obbligo scatta SOLO su "In corso" e SOLO qui e nei due router del
    # Cantiere. Non sta in `modifica_task` di proposito: quella funzione è
    # chiamata anche dalla propagazione di `salva_consuntivo`, dove a scrivere
    # è il DIPENDENTE che dichiara «ci sto lavorando». Bloccare lì punirebbe
    # chi il lavoro lo sta facendo per una lacuna di pianificazione del PM.
    # L'obbligo è di chi AVVIA il task, non di chi lo consuntiva.
    #
    # `not dipendente_id` copre insieme None e "" — il default del parametro è
    # la stringa vuota e i router passano `nt.dipendente_id` grezzo (DTO
    # `NuovoTask.dipendente_id: str = ""`): un `is None` mancherebbe il caso
    # che si verifica davvero.
    if stato == "In corso" and not dipendente_id:
        session.close()
        raise ValueError(
            f"Il task '{nome}' non può nascere in stato 'In corso' senza "
            f"assegnatario: un task che entra in lavorazione deve avere un "
            f"responsabile. Assegna un dipendente, oppure crealo in "
            f"'Da iniziare' e avvialo dopo averlo assegnato."
        )

    # Step 3.1: valida le dipendenze a monte — errori applicativi chiari,
    # non FK/CHECK/UNIQUE violation grezze del DB.
    dipendenze = dipendenze or []
    if dipendenze:
        pred_ids = [d["task_predecessore_id"] for d in dipendenze]

        # Self-loop
        if new_id in pred_ids:
            session.close()
            raise ValueError(
                f"Dipendenza self-loop rifiutata: il task in creazione "
                f"({new_id}) non può essere predecessore di se stesso."
            )

        # Duplicati nella lista
        if len(set(pred_ids)) != len(pred_ids):
            session.close()
            raise ValueError(
                f"Predecessori duplicati nella lista dipendenze: "
                f"{[p for p in pred_ids if pred_ids.count(p) > 1]}. "
                f"Ogni (predecessore, successore) deve essere unico."
            )

        # Tipi dipendenza ammessi
        for d in dipendenze:
            tipo = d.get("tipo_dipendenza", "FS")
            if tipo not in TIPI_DIPENDENZA:
                session.close()
                raise ValueError(
                    f"Tipo dipendenza '{tipo}' non ammesso. "
                    f"Valori accettati: {TIPI_DIPENDENZA}."
                )

        # Predecessori esistenti (FK orfani) — una sola query
        esistenti = {r[0] for r in session.query(Task.id).filter(
            Task.id.in_(pred_ids)
        ).all()}
        orfani = [p for p in pred_ids if p not in esistenti]
        if orfani:
            session.close()
            raise ValueError(
                f"Predecessori inesistenti: {orfani}. "
                f"Creare i task predecessori prima, o rimuoverli dalla lista."
            )

    task = Task(
        id=new_id, progetto_id=progetto_id, nome=nome, fase_id=fase_row.id,
        ore_stimate=ore_stimate,
        data_inizio=data_inizio.date() if isinstance(data_inizio, datetime) else data_inizio,
        data_fine=data_fine.date() if isinstance(data_fine, datetime) else data_fine,
        stato=stato, profilo_richiesto=profilo_richiesto,
        dipendente_id=dipendente_id,
    )
    session.add(task)
    # Flush esplicito: il task diventa visibile alle FK delle DipendenzaTask
    # successive. Vedi docstring "Timing degli id e sequenza transazionale".
    session.flush()

    # Step 3.1: crea le righe DipendenzaTask (validate sopra)
    for d in dipendenze:
        session.add(DipendenzaTask(
            task_predecessore_id=d["task_predecessore_id"],
            task_successore_id=new_id,
            tipo_dipendenza=d.get("tipo_dipendenza", "FS"),
        ))

    # Step 4 sottotask (06/08/2026): qui si scriveva anche una riga
    # `Assegnazione` che duplicava `Task.dipendente_id`, appena impostato sopra.
    # Rimossa: l'assegnazione ha UNA sola sorgente, la colonna sul task. Il
    # mirror non veniva mantenuto da nessun'altra parte (`modifica_task`
    # aggiorna solo la colonna), quindi era destinato a divergere appena il PM
    # riassegnava un task dal Cantiere. La tabella resta in schema con le sue
    # righe storiche, ma nessuno la scrive né la legge più — vedi
    # `progetti_attivi_visibili`, che era il suo unico lettore.
    session.commit()
    session.close()
    return new_id


def sostituisci_dipendenze(task_id, dipendenze):
    """Step 3.1 (Gruppo B): SOSTITUISCE l'intera lista di dipendenze entranti
    di un task esistente (approccio "replace").

    Mentre `aggiungi_task` imposta le dipendenze SOLO alla creazione, questo
    helper le modifica su un task già esistente: cancella tutte le righe
    `dipendenza_task` con `task_successore_id == task_id` e ricrea quelle
    passate. È il backend dell'endpoint PUT /api/tasks/{task_id}/dipendenze.

    Args:
      task_id: id del task SUCCESSORE (quello le cui dipendenze si modificano).
      dipendenze: lista di dict con chiavi:
        - task_predecessore_id (str, obbligatorio): id del task predecessore;
        - tipo_dipendenza (str, opzionale, default 'FS'): uno di TIPI_DIPENDENZA.
        Lista vuota → rimuove tutte le dipendenze entranti del task.

    Validazione (stesse regole di `aggiungi_task`, errori applicativi chiari
    invece di FK/UNIQUE/CHECK grezzi del DB):
      - il task_id deve esistere;
      - ogni task_predecessore_id deve esistere (no FK orfana);
      - no self-loop (predecessore == task_id);
      - no predecessori duplicati nella lista. NB: il vincolo UNIQUE è su
        (task_predecessore_id, task_successore_id), quindi — avendo qui un
        unico successore — due righe sullo stesso predecessore con tipi diversi
        (es. SS+FF sulla stessa coppia) NON sono ammesse: vengono rifiutate qui
        come duplicati (debito noto Step 3.1);
      - tipo_dipendenza ∈ TIPI_DIPENDENZA (default 'FS' se assente).

    Raises:
      ValueError: per ognuna delle violazioni sopra (il router → HTTP 400).

    Returns:
      list[dict]: la lista aggiornata delle dipendenze entranti del task,
        nel formato {task_predecessore_id, tipo_dipendenza}.
    """
    from models import DipendenzaTask, TIPI_DIPENDENZA  # import locale per evitare cicli

    dipendenze = dipendenze or []
    session = get_session()

    # Il task successore deve esistere.
    if not session.query(Task.id).filter(Task.id == task_id).first():
        session.close()
        raise ValueError(f"Task '{task_id}' inesistente.")

    if dipendenze:
        pred_ids = [d["task_predecessore_id"] for d in dipendenze]

        # Self-loop
        if task_id in pred_ids:
            session.close()
            raise ValueError(
                f"Dipendenza self-loop rifiutata: il task "
                f"({task_id}) non può essere predecessore di se stesso."
            )

        # Duplicati nella lista (copre anche il vincolo UNIQUE sulla coppia:
        # stesso predecessore con tipi diversi = stessa coppia ordinata).
        if len(set(pred_ids)) != len(pred_ids):
            session.close()
            raise ValueError(
                f"Predecessori duplicati nella lista dipendenze: "
                f"{sorted({p for p in pred_ids if pred_ids.count(p) > 1})}. "
                f"Ogni (predecessore, successore) deve essere unico: non è "
                f"ammesso lo stesso predecessore con tipi diversi sulla stessa "
                f"coppia."
            )

        # Tipi dipendenza ammessi
        for d in dipendenze:
            tipo = d.get("tipo_dipendenza", "FS")
            if tipo not in TIPI_DIPENDENZA:
                session.close()
                raise ValueError(
                    f"Tipo dipendenza '{tipo}' non ammesso. "
                    f"Valori accettati: {TIPI_DIPENDENZA}."
                )

        # Predecessori esistenti (FK orfani) — una sola query
        esistenti = {r[0] for r in session.query(Task.id).filter(
            Task.id.in_(pred_ids)
        ).all()}
        orfani = [p for p in pred_ids if p not in esistenti]
        if orfani:
            session.close()
            raise ValueError(
                f"Predecessori inesistenti: {orfani}. "
                f"Creare i task predecessori prima, o rimuoverli dalla lista."
            )

    # Transazione: cancella le entranti correnti, ricrea dalla lista.
    try:
        session.query(DipendenzaTask).filter(
            DipendenzaTask.task_successore_id == task_id
        ).delete(synchronize_session=False)

        for d in dipendenze:
            session.add(DipendenzaTask(
                task_predecessore_id=d["task_predecessore_id"],
                task_successore_id=task_id,
                tipo_dipendenza=d.get("tipo_dipendenza", "FS"),
            ))
        session.commit()

        righe = session.query(DipendenzaTask).filter(
            DipendenzaTask.task_successore_id == task_id
        ).all()
        return [
            {"task_predecessore_id": r.task_predecessore_id,
             "tipo_dipendenza": r.tipo_dipendenza}
            for r in righe
        ]
    finally:
        session.close()


def modifica_task(task_id, **kwargs):
    session = get_session()
    task = session.query(Task).filter(Task.id == task_id).first()
    if not task:
        session.close()
        return False
    for campo, valore in kwargs.items():
        if hasattr(task, campo):
            if campo in ("data_inizio", "data_fine") and isinstance(valore, datetime):
                valore = valore.date()
            setattr(task, campo, valore)
    session.commit()
    session.close()
    return True


def cambia_stato_progetto(progetto_id, nuovo_stato):
    session = get_session()
    proj = session.query(Progetto).filter(Progetto.id == progetto_id).first()
    if not proj:
        session.close()
        return False
    proj.stato = nuovo_stato
    session.commit()
    session.close()
    return True


# ══════════════════════════════════════════════════════════════════════
# SEGNALAZIONI PERSISTENTI
# ══════════════════════════════════════════════════════════════════════

def get_segnalazioni():
    session = get_session()
    rows = session.query(Segnalazione).order_by(Segnalazione.created_at.desc()).all()
    result = []
    for r in rows:
        dip_nome = ""
        if r.dipendente_id:
            try:
                dip_nome = get_dipendente(r.dipendente_id)["nome"]
            except (IndexError, KeyError):
                pass
        result.append({
            "id": r.id, "tipo": r.tipo, "priorita": r.priorita,
            "dipendente_id": r.dipendente_id or "",
            "dipendente": dip_nome,
            "dettaglio": r.dettaglio,
            "timestamp": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        })
    session.close()
    return result


def aggiungi_segnalazione(tipo, priorita, dipendente_id, dettaglio):
    session = get_session()
    # Leggi MAX id dal database
    from sqlalchemy import func
    max_id = session.query(func.max(Segnalazione.id)).scalar()
    if max_id and max_id.startswith("S") and max_id[1:].isdigit():
        next_num = int(max_id[1:]) + 1
    else:
        next_num = 1
    new_id = f"S{next_num:03d}"
    session.add(Segnalazione(
        id=new_id, tipo=tipo, priorita=priorita,
        dipendente_id=dipendente_id, dettaglio=dettaglio,
        fonte="chatbot", stato="aperta",
    ))
    session.commit()
    session.close()
    return new_id


# ══════════════════════════════════════════════════════════════════════
# CONSUNTIVI — SALVATAGGIO
# ══════════════════════════════════════════════════════════════════════

def _nota_task(testo):
    """Normalizza la nota «a che punto sono»: stringa vuota o soli spazi → None.

    In DB la nota assente è NULL, non "": così `nota IS NOT NULL` significa
    davvero «il dipendente ha scritto qualcosa» e non serve ricordarsi di
    testare anche la stringa vuota ogni volta che la si legge.
    """
    testo = (testo or "").strip()
    return testo or None


def _stato_da_avanzamento(percentuale, bloccato):
    """Lo stato dichiarato di un sottotask: derivato dallo slider, tranne il blocco.

    Step 4 (06/08/2026). Sul SOTTOTASK lo stato non è un input separato dallo
    slider, come invece è sul task: chiedere due volte la stessa cosa — «a che
    punto sei» e «che stato ha» — è il modo sicuro di raccogliere due risposte
    che si contraddicono. Due dei tre stati dichiarabili sono già scritti nella
    percentuale, e si leggono da lì.

    BLOCCATO È L'ECCEZIONE, e per forza: non è derivabile. Un pezzo può essere
    fermo al 40% in attesa di un fornitore, e il 40% da solo è indistinguibile
    da «avanza piano». È l'unica informazione che lo slider non contiene, ed è
    per questo l'unica che si chiede a parte.

    100  → "Completato"
    1-99 → "In corso"
    0    → None
    Lo ZERO NON è "In corso", ed è la scelta meno ovvia delle tre. I tre stati
    dichiarabili fanno ciascuno un'affermazione positiva — sto lavorando, ho
    finito, sono fermo — e lo 0% le nega tutte: niente è stato fatto, e se il
    motivo fosse un impedimento esisterebbe il flag Bloccato per dirlo. Scrivere
    "In corso" su una riga che deriva 0 ore e 0 avanzamento significherebbe
    affermare un'attività che il dato stesso smentisce, e renderebbe quella riga
    indistinguibile da un pezzo fermo che nessuno ha segnalato. `None` ha già in
    questo modello il significato esatto che serve — «non si è espresso sullo
    stato», vedi il commento su ConsuntivoSottotask.stato_dichiarato — ed è
    un'assenza onesta invece di un'affermazione gonfiata.

    `percentuale is None` senza blocco → None: non c'è niente da cui derivare.
    Sta al chiamante decidere se scrivere quel None o non toccare la colonna;
    qui si mappa e basta.
    """
    if bloccato:
        return "Bloccato"
    if percentuale is None:
        return None
    if percentuale >= 100:
        return "Completato"
    if percentuale > 0:
        return "In corso"
    return None


def salva_consuntivo(dipendente_id, settimana, ore_per_task, stati_per_task,
                     giorni_sede=None, giorni_remoto=None,
                     ore_assenza=None, tipo_assenza=None, nota_assenza=None,
                     spese_lista=None, note_per_task=None,
                     avanzamenti_sottotask=None, ore_effettive_sottotask=None,
                     bloccati_sottotask=None, note_sottotask=None,
                     percentuale_per_task=None, ore_effettive_per_task=None,
                     viste_task=None, viste_sottotask=None,
                     ore_stimate_residue_per_task=None,
                     ore_stimate_residue_sottotask=None):
    """
    Salva il consuntivo settimanale completo di un dipendente.

    I task da scrivere sono l'UNIONE delle chiavi di ore_per_task,
    stati_per_task e note_per_task: un task entra nel salvataggio se ha almeno
    uno dei tre, non solo se ha le ore.

    ore_per_task: dict {task_id: ore}. Chiave assente = ore non dichiarate,
                 che NON è 0: sulla riga esistente `ore_dichiarate` resta com'è
                 (dichiarare uno stato non azzera le ore già inserite), sulla
                 riga nuova si parte da 0.
    stati_per_task: dict {task_id: stato} — SOLO stati dichiarabili
                 (models.STATI_DICHIARABILI). La validazione sta a monte, nel
                 DTO della route: qui si assume già filtrato.
    note_per_task: dict {task_id: «a che punto sono»} → Consuntivo.nota.
                 None = non pervenuto, non toccare le note esistenti (stessa
                 convenzione di spese_lista). Chiave presente con stringa
                 vuota = cancella la nota; chiave assente = lascia com'è.
    spese_lista: None = non pervenuto, non toccare le spese esistenti.
                 [] o lista = stato COMPLETO della settimana, sostituisce.
    giorni_sede, giorni_remoto, ore_assenza, tipo_assenza, nota_assenza:
                 None = non pervenuto. Se lo sono TUTTI, PresenzaSettimanale
                 non viene nemmeno interrogata; se lo sono solo alcuni, la riga
                 esistente è aggiornata SUI SOLI campi pervenuti (caso misto:
                 `ore_assenza` senza i giorni non deve riportare i giorni a
                 zero).

    LO STATO È IL CAMPO PRIMARIO. Le ore sono secondarie: un task può arrivare
    con 0 ore e stato "Completato" ed è una compilazione valida. Per questo lo
    stato dichiarato NON si ferma sul Consuntivo — arriva su Task.stato, che è
    ciò che il PM legge nel Cantiere e ciò che decide se il task ricompare in
    /me la settimana dopo. Senza propagazione, marcare Completato non aveva
    alcun effetto osservabile.

    La propagazione passa da `modifica_task` — la stessa funzione che usa il
    Cantiere — e non da una `setattr` diretta: un solo punto di scrittura su
    Task.stato, così quando ci si appenderà logica (audit, cascata,
    notifiche) varrà per entrambe le porte d'ingresso.

    La `settimana` viene normalizzata al lunedì con `_lunedi` — stessa regola
    della lettura, e qui è la riga che ripara il bug dei duplicati. Prima
    arrivava `datetime.now()` dalla route, cioè il giorno della compilazione:
    la UNIQUE (task_id, dipendente_id, settimana) non riconosceva il doppione,
    e ricompilare martedì dopo aver compilato lunedì inseriva una riga NUOVA
    invece di aggiornare quella esistente. In lettura le due righe cadono
    entrambe nel range lun..dom e si sommano: 6h corrette in 8h diventavano
    14h. Stesso meccanismo su PresenzaSettimanale (UNIQUE dip+settimana).

    PRESA IN VISIONE — `viste_task` e `viste_sottotask` (nodo F-2, 02/09/2026)
    -------------------------------------------------------------------------
    Due insiemi di id: le unità su cui il dipendente ha confermato «l'ho
    guardata, è ancora ferma». Scrivono `presa_visione=True` sulla riga della
    settimana, creandola se non c'è — la presa-visione può benissimo essere
    l'UNICA cosa che quella persona fa su quell'unità quella settimana, ed è
    proprio il caso che questo nodo esiste per rendere registrabile.

    COSA NON TOCCANO, e non per omissione: `percentuale` e `stato_dichiarato`.
    Una presa-visione non è un avanzamento e non è uno sblocco. Un pezzo
    Bloccato preso in visione resta Bloccato — se toccasse lo stato, confermare
    «è ancora fermo» avrebbe l'effetto di dire «non è più fermo», che è il
    contrario. È la ragione per cui questo è un canale a sé e non il riuso di
    `avanzamenti_sottotask`: là dentro l'id fa riderivare lo stato.

    PORTANO SOLO ID. Una nota nuova viaggia in `note_per_task`/`note_sottotask`
    come qualunque nota scritta a mano, e si salva normalmente. La
    `nota_ereditata` che `/me` espone non ha modo di tornare indietro da qui: il
    canale non ha un campo dove metterla, e questo impedisce per costruzione che
    il dipendente si ritrovi a firmare le parole scritte da un collega in una
    settimana precedente.

    `compilato=True` e `data_compilazione` si valorizzano come per ogni altra
    scrittura: l'utente HA toccato la riga. Ma restano due fatti distinti —
    `compilato` dice «salvata», `presa_visione` dice «confermata ferma» — e la
    migration e7f8a9b0c1d2 spiega perché non potevano essere la stessa colonna.
    """
    from models import PresenzaSettimanale, Spesa, Sottotask, ConsuntivoSottotask

    session = get_session()
    try:
        settimana_date = _lunedi(settimana)
        avanzamenti_sottotask = avanzamenti_sottotask or {}
        ore_effettive_sottotask = ore_effettive_sottotask or {}
        bloccati_sottotask = set(bloccati_sottotask or ())
        percentuale_per_task = percentuale_per_task or {}
        ore_effettive_per_task = ore_effettive_per_task or {}
        # STIMA RESIDUA (04/09/2026) — «quante ore mancano», per unità.
        # INERTE: non entra in `_aggrega_ore_unita`, non tocca `ore_dichiarate`
        # né `Task.stato`. Si scrive sulla riga della settimana e si rilegge da
        # `/me`, e basta — a differenza di `ore_effettive`, che le somiglia per
        # forma ma è dentro il motore delle ore.
        ore_stimate_residue_per_task = ore_stimate_residue_per_task or {}
        ore_stimate_residue_sottotask = ore_stimate_residue_sottotask or {}
        # Nodo F-2. `set` e non dict: portano solo appartenenza, nessun valore.
        viste_task = set(viste_task or ())
        viste_sottotask = set(viste_sottotask or ())
        # `note_sottotask` NON si normalizza a {}: None e {} vogliono dire cose
        # diverse (non gestisco le note / le gestisco e questa volta nessuna),
        # esattamente come `note_per_task`.
        # Un salvataggio «tocca i sottotask» se porta almeno uno dei quattro campi.
        # Calcolato una volta sola: quando qualcuno ne aggiungerà un quinto, i rami
        # non divergeranno.
        tocca_sottotask = bool(
            avanzamenti_sottotask or ore_effettive_sottotask
            or bloccati_sottotask or note_sottotask
            # Nodo F-2: una presa-visione È un salvataggio sui pezzi. Senza
            # questo termine il blocco sotto non girerebbe e la conferma
            # «ancora ferma» non verrebbe scritta da nessuna parte.
            or viste_sottotask
        )
        avvisi = []          # segnalazioni non bloccanti, tornano al chiamante

        # 0) AVANZAMENTO SUI SOTTOTASK — si scrive PRIMA del ciclo sui task.
        # L'ordine non è di comodo: le ore del task sono DERIVATE da queste righe,
        # e il calcolo del Δ (`ore_derivate_sottotask`) deve poterle già leggere.
        # Tutto nella stessa sessione e nello stesso commit del ciclo: se le
        # dichiarazioni finissero in una transazione separata, un errore a metà
        # lascerebbe scritto l'avanzamento e non le ore che ne discendono.
        #
        # Upsert manuale sulla UNIQUE (sottotask, dipendente, settimana), identico
        # nella forma a quello su Consuntivo poco sotto: ricompilare la stessa
        # settimana AGGIORNA la riga, non ne aggiunge una seconda. È lo stesso bug
        # dei duplicati descritto in fondo a questa docstring, e la UNIQUE lo
        # intercetta solo perché la settimana è già normalizzata al lunedì.
        #
        # `stato_dichiarato` e `nota` della riga-sottotask restano NULL: oggi il
        # form manda solo l'avanzamento. Le colonne esistono (migration
        # f2a3b4c5d6e7) e verranno riempite quando il form le porterà.
        # Si itera sull'UNIONE dei due dizionari, non su uno dei due: avanzamento e
        # ore effettive sono campi INDIPENDENTI della stessa riga e possono arrivare
        # insieme, separatamente, o in salvataggi diversi. Un pezzo fermo porta solo
        # le ore (la percentuale non si muove), un pezzo che avanza nei tempi porta
        # solo l'avanzamento.
        # Ciascun campo si scrive SOLO se pervenuto — la convenzione «chiave assente
        # = non toccare» già usata per `note_per_task` e per le presenze. Senza,
        # dichiarare l'avanzamento la settimana dopo azzererebbe le ore effettive
        # scritte prima, e viceversa: due campi che si cancellano a vicenda a ogni
        # salvataggio parziale.
        sottotask_toccati = dict.fromkeys(
            list(avanzamenti_sottotask) + list(ore_effettive_sottotask)
            + sorted(bloccati_sottotask) + list(note_sottotask or {})
            # Nodo F-2: un pezzo preso in visione entra nel giro anche se non
            # porta null'altro — la sua riga va creata o aggiornata comunque.
            + sorted(viste_sottotask)
            # STIMA RESIDUA: stessa ragione di tutti gli altri termini di
            # quest'unione. «Non ho avanzato, ma ora so che ne mancano 20» è
            # una compilazione legittima e frequente — anzi, è proprio il caso
            # per cui il campo esiste. Senza questo termine il pezzo non
            # entrerebbe nel ciclo e il numero sparirebbe senza errore.
            + list(ore_stimate_residue_sottotask)
        )
        for sottotask_id in sottotask_toccati:
            riga = session.query(ConsuntivoSottotask).filter(
                ConsuntivoSottotask.sottotask_id == sottotask_id,
                ConsuntivoSottotask.dipendente_id == dipendente_id,
                ConsuntivoSottotask.settimana == settimana_date,
            ).first()
            if riga is None:
                riga = ConsuntivoSottotask(
                    sottotask_id=sottotask_id,
                    dipendente_id=dipendente_id,
                    settimana=settimana_date,
                )
                session.add(riga)

            if sottotask_id in avanzamenti_sottotask:
                riga.percentuale = avanzamenti_sottotask[sottotask_id]
            if sottotask_id in ore_effettive_sottotask:
                riga.ore_effettive = ore_effettive_sottotask[sottotask_id]
            # Stessa convenzione «chiave assente = non toccare»: dichiarare
            # l'avanzamento la settimana dopo non deve azzerare una stima
            # residua scritta prima.
            if sottotask_id in ore_stimate_residue_sottotask:
                riga.ore_stimate_residue = ore_stimate_residue_sottotask[sottotask_id]

            # Nota: stesso trattamento delle note-task, `_nota_task` compreso —
            # vuota o soli spazi diventa NULL, così `nota IS NOT NULL` significa
            # davvero «ha scritto qualcosa» anche qui. La chiave assente NON tocca
            # la nota esistente: il form manda solo quelle modificate, e riscrivere
            # NULL a ogni salvataggio cancellerebbe il diario del pezzo.
            if note_sottotask is not None and sottotask_id in note_sottotask:
                riga.nota = _nota_task(note_sottotask[sottotask_id])

            # Stato dichiarato: si RICALCOLA ogni volta che arriva uno dei suoi due
            # input (la percentuale o il flag di blocco), invece di essere scritto
            # una volta e lasciato lì. È un campo derivato, e un derivato che non
            # segue la sua sorgente è solo una vecchia risposta: correggere il 100%
            # in 60% e ritrovarsi la riga ancora "Completato" sarebbe una
            # contraddizione scritta in tabella.
            # Se non arriva nessuno dei due, la colonna non si tocca — un
            # salvataggio di sole ore effettive non cancella lo stato dichiarato
            # prima (stessa convenzione delle note e delle presenze).
            if sottotask_id in avanzamenti_sottotask or sottotask_id in bloccati_sottotask:
                riga.stato_dichiarato = _stato_da_avanzamento(
                    riga.percentuale, sottotask_id in bloccati_sottotask
                )

            # Nodo F-2: la presa-visione si scrive DOPO il ricalcolo dello stato
            # e non lo tocca — è il punto in cui l'asimmetria col canale degli
            # avanzamenti diventa codice. `viste_sottotask` non compare
            # nell'`if` qui sopra: un pezzo Bloccato confermato «ancora fermo»
            # NON viene riderivato, quindi resta Bloccato. Se la presa-visione
            # passasse per `avanzamenti_sottotask`, ricadrebbe in quel ramo e
            # `_stato_da_avanzamento` lo sbloccherebbe in silenzio — confermare
            # «è ancora fermo» avrebbe l'effetto di dire «non è più fermo».
            # Si SCRIVE e non si alterna: `= True` solo quando l'id è arrivato,
            # perché un salvataggio che non parla di questo pezzo non deve
            # cancellare una conferma data prima nella stessa settimana.
            if sottotask_id in viste_sottotask:
                riga.presa_visione = True

            riga.compilato = True
            riga.data_compilazione = datetime.utcnow()

        # Flush e non commit: le righe diventano visibili alle query successive
        # DENTRO questa transazione — che è ciò che serve alla derivazione — senza
        # rendere definitivo niente finché il salvataggio non è completo.
        derivate_per_task = {}
        if tocca_sottotask:
            session.flush()

            # 0-bis) DERIVAZIONE E AGGREGAZIONE SUL TASK.
            #
            # SI RIPARTE DAL DATABASE, NON DAL PAYLOAD. Le ore del task si
            # ricalcolano sommando TUTTE le dichiarazioni di questo dipendente su
            # quel task in quella settimana, comprese quelle di salvataggi
            # precedenti che il body corrente non ripete. È obbligatorio, non
            # prudenziale: l'upsert sotto ASSEGNA (`existing.ore_dichiarate = ore`)
            # invece di sommare, quindi aggregare i soli sottotask del payload
            # cancellerebbe le ore derivate dagli altri. Compilo A (5h), poi
            # ri-apro la settimana e tocco solo B (3h): senza questo, il task
            # passerebbe da 5 a 3 invece che a 8.
            task_dei_sottotask = {
                r.task_id
                for r in session.query(Sottotask.task_id)
                .filter(Sottotask.id.in_(list(sottotask_toccati))).all()
            }
            dichiarazioni = (
                session.query(
                    ConsuntivoSottotask.sottotask_id,
                    ConsuntivoSottotask.percentuale,
                    ConsuntivoSottotask.ore_effettive,
                )
                .join(Sottotask, Sottotask.id == ConsuntivoSottotask.sottotask_id)
                .filter(
                    Sottotask.task_id.in_(task_dei_sottotask),
                    ConsuntivoSottotask.dipendente_id == dipendente_id,
                    ConsuntivoSottotask.settimana == settimana_date,
                )
                .all()
            )

            derivate_per_task, non_derivabili = _aggrega_ore_unita(
                session, "sottotask", dichiarazioni, settimana_date
            )

            if non_derivabili:
                nomi = dict(
                    session.query(Sottotask.id, Sottotask.nome)
                    .filter(Sottotask.id.in_(non_derivabili)).all()
                )
                for sottotask_id in sorted(non_derivabili):
                    avvisi.append(
                        f"Sottotask '{nomi.get(sottotask_id, sottotask_id)}': "
                        f"avanzamento registrato ma ore non derivate, manca "
                        f"`ore_stimate`. Chiedi al PM di stimare il pezzo dal "
                        f"Cantiere; le ore si ricalcoleranno alla prossima "
                        f"dichiarazione."
                    )

            # 0-ter) RICALCOLO DELLA SETTIMANA A VALLE.
            #
            # Scrivere un avanzamento a W cambia la BASELINE di chi viene dopo, e
            # le ore già derivate a valle diventano sbagliate. Il caso reale è il
            # recupero: `settimane_selezionabili` riapre la settimana precedente se
            # incompleta, quindi si compila W, poi si torna su W−1.
            #   W dichiarato 60% con baseline 0   → 60% delle ore, scritto.
            #   poi W−1 dichiarato 40%            → 40% delle ore.
            #   ma ora il Δ giusto di W è 60−40 = 20%, non 60%.
            # Senza questo blocco resterebbero in DB 60%+40% = 100% delle ore per
            # un pezzo dichiarato al 60%. Non è un arrotondamento: è il 67% in più.
            #
            # SI RICALCOLA UNA SOLA SETTIMANA, non una cascata — ed è la MONOTONIA
            # imposta in `routes/consuntivi._valida_avanzamenti_sottotask` a
            # garantirlo. Inserire una dichiarazione a W invalida la baseline della
            # PRIMA settimana dichiarata dopo W, e basta: le successive hanno per
            # baseline quella, il cui VALORE non è cambiato (è cambiato solo il suo
            # Δ). Niente propagazione, niente ricorsione.
            #
            # Il ricalcolo usa `ore_stimate` CORRENTE, non quella di allora: il
            # motore è agnostico al passato, e la fotografia storica è compito del
            # SAL (`_serializza_stato_progetto`), che è autocontenuto apposta.
            successive = (
                session.query(
                    ConsuntivoSottotask.sottotask_id,
                    ConsuntivoSottotask.settimana,
                    Sottotask.task_id,
                )
                .join(Sottotask, Sottotask.id == ConsuntivoSottotask.sottotask_id)
                .filter(
                    ConsuntivoSottotask.sottotask_id.in_(list(avanzamenti_sottotask)),
                    ConsuntivoSottotask.settimana > settimana_date,
                    ConsuntivoSottotask.percentuale.isnot(None),
                )
                .all()
            )
            # La PRIMA settimana dichiarata dopo W, per sottotask → l'insieme delle
            # coppie (task, settimana) da rifare. Due sottotask dello stesso task
            # con la stessa settimana a valle collassano in una coppia sola.
            prima_dopo = {}
            for sid, sett_dopo, tid in successive:
                if sid not in prima_dopo or sett_dopo < prima_dopo[sid][0]:
                    prima_dopo[sid] = (sett_dopo, tid)
            da_rifare = {(tid, sett_dopo) for sett_dopo, tid in prima_dopo.values()}

            for tid, sett_dopo in sorted(da_rifare):
                # TUTTE le dichiarazioni su quel task in quella settimana, non solo
                # quelle dei sottotask toccati oggi: la riga Consuntivo che stiamo
                # per riscrivere le aggrega tutte, e ricalcolarne una parte
                # cancellerebbe il resto (stessa ragione della rilettura dal DB
                # nel blocco 0-bis).
                righe_dopo = (
                    session.query(
                        ConsuntivoSottotask.sottotask_id,
                        ConsuntivoSottotask.dipendente_id,
                        ConsuntivoSottotask.percentuale,
                        ConsuntivoSottotask.ore_effettive,
                    )
                    .join(Sottotask, Sottotask.id == ConsuntivoSottotask.sottotask_id)
                    .filter(
                        Sottotask.task_id == tid,
                        ConsuntivoSottotask.settimana == sett_dopo,
                    )
                    .all()
                )
                # Raggruppate per DIPENDENTE: la grana di Consuntivo è (task,
                # dipendente, settimana), e chi ha dichiarato a valle può non essere
                # chi sta salvando adesso — un sottotask può avere un assegnatario
                # proprio in override (Sottotask.dipendente_id). Si riscrive la riga
                # di ciascuno, non quella di chi ha in mano il form.
                per_dipendente = {}
                for sid, did, pct, ore_eff in righe_dopo:
                    per_dipendente.setdefault(did, []).append((sid, pct, ore_eff))

                for did, righe_dip in per_dipendente.items():
                    # Stesso helper dell'aggregazione sopra, quindi stessa regola:
                    # dove ci sono ore effettive, il ricalcolo NON le tocca. Sono un
                    # dato esplicito e non una derivata, e una baseline cambiata a
                    # monte non ha voce in capitolo su quante ore è costato davvero
                    # quel pezzo. È la differenza fra correggere un calcolo e
                    # riscrivere una dichiarazione.
                    per_task_dopo, _ = _aggrega_ore_unita(session, "sottotask", righe_dip, sett_dopo)
                    totale = per_task_dopo.get(tid, 0.0)

                    riga_cons = session.query(Consuntivo).filter(
                        Consuntivo.task_id == tid,
                        Consuntivo.dipendente_id == did,
                        Consuntivo.settimana == sett_dopo,
                    ).first()
                    if riga_cons:
                        riga_cons.ore_dichiarate = totale
                    else:
                        # Non dovrebbe capitare — se ci sono dichiarazioni a valle
                        # la riga esiste — ma se manca la si crea invece di perdere
                        # le ore. `compilato=True` perché una dichiarazione sui
                        # sottotask È una compilazione.
                        session.add(Consuntivo(
                            task_id=tid,
                            dipendente_id=did,
                            settimana=sett_dopo,
                            ore_dichiarate=totale,
                            compilato=True,
                            data_compilazione=datetime.utcnow(),
                        ))

        # ── 0-quater) IL TASK COME UNITÀ DI LAVORO ──────────────────────────
        # Stessa derivazione dei pezzi, su un'entità diversa: `tipo="task"` fa
        # leggere la percentuale da `Consuntivo.percentuale` e la stima da
        # `Task.ore_pianificate`. Non c'è aggregazione da fare — le ore che ne
        # escono sono già del task — e infatti `_aggrega_ore_unita` non ha un ramo
        # per questo: la somma di un elemento solo È il passaggio diretto.
        #
        # MUTUA ESCLUSIONE: si deriva SOLO per i task che `tipo_unita_per_task`
        # classifica come unità. Su un task scomposto la percentuale-task viene
        # ignorata e nemmeno scritta: lasciarla sulla riga creerebbe una seconda
        # verità sulle ore dello stesso task, che è il conflitto già risolto una
        # volta fra derivate e manuali. Chi l'ha mandata lo scopre dagli `avvisi`,
        # non in silenzio.
        task_unita = set()
        if percentuale_per_task or ore_effettive_per_task:
            candidati = list(dict.fromkeys(
                list(percentuale_per_task) + list(ore_effettive_per_task)
            ))
            tipi = tipo_unita_per_task(session, candidati)
            task_unita = {t for t in candidati if tipi.get(t) == "task"}

            scartati = [t for t in candidati if tipi.get(t) == "sottotask"]
            for task_id in sorted(scartati):
                avvisi.append(
                    f"Task '{task_id}': è scomposto in sottotask, quindi le sue ore "
                    f"vengono dai pezzi. L'avanzamento dichiarato sul task è stato "
                    f"ignorato — dichiaralo sui singoli sottotask."
                )

            if task_unita:
                righe_task = [
                    (task_id,
                     percentuale_per_task.get(task_id),
                     ore_effettive_per_task.get(task_id))
                    for task_id in sorted(task_unita)
                ]
                derivate_task, non_derivabili_task = _aggrega_ore_unita(
                    session, "task", righe_task, settimana_date
                )
                derivate_per_task.update(derivate_task)

                for task_id in sorted(non_derivabili_task):
                    avvisi.append(
                        f"Task '{task_id}': avanzamento registrato ma ore non "
                        f"derivate, manca `ore_pianificate`. Chiedi al PM di "
                        f"pianificare il task dal Cantiere; le ore si "
                        f"ricalcoleranno alla prossima dichiarazione."
                    )

        # Le DERIVATE VINCONO sulle ore dichiarate a mano per lo stesso task: se un
        # task è stato scomposto, la verità sulle sue ore è la somma dei pezzi.
        # Dizionario NUOVO e non mutazione: `ore_per_task` appartiene al chiamante,
        # e la route lo rilegge dal DTO.
        ore_per_task = {**ore_per_task, **derivate_per_task}

        # 1) Salva/aggiorna ore, stato e nota per ogni task.
        # Si itera sull'UNIONE delle chiavi dei tre dizionari, non su ore_per_task:
        # le ore non sono più il campo che decide se un task è stato compilato. Il
        # campo primario è lo stato — «a che punto sono», non «quanto ho lavorato»
        # — e le ore sono facoltative. Ciclando su ore_per_task, una compilazione
        # di soli stati (caso ormai normale) non entrava mai nel ciclo: la funzione
        # tornava True senza aver scritto una riga. Residuo di quando le ore erano
        # obbligatorie.
        # dict.fromkeys e non set(): preserva l'ordine di arrivo, così le scritture
        # restano deterministiche e i test riproducibili.
        task_toccati = dict.fromkeys(
            list(ore_per_task) + list(stati_per_task) + list(note_per_task or {})
            + sorted(task_unita)
            # Nodo F-2: un task preso in visione entra anche se non porta altro.
            + sorted(viste_task)
            # ── STIMA RESIDUA — ed è QUI, non fra i `candidati` sopra ──────
            # Il caso «non ho avanzato, ma ora so che ne mancano 20» è quello
            # per cui il campo esiste, e senza questo termine non entrerebbe
            # nel ciclo: nessuna riga scritta, nessun errore, numero perso.
            #
            # ⚠ MA NON VA IN `candidati`/`task_unita`, e la differenza non è
            # stilistica. Quell'insieme decide chi passa da `_aggrega_ore_unita`,
            # cioè di chi si RICALCOLANO le ore. Un task che porta solo il
            # residuo non ha né percentuale né ore effettive: `ore_derivate_unita`
            # con `pct=None` restituisce `ore: 0.0` (non `None`), quel 3.0 → 0.0
            # finirebbe in `derivate_per_task`, che poi VINCE su `ore_per_task`
            # — e le ore già dichiarate nella settimana verrebbero azzerate da
            # una dichiarazione che sulle ore non diceva nulla.
            #
            # Le due unioni rispondono a due domande diverse: `task_toccati` =
            # «di chi scrivo la riga», `task_unita` = «di chi ricalcolo le ore».
            # Il residuo è inerte, quindi appartiene solo alla prima.
            + list(ore_stimate_residue_per_task)
        )
        stati_dichiarati = {}   # task_id → stato, da propagare dopo il commit
        for task_id in task_toccati:
            # `ore is None` = ore non dichiarate: diverso da 0 («non ci ho
            # lavorato»). Sulla riga esistente le ore non si toccano, sulla nuova
            # si parte da 0.
            ore = ore_per_task.get(task_id)
            stato = stati_per_task.get(task_id)
            # La nota conta come pervenuta anche se è la stringa vuota: cancellare
            # una nota è un ATTO del dipendente, non un non-evento, e va scritto.
            nota_pervenuta = note_per_task is not None and task_id in note_per_task
            # Salta solo i task che non portano NIENTE: né stato, né nota, né ore.
            # `not ore` copre insieme None (ore non dichiarate) e 0 («non ci ho
            # lavorato»): l'intenzione non dipende più dal fatto accidentale che
            # `None == 0` sia False, che è ciò che teneva in piedi il caso
            # «solo nota» — un `or 0` aggiunto a monte lo avrebbe rotto in
            # silenzio, facendo sparire le note senza errori.
            # La guardia serve ancora: il form manda a 0 anche i task su cui non
            # si è lavorato, e senza di essa ogni salvataggio creerebbe una riga
            # vuota per ciascuno.
            #
            # `task_id not in derivate_per_task` è il quarto termine (Step 4): un
            # task le cui uniche dichiarazioni stanno sui SOTTOTASK deve entrare
            # comunque. Le sue ore derivate valgono legittimamente 0.0 — Δ=0 vuol
            # dire «questa settimana il pezzo non è avanzato», che è una
            # dichiarazione, non un silenzio — e senza questo termine `not ore`
            # sarebbe vero e la riga Consuntivo non verrebbe mai scritta. La
            # settimana risulterebbe non compilata su quel task pur avendo il
            # dipendente mosso (o volutamente non mosso) lo slider.
            #
            # `task_id not in viste_task` è il quinto termine (nodo F-2): una
            # presa-visione è una dichiarazione, non un silenzio, ed è spesso
            # l'UNICA cosa che quel salvataggio dice su quel task. Senza questo
            # termine la riga non verrebbe mai scritta e la conferma «ancora
            # ferma» sparirebbe — proprio il caso che il nodo esiste per
            # registrare.
            # `ore_stimate_residue_per_task` è il SESTO termine, e la sua
            # assenza è stata un bug vero per qualche minuto: il campo era già
            # in `task_toccati`, la scrittura già pronta, e la riga non veniva
            # comunque creata. Perché i cancelli sono DUE e fanno cose diverse
            # — `task_toccati` decide chi si CONSIDERA, questo `continue` chi si
            # SCRIVE — e una compilazione di solo residuo supera il primo e
            # cadeva sul secondo, senza errore né avviso. Esattamente il modo in
            # cui un dato sparisce in silenzio.
            if (not stato and not nota_pervenuta and not ore
                    and task_id not in derivate_per_task
                    and task_id not in task_unita
                    and task_id not in viste_task
                    and task_id not in ore_stimate_residue_per_task):
                continue

            # motivo_fermo è un flag, non un archivio: va RIALLINEATO a ogni
            # salvataggio, non solo popolato. Prima il ramo `else` non esisteva e
            # un task sbloccato la settimana dopo restava marcato «bloccato» per
            # sempre. Il perché del blocco lo scrive il dipendente in `nota`.
            existing = session.query(Consuntivo).filter(
                Consuntivo.task_id == task_id,
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana == settimana_date,
            ).first()

            # Step 4 (07/08/2026): su un task-UNITÀ che porta un avanzamento, lo
            # stato non si prende da `stati_per_task` — si DERIVA dal cursore, come
            # sul sottotask. Di `stati_per_task` resta significativo il solo
            # «Bloccato», l'unica cosa che una percentuale non può dire.
            # Fuori da questo caso `stato` resta esattamente quello di prima: un
            # task senza percentuale (o scomposto) continua a dichiarare lo stato a
            # mano, e il comportamento storico non si muove di una virgola.
            if task_id in task_unita:
                bloccato = (stato == "Bloccato")
                if task_id in percentuale_per_task or bloccato:
                    pct_finale = percentuale_per_task.get(
                        task_id, existing.percentuale if existing else None
                    )
                    stato = _stato_da_avanzamento(pct_finale, bloccato)

            # motivo_fermo è un flag, non un archivio: va RIALLINEATO a ogni
            # salvataggio. Si calcola DOPO l'eventuale derivazione, altrimenti un
            # blocco derivato non lo accenderebbe.
            motivo = "Segnalato come bloccato dal dipendente" if stato == "Bloccato" else None

            if existing:
                if ore is not None:
                    existing.ore_dichiarate = ore
                # I due campi dell'unità di lavoro, con la convenzione «chiave
                # assente = non toccare» degli altri: dichiarare le ore effettive
                # non deve cancellare la percentuale scritta prima, né viceversa.
                if task_id in percentuale_per_task:
                    existing.percentuale = percentuale_per_task[task_id]
                if task_id in ore_effettive_per_task:
                    existing.ore_effettive = ore_effettive_per_task[task_id]
                # Stima residua, stessa convenzione: chiave assente = non
                # toccare. Una settimana in cui si dichiara solo l'avanzamento
                # non deve cancellare il «ne mancano 20» scritto prima.
                if task_id in ore_stimate_residue_per_task:
                    existing.ore_stimate_residue = ore_stimate_residue_per_task[task_id]
                existing.compilato = True
                existing.data_compilazione = datetime.utcnow()
                existing.motivo_fermo = motivo
                # Nodo F-2. `= True` solo quando l'id è arrivato, mai `= False`
                # altrimenti: un salvataggio che non parla di questo task non
                # deve cancellare una conferma data prima nella stessa
                # settimana. È l'opposto di `motivo_fermo`, che sopra si
                # RIALLINEA a ogni giro perché è un flag derivato dallo stato —
                # questa invece è una dichiarazione, e le dichiarazioni non si
                # ritirano da sole.
                # Non tocca `percentuale` né `stato_dichiarato`: una
                # presa-visione non è un avanzamento e non è uno sblocco.
                if task_id in viste_task:
                    existing.presa_visione = True
                # Lo stato dichiarato resta anche sulla riga della settimana, non
                # solo su Task.stato: quest'ultimo è a sovrascrittura e non dice né
                # chi né quando. `stato` assente = non pervenuto, la colonna non si
                # tocca (stessa convenzione di note e presenze): un salvataggio di
                # sole ore non cancella la dichiarazione fatta prima.
                if stato:
                    existing.stato_dichiarato = stato
                if note_per_task is not None and task_id in note_per_task:
                    existing.nota = _nota_task(note_per_task[task_id])
            else:
                session.add(Consuntivo(
                    task_id=task_id,
                    dipendente_id=dipendente_id,
                    settimana=settimana_date,
                    ore_dichiarate=ore if ore is not None else 0,
                    compilato=True,
                    data_compilazione=datetime.utcnow(),
                    motivo_fermo=motivo,
                    nota=_nota_task((note_per_task or {}).get(task_id)),
                    # None se il task non è in stati_per_task: la riga nasce da
                    # sole ore o sola nota e nessuno si è espresso sullo stato.
                    stato_dichiarato=stato,
                    percentuale=percentuale_per_task.get(task_id),
                    ore_effettive=ore_effettive_per_task.get(task_id),
                    # `.get()` → None se non pervenuta, che in colonna è
                    # «non stimato». La riga può nascere DALLA SOLA stima
                    # residua, come dalla sola presa-visione.
                    ore_stimate_residue=ore_stimate_residue_per_task.get(task_id),
                    # Nodo F-2: la riga può nascere DALLA SOLA presa-visione —
                    # è il caso normale di un task fermo che qualcuno conferma
                    # senza avere altro da dire.
                    presa_visione=task_id in viste_task,
                ))

            if stato:
                stati_dichiarati[task_id] = stato

        # 1-bis) RICALCOLO A VALLE, per i task-unità.
        #
        # Stessa logica del blocco 0-ter sui sottotask, su un'altra tabella: la
        # dichiarazione di W cambia la baseline della prima settimana dichiarata
        # dopo, e le ore già derivate lì vanno rifatte. Una settimana sola, per la
        # stessa ragione (monotonia imposta a monte, niente cascata).
        #
        # STA QUI E NON ACCANTO ALLA DERIVAZIONE, a differenza del gemello sui
        # sottotask, e la ragione è l'ordine di scrittura: le righe
        # ConsuntivoSottotask si scrivono e si flushano PRIMA di derivare, mentre la
        # percentuale del TASK finisce sulla riga Consuntivo che il ciclo qui sopra
        # ha appena scritto. Ricalcolando prima, la baseline della settimana a valle
        # non vedrebbe la dichiarazione appena inserita e ricalcolerebbe lo stesso
        # numero di prima — cioè non ricalcolerebbe affatto, in silenzio.
        # La query sotto fa autoflush della riga nuova, che è ciò che serve.
        if task_unita:
            for task_id, sett_dopo in sorted(
                _prima_settimana_dopo(
                    session, "task", sorted(task_unita), settimana_date
                ).items()
            ):
                # Tutte le righe di quel task in quella settimana: la percentuale è
                # per (task, dipendente, settimana), quindi più persone possono
                # averne una — ciascuna con la propria riga da riscrivere, come per
                # i pezzi con assegnatario diverso.
                righe_dopo = (
                    session.query(Consuntivo)
                    .filter(
                        Consuntivo.task_id == task_id,
                        Consuntivo.settimana == sett_dopo,
                    )
                    .all()
                )
                for riga in righe_dopo:
                    ricalcolo, _ = _aggrega_ore_unita(
                        session, "task",
                        [(task_id, riga.percentuale, riga.ore_effettive)],
                        sett_dopo,
                    )
                    # `.get` con default 0.0: se il ricalcolo non produce nulla
                    # (percentuale sparita, o stima mancante) la riga va a zero, non
                    # resta col valore vecchio che ora è falso.
                    riga.ore_dichiarate = ricalcolo.get(task_id, 0.0)

        # 2) Presenze settimanali (smart working + assenze) — SOLO SE PERVENUTE.
        # Ogni campo è aggiornato singolarmente e solo se non è None: il blocco non
        # riscrive mai i campi che il chiamante non ha nominato. Stessa convenzione
        # di `spese_lista` e `note_per_task`: None = «non gestisco questo campo».
        # Prima erano parametri con default 0/0/0/""/"" scritti incondizionatamente,
        # e i default sono nati quando il body del form portava sempre tutto. Con un
        # client che manda solo uno stato (le presenze le ha compilate ieri, in
        # un'altra schermata) quei default tornavano in DB come dati veri: 1 giorno
        # in sede e 4 da remoto diventavano 3 e 2 al primo salvataggio di una nota.
        # Un default non è un dato dichiarato — e sovrascriverlo in silenzio è
        # peggio che non scriverlo.
        presenze_pervenute = {
            campo: valore
            for campo, valore in (
                ("giorni_sede", giorni_sede),
                ("giorni_remoto", giorni_remoto),
                ("ore_assenza", ore_assenza),
                ("tipo_assenza", tipo_assenza),
                ("nota_assenza", nota_assenza),
            )
            if valore is not None
        }

        if presenze_pervenute:
            existing_pres = session.query(PresenzaSettimanale).filter(
                PresenzaSettimanale.dipendente_id == dipendente_id,
                PresenzaSettimanale.settimana == settimana_date,
            ).first()

            if existing_pres is None:
                # Riga nuova: i campi NON pervenuti restano al default di colonna
                # (0), non a un valore inventato qui.
                existing_pres = PresenzaSettimanale(
                    dipendente_id=dipendente_id,
                    settimana=settimana_date,
                )
                session.add(existing_pres)

            for campo, valore in presenze_pervenute.items():
                setattr(existing_pres, campo, valore)

            # Coerenza dell'assenza: se le ore di assenza sono state dichiarate a
            # zero, l'assenza non c'è e tipo/nota non hanno più un referente —
            # vanno azzerati anche se sono arrivati valorizzati. Vale solo quando
            # `ore_assenza` è pervenuto: senza, non sappiamo nulla dell'assenza e
            # non tocchiamo ciò che c'è già.
            if ore_assenza is not None and ore_assenza <= 0:
                existing_pres.tipo_assenza = None
                existing_pres.nota_assenza = None

        # 3) Salva spese — SOSTITUZIONE, non accodamento.
        # Il form manda lo stato completo delle spese della settimana, non righe
        # incrementali: non c'è modo di dire «questa riga è nuova» o «questa l'ho
        # cancellata». Prima erano `session.add()` incondizionati senza lookup, e
        # Spesa non ha UNIQUE a proteggere: ogni ri-salvataggio re-inseriva tutte
        # le spese del form, moltiplicando i rimborsi a ogni click su «Invia».
        # Cancella-e-riscrivi è l'unica semantica coerente con un form di stato.
        # `spese_lista is None` = campo non pervenuto (chiamante che non gestisce
        # le spese) → non toccare nulla. `[]` = «questa settimana nessuna spesa»
        # → svuota davvero.
        if spese_lista is not None:
            session.query(Spesa).filter(
                Spesa.dipendente_id == dipendente_id,
                Spesa.settimana == settimana_date,
            ).delete(synchronize_session=False)

            for spesa in spese_lista:
                if spesa.get("importo", 0) > 0:
                    session.add(Spesa(
                        dipendente_id=dipendente_id,
                        settimana=settimana_date,
                        descrizione=spesa.get("descrizione", ""),
                        importo=spesa["importo"],
                        categoria=spesa.get("categoria", ""),
                    ))

        # 4) Legge lo stato ATTUALE dei task dichiarati (serve al passo 5, ma la
        # sessione è ancora aperta: una query in più invece di una sessione in più).
        stati_correnti = {}
        if stati_dichiarati:
            stati_correnti = dict(
                session.query(Task.id, Task.stato)
                .filter(Task.id.in_(list(stati_dichiarati)))
                .all()
            )

        session.commit()
    except Exception:
        # Non si inghiotte: si ripulisce e si ri-solleva. Il chiamante deve
        # vedere l'errore — è la route a tradurlo in HTTP. Senza il
        # rollback esplicito la transazione resterebbe aperta fino al GC,
        # tenendo i LOCK sulle righe toccate: i dati non si corrompono (il
        # commit non è mai stato raggiunto) ma chiunque altro scriva su
        # quelle righe si blocca. Scoperto misurando: la verifica di
        # atomicità dello Step 4 andò in timeout proprio così.
        session.rollback()
        raise
    finally:
        # SEMPRE, percorso felice e percorso d'errore. Assorbe il
        # `session.close()` che stava dopo il commit.
        session.close()

    # 5) PROPAGAZIONE: lo stato dichiarato arriva su Task.stato.
    # Fuori dalla sessione del consuntivo e DOPO il commit, di proposito:
    # `modifica_task` apre la propria sessione (è la porta del Cantiere) e le
    # ore restano salvate anche se un task nel frattempo è sparito.
    for task_id, stato in stati_dichiarati.items():
        corrente = stati_correnti.get(task_id)
        if corrente is None or corrente == stato:
            continue  # task inesistente, o già in quello stato: niente da fare
        if corrente in ("Sospeso", "Annullato"):
            # Decisioni di pianificazione del PM. Il form del dipendente non le
            # mostra e non può rappresentarle: se propagassimo, un "In corso"
            # di default sovrascriverebbe in silenzio una sospensione decisa
            # altrove. Chi dichiara non può disfare ciò che non vede.
            continue
        modifica_task(task_id, stato=stato)

    # Ritorno DICT e non più `True` (Step 4, 06/08/2026). Serviva un canale per
    # gli avvisi non bloccanti — oggi: avanzamento dichiarato su un sottotask
    # senza `ore_stimate`, che non si può derivare. Sono casi in cui il
    # salvataggio RIESCE e va detto lo stesso: rifiutarlo con 400 farebbe
    # pagare al dipendente una stima che manca al PM, e ingoiarli in silenzio
    # farebbe sparire ore davvero lavorate.
    # `ok` conserva esattamente la semantica del vecchio booleano, così la
    # route continua a esporre `salvato` con lo stesso significato.
    return {"ok": True, "avvisi": avvisi}

# ══════════════════════════════════════════════════════════════════════
# SAL — snapshot storico del GANTT (DESIGN_SAL.md)
# ══════════════════════════════════════════════════════════════════════

def _iso(d):
    """date/datetime → stringa ISO, None → None."""
    return d.isoformat() if d is not None else None


def _nome_dip(session, did):
    """Nome del dipendente per id, None se assente. Usa la sessione data."""
    if not did:
        return None
    row = session.query(Dipendente.nome).filter(Dipendente.id == did).first()
    return row[0] if row else None


def _serializza_stato_progetto(pid):
    """Serializza lo stato completo del progetto nel formato SAL concordato.

    Formato (DESIGN_SAL, confermato 26/06/2026):
      {schema_version, progetto:{...}, fasi:[{..., task:[...]}]}
    - nomi denormalizzati (pm, dipendente, azienda) → snapshot autocontenuto;
    - le tre ore sui task (stimate/pianificate/consumate) + ore di fase
      (vendute/pianificate/consumate);
    - ore_consumate calcolata QUI da SUM(Consuntivo.ore_dichiarate), NON dalla
      colonna denormalizzata (stale): rende la foto veritiera. Fase = somma dei
      consumi dei suoi task (coerenza fase↔task per costruzione).
    Solleva ValueError se il progetto non esiste.
    """
    from sqlalchemy import func
    from models import Fase, Azienda, DipendenzaTask

    session = get_session()
    try:
        p = session.query(Progetto).filter(Progetto.id == pid).first()
        if p is None:
            raise ValueError(f"Progetto '{pid}' non trovato")

        azienda_nome = None
        if p.azienda_id is not None:
            az = session.query(Azienda.nome).filter(Azienda.id == p.azienda_id).first()
            azienda_nome = az[0] if az else None

        progetto = {
            "id": p.id, "nome": p.nome, "cliente": p.cliente,
            "stato": p.stato, "tipologia": p.tipologia,
            # `urgenza` (ex `ritardabilita`, rinominata il 03/09/2026). La forma
            # dello snapshot cambia, ed è indolore: `sal_snapshot` ha 0 righe,
            # quindi non esiste una foto vecchia da leggere in due formati. Se
            # ce ne fossero state, sarebbe servito alzare `schema_version`.
            "priorita": p.priorita, "urgenza": p.urgenza,
            "data_inizio": _iso(p.data_inizio), "data_fine": _iso(p.data_fine),
            "fase_corrente": p.fase_corrente, "sede": p.sede,
            "pm_id": p.pm_id, "pm_nome": _nome_dip(session, p.pm_id),
            "azienda_id": p.azienda_id, "azienda_nome": azienda_nome, "area": p.area,
            "scadenza_bando": _iso(p.scadenza_bando),
            # NB: i campi ECONOMICI (budget_ore, valore_contratto, giornate_vendute)
            # NON stanno nel SAL: il SAL fotografa SOLO la struttura del GANTT.
            # L'economia ha il suo archivio separato (Bollettino economico).
            # narrativa per IA-Archivio (il "perché")
            "descrizione": p.descrizione, "motivo_sospensione": p.motivo_sospensione,
            "lezioni_apprese": p.lezioni_apprese,
        }

        # ore_consumate reali: SUM(Consuntivo.ore_dichiarate) per task del progetto.
        cons_per_task = dict(
            session.query(
                Consuntivo.task_id,
                func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0.0),
            )
            .join(Task, Consuntivo.task_id == Task.id)
            .filter(Task.progetto_id == pid)
            .group_by(Consuntivo.task_id)
            .all()
        )

        fasi = (
            session.query(Fase)
            .filter(Fase.progetto_id == pid)
            .order_by(Fase.ordine)
            .all()
        )
        fasi_out = []
        for f in fasi:
            tasks = (
                session.query(Task)
                .filter(Task.fase_id == f.id)
                .order_by(Task.ordine, Task.id)
                .all()
            )
            task_out = []
            fase_consumate = 0.0
            for t in tasks:
                t_cons = float(cons_per_task.get(t.id, 0.0))
                fase_consumate += t_cons
                deps = (
                    session.query(DipendenzaTask)
                    .filter(DipendenzaTask.task_successore_id == t.id)
                    .all()
                )
                task_out.append({
                    "id": t.id, "nome": t.nome, "stato": t.stato,
                    "data_inizio": _iso(t.data_inizio), "data_fine": _iso(t.data_fine),
                    "ore_stimate": t.ore_stimate,
                    "ore_pianificate": t.ore_pianificate,
                    "ore_consumate": t_cons,
                    "profilo_richiesto": t.profilo_richiesto,
                    "dipendente_id": t.dipendente_id,
                    "dipendente_nome": _nome_dip(session, t.dipendente_id),
                    "motivo_blocco": t.motivo_blocco, "note": t.note,
                    "dipendenze": [
                        {"task_predecessore_id": d.task_predecessore_id,
                         "tipo_dipendenza": d.tipo_dipendenza}
                        for d in deps
                    ],
                })
            fasi_out.append({
                "id": f.id, "nome": f.nome, "ordine": f.ordine,
                "data_inizio": _iso(f.data_inizio), "data_fine": _iso(f.data_fine),
                "stato": f.stato,
                "ore_vendute": f.ore_vendute, "ore_pianificate": f.ore_pianificate,
                "ore_consumate": round(fase_consumate, 1),
                "task": task_out,
            })

        # schema_version 2: rimossi i campi economici dal blocco progetto
        # (SAL puro strutturale; economia → Bollettino economico).
        return {"schema_version": 2, "progetto": progetto, "fasi": fasi_out}
    finally:
        session.close()


def get_progetto_meta(pid):
    """Metadati minimi per autorizzazione/esistenza: {id, nome, pm_id} o None."""
    session = get_session()
    try:
        p = session.query(Progetto.id, Progetto.nome, Progetto.pm_id).filter(
            Progetto.id == pid
        ).first()
        if p is None:
            return None
        return {"id": p[0], "nome": p[1], "pm_id": p[2]}
    finally:
        session.close()


def crea_snapshot(progetto_id, consolidato_da=None, nota=None):
    """Crea uno snapshot SAL serializzando lo stato corrente del progetto.

    Ritorna i metadati dello snapshot creato (non l'intero JSON).
    Solleva ValueError se il progetto non esiste (via serializzatore).
    """
    from models import SalSnapshot

    stato = _serializza_stato_progetto(progetto_id)  # ValueError se inesistente

    session = get_session()
    try:
        snap = SalSnapshot(
            progetto_id=progetto_id,
            consolidato_da=consolidato_da,
            nota=nota,
            stato=stato,
        )
        session.add(snap)
        session.commit()
        session.refresh(snap)  # per data_snapshot (server_default now())
        return {
            "id": snap.id,
            "progetto_id": snap.progetto_id,
            "data_snapshot": _iso(snap.data_snapshot),
            "consolidato_da": snap.consolidato_da,
            "nota": snap.nota,
        }
    finally:
        session.close()


def lista_snapshot_progetto(pid):
    """Storico SINTETICO degli snapshot di un progetto (NO JSON stato).

    Ritorna lista di {id, data_snapshot, consolidato_da, consolidato_da_nome,
    nota} ordinata per data desc (il più recente prima). Il JSON `stato`
    completo si legge solo nel dettaglio (get_snapshot).
    """
    from models import SalSnapshot
    session = get_session()
    try:
        rows = (
            session.query(
                SalSnapshot.id, SalSnapshot.data_snapshot,
                SalSnapshot.consolidato_da, SalSnapshot.nota,
            )
            .filter(SalSnapshot.progetto_id == pid)
            .order_by(SalSnapshot.data_snapshot.desc(), SalSnapshot.id.desc())
            .all()
        )
        return [{
            "id": r[0],
            "data_snapshot": _iso(r[1]),
            "consolidato_da": r[2],
            "consolidato_da_nome": _nome_dip(session, r[2]),
            "nota": r[3],
        } for r in rows]
    finally:
        session.close()


def get_snapshot_progetto_id(snap_id):
    """progetto_id di uno snapshot (per l'auth a monte), None se inesistente."""
    from models import SalSnapshot
    session = get_session()
    try:
        r = session.query(SalSnapshot.progetto_id).filter(
            SalSnapshot.id == snap_id
        ).first()
        return r[0] if r else None
    finally:
        session.close()


def get_snapshot(snap_id):
    """Snapshot COMPLETO (incluso JSON `stato`) o None se inesistente."""
    from models import SalSnapshot
    session = get_session()
    try:
        s = session.query(SalSnapshot).filter(SalSnapshot.id == snap_id).first()
        if s is None:
            return None
        return {
            "id": s.id,
            "progetto_id": s.progetto_id,
            "data_snapshot": _iso(s.data_snapshot),
            "consolidato_da": s.consolidato_da,
            "consolidato_da_nome": _nome_dip(session, s.consolidato_da),
            "nota": s.nota,
            "stato": s.stato,
        }
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════
# ECONOMIA — marginalità per progetto + erosione + aggregato per azienda
# ══════════════════════════════════════════════════════════════════════

def _pct(margine, valore):
    """margine/valore in %, 0 se valore non positivo."""
    return round(margine / valore * 100, 1) if valore and valore > 0 else 0.0


def margini_economia():
    """Marginalità economica (versione B — erosione da sovraccarico).

    Solo progetti COMMERCIALI/BANDI: gli interni (tipologia 'interna') sono
    esclusi per TIPOLOGIA (non per id: il vecchio filtro `id != 'P010'` era un
    hack morto che, dopo il redesign seed, non escludeva più gli interni e per
    giunta tagliava fuori il nuovo P010/Maida).

    Per ogni progetto, tre margini = valore_contratto − costo su tre basi-ore:
      - VENDUTO   (contratto): costo da Fase.ore_vendute ripartite sui task in
        proporzione a ore_pianificate, al costo_ora dell'assegnatario (Opzione B).
        Fallback (→ costo_stimato=True): fase senza ore_pianificate → split
        uniforme; task/fase senza assegnatario → tariffa media di progetto.
      - PIANIFICATO (piano PM): Σ task (ore_pianificate × costo_ora[assegnatario]).
      - CONSUMATO  (reale): Σ consuntivi (ore_dichiarate × costo_ora[chi ha loggato]).
        Identico al precedente `margine_attuale` (oracolo invariato).

    Due erosioni (euro e punti percentuali):
      - commerciale = margine_venduto − margine_consumato  (sforiamo il contratto?)
      - operativa   = margine_pianificato − margine_consumato (sforiamo il piano?)

    Output a due livelli: {"progetti": [...], "totali_per_azienda": [...]}.
    Coerenza: i totali di azienda sono la SOMMA dei valori (arrotondati) dei
    progetti del ramo → Σ per-progetto == totale per costruzione.
    """
    from models import Fase, Azienda

    session = get_session()
    try:
        # mappe di supporto (una query ciascuna)
        dip = {
            d.id: {"nome": d.nome, "profilo": d.profilo, "costo_ora": float(d.costo_ora or 0)}
            for d in session.query(Dipendente).all()
        }
        azienda_nome = {a.id: a.nome for a in session.query(Azienda).all()}

        def rate(did):
            return dip.get(did, {}).get("costo_ora", 0.0) if did else 0.0

        progetti = (
            session.query(Progetto)
            .filter(Progetto.tipologia != "interna")  # esclusione per tipologia
            .all()
        )

        per_progetto = []
        for p in progetti:
            tasks = session.query(Task).filter(Task.progetto_id == p.id).all()
            fasi = session.query(Fase).filter(Fase.progetto_id == p.id).all()
            fallback = False

            # --- tariffa media di progetto (pesata sulle ore pianificate) ---
            num = sum((t.ore_pianificate or 0) * rate(t.dipendente_id)
                      for t in tasks if rate(t.dipendente_id))
            den = sum((t.ore_pianificate or 0)
                      for t in tasks if rate(t.dipendente_id))
            if den > 0:
                avg_rate = num / den
            else:
                rates = [rate(t.dipendente_id) for t in tasks if rate(t.dipendente_id)]
                avg_rate = sum(rates) / len(rates) if rates else 0.0

            # --- CONSUMATO (reale, dai consuntivi) — identico al vecchio calcolo ---
            costo_consumato = 0.0
            ore_consumate = 0.0
            costi_per_persona = {}
            cons = (session.query(Consuntivo).join(Task, Consuntivo.task_id == Task.id)
                    .filter(Task.progetto_id == p.id).all())
            for c in cons:
                if c.ore_dichiarate <= 0:
                    continue
                r = rate(c.dipendente_id)
                costo_consumato += c.ore_dichiarate * r
                ore_consumate += c.ore_dichiarate
                if c.dipendente_id not in costi_per_persona:
                    info = dip.get(c.dipendente_id, {"nome": c.dipendente_id, "profilo": "-"})
                    costi_per_persona[c.dipendente_id] = {
                        "nome": info["nome"], "profilo": info["profilo"],
                        "costo_ora": r, "ore": 0, "costo": 0,
                    }
                costi_per_persona[c.dipendente_id]["ore"] += c.ore_dichiarate
                costi_per_persona[c.dipendente_id]["costo"] += c.ore_dichiarate * r

            # --- PIANIFICATO (piano PM): ore_pianificate × rate assegnatario ---
            costo_pianificato = 0.0
            for t in tasks:
                op = t.ore_pianificate or 0
                if op <= 0:
                    continue
                r = rate(t.dipendente_id)
                if not r:  # ore pianificate senza tariffa attribuibile
                    r = avg_rate
                    fallback = True
                costo_pianificato += op * r

            # --- VENDUTO (Opzione B): Fase.ore_vendute ripartite per ore_pianificate ---
            costo_venduto = 0.0
            tasks_per_fase = {}
            for t in tasks:
                tasks_per_fase.setdefault(t.fase_id, []).append(t)
            for f in fasi:
                ov = float(f.ore_vendute or 0)
                if ov <= 0:
                    continue
                ftasks = tasks_per_fase.get(f.id, [])
                if not ftasks:
                    costo_venduto += ov * avg_rate
                    fallback = True
                    continue
                sum_plan = sum((t.ore_pianificate or 0) for t in ftasks)
                if sum_plan > 0:
                    for t in ftasks:
                        quota = ov * (t.ore_pianificate or 0) / sum_plan
                        r = rate(t.dipendente_id)
                        if not r:
                            r = avg_rate
                            fallback = True
                        costo_venduto += quota * r
                else:
                    # nessuna ora pianificata nella fase → split uniforme
                    fallback = True
                    n = len(ftasks)
                    for t in ftasks:
                        r = rate(t.dipendente_id) or avg_rate
                        costo_venduto += (ov / n) * r

            valore = float(p.valore_contratto or 0)
            m_venduto = round(valore - costo_venduto, 2)
            m_pianificato = round(valore - costo_pianificato, 2)
            m_consumato = round(valore - costo_consumato, 2)
            pct_venduto = _pct(m_venduto, valore)
            pct_pianificato = _pct(m_pianificato, valore)
            pct_consumato = _pct(m_consumato, valore)

            per_progetto.append({
                "progetto_id": p.id, "nome": p.nome,
                "cliente": p.cliente, "stato": p.stato, "tipologia": p.tipologia,
                "azienda_id": p.azienda_id,
                "azienda_nome": azienda_nome.get(p.azienda_id),
                "valore_contratto": valore,
                "ore_consuntivate": round(ore_consumate, 1),
                # tre costi e tre margini
                "costo_venduto": round(costo_venduto, 2),
                "costo_pianificato": round(costo_pianificato, 2),
                "costo_consumato": round(costo_consumato, 2),
                "margine_venduto": m_venduto, "margine_venduto_pct": pct_venduto,
                "margine_pianificato": m_pianificato, "margine_pianificato_pct": pct_pianificato,
                "margine_consumato": m_consumato, "margine_consumato_pct": pct_consumato,
                # due erosioni (euro e punti percentuali)
                "erosione_commerciale_eur": round(m_venduto - m_consumato, 2),
                "erosione_commerciale_pp": round(pct_venduto - pct_consumato, 1),
                "erosione_operativa_eur": round(m_pianificato - m_consumato, 2),
                "erosione_operativa_pp": round(pct_pianificato - pct_consumato, 1),
                # trasparenza: margine approssimato per dati incompleti
                "costo_stimato": fallback,
                # compat con il payload precedente (oracolo: margine_attuale invariato)
                "costo_effettivo": round(costo_consumato, 2),
                "margine_attuale": m_consumato, "margine_pct": pct_consumato,
                "dettaglio_persone": sorted(
                    costi_per_persona.values(), key=lambda x: x["costo"], reverse=True
                ),
            })

        # --- aggregato per azienda (somma dei valori arrotondati per coerenza) ---
        tot = {}
        for r in per_progetto:
            k = r["azienda_id"]
            if k not in tot:
                tot[k] = {
                    "azienda_id": k, "azienda_nome": r["azienda_nome"],
                    "n_progetti": 0, "valore_contratto": 0.0,
                    "costo_venduto": 0.0, "costo_pianificato": 0.0, "costo_consumato": 0.0,
                    "costo_stimato": False,
                }
            a = tot[k]
            a["n_progetti"] += 1
            a["valore_contratto"] += r["valore_contratto"]
            a["costo_venduto"] += r["costo_venduto"]
            a["costo_pianificato"] += r["costo_pianificato"]
            a["costo_consumato"] += r["costo_consumato"]
            a["costo_stimato"] = a["costo_stimato"] or r["costo_stimato"]

        totali_per_azienda = []
        for a in tot.values():
            val = round(a["valore_contratto"], 2)
            mv = round(val - a["costo_venduto"], 2)
            mp = round(val - a["costo_pianificato"], 2)
            mc = round(val - a["costo_consumato"], 2)
            pv, pp_, pc = _pct(mv, val), _pct(mp, val), _pct(mc, val)
            totali_per_azienda.append({
                "azienda_id": a["azienda_id"], "azienda_nome": a["azienda_nome"],
                "n_progetti": a["n_progetti"], "valore_contratto": val,
                "costo_venduto": round(a["costo_venduto"], 2),
                "costo_pianificato": round(a["costo_pianificato"], 2),
                "costo_consumato": round(a["costo_consumato"], 2),
                "margine_venduto": mv, "margine_venduto_pct": pv,
                "margine_pianificato": mp, "margine_pianificato_pct": pp_,
                "margine_consumato": mc, "margine_consumato_pct": pc,
                "erosione_commerciale_eur": round(mv - mc, 2),
                "erosione_commerciale_pp": round(pv - pc, 1),
                "erosione_operativa_eur": round(mp - mc, 2),
                "erosione_operativa_pp": round(pp_ - pc, 1),
                "costo_stimato": a["costo_stimato"],
            })

        per_progetto.sort(key=lambda x: x["margine_consumato_pct"])
        totali_per_azienda.sort(key=lambda x: (x["azienda_nome"] or ""))
        return {"progetti": per_progetto, "totali_per_azienda": totali_per_azienda}
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════
# BOLLETTINO ECONOMICO — archivio storico della marginalità (DESIGN: separato dal SAL)
# ══════════════════════════════════════════════════════════════════════

def _serializza_economia_progetto(pid):
    """Congela l'economia di UN progetto nel formato Bollettino.

    Riusa margini_economia() (NON la tocca): ne filtra a valle la riga del
    progetto, che contiene già margini calcolati (3 margini + 2 erosioni),
    grezzi (valore, costi, costo_ora per persona in dettaglio_persone),
    azienda denormalizzata e flag costo_stimato. La arricchisce con le ore
    aggregate grezze (vendute/pianificate; le consumate ci sono già).
    Solleva ValueError se il progetto non è in Economia (inesistente o interno).
    """
    from sqlalchemy import func
    from models import Fase

    eco = margini_economia()
    riga = next((p for p in eco["progetti"] if p["progetto_id"] == pid), None)
    if riga is None:
        raise ValueError(
            f"Progetto '{pid}' non presente in Economia (inesistente o interno)"
        )

    riga = dict(riga)  # copia: non mutare l'output condiviso
    session = get_session()
    try:
        ore_vendute = float(
            session.query(func.coalesce(func.sum(Fase.ore_vendute), 0.0))
            .filter(Fase.progetto_id == pid).scalar() or 0.0
        )
        ore_pianificate = float(
            session.query(func.coalesce(func.sum(Task.ore_pianificate), 0.0))
            .filter(Task.progetto_id == pid).scalar() or 0.0
        )
    finally:
        session.close()
    riga["ore_vendute"] = round(ore_vendute, 1)
    riga["ore_pianificate"] = round(ore_pianificate, 1)

    return {"schema_version": 1, "progetto": riga}


def crea_bollettino(progetto_id, consolidato_da=None, nota=None):
    """Crea un Bollettino economico congelando l'economia corrente del progetto.
    Ritorna i metadati (non l'intero JSON). ValueError se progetto non in Economia.
    """
    from models import BollettinoEconomico

    stato = _serializza_economia_progetto(progetto_id)  # ValueError se assente

    session = get_session()
    try:
        b = BollettinoEconomico(
            progetto_id=progetto_id,
            consolidato_da=consolidato_da,
            nota=nota,
            stato=stato,
        )
        session.add(b)
        session.commit()
        session.refresh(b)
        return {
            "id": b.id,
            "progetto_id": b.progetto_id,
            "data_snapshot": _iso(b.data_snapshot),
            "consolidato_da": b.consolidato_da,
            "nota": b.nota,
        }
    finally:
        session.close()


def lista_bollettini_progetto(pid):
    """Storico SINTETICO dei bollettini di un progetto (NO JSON stato), data desc."""
    from models import BollettinoEconomico
    session = get_session()
    try:
        rows = (
            session.query(
                BollettinoEconomico.id, BollettinoEconomico.data_snapshot,
                BollettinoEconomico.consolidato_da, BollettinoEconomico.nota,
            )
            .filter(BollettinoEconomico.progetto_id == pid)
            .order_by(BollettinoEconomico.data_snapshot.desc(), BollettinoEconomico.id.desc())
            .all()
        )
        return [{
            "id": r[0],
            "data_snapshot": _iso(r[1]),
            "consolidato_da": r[2],
            "consolidato_da_nome": _nome_dip(session, r[2]),
            "nota": r[3],
        } for r in rows]
    finally:
        session.close()


def get_bollettino_progetto_id(bid):
    """progetto_id di un bollettino (per l'auth a monte), None se inesistente."""
    from models import BollettinoEconomico
    session = get_session()
    try:
        r = session.query(BollettinoEconomico.progetto_id).filter(
            BollettinoEconomico.id == bid
        ).first()
        return r[0] if r else None
    finally:
        session.close()


def get_bollettino(bid):
    """Bollettino COMPLETO (incluso JSON `stato`) o None se inesistente."""
    from models import BollettinoEconomico
    session = get_session()
    try:
        b = session.query(BollettinoEconomico).filter(BollettinoEconomico.id == bid).first()
        if b is None:
            return None
        return {
            "id": b.id,
            "progetto_id": b.progetto_id,
            "data_snapshot": _iso(b.data_snapshot),
            "consolidato_da": b.consolidato_da,
            "consolidato_da_nome": _nome_dip(session, b.consolidato_da),
            "nota": b.nota,
            "stato": b.stato,
        }
    finally:
        session.close()
