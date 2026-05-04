# AUTH_MODEL.md — Disegno del modello di autorizzazione

Documento di blueprint per l'evoluzione del sistema di permessi del GANTT Agent.
Non descrive cosa è implementato in R1, ma cosa **potrebbe diventare** quando il bisogno emergerà.

**Stato:** disegno preliminare, non implementato
**Versione:** 1.0
**Data:** 4 maggio 2026
**Autore:** Ludovica Di Cianni con Claude

---

## Indice

1. [Stato attuale R1: RBAC duale](#stato-attuale-r1)
2. [Evoluzione R2: ABAC su progetto](#evoluzione-r2)
3. [Evoluzione R3 (eventuale): multi-role groups](#evoluzione-r3)
4. [Lista permessi astratti proposta](#lista-permessi-astratti)
5. [Mapping permessi → endpoint](#mapping-permessi-endpoint)
6. [Decision tree: quando passare da uno stadio all'altro](#decision-tree)

---

## Stato attuale R1

**Modello:** RBAC duale tramite campo stringa `Utente.ruolo_app`.

**Ruoli:**
- `user` — accesso ai propri task, propria consuntivazione, profilo
- `manager` — accesso completo (Configurazione, Pipeline, Economia, modifica GANTT, scenario)

**Pro:**
- Semplice da capire e implementare
- Sufficiente per IMC con 15 persone, struttura piatta
- Test rapidi: due utenti seed con due ruoli coprono tutti i casi

**Contro:**
- Granularità grossolana
- Non distingue "PM operativo di un progetto" da "manager strategico"
- Non scala se IMC cresce o se l'app diventa multi-tenant

---

## Evoluzione R2

**Modello:** RBAC duale + ABAC su progetto.

**Bisogno di business identificato (Francesco, 28 aprile 2026):**
> In IMC non esistono team consolidati, ma quando nascono per progetto è necessario che uno o più membri diventino PM di quel progetto specifico e possano modificarne deliverable, vedere economia parziale, ecc. Persone come Cosimo o Daniele non diventeranno mai PM.

**Cambiamenti al modello dati:**

Opzione A — Singolo PM per progetto (semplice):
```
Progetto:
  - id, nome, ...
  - pm_id (FK utenti, nullable)  ← nuovo campo
```

Opzione B — Team multipli con ruoli (più scalabile):
```
ProgettoMembri (tabella M2M):
  - id (PK)
  - progetto_id (FK Progetto)
  - utente_id (FK Utente)
  - ruolo_progetto (enum: 'pm', 'team_member', 'osservatore')
  - attivo (bool, soft delete)
  - assegnato_da (FK Utente, audit)
  - assegnato_il (datetime)
```

**Cambiamenti alla logica di autorizzazione:**

Nuova dependency factory:
```python
def require_pm_or_manager(progetto_id: str):
    """Manager globale OPPURE PM del progetto specifico."""
    def _check(user: Utente = Depends(get_current_user), db = Depends(get_db)):
        if user.ruolo_app == "manager":
            return user
        # Check: l'utente è PM di questo progetto?
        if _is_pm_of(db, user.id, progetto_id):
            return user
        raise HTTPException(403, "Non sei PM di questo progetto")
    return _check
```

**Endpoint che usano la nuova dependency:**
- `PATCH /api/progetti/{progetto_id}` — modifica progetto
- `POST /api/fasi` (su progetto specifico) — aggiunge fasi
- `POST /api/task/applica` (su progetto specifico) — modifica task del progetto
- `POST /api/scenario/simula` (su progetto specifico)
- Eventualmente `GET /api/economia/margini/{progetto_id}` se vogliamo dare al PM la vista economica del SUO progetto

**Endpoint che restano `require_manager`:**
- Tutti i CRUD di Configurazione (ruoli, dipendenti, competenze)
- `GET /api/economia/margini` (lista globale, sempre manager-only)
- `GET /api/risorse/suggerisci-bilanciamento` (vista globale)

**Stima implementazione R2:** 3-4 giornate concentrate.

---

## Evoluzione R3

**Modello:** multi-role groups con permessi astratti (livello "enterprise").

**Trigger:** quando l'app passa da uso interno a **prodotto multi-tenant** vendibile a clienti con strutture organizzative complesse.

**Cambiamenti al modello dati:**

```
Permesso:
  - codice (PK, es. "economia.read", "pipeline.write")
  - descrizione

Gruppo:
  - id (PK)
  - nome (es. "Direzione", "PM", "Amministrazione", "IT Admin")
  - descrizione

GruppoPermessi (M2M):
  - gruppo_id
  - permesso_codice

UtenteGruppi (M2M):
  - utente_id
  - gruppo_id
```

**Logica di autorizzazione:**

```python
def require_permission(permission_code: str):
    """L'utente ha il permesso (via almeno uno dei suoi gruppi)?"""
    def _check(user: Utente = Depends(get_current_user), db = Depends(get_db)):
        if _user_has_permission(db, user.id, permission_code):
            return user
        raise HTTPException(403, f"Permesso richiesto: {permission_code}")
    return _check
```

Endpoint:
```python
@router.get("/api/economia/margini")
def economia_margini(_: Utente = Depends(require_permission("economia.read"))):
    ...
```

**Vantaggi:**
- I permessi sono atomici e riusabili
- I gruppi compongono permessi
- Una persona in più gruppi ha l'**unione** dei permessi
- Aggiungere un nuovo gruppo o permesso non richiede tocchi al codice degli endpoint
- UI di gestione permessi è generica (non hardcoded)

**Coesistenza con ABAC:**
ABAC su progetto (tabella `ProgettoMembri`) **non viene sostituito**. Resta come meccanismo per "questo PM su questo progetto specifico". I permessi globali via gruppi e i permessi su risorsa via ABAC sono **complementari**.

Esempio: un endpoint `PATCH /api/progetti/{id}` può richiedere:
- O permesso globale `progetti.modify` (manager generale)
- O membership PM su quel progetto specifico

**Stima implementazione R3:** 1-2 settimane concentrate, escluso lavoro UI di gestione permessi.

---

## Lista permessi astratti

Proposta di nomenclatura per i permessi quando si arriverà a R3. **Convenzione:** `dominio.azione`.

### Configurazione (admin)
- `config.read` — vedi tabelle ruoli, dipendenti, competenze, fasi catalogo
- `config.write` — crea/modifica/elimina entità di Configurazione

### Progetti (Pipeline)
- `progetti.read` — vedi lista progetti, dettagli
- `progetti.create` — crea nuovo progetto
- `progetti.modify` — modifica progetto esistente
- `progetti.delete` — elimina progetto (soft delete)
- `progetti.read_economia` — vedi dati economici del progetto (margini)

### Fasi e task
- `fasi.read` — vedi fasi di un progetto
- `fasi.write` — crea/modifica/elimina fasi
- `tasks.read` — vedi task
- `tasks.write` — crea/modifica/elimina task
- `tasks.assign` — assegna task a un dipendente

### Consuntivazione
- `consuntivi.read_self` — vedi propri consuntivi
- `consuntivi.read_all` — vedi consuntivi di tutti
- `consuntivi.write_self` — modifica propri consuntivi
- `consuntivi.write_all` — modifica consuntivi di chiunque (manager/admin)

### Economia
- `economia.read_self` — vedi economia dei propri progetti (PM)
- `economia.read_all` — vedi economia di tutti i progetti (manager)
- `economia.write` — modifica costi orari, marginalità (admin/direzione)

### Risorse e bilanciamento
- `risorse.read` — vedi heatmap, saturazione
- `risorse.suggest_balance` — chiedi suggerimenti di bilanciamento

### Scenario
- `scenario.simulate` — esegui simulazioni
- `scenario.confirm` — applica scenari simulati al GANTT

### IA
- `ai.chat` — usa il chatbot
- `ai.suggest` — chiedi suggerimenti su task/fasi
- `ai.analyze` — analisi GANTT proattiva

### Attività interne
- `attivita.read_self` / `attivita.write_self`
- `attivita.read_all` / `attivita.write_all`

---

## Mapping gruppi → permessi (proposta R3)

Esempio di come si potrebbero strutturare i gruppi per IMC:

| Gruppo | Permessi |
|---|---|
| **Dipendente base** | `consuntivi.read_self`, `consuntivi.write_self`, `attivita.read_self`, `attivita.write_self`, `tasks.read` (sui propri), `progetti.read` (sui propri) |
| **PM** | tutti i precedenti + `progetti.modify` (sui propri), `fasi.write`, `tasks.write` (sui propri progetti), `tasks.assign`, `economia.read_self`, `scenario.simulate`, `ai.chat`, `ai.suggest` |
| **Amministrazione** | `economia.read_all`, `economia.write`, `consuntivi.read_all`, `attivita.read_all` |
| **IT Admin** | `config.read`, `config.write` |
| **Direzione** | tutti i permessi |

**Nota:** una persona può appartenere a più gruppi e i permessi si sommano. Es. Roberto = "Dipendente base" + "PM" + "IT Admin" → ha l'unione dei tre.

---

## Decision tree

Quando passare da R1 (RBAC duale) a stadi successivi?

**Resta in R1 (RBAC duale) se:**
- IMC continua a usare l'app internamente con strutture relativamente piatte
- I "PM di progetto" possono essere gestiti come `manager` globali (con la cautela umana che non vedano cose di altri progetti)
- L'app non viene venduta a clienti esterni

**Passa a R2 (ABAC su progetto) se:**
- Diventa frustrante che un PM "manager" veda tutto invece che solo il suo progetto
- Si vuole audit pulito: "chi ha modificato cosa di chi"
- Si vuole che la sidebar/UI mostri "I miei progetti" per i PM
- L'app resta interna o viene venduta a clienti piccoli (< 50 dipendenti)

**Passa a R3 (multi-role groups) se:**
- L'app diventa prodotto vendibile a clienti enterprise
- I clienti hanno strutture organizzative complesse (es. 100+ dipendenti, divisioni, ruoli sovrapposti)
- Si vogliono permessi granulari configurabili dal cliente stesso senza toccare codice
- Si introduce multi-tenancy

**Trigger non tecnologici (anche solo uno è sufficiente):**
- Vincenzo conferma che l'app andrà a clienti esterni
- Un primo cliente esterno paga per usarla
- Si presenta in conferenze, demo, materiali commerciali

---

## Implicazioni di pricing/commerciale (R3)

Se si arriva a R3, considerare:
- **Tier free / standard:** RBAC duale (semplice)
- **Tier enterprise:** multi-role groups + ABAC + audit log + SSO

Questa è una **strategia di prodotto**, non solo tecnica. Da discutere con Vincenzo quando il momento sarà maturo.

---

## Storico decisioni

- **4 maggio 2026:** Ludovica decide di restare su RBAC duale per R1. Disegno R2/R3 documentato qui per evoluzione futura. La decisione è incrementale: si valuterà di nuovo quando R1 sarà consegnato e R2 partirà.

---

## Riferimenti incrociati

- `SECURITY_BACKLOG.md` — sezione 1 "Modello di autorizzazione"
- `backend/deps.py` — dependency attuali (R1)
- `backend/auth.py` — utility hash + JWT
- `HANDOFF_v11.md` — handoff di chiusura R1 (in evoluzione)
