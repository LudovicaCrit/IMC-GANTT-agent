"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/consuntivi.py — Router per endpoint /api/consuntivi
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi ai consuntivi settimanali dei dipendenti.
È il cuore tecnico della pagina Consuntivazione e della futura Vista
Helena (Blocco 3 roadmap). Implementa rigorosamente il pattern
Scenario B + self-or-manager + Pattern Y (anti-impersonation in scrittura).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/consuntivi/settimana        │ GET      │ manager (tutti) / pm (i suoi)│
│ /api/consuntivi/me               │ GET      │ AUTH-ONLY (intrinseco self)  │
│ /api/consuntivi/salva-blocchi    │ POST     │ AUTH-ONLY (solo per sé)      │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/consuntivi/settimana
   - manager → perimetro AZIENDALE (tutti i dipendenti). Invariato.
     pm      → i dipendenti con task sui progetti che DIRIGE
               (`progetti_diretti_da`, non `progetti_attivi_visibili`).
     user    → 403: la sua vista è /me.
   - Settimana corrente. Per ogni dipendente: ore_per_task, totale_ore,
     flag `compilato`, e i conteggi n_segnalazioni / n_fermi / n_in_ritardo.
   - Ogni voce di `ore_per_task` porta il CONTENUTO della dichiarazione, non
     le sole ore: nota, ore_stimate_residue, stato_dichiarato, stato_task,
     data_fine, in_ritardo, presa_visione, più task_id/progetto_id per
     agganciare un drill-down.
   - Include anche dipendenti che NON hanno compilato (totale_ore=0,
     compilato=False), purché abbiano almeno 1 task attivo E siano nel
     perimetro di chi chiede.
   - `compilato` = HA RISPOSTO (esiste una riga), non «ha dichiarato ore»:
     le righe a zero ore sono dichiarazioni-ferme, e sono il contenuto per cui
     la vista-PM esiste. Vedi il rovesciamento della regola di scarto nel
     corpo della funzione.
   - Output ordinato: prima i compilati, poi per nome.

2. GET /api/consuntivi/me
   - AUTH-ONLY: nessun parametro `dipendente_id` accettato.
     L'identità del chiamante determina di chi mostrare i consuntivi.
   - Vista PERSONALE: il dipendente vede SOLO i propri consuntivi.
   - Funziona per user (Helena) e per manager (Ludovica può vedere se
     stessa così, anche se ha accesso a /settimana per la vista aziendale).
   - 400 se l'utente non è collegato a un dipendente
     (current_user.dipendente_id is None).
   - Layout A': parte dai TASK del dipendente (non dai Consuntivi),
     via data.task_settimana_dipendente (riusabile dalla Home-utente).
   - Query param opzionale `settimana` (ISO YYYY-MM-DD, qualsiasi giorno
     della settimana → normalizzato al lunedì da data.lunedi_settimana).
     Assente = settimana corrente. Ammesse solo corrente e precedente:
     qualsiasi altra → 400. Serve a chi non ha compilato in tempo e a chi
     deve correggersi; non si compila in anticipo né si riscrive un mese fa.
   - Restituisce: nome, profilo, ore_contrattuali, settimana (lunedì ISO),
     settimane_disponibili, totale_ore, task_settimana, compilato.
   - Ogni voce di `task_settimana` porta `in_ritardo` (bool): DERIVATO
     (finestra del task chiusa + task non chiuso), non dichiarato. Il ritardo
     non è uno stato che il dipendente sceglie — non è nella tendina: è una
     segnalazione che il sistema calcola e il frontend mostra accanto al task.
   - `settimane_disponibili`: le due settimane apribili, ciascuna con
     lunedi/etichetta. La finestra è TEMPORALE: corrente e
     precedente sono entrambe aperte, in lettura e in scrittura, e una
     settimana si chiude quando diventa due-settimane-fa — cioè esce dalla
     lista. Le ore già dichiarate non chiudono niente (fix N17). La guardia in
     scrittura sta su POST /salva-blocchi, non qui.

