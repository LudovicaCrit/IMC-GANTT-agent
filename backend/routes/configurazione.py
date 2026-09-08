"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/configurazione.py — Router per endpoint /api/config
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone i CRUD admin della pagina Configurazione del frontend. Cinque
famiglie di entità anagrafiche e di catalogo:
  - Ruoli (RBAC system: admin/manager/user)
  - Competenze (lista piatta di 33 voci attuali, R2: forse categorizzate)
  - Dipendenti (anagrafica completa con ruolo + competenze + costo orario)
  - Fasi standard (template di fasi per duplicare in nuovi progetti)
  - Fasi catalogo (lista piatta di fasi disponibili per pianificazione)
Tutti gli endpoint sono manager-only (RBAC semplice, niente Pattern Y
perché stiamo lavorando su entità globali, non su dati dipendente-specifici).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────────────┬──────────┬─────────────────┐
│ Path                                         │ Metodo   │ Auth            │
├──────────────────────────────────────────────┼──────────┼─────────────────┤
│ /api/config/ruoli                            │ GET      │ require_manager │
│ /api/config/ruoli                            │ POST     │ require_manager │
│ /api/config/ruoli/{ruolo_id}                 │ PATCH    │ require_manager │
│ /api/config/ruoli/{ruolo_id}                 │ DELETE   │ require_manager │
│ /api/config/competenze                       │ GET      │ require_manager │
│ /api/config/competenze                       │ POST     │ require_manager │
│ /api/config/competenze/{comp_id}             │ DELETE   │ require_manager │
│ /api/config/dipendenti                       │ GET      │ require_manager │
│ /api/config/dipendenti                       │ POST     │ require_manager │
│ /api/config/dipendenti/{dip_id}              │ PATCH    │ require_manager │
│ /api/config/dipendenti/{dip_id}              │ DELETE   │ require_manager │
│ /api/config/fasi-standard                    │ GET      │ require_manager │
│ /api/config/fasi-standard                    │ POST     │ require_manager │
│ /api/config/fasi-standard/{fs_id}            │ DELETE   │ require_manager │
│ /api/config/fasi-catalogo                    │ GET      │ require_manager │
│ /api/config/fasi-catalogo                    │ POST     │ require_manager │
│ /api/config/fasi-catalogo/{fase_id}          │ DELETE   │ require_manager │
└──────────────────────────────────────────────┴──────────┴─────────────────┘

DETTAGLIO PER FAMIGLIA
──────────────────────

== RUOLI ==
1-4. CRUD completo (GET/POST/PATCH/DELETE).
   - Ruoli sono le 3 categorie RBAC: admin, manager, user.
   - DELETE è soft (set attivo=False), non hard delete.
   - Vincolo unicità su `nome`.

== COMPETENZE ==
5-7. CR + Soft Delete (no PATCH per scelta — le competenze hanno solo nome).
   - Lista piatta di 33 elementi (oggi). R2: decisione aperta su
     categorizzazione (gerarchia + livelli).
   - DELETE soft (set attivo=False).

== DIPENDENTI (CRUD arricchito) ==
8-11. CRUD completo: lista con dati aggregati (ruolo, competenze, costo,
     sede, email), POST con generazione automatica ID (D001, D002...) e
     associazione M2M competenze, PATCH che aggiorna anche le competenze
     M2M, DELETE soft.

== FASI STANDARD (template) ==
12-14. Template di fasi raggruppati per nome template. GET restituisce
     dict {template_nome: [fasi]}. Hard DELETE.

== FASI CATALOGO ==
15-17. Lista piatta di fasi disponibili per la pianificazione. Internamente
     stoccate in FaseStandard con `template_nome="_catalogo"` come trucco
     di organizzazione (un solo "template" speciale = il catalogo). Se il
     catalogo è vuoto, il GET fa fallback estraendo tutti i nomi unici dai
     template esistenti. Vincolo unicità sul nome.

PATTERN AUTH USATI
──────────────────
- `require_manager`: tutti gli endpoint sono pura amministrazione di
  cataloghi globali, niente Pattern Y / Scenario B.

DIPENDENZE
──────────
- `models`: `get_session` (per accesso SQLAlchemy diretto), `Utente`,
  `Ruolo`, `Competenza`, `Dipendente`, `DipendentiCompetenze`,
  `FaseStandard`.