3. POST /api/consuntivi/salva-blocchi
   - SOLO PER SÉ: nessun `dipendente_id` nel body, l'intestatario è l'utente
     loggato, e non c'è deroga per il manager. Consuntivare è un atto in
     prima persona.
   - Body: settimana + `unita` (una per riga della griglia: tipo, id,
     blocchi-ore per giorno, stato, nota, «resta»).
   - Le validazioni in tre tempi, ognuno un 400 che elenca TUTTE le
     violazioni del suo livello: il DTO (body), la route (settimana e
     giorni), lo strato dati (appartenenza, tetto delle 24h).
   - Lo stato dichiarato si propaga su Task.stato passando da `modifica_task`
     (la stessa porta del Cantiere), DOPO il commit e con un avviso se
     fallisce: ore salvate e stato non riportato è meglio di un 500 che fa
     credere perso un salvataggio riuscito.

   ⓘ C'ERA ANCHE `POST /api/consuntivi/salva`, la porta della pagina a
     cursore, con Pattern Y (self-or-manager) e un body a dizionari paralleli.
     È uscita col passo 5.3 (23/09/2026) insieme alla pagina che la chiamava, e
     col passo 5.4 è uscito anche il motore che ci stava dietro — quello che
     DERIVAVA le ore dall'avanzamento dichiarato. Oggi le ore si dichiarano per
     giorno e non si derivano da niente.

PATTERN AUTH USATI
──────────────────
- `get_current_user` + dispatch sul ruolo: la vista aggregata serve manager
  (perimetro aziendale) e pm (perimetro dei progetti che dirige); il `user`
  riceve 403 — la sua vista e' /me.
- `get_current_user` + check `dipendente_id`: per le viste personali
  intrinseche (`/me`, `/salva-blocchi`). Il Pattern Y (self-or-manager) in
  scrittura è uscito col passo 5.3: non c'è più una scrittura per conto terzi.

NOTE DI DOMINIO
───────────────
La vista personale `/api/consuntivi/me` è esattamente quella che alimenterà
la pagina Consuntivazione di Helena nella Vista User (Blocco 3 roadmap).
Coerente con la "filosofia della settimana intera" e con Scenario B.

📌 TODO Blocco 3 roadmap (Vista Helena + Form Consuntivazione):
   Il payload restituito da `/api/consuntivi/me` potrebbe arricchirsi:
   - reminder integrati ("non hai ancora compilato")
   - task in scadenza
   - flag `motivo_richiesto` se task bloccato/in ritardo senza nota
   - storia delle ultime N settimane

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `task_settimana_dipendente`,
  `settimane_selezionabili`, `salva_blocchi_settimana`.
- `models`: `Dipendente`, `Task`, `Consuntivo`, `get_session` (lettura
  diretta Postgres).
- `deps`: `get_current_user`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
La vista `/me` non ha più early-return sulla tabella Consuntivi vuota: parte
dai Task attivi, quindi `task_settimana` è popolata anche alla prima
compilazione (ore_consumate=0), non lista vuota.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
Letture migrate da DataFrame in cache a Postgres diretto il 21 maggio 2026
(handoff migrazione §6-ter), preservando iso-comportamento.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Literal, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import func, and_
from sqlalchemy.orm import joinedload, contains_eager

from deps import get_current_user
from models import (
    Utente, Dipendente, Task, Progetto, Consuntivo, OreSettimanali, get_session,
    STATI_DICHIARABILI,
)
from data import (
    get_dipendente,
    task_settimana_dipendente,
    lunedi_settimana,
    settimane_selezionabili,
    # Vista-PM (07/09/2026): il perimetro di chi dirige, e la regola del
    # ritardo — entrambi dallo strato dati, per non riscriverli qui.
    progetti_diretti_da,
    dipendenti_con_task_su,
    task_in_ritardo,
    # Consuntivazione a ore, passo 3: il salvataggio a blocchi.
    salva_blocchi_settimana,
    ConsuntivoNonValido,
)


# ── DTO del salvataggio A BLOCCHI (consuntivazione a ore, passo 3) ─────────
# Il payload di POST /salva-blocchi: una lista di UNITÀ, una per riga della
# griglia. Nessun dizionario parallelo per campo, nessuna percentuale.
#
# ASSENTE ≠ NULL, ed è la semantica del salvataggio (decisione D3):
#   blocchi       assente = non toccare le ore · [] = azzera · null = errore
#   stato, nota,
#   residuo,
#   presa_visione assente = non toccare · null = cancella
# L'assenza si legge da `model_fields_set`, non dal valore: un campo con
# default None non distingue da solo «non mandato» da «mandato null».
#
# NIENTE `dipendente_id`: si consuntiva solo per sé, l'intestatario è l'utente
# loggato. `extra="forbid"` fa rifiutare un `dipendente_id` mandato per
# abitudine dal vecchio contratto, invece di ignorarlo in silenzio.
#
# DOVE VA UNA VALIDAZIONE — la nota di metodo, che il passo 5.3 ha ereditato
# dal DTO di /salva insieme al suo unico insegnamento davvero costato caro:
#
#   Il DTO vede SOLO il body. Qualunque regola che dipenda da cosa c'è già in
#   database non può stare lì, e va dove lo stato attuale è conoscibile.
#
# «Bloccato richiede una nota» sembra una regola sul body, e sul vecchio /salva
# era scritta nel DTO come `not note_per_task.get(id)`: sbagliata, perché il
# form manda solo le note MODIFICATE. Ridichiarare Bloccato senza ritoccare una
# nota già salvata prendeva 400 — un salvataggio legittimo rifiutato, per una
# regola messa dove non poteva vedere la nota che esisteva. Qui la stessa regola
# vive in `_valida_unita_blocchi` (strato dati), che il DB ce l'ha davanti.
#
# Prima di aggiungere una regola qui, chiedersi «per rispondere mi basta il
# body?». Se la risposta è no — anche solo «dipende da cosa c'era prima» — va
# nella route (se le serve la settimana normalizzata) o nello strato dati.

class BloccoOreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    giorno: date
    # Decimal e non float: pydantic lo legge dal JSON senza perdite, così
    # «più di 2 decimali» si decide sul valore scritto dal client e non sulla
    # sua approssimazione binaria.
    ore: Decimal


class UnitaConsuntivoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["task", "sottotask"]
    # str per i task ("T017"), int per i sottotask: si valida contro `tipo`.
    id: Union[str, int]
    stato_dichiarato: Optional[str] = None
    nota: Optional[str] = None
    ore_stimate_residue: Optional[float] = None
    presa_visione: Optional[bool] = None
    blocchi: Optional[list[BloccoOreIn]] = None


class SalvaBlocchiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Obbligatoria: una scrittura non deve finire su una settimana implicita
    # (a mezzanotte di domenica «la corrente» cambia sotto le mani).
    settimana: str
    unita: list[UnitaConsuntivoIn]

    @model_validator(mode="after")
    def _valida_payload(self):
        """Le regole che si decidono dal SOLO body (vedi «DOVE VA UNA
        VALIDAZIONE» sopra la classe). Raccoglie TUTTE le violazioni e le rende
        in un solo 400: una settimana si corregge in un giro.
        Restano fuori, e stanno nella route o nello strato dati, le regole che
        chiedono la settimana normalizzata (giorni) o il DB (appartenenza,
        tetto giornaliero, settimana compilabile)."""
        errori = []
        viste = set()
        for u in self.unita:
            et = f"{u.tipo} {u.id}"
            campi = u.model_fields_set

            # D2 — il tipo dell'id segue il tipo dell'unità. `bool` è un int in
            # Python: va escluso esplicitamente.
            if u.tipo == "task" and not isinstance(u.id, str):
                errori.append(f"{et}: l'id di un task è una stringa (es. \"T017\")")
            if u.tipo == "sottotask" and (not isinstance(u.id, int) or isinstance(u.id, bool)):
                errori.append(f"{et}: l'id di un sottotask è un numero intero")

            # N12 — la stessa unità due volte: quale delle due vale?
            if (u.tipo, u.id) in viste:
                errori.append(f"{et}: compare due volte nel salvataggio")
            viste.add((u.tipo, u.id))

            if "stato_dichiarato" in campi and u.stato_dichiarato is not None \
                    and u.stato_dichiarato not in STATI_DICHIARABILI:
                errori.append(
                    f"{et}: stato '{u.stato_dichiarato}' non dichiarabile "
                    f"(ammessi: {', '.join(STATI_DICHIARABILI)})"
                )

            if "blocchi" in campi and u.blocchi is None:
                errori.append(
                    f"{et}: `blocchi` non può essere null — manda [] per azzerare "
                    f"le ore, oppure ometti il campo per non toccarle"
                )

            giorni = set()
            for b in u.blocchi or []:
                # N4 — lo zero non si manda: «nessuna ora» è l'assenza del blocco.
                if not b.ore.is_finite() or b.ore <= 0:
                    errori.append(
                        f"{et}, {b.giorno}: ore {b.ore} non valide — devono essere "
                        f"maggiori di zero (per zero ore non mandare il blocco)"
                    )
                # N3 — nessun arrotondamento silenzioso.
                elif b.ore.as_tuple().exponent < -2:
                    errori.append(
                        f"{et}, {b.giorno}: ore {b.ore} con più di 2 decimali"
                    )
                # N11 — due blocchi sullo stesso giorno della stessa unità.
                if b.giorno in giorni:
                    errori.append(f"{et}: il giorno {b.giorno} compare due volte")
                giorni.add(b.giorno)

            # N5 (O4) — ore senza stato: niente task-fantasma. Lo stato deve
            # arrivare NEL payload, non basta quello già in DB (stessa ragione di
            # D4). N6, stato senza blocchi, invece passa.
            if u.blocchi and ("stato_dichiarato" not in campi or u.stato_dichiarato is None):
                errori.append(
                    f"{et}: ci sono ore ma manca `stato_dichiarato` — dichiara "
                    f"a che punto è (In corso, Completato o Bloccato)"
                )

            # D4 — Bloccato vuole la nota NEL payload: con la sostituzione
            # completa, una nota assente non vuol dire «c'è già in DB».
            if u.stato_dichiarato == "Bloccato" and not (u.nota or "").strip():
                errori.append(f"{et}: Bloccato richiede una nota che spieghi il motivo")

            if u.ore_stimate_residue is not None and u.ore_stimate_residue < 0:
                errori.append(
                    f"{et}: ore residue {u.ore_stimate_residue} negative "
                    f"(0 è ammesso: «non manca più niente»)"
                )

            # N22 — «confermo che è ferma» e delle ore nella stessa settimana si
            # contraddicono. Scatta SOLO con blocchi presenti e NON vuoti:
            # presa_visione=true con `blocchi: []` (ore azzerate) o con i blocchi
            # assenti (ore non toccate) è ammessa.
            if u.presa_visione is True and u.blocchi:
                errori.append(
                    f"{et}: un'unità confermata ferma non può avere ore questa "
                    f"settimana — togli la conferma o togli le ore"
                )

        if errori:
            raise HTTPException(400, "Consuntivo non salvato: " + "; ".join(errori))
        return self


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/consuntivi", tags=["consuntivi"])