- `deps`: `require_manager`.
- `sqlalchemy.func`: per query MAX su id Dipendente e Ordine FaseStandard.

NOTE TECNICHE
─────────────
Questo router NON usa i DataFrame `_DIPENDENTI()` / `_PROGETTI()` / ecc.
perché lavora direttamente con SQLAlchemy via `get_session()`. Questo è
corretto: la Configurazione modifica le anagrafiche di base, e i
DataFrame sono cache dei dati operativi. Quando una scrittura completa,
i DataFrame andranno invalidati al prossimo `_reload()` automatico.

DTO replicati nel file (precedentemente in main.py):
  - RuoloRequest
  - CompetenzaRequest
  - DipendenteCfgRequest
  - FaseStandardRequest
  - FaseCatalogoRequest

📌 TODO Pulizia DTO orfani: rimuovere queste 5 classi da main.py nel
commit dedicato post-refactoring.

📌 TODO R2 / Roberto:
  - Multi-role groups: un dipendente potrebbe appartenere a più gruppi
    (es. "PM" + "Sviluppatore"). Modello dati attuale: 1 ruolo per
    dipendente. R3 cambia tutto questo.
  - Field-level authorization: oggi è manager-vede-tutto, R2 vorrà
    granulare (es. costo_ora visibile solo a HR).

STORIA
──────
Estratto da main.py il 6 maggio 2026 nell'ambito del refactoring strangler.
È il quinto e penultimo blocco da migrare (restano agent.py, scenario.py,
fasi.py per chiudere il refactoring).
═══════════════════════════════════════════════════════════════════════════
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from deps import require_manager
from models import (
    get_session,
    Utente, Ruolo, Competenza, Dipendente, Azienda,
    DipendentiCompetenze, FaseStandard, TIPI_RUOLO,
)


# ── DTO ──────────────────────────────────────────────────────────────────
class RuoloRequest(BaseModel):
    nome: str
    descrizione: str = ""


class CompetenzaRequest(BaseModel):
    nome: str


class DipendenteCfgRequest(BaseModel):
    nome: str
    profilo: str
    # OPZIONALE nel DTO, OBBLIGATORIO alla creazione — e la differenza non è una
    # scappatoia. Questo DTO è condiviso da POST e PATCH: `Dipendente.azienda_id`
    # è NOT NULL e alla creazione va per forza deciso, ma in modifica il campo
    # può mancare e significa «non cambiare azienda». Dichiararlo obbligatorio
    # qui farebbe fallire con 422 ogni PATCH del form — che non lo manda e che
    # oggi funziona: si aggiusterebbe l'azione rotta rompendo quella sana.
    # La guardia sta quindi in `crea_dipendente`, dove il caso è distinguibile.
    azienda_id: int | None = None
    ruolo_id: int | None = None
    ore_sett: int = 40
    costo_ora: float | None = None
    email: str = ""
    sede: str = ""
    competenze: list[str] = []


class FaseStandardRequest(BaseModel):
    template_nome: str
    fase_nome: str
    ordine: int = 1
    percentuale_ore: float | None = None


class FaseCatalogoRequest(BaseModel):
    nome: str


# ── Router ───────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["configurazione"])


# ═════════════════════════════════════════════════════════════════════════
# RUOLI — CRUD completo
# ═════════════════════════════════════════════════════════════════════════

@router.get("/ruoli")
def lista_ruoli(
    tipo: str | None = None,
    _: Utente = Depends(require_manager),
):
    """Lista ruoli attivi ordinati per nome. `?tipo=base|funzionale` per filtrare.

    OGNI RUOLO PORTA IL SUO `tipo` NEL PAYLOAD, e il filtro è opzionale. La
    scelta non è indifferente, perché i tre consumatori vogliono cose diverse:

      form dipendente, select «Inquadramento» → solo i 'base'
      Cantiere, tendina «Profilo richiesto»   → TUTTI (un task può chiedere 'PM')
      Configurazione → TabRuoli               → TUTTI, col tipo da mostrare

    Il filtro non ha default restrittivo: senza parametro l'endpoint risponde
    come ha sempre risposto. Restringere il default avrebbe silenziosamente
    tolto voci a Cantiere e a TabRuoli, che non hanno chiesto niente.

    Un valore di `tipo` fuori dai due ammessi è un 422, non una lista vuota: una
    lista vuota si legge come «non ci sono ruoli», che è la risposta giusta a
    una domanda diversa da quella posta.
    """
    if tipo is not None and tipo not in TIPI_RUOLO:
        raise HTTPException(
            422, f"tipo '{tipo}' non valido: ammessi {', '.join(TIPI_RUOLO)}"
        )
    session = get_session()
    q = session.query(Ruolo).filter(Ruolo.attivo == True)
    if tipo is not None:
        q = q.filter(Ruolo.tipo == tipo)
    ruoli = q.order_by(Ruolo.nome).all()
    result = [
        {"id": r.id, "nome": r.nome, "descrizione": r.descrizione or "", "tipo": r.tipo}
        for r in ruoli
    ]
    session.close()
    return result


@router.post("/ruoli")
def crea_ruolo(req: RuoloRequest, _: Utente = Depends(require_manager)):
    """Crea un nuovo ruolo. 400 se nome duplicato."""
    session = get_session()
    existing = session.query(Ruolo).filter(Ruolo.nome == req.nome).first()
    if existing:
        session.close()
        raise HTTPException(400, f"Ruolo '{req.nome}' esiste già")
    ruolo = Ruolo(nome=req.nome, descrizione=req.descrizione)
    session.add(ruolo)
    session.commit()
    result = {"id": ruolo.id, "nome": ruolo.nome}
    session.close()
    return result


@router.patch("/ruoli/{ruolo_id}")
def modifica_ruolo(ruolo_id: int, req: RuoloRequest, _: Utente = Depends(require_manager)):
    """Modifica nome e/o descrizione di un ruolo. 404 se non trovato."""
    session = get_session()
    ruolo = session.query(Ruolo).filter(Ruolo.id == ruolo_id).first()
    if not ruolo:
        session.close()
        raise HTTPException(404, "Ruolo non trovato")
    ruolo.nome = req.nome
    if req.descrizione:
        ruolo.descrizione = req.descrizione
    session.commit()
    session.close()
    return {"ok": True}


@router.delete("/ruoli/{ruolo_id}")
def elimina_ruolo(ruolo_id: int, _: Utente = Depends(require_manager)):
    """Soft delete: imposta attivo=False (non hard delete)."""
    session = get_session()
    ruolo = session.query(Ruolo).filter(Ruolo.id == ruolo_id).first()
    if not ruolo:
        session.close()
        raise HTTPException(404, "Ruolo non trovato")
    ruolo.attivo = False
    session.commit()
    session.close()
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════
# COMPETENZE — CR + Soft Delete
# ═════════════════════════════════════════════════════════════════════════

@router.get("/competenze")
def lista_competenze(_: Utente = Depends(require_manager)):
    """Lista competenze attive ordinate per nome."""
    session = get_session()
    comps = session.query(Competenza).filter(Competenza.attivo == True).order_by(Competenza.nome).all()
    result = [{"id": c.id, "nome": c.nome} for c in comps]
    session.close()
    return result


@router.post("/competenze")
def crea_competenza(req: CompetenzaRequest, _: Utente = Depends(require_manager)):
    """Crea una nuova competenza. 400 se nome duplicato."""
    session = get_session()
    existing = session.query(Competenza).filter(Competenza.nome == req.nome).first()
    if existing:
        session.close()
        raise HTTPException(400, f"Competenza '{req.nome}' esiste già")
    comp = Competenza(nome=req.nome)
    session.add(comp)
    session.commit()
    result = {"id": comp.id, "nome": comp.nome}
    session.close()
    return result


@router.delete("/competenze/{comp_id}")
def elimina_competenza(comp_id: int, _: Utente = Depends(require_manager)):
    """Soft delete: imposta attivo=False."""
    session = get_session()
    comp = session.query(Competenza).filter(Competenza.id == comp_id).first()
    if not comp:
        session.close()
        raise HTTPException(404, "Competenza non trovata")
    comp.attivo = False
    session.commit()
    session.close()
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════
# DIPENDENTI — CRUD arricchito (con ruolo, competenze M2M, costo_ora)
# ═════════════════════════════════════════════════════════════════════════