@router.get("/settimana")
def consuntivi_settimana_corrente(current_user: Utente = Depends(get_current_user)):
    """Le dichiarazioni della settimana corrente, nel perimetro di chi chiede.

    UNA VISTA, DUE PERIMETRI (07/09/2026)
    --------------------------------------
    Era manager-only e aziendale. Ora il PM legge le segnalazioni del proprio
    gruppo dallo stesso endpoint: la domanda-dati è la stessa — «cosa hanno
    dichiarato i miei questa settimana» — e cambia solo chi definisce «i miei».
    Due endpoint avrebbero significato due regole di visibilità sulla stessa
    tabella, cioè la regola-in-due-copie che questo codice combatte da mesi.

      manager → tutti. Comportamento invariato: `perimetro is None`, e nessun
                filtro si applica.
      pm      → i dipendenti che lavorano sui progetti che DIRIGE
                (`progetti_diretti_da`, NON `progetti_attivi_visibili`: quella
                include anche i progetti dove il pm ha solo un task, diretti da
                altri — misurato, farebbe passare il perimetro da 8 a 14
                dipendenti su 18).
      user    → 403. Un dipendente non legge le dichiarazioni dei colleghi; la
                sua vista è /api/consuntivi/me.

    IL FILTRO-RUOLO STA IN UN PUNTO SOLO — il blocco `perimetro` qui sotto.
    Sotto quel punto il codice non sa più chi sta chiedendo: applica un filtro
    se c'è, e basta. È la stessa disciplina di `progetti_attivi_visibili`, dove
    l'identità si decide una volta e il resto è comune.

    IL PAYLOAD È IDENTICO PER I DUE RUOLI. Cambia CHI ci finisce dentro, non
    cosa contiene: un solo formato da consumare, e il giorno che il management
    vuole leggere una nota non serve un endpoint nuovo. Costa poco — misurate
    53-72 righe a settimana per tutta l'azienda.
    """
    # ── IL PERIMETRO — l'unico punto dove il ruolo conta ────────────────
    if current_user.ruolo_app == "manager":
        perimetro_dipendenti = None          # None = nessun filtro, tutti
    elif current_user.ruolo_app == "pm":
        progetti = progetti_diretti_da(current_user.dipendente_id)
        perimetro_dipendenti = set(dipendenti_con_task_su(progetti))
        # Un PM senza progetti diretti ha un perimetro VUOTO, che è diverso da
        # «nessun filtro»: `set()` è falsy ma non è None, e il codice sotto
        # distingue i due casi. Confonderli gli mostrerebbe tutta l'azienda.
    else:
        raise HTTPException(
            403,
            "Questa vista è riservata a manager e PM. Le tue dichiarazioni "
            "sono in /api/consuntivi/me.",
        )

    lun = datetime.now() - timedelta(days=datetime.now().weekday())
    lun_date = lun.date() if hasattr(lun, 'date') else lun
    ven_date = lun_date + timedelta(days=6)
    oggi = date.today()

    session = get_session()
    # Iso-comportamento: l'originale fa early-return [] se la tabella
    # consuntivi è completamente vuota (db appena seedato, prima
    # compilazione mai avvenuta). Replicato con una query indicizzata
    # su PK, di costo trascurabile.
    has_any = session.query(Consuntivo.id).first() is not None
    if not has_any:
        session.close()
        return []

    # Una sola query che carica anche Task → Progetto: evita N+1 nel
    # lookup di nome task/progetto durante il loop.
    #
    # LE ORE VENGONO DALLA VISTA `ore_settimanali` (passo 2 della
    # consuntivazione a ore), agganciata con un OUTER JOIN sulla stessa chiave
    # della riga — (task, dipendente, settimana) — dentro questa stessa query:
    # una lookup separata sarebbe stata una query in più a ogni apertura della
    # vista. Outer perché una riga a zero ore non ha blocchi, e deve restare
    # (è una dichiarazione-ferma: vedi la regola di scarto più sotto).
    # Il join sulla `settimana` regge perché `consuntivi.settimana` è sempre il
    # lunedì (`_lunedi` in scrittura, verificato nella migration f1a2b3c4d5e6).
    #
    # Task e Progetto con JOIN ESPLICITI + `contains_eager`, non `joinedload`:
    # quest'ultimo aggancia le tabelle con alias anonimi, su cui l'ORDER BY più
    # sotto non può appoggiarsi. Stessa query unica, stesse relazioni caricate.
    # OUTER come il `joinedload` che sostituiscono: nessuna riga esce dal
    # risultato per effetto del join.
    q_cons = session.query(Consuntivo, OreSettimanali.c.ore).outerjoin(
        Consuntivo.task
    ).outerjoin(
        Task.progetto
    ).options(
        contains_eager(Consuntivo.task).contains_eager(Task.progetto)
    ).outerjoin(OreSettimanali, and_(
        OreSettimanali.c.task_id == Consuntivo.task_id,
        OreSettimanali.c.dipendente_id == Consuntivo.dipendente_id,
        OreSettimanali.c.settimana == Consuntivo.settimana,
    )).filter(
        Consuntivo.settimana >= lun_date,
        Consuntivo.settimana <= ven_date,
    )
    # Il perimetro si applica sul DIPENDENTE e non sul progetto del task, ed è
    # una scelta: un dipendente del gruppo che ha lavorato anche su un progetto
    # altrui va mostrato per intero, con tutte le sue ore. Filtrando per
    # progetto il PM vedrebbe una settimana mutilata — «Marco: 12h» quando ne
    # ha fatte 38 — e il confronto con le ore contrattuali, che è metà del
    # senso di questa vista, direbbe il falso.
    if perimetro_dipendenti is not None:
        q_cons = q_cons.filter(Consuntivo.dipendente_id.in_(perimetro_dipendenti or [""]))
    # ORDER BY esplicito, e non è cosmetico. Senza, l'«ordine di arrivo» qui
    # sotto era l'ordine FISICO delle righe, che nessuno garantisce: bastava
    # un piano diverso per cambiarlo. È successo davvero — l'outer join sulla
    # vista ha fatto scegliere a Postgres un hash join e i task dentro
    # `ore_per_task` sono usciti rimescolati (verificato: stessi valori, ordine
    # diverso).
    #
    # PROGETTO → NOME DEL TASK, ed è l'ordine che l'utente VEDE: VistaPM e
    # VistaManagement rendono `ore_per_task` così come arriva, senza sort lato
    # client (VistaPM lo divide in «con segnale» / «sole ore», e dentro ciascun
    # gruppo l'ordine resta questo). I task finiscono raggruppati sotto
    # l'etichetta-progetto che ogni riga mostra. Il progetto per `id`, come
    # `gantt_strutturato`. `Task.id` in coda solo come spareggio fra omonimi.
    # L'ordine delle PERSONE non dipende da qui: lo fissa il `sorted` finale.
    cons_sett = q_cons.order_by(Progetto.id, Task.nome, Task.id).all()

    # Raggruppa per dipendente_id (mantiene l'ordine di arrivo, come
    # `unique()` su pandas Series).
    cons_per_dip = {}
    for c, ore in cons_sett:
        cons_per_dip.setdefault(c.dipendente_id, []).append((c, float(ore or 0)))

    risultato = []
    for did, lista_cons in cons_per_dip.items():
        try:
            dip = get_dipendente(did)
        except (IndexError, KeyError):
            continue
        ore_per_task = []
        totale = 0
        n_segnalazioni = n_fermi = n_ritardo = 0
        for c, ore in lista_cons:
            t = c.task
            if t is None:
                continue
            # ── LA REGOLA DI SCARTO, ROVESCIATA (07/09/2026) ─────────────
            # Prima: `if c.ore_dichiarate > 0`. Le righe a ZERO ore venivano
            # buttate — cioè esattamente le dichiarazioni-ferme, «sono fermo,
            # zero ore, ecco perché», che sono il contenuto per cui la
            # vista-PM esiste. Storicamente sono 386 righe su 2.635 (15%).
            #
            # Lo scarto aveva anche un secondo effetto, più insidioso: chi
            # aveva SOLO righe a zero ore restava con `ore_per_task` vuoto,
            # non entrava in `risultato` e finiva fra i NON-COMPILANTI pur
            # avendo risposto. «Compilato» significava «ha dichiarato ore»,
            # non «ha risposto». Ora significa la seconda, che è la domanda
            # che la vista pone.
            proj = t.progetto
            in_ritardo = task_in_ritardo(t.data_fine, t.stato, oggi)
            ore_per_task.append({
                # `task_id` e `progetto_id` non c'erano: senza, nessun
                # drill-down è agganciabile e i nomi sono un vicolo cieco.
                "task_id": t.id,
                "task_nome": t.nome,
                "progetto_id": t.progetto_id,
                "progetto": proj.nome if proj else "?",
                "ore": ore,
                # ── Il CONTENUTO della dichiarazione ─────────────────────
                # È ciò che la vista-management non ha mai portato: sole ore,
                # e le ore non dicono cosa sta succedendo.
                # `percentuale` e `ore_effettive` stavano qui: uscite col passo
                # 5.5, nessun client le leggeva e le colonne escono al 5.6.
                "nota": c.nota,
                # Il campo della A (04/09): questa vista è il suo primo lettore.
                "ore_stimate_residue": c.ore_stimate_residue,
                "stato_dichiarato": c.stato_dichiarato,
                "stato_task": t.stato,
                "data_fine": t.data_fine.isoformat() if t.data_fine else None,
                "in_ritardo": in_ritardo,
                "presa_visione": bool(c.presa_visione),
            })
            totale += ore
            # Conteggi calcolati QUI e non lato client: il management riceve
            # lo stesso payload del PM ma lo rende come sintesi, e una sintesi
            # non può ricavarsi contando righe che si è deciso di non mostrare.
            if c.nota:
                n_segnalazioni += 1
            if c.stato_dichiarato == "Bloccato":
                n_fermi += 1
            if in_ritardo:
                n_ritardo += 1

        # `lista_cons` e non `ore_per_task`: una persona entra se ha una riga,
        # anche a zero ore. Vedi il rovesciamento qui sopra.
        if lista_cons:
            risultato.append({
                "dipendente_id": did,
                "nome": dip["nome"],
                "profilo": dip["profilo"],
                "ore_contrattuali": int(dip["ore_sett"]),
                # 2 decimali: somma di ore da blocchi (NUMERIC(5,2)), come in /me.
                "totale_ore": round(totale, 2),
                "ore_per_task": ore_per_task,
                "compilato": True,
                # I conteggi della sintesi. Il management li legge in cima e
                # apre il dettaglio solo dove c'è qualcosa; il PM legge il
                # dettaglio e basta. Stesso payload, due letture.
                "n_segnalazioni": n_segnalazioni,
                "n_fermi": n_fermi,
                "n_in_ritardo": n_ritardo,
            })

    # Aggiungi dipendenti che NON hanno compilato (con almeno 1 task attivo).
    # Conteggio task attivi per dipendente fatto in UNA query aggregata,
    # invece di un filtro DataFrame per ciascuno.
    q_dip = session.query(Dipendente).options(joinedload(Dipendente.ruolo_rel)).filter(Dipendente.attivo == True)
    # IL PERIMETRO VALE ANCHE QUI, ed è la metà che si dimentica. Senza, un PM
    # vedrebbe correttamente solo le PROPRIE dichiarazioni ma continuerebbe a
    # vedere l'intera anagrafica aziendale fra i non-compilanti: 4 compilanti
    # suoi e 14 «mancanti» che non sono affar suo. Il gruppo si deriva dai TASK
    # sui progetti diretti (`dipendenti_con_task_su`) e non dai consuntivi —
    # chi non ha compilato non ha righe, e partendo da quelle sarebbe invisibile
    # proprio nel momento in cui lo si cerca.
    if perimetro_dipendenti is not None:
        q_dip = q_dip.filter(Dipendente.id.in_(perimetro_dipendenti or [""]))
    dipendenti_attivi = q_dip.all()
    task_count_rows = session.query(
        Task.dipendente_id, func.count(Task.id)
    ).filter(
        Task.stato.in_(["In corso", "Da iniziare"])
    ).group_by(Task.dipendente_id).all()
    task_count = {row[0]: row[1] for row in task_count_rows}
    session.close()

    ids_gia_presenti = {r["dipendente_id"] for r in risultato}
    for d in dipendenti_attivi:
        if d.id in ids_gia_presenti:
            continue
        if task_count.get(d.id, 0) > 0:
            risultato.append({
                "dipendente_id": d.id,
                "nome": d.nome,
                "profilo": d.ruolo_rel.nome if d.ruolo_rel else "",
                "ore_contrattuali": int(d.ore_sett),
                "totale_ore": 0,
                "ore_per_task": [],
                "compilato": False,
                "n_segnalazioni": 0,
                "n_fermi": 0,
                "n_in_ritardo": 0,
            })

    return sorted(risultato, key=lambda x: (-x["compilato"], x["nome"]))