@router.get("/aziende")
def lista_aziende(_: Utente = Depends(require_manager)):
    """Le aziende del gruppo, per il selettore del form-dipendente.

    Endpoint nuovo (07/09/2026): `Azienda` è una TABELLA, non due costanti.
    Oggi contiene IMC-Improve e Innovation Plaza, ma il seed la costruisce dai
    dati (`nomi_azienda` unisce le due canoniche a quelle referenziate), quindi
    un terzo ramo del gruppo comparirebbe in DB senza che nessuno tocchi il
    codice. Un `<select>` con due voci cablate nel frontend non lo vedrebbe, e
    il primo assunto di quel ramo sarebbe ininseribile.
    """
    session = get_session()
    aziende = session.query(Azienda).order_by(Azienda.nome).all()
    result = [{"id": a.id, "nome": a.nome} for a in aziende]
    session.close()
    return result


@router.get("/dipendenti")
def lista_dipendenti_config(_: Utente = Depends(require_manager)):
    """Dipendenti con ruolo, competenze, costo_ora per la pagina Configurazione.

    Diverso da `/api/dipendenti` (in routes/dipendenti.py) che restituisce
    info aggregate operative (carico, saturazione, progetti). Questo
    restituisce l'anagrafica completa da editare.
    """
    session = get_session()
    dips = session.query(Dipendente).filter(Dipendente.attivo == True).order_by(Dipendente.nome).all()
    result = []
    for d in dips:
        comps = session.query(Competenza.nome).join(DipendentiCompetenze).filter(
            DipendentiCompetenze.dipendente_id == d.id
        ).all()
        result.append({
            "id": d.id,
            "nome": d.nome,
            "profilo": d.profilo,
            "ruolo_id": d.ruolo_id,
            "ore_sett": d.ore_sett,
            "costo_ora": d.costo_ora,
            "email": d.email or "",
            "sede": d.sede or "",
            # `azienda_id` serve al form in MODIFICA: senza, il selettore non
            # potrebbe mostrare l'azienda attuale e ogni salvataggio la
            # rimanderebbe indietro vuota (= «non cambiare»), rendendo lo
            # spostamento fra aziende impossibile proprio dove si edita.
            # `azienda` (il nome) evita al client una seconda lettura per
            # mostrare l'etichetta in elenco.
            "azienda_id": d.azienda_id,
            "azienda": d.azienda_rel.nome if d.azienda_rel else None,
            "competenze": [c[0] for c in comps],
        })
    session.close()
    return result


def _associa_competenze(session, dipendente_id, nomi):
    """Associa alla M2M le competenze IN CATALOGO. Restituisce i nomi SCARTATI.

    Il comportamento non cambia: un nome fuori catalogo continua a non essere
    associato, ed è giusto — `dipendenti_competenze` ha una FK verso
    `competenze` e non può rappresentare un nome che non esiste.

    CAMBIA CHE LO SCARTO SI VEDE. Prima i due punti di scrittura facevano
    `if comp:` e tiravano dritto: il nome finiva nella colonna JSON
    `Dipendente.competenze` (testo libero, accetta tutto) e NON nella M2M, senza
    che nessuno lo sapesse. È così che oggi 4 dipendenti su 18 hanno le due
    sorgenti divergenti — `IA`, `analisi`, `archivio`, `organizzazione` esistono
    solo dalla parte sbagliata del doppione, e nessuno se n'è accorto per mesi.
    Non è un errore da bloccare: è una domanda da porre («questa competenza va
    censita, o è un refuso?»), e finché resta muta nessuno la pone.

    NON decide nulla sulle 4 orfane già in DB, e non tocca dati esistenti:
    rende solo rumoroso lo scarto da qui in avanti.

    AGGIORNAMENTO (08/09/2026, recisione del doppione): la colonna JSON non si
    scrive più — né qui né in creazione né nel seed. Quindi la frase sopra vale
    per la storia, non per il presente: un nome fuori catalogo oggi non «finisce
    nel JSON», non finisce da nessuna parte. Lo scarto è passato da invisibile-
    ma-recuperabile a visibile-e-definitivo, ed è il motivo per cui la
    segnalazione ora è l'unica rete rimasta.

    Un helper e non due copie del ciclo: erano già identici in POST e PATCH, e
    una segnalazione scritta due volte è una segnalazione che prima o poi
    esiste in un ramo solo.
    """
    scartati = []
    for nome in nomi:
        comp = session.query(Competenza).filter(Competenza.nome == nome).first()
        if comp:
            session.add(DipendentiCompetenze(
                dipendente_id=dipendente_id, competenza_id=comp.id
            ))
        else:
            scartati.append(nome)
            logger.warning(
                "Competenza '%s' non in catalogo: NON associata al dipendente %s "
                "e NON salvata da nessuna parte — il nome è perso. "
                "Censirla in Configurazione → Competenze e rifare il salvataggio, "
                "oppure toglierla dal profilo.",
                nome, dipendente_id,
            )
    return scartati


def _avvisi_competenze(scartati):
    """Gli scarti in forma leggibile, per il payload di risposta.

    Stessa convenzione di `salva_consuntivo`, che ritorna `{ok, avvisi}`: lista
    VUOTA nel caso normale, così il client non deve distinguere «campo assente»
    da «nessun avviso».

    DA QUANDO IL JSON NON SI SCRIVE PIÙ, QUESTI AVVISI PESANO DI PIÙ. Prima uno
    scarto era invisibile ma recuperabile: il nome restava nella colonna JSON e
    si poteva ripescarlo. Ora la M2M è l'unica destinazione, e un nome fuori
    catalogo non viene salvato da nessuna parte — chi lo ha digitato lo vede
    sparire al salvataggio successivo. L'avviso è l'unica cosa che glielo dice,
    e il form ANCORA NON LO MOSTRA (`await create(form)` ignora la risposta):
    mostrarlo è una riga di frontend, ed è diventata la più utile del giro.
    """
    return [
        f"Competenza '{n}' non è in catalogo e NON è stata salvata. "
        f"Censiscila in Configurazione → Competenze e risalva il profilo, "
        f"altrimenti il nome va perso."
        for n in scartati
    ]


def _azienda_valida_o_422(session, azienda_id, obbligatoria):
    """Verifica che l'azienda esista. Alza 422 PARLANTE, mai 500.

    `POST /config/dipendenti` era rotto da sempre: il DTO non aveva
    `azienda_id`, l'endpoint non lo passava, e `Dipendente.azienda_id` è NOT
    NULL — quindi ogni creazione moriva sul flush con un `NotNullViolation`,
    cioè un 500 opaco su un vincolo che il chiamante non poteva nemmeno vedere
    nel contratto dell'API. Creare un dipendente dalla Configurazione non ha
    mai funzionato.

    Le due domande sono separate perché lo sono davvero:
      - «manca?»       → solo alla creazione è un errore (in modifica significa
                         «lascia l'azienda com'è»);
      - «esiste?»      → sempre, in entrambe. Un id inesistente violerebbe la
                         FK, e una FK violata è di nuovo un 500.
    """
    if azienda_id is None:
        if obbligatoria:
            aziende = session.query(Azienda).order_by(Azienda.id).all()
            raise HTTPException(
                422,
                "azienda_id è obbligatorio: ogni dipendente appartiene a "
                "un'azienda del gruppo. Valori ammessi: "
                + ", ".join(f"{a.id} ({a.nome})" for a in aziende),
            )
        return None
    az = session.query(Azienda).filter(Azienda.id == azienda_id).first()
    if az is None:
        aziende = session.query(Azienda).order_by(Azienda.id).all()
        raise HTTPException(
            422,
            f"azienda_id {azienda_id} non esiste. Valori ammessi: "
            + ", ".join(f"{a.id} ({a.nome})" for a in aziende),
        )
    return az