@router.get("/me")
def consuntivi_settimana_me(
    settimana: Optional[str] = Query(
        None,
        description="Lunedì della settimana in ISO (YYYY-MM-DD). Assente = "
                    "settimana corrente. Ammesse solo la corrente e la "
                    "precedente; qualsiasi giorno della settimana è accettato "
                    "e viene normalizzato al lunedì.",
    ),
    current_user: Utente = Depends(get_current_user),
):
    """Vista PERSONALE (Layout A'): «ecco cosa era previsto per te in questa
    settimana». Self intrinseco: il dipendente è l'utente loggato, niente
    parametro `dipendente_id`.

    Parte dai TASK del dipendente (non dai Consuntivi): la lista
    `task_settimana` contiene sempre i task da compilare, con le ore già
    dichiarate attaccate (0 se non ancora compilato). La logica riusabile
    sta in data.task_settimana_dipendente (la userà anche la Home-utente).

    Il param `settimana` serve all'indietro: chi non ha compilato entro
    domenica deve poter tornare sulla settimana scorsa, e chi ha sbagliato
    deve potersi correggere. Si ferma lì — non si compila in anticipo e non si
    riscrive un mese fa. La normalizzazione al lunedì passa da
    data.lunedi_settimana (la stessa regola della scrittura: mai ricalcolarla
    qui).

    La settimana scorsa si apre in lettura E in scrittura finché è la scorsa
    (fix N17): la finestra è temporale, le ore già dichiarate non la chiudono.
    La guardia sulla scrittura sta su POST /salva, non qui.
    """
    if not current_user.dipendente_id:
        raise HTTPException(400, "Utente non collegato a un dipendente")

    try:
        dip = get_dipendente(current_user.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    disponibili = settimane_selezionabili(current_user.dipendente_id)

    if settimana is None:
        lun = lunedi_settimana()
    else:
        try:
            lun = lunedi_settimana(settimana)
        except ValueError:
            raise HTTPException(
                400,
                f"Settimana '{settimana}' non è una data ISO valida "
                f"(atteso YYYY-MM-DD)",
            )
        ammesse = [s["lunedi"] for s in disponibili]
        if lun.isoformat() not in ammesse:
            raise HTTPException(
                400,
                f"Settimana '{lun.isoformat()}' non consultabile: sono "
                f"ammesse solo la corrente e la precedente "
                f"({', '.join(ammesse)})",
            )

    task_settimana = task_settimana_dipendente(current_user.dipendente_id, lun)
    totale = sum(t["ore_consumate"] for t in task_settimana)

    # C'ERA ANCHE `unita`: la settimana già impacchettata nella forma esatta del
    # payload di /salva-blocchi, costruita al passo 3 perché la griglia la
    # rimandasse così com'era. La griglia ha poi scelto di costruirsi il payload
    # da `task_settimana`, che le serve comunque per disegnare le righe, e
    # `unita` non l'ha letta mai nessuno: è uscita col passo 5.5 insieme a
    # `compilato`, che aveva la stessa storia.
    return {
        "dipendente_id": current_user.dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "settimana": lun.isoformat(),
        "settimane_disponibili": disponibili,
        # 2 decimali come le ore da cui è sommato (vedi `ore_consumate`).
        "totale_ore": round(totale, 2),
        "task_settimana": task_settimana,
    }


# ═════════════════════════════════════════════════════════════════════════
# POST /api/consuntivi/salva-blocchi — l'unica porta di scrittura
# ═════════════════════════════════════════════════════════════════════════
# Nato al passo 3 accanto a POST /salva, che ha affiancato finché la griglia
# non è stata pronta. /salva è uscito col passo 5.3 (23/09/2026): da allora
# le ore entrano da qui e da nessun altro posto.

def _settimana_scrivibile(dipendente_id, settimana_raw):
    """Lunedì della settimana richiesta, se il dipendente può scriverci; 400
    altrimenti. Le regole sono quelle dello strato dati (`lunedi_settimana`,
    `settimane_selezionabili`): qui c'è solo la loro traduzione in errori.
    Una sola regola da tradurre — la finestra corrente+precedente (N17): la
    settimana scade col calendario, non col monte ore.

    Fino al passo 5.3 questa traduzione esisteva in DUE copie, qui e dentro la
    route di POST /salva, tenute uguali a mano: era il prezzo dichiarato del
    far convivere le due porte (D7). Uscita quella porta, è rimasta una.
    """
    try:
        lun = lunedi_settimana(settimana_raw)
    except ValueError:
        raise HTTPException(
            400,
            f"Settimana '{settimana_raw}' non è una data ISO valida "
            f"(atteso YYYY-MM-DD)",
        )
    disponibili = [s["lunedi"] for s in settimane_selezionabili(dipendente_id)]
    if lun.isoformat() not in disponibili:
        raise HTTPException(
            400,
            f"Settimana '{lun.isoformat()}' fuori dalla finestra: puoi "
            f"consuntivare solo questa settimana e la precedente "
            f"({', '.join(disponibili)})",
        )
    return lun


@router.post("/salva-blocchi")
def salva_blocchi_endpoint(
    req: SalvaBlocchiRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Salva le ore a blocchi dell'utente loggato per una settimana.

    SOLO PER SÉ. Non c'è `dipendente_id` nel body e non c'è deroga per il
    manager: consuntivare è un atto in prima persona, nessuno intesta ore a un
    altro. (Il vecchio /salva ha ancora il Pattern Y: esce con lui al passo 5.)

    Le validazioni in tre tempi, ognuno un 400 che elenca TUTTE le violazioni
    del suo livello, e nulla viene scritto se uno qualsiasi fallisce (N15):
      1. il body (DTO `SalvaBlocchiRequest`);
      2. la settimana (N17) e i giorni rispetto alla settimana e a oggi (N1, N2);
      3. il database: appartenenza delle unità (N13), task scomposti (M8/M9),
         tetto delle 24h (N14) — nello strato dati, dentro la stessa sessione
         che poi scrive.
    """
    dipendente_id = current_user.dipendente_id
    if not dipendente_id:
        raise HTTPException(400, "Utente non collegato a un dipendente")
    try:
        get_dipendente(dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    lun = _settimana_scrivibile(dipendente_id, req.settimana)

    # N2 / N1 — i giorni: dentro lunedì-venerdì della settimana, e non nel
    # futuro. Qui e non nel DTO perché servono la settimana normalizzata e il
    # confronto con oggi.
    oggi = date.today()
    ven = lun + timedelta(days=4)
    errori = []
    for u in req.unita:
        for b in u.blocchi or []:
            if not (lun <= b.giorno <= ven):
                errori.append(
                    f"{u.tipo} {u.id}: il giorno {b.giorno} non è fra lunedì e "
                    f"venerdì della settimana {lun.isoformat()}"
                )
            elif b.giorno > oggi:
                errori.append(
                    f"{u.tipo} {u.id}: il giorno {b.giorno} è nel futuro, si "
                    f"dichiarano solo ore già lavorate"
                )
    if errori:
        raise HTTPException(400, "Consuntivo non salvato: " + "; ".join(errori))

    unita = [
        {
            "tipo": u.tipo,
            "id": u.id,
            "blocchi": (None if "blocchi" not in u.model_fields_set
                        else [(b.giorno, b.ore) for b in u.blocchi]),
            "tocca_stato": "stato_dichiarato" in u.model_fields_set,
            "stato": u.stato_dichiarato,
            "tocca_nota": "nota" in u.model_fields_set,
            "nota": u.nota,
            "tocca_residuo": "ore_stimate_residue" in u.model_fields_set,
            "residuo": u.ore_stimate_residue,
            # Niente `tocca_`: per la presa visione assente e null coincidono
            # («non toccare»), e lo decide il valore da solo.
            "presa_visione": u.presa_visione,
        }
        for u in req.unita
    ]
    try:
        esito = salva_blocchi_settimana(dipendente_id, lun, unita)
    except ConsuntivoNonValido as e:
        raise HTTPException(400, "Consuntivo non salvato: " + "; ".join(e.errori))

    # `avvisi`: segnalazioni non bloccanti — oggi la propagazione dello stato su
    # un task fallita dopo il commit («ore salvate, stato non riportato,
    # riprova»). Lista vuota nel caso normale, sempre presente.
    return {
        "salvato": True,
        "settimana": lun.isoformat(),
        "avvisi": esito["avvisi"],
    }