@router.post("/dipendenti")
def crea_dipendente(req: DipendenteCfgRequest, _: Utente = Depends(require_manager)):
    """Crea un nuovo dipendente con ID generato automaticamente (D001, D002...).

    Associa anche le competenze M2M se passate nel payload.
    """
    session = get_session()
    # PRIMA di generare l'id: se l'azienda non va bene, non si crea niente e
    # non si consuma un numero della sequenza.
    try:
        _azienda_valida_o_422(session, req.azienda_id, obbligatoria=True)
    except HTTPException:
        session.close()
        raise
    # Genera prossimo ID seguendo il formato DXXX
    max_id = session.query(func.max(Dipendente.id)).scalar()
    if max_id and max_id.startswith("D") and max_id[1:].isdigit():
        next_num = int(max_id[1:]) + 1
    else:
        next_num = 1
    new_id = f"D{next_num:03d}"

    dip = Dipendente(
        id=new_id, nome=req.nome, profilo=req.profilo,
        azienda_id=req.azienda_id,
        ruolo_id=req.ruolo_id, ore_sett=req.ore_sett,
        costo_ora=req.costo_ora, email=req.email, sede=req.sede,
        # `competenze` (JSON) NON si scrive più: la M2M è l'unica sorgente.
        # La colonna resta in tabella, inerte, finché il 'PM' delle 5 persone
        # non è ricollocato nel modello ruoli-funzionali; da qui in avanti non
        # riceve più valori, così non può tornare a divergere dalla M2M.
    )
    session.add(dip)
    session.flush()

    # Associa competenze M2M (gli scarti tornano al chiamante, non spariscono)
    scartati = _associa_competenze(session, new_id, req.competenze)

    session.commit()
    session.close()
    return {"id": new_id, "nome": req.nome, "avvisi": _avvisi_competenze(scartati)}


@router.patch("/dipendenti/{dip_id}")
def modifica_dipendente(dip_id: str, req: DipendenteCfgRequest, _: Utente = Depends(require_manager)):
    """Modifica un dipendente esistente, incluse le competenze M2M.

    Le competenze vengono prima TUTTE rimosse (per il dipendente) e poi
    riassociate da capo: garantisce coerenza tra payload e db.
    """
    session = get_session()
    dip = session.query(Dipendente).filter(Dipendente.id == dip_id).first()
    if not dip:
        session.close()
        raise HTTPException(404, "Dipendente non trovato")

    # `azienda_id` assente = «non cambiare», l'unico campo con questa
    # convenzione perché è l'unico che il form non manda. Se arriva, si valida
    # e si applica: spostare una persona fra IMC-Improve e Innovation Plaza
    # diventa possibile, e prima non lo era da nessuna parte.
    try:
        _azienda_valida_o_422(session, req.azienda_id, obbligatoria=False)
    except HTTPException:
        session.close()
        raise
    if req.azienda_id is not None:
        dip.azienda_id = req.azienda_id

    dip.nome = req.nome
    dip.profilo = req.profilo
    dip.ruolo_id = req.ruolo_id
    dip.ore_sett = req.ore_sett
    dip.costo_ora = req.costo_ora
    dip.email = req.email
    dip.sede = req.sede
    # `dip.competenze` (JSON) NON si aggiorna più: vedi la nota in creazione.
    # Il valore già in colonna resta com'è — fossile, non più letto da nessuno.

    # Aggiorna competenze M2M: cancella tutte e ri-aggiungi
    session.query(DipendentiCompetenze).filter(
        DipendentiCompetenze.dipendente_id == dip_id
    ).delete()
    scartati = _associa_competenze(session, dip_id, req.competenze)

    session.commit()
    session.close()
    return {"ok": True, "avvisi": _avvisi_competenze(scartati)}


@router.delete("/dipendenti/{dip_id}")
def elimina_dipendente(dip_id: str, _: Utente = Depends(require_manager)):
    """Soft delete: imposta attivo=False. Lascia M2M intatti per audit."""
    session = get_session()
    dip = session.query(Dipendente).filter(Dipendente.id == dip_id).first()
    if not dip:
        session.close()
        raise HTTPException(404, "Dipendente non trovato")
    dip.attivo = False
    session.commit()
    session.close()
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════
# FASI STANDARD — Template raggruppati
# ═════════════════════════════════════════════════════════════════════════

@router.get("/fasi-standard")
def lista_fasi_standard(_: Utente = Depends(require_manager)):
    """Restituisce i template raggruppati per nome template.

    Output: {template_nome: [{id, fase_nome, ordine, percentuale_ore}, ...]}
    """
    session = get_session()
    fasi = session.query(FaseStandard).order_by(FaseStandard.template_nome, FaseStandard.ordine).all()
    templates = {}
    for f in fasi:
        if f.template_nome not in templates:
            templates[f.template_nome] = []
        templates[f.template_nome].append({
            "id": f.id,
            "fase_nome": f.fase_nome,
            "ordine": f.ordine,
            "percentuale_ore": f.percentuale_ore,
        })
    session.close()
    return templates


@router.post("/fasi-standard")
def crea_fase_standard(req: FaseStandardRequest, _: Utente = Depends(require_manager)):
    """Crea una nuova fase in un template (esistente o nuovo)."""
    session = get_session()
    fs = FaseStandard(
        template_nome=req.template_nome,
        fase_nome=req.fase_nome,
        ordine=req.ordine,
        percentuale_ore=req.percentuale_ore,
    )
    session.add(fs)
    session.commit()
    result = {"id": fs.id, "template_nome": req.template_nome, "fase_nome": req.fase_nome}
    session.close()
    return result


@router.delete("/fasi-standard/{fs_id}")
def elimina_fase_standard(fs_id: int, _: Utente = Depends(require_manager)):
    """Hard delete della fase standard (non soft delete come per anagrafiche)."""
    session = get_session()
    fs = session.query(FaseStandard).filter(FaseStandard.id == fs_id).first()
    if not fs:
        session.close()
        raise HTTPException(404, "Fase standard non trovata")
    session.delete(fs)
    session.commit()
    session.close()
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════
# FASI CATALOGO — Lista piatta per pianificazione (template "_catalogo")
# ═════════════════════════════════════════════════════════════════════════

@router.get("/fasi-catalogo")
def lista_fasi_catalogo(_: Utente = Depends(require_manager)):
    """Lista piatta di fasi disponibili per la pianificazione.

    Internamente stoccate in FaseStandard con template_nome="_catalogo".
    Se il catalogo è vuoto, fallback estraendo nomi unici dai template
    esistenti — utile per migration progressiva.
    """
    session = get_session()
    fasi = session.query(FaseStandard).filter(
        FaseStandard.template_nome == "_catalogo"
    ).order_by(FaseStandard.ordine).all()

    # Fallback se catalogo vuoto: estrai nomi unici dai template
    if not fasi:
        fasi_template = session.query(FaseStandard).order_by(FaseStandard.ordine).all()
        nomi_visti = set()
        result = []
        for f in fasi_template:
            if f.fase_nome not in nomi_visti:
                nomi_visti.add(f.fase_nome)
                result.append({"id": f.id, "nome": f.fase_nome, "ordine": f.ordine})
        session.close()
        return result

    result = [{"id": f.id, "nome": f.fase_nome, "ordine": f.ordine} for f in fasi]
    session.close()
    return result


@router.post("/fasi-catalogo")
def crea_fase_catalogo(req: FaseCatalogoRequest, _: Utente = Depends(require_manager)):
    """Aggiunge una fase al catalogo. 400 se nome duplicato."""
    session = get_session()
    # Controlla duplicati
    existing = session.query(FaseStandard).filter(
        FaseStandard.template_nome == "_catalogo",
        FaseStandard.fase_nome == req.nome
    ).first()
    if existing:
        session.close()
        raise HTTPException(400, f"Fase '{req.nome}' esiste già")

    # Trova prossimo ordine
    max_ordine = session.query(func.max(FaseStandard.ordine)).filter(
        FaseStandard.template_nome == "_catalogo"
    ).scalar() or 0

    fs = FaseStandard(
        template_nome="_catalogo",
        fase_nome=req.nome,
        ordine=max_ordine + 1,
    )
    session.add(fs)
    session.commit()
    result = {"id": fs.id, "nome": fs.fase_nome, "ordine": fs.ordine}
    session.close()
    return result


@router.delete("/fasi-catalogo/{fase_id}")
def elimina_fase_catalogo(fase_id: int, _: Utente = Depends(require_manager)):
    """Hard delete della fase catalogo."""
    session = get_session()
    fs = session.query(FaseStandard).filter(FaseStandard.id == fase_id).first()
    if not fs:
        session.close()
        raise HTTPException(404, "Fase non trovata")
    session.delete(fs)
    session.commit()
    session.close()
    return {"ok": True}
