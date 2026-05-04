# SECURITY_BACKLOG.md

Difese di sicurezza e modello di autorizzazione del GANTT Agent.
Documento vivo: traccia ciò che è implementato, ciò che è posticipato e ciò che va valutato.

**Stato:** ✅ implementato | ⏭ posticipato a R2 | 🔭 long-term | ⚠️ da decidere

**Ultimo aggiornamento:** 4 maggio 2026 (pomeriggio)
**Autore:** Ludovica Di Cianni con Claude (sessioni 29 aprile + 4 maggio 2026)

---

## 1. Modello di autorizzazione

### ✅ Implementato in R1 (RBAC duale + filtri)

Sistema **RBAC** (Role-Based Access Control) con due ruoli:

- **`user`** — accesso ai propri task, propria consuntivazione, profilo, dettaglio sé stesso. **NON** vede GANTT aziendale, lista progetti, Economia, Configurazione, Risorse.
- **`manager`** — accesso completo (Configurazione, Pipeline, Economia, GANTT aziendale, Risorse, modifica GANTT, scenario)

**Implementazione:**
- Campo `ruolo_app` nella tabella `utenti` (enum: `user` | `manager`)
- Dependency FastAPI `get_current_user` (autenticato) e `require_manager` (autorizzato)
- Distinzione **401** (non autenticato) vs **403** (non autorizzato)
- Pattern **self-or-manager** già applicato in:
  - `GET /api/dipendenti/{id}` — user vede solo se stesso, manager vede tutti
  - `GET /api/tasks` — user vede solo i propri task (filtro nel corpo), manager vede tutto

**Filosofia "Scenario B" adottata** (decisione del 4 maggio dopo conferma con memoria di Andrea/Vincenzo):
> Il dipendente vede solo le proprie cose. Il GANTT aziendale, la lista progetti, l'Economia, le Risorse aggregate sono manager-only. Questo riflette la cultura IMC: "questo è un servizio di Consuntivazione per il dipendente e di organizzazione per PM/Management".

### ⏭ R2 — Evoluzione a ABAC su progetto (PM-on-project)

**Bisogno emerso da Francesco (28 aprile 2026):** in IMC non esistono team consolidati, ma quando nascono per progetto sarà necessario che **uno o più membri del team diventino PM di quel progetto specifico** e possano modificarne deliverable, vedere economia parziale, ecc. Persone come Cosimo o Daniele non diventeranno mai PM.

**Modello target:**
- Aggiungere campo `pm_id` (FK utenti, nullable) sulla tabella `Progetto` per "un PM principale" — sufficiente nella maggior parte dei casi
- Quando emergerà bisogno di team multipli con ruoli (PM, team_member, osservatore): introdurre tabella M2M `progetto_membri (progetto_id, utente_id, ruolo_progetto, attivo, assegnato_da, assegnato_il)`

**Stima R2 completo (RBAC duale → RBAC + ABAC):** 3-4 giornate concentrate.

### 🔭 R3 (eventuale, se commerciale) — Multi-role groups

**Bisogno potenziale:** se l'app diventa prodotto vendibile a clienti enterprise (con strutture organizzative complesse, decine/centinaia di dipendenti, ruoli sovrapposti).

**Modello:** tabelle `gruppi`, `permessi`, `gruppi_permessi`, `utenti_gruppi`. I permessi della persona = unione dei permessi di tutti i suoi gruppi.

**Riferimento:** pattern visto da Roberto in altro progetto (low-code) il 4 maggio 2026. Sistema dove una persona appartiene a uno o più gruppi e i permessi si sommano.

**Coesistenza con ABAC:** ABAC su progetto (`progetto_membri`) **non viene sostituito** ma resta complementare.

**Stima R3:** 1-2 settimane concentrate, escluso lavoro UI di gestione permessi.

### 🟡 Preparazione gratuita per R1 (consigliata, non urgente)

Tre piccoli interventi che non rallentano R1 e accorciano R2:

1. **Aggiungere campo `pm_id` (nullable) sulla tabella `Progetto`** già in R1.
2. **Helper interno `_user_can_modify_project(user, progetto_id)`** negli endpoint che riguardano un progetto. Per R1 ritorna `user.ruolo_app == "manager"`. In R2 si modifica in un solo posto.
3. **Convenzione di scrittura nei commenti/commit:** usare esplicitamente la parola "RBAC" nei punti dove è applicato un controllo ruolo. Es. `# RBAC: solo manager — TODO R2: ABAC con pm_id`.

### ❌ NON implementiamo (decisioni esplicite)

- **"Vista Economia overview pubblica" per trasparenza interna.** Considerato e scartato (Vincenzo l'ha pensata come pagina management; IMC è 15 persone con AD molto presente, la trasparenza passa via parole, non via UI).

### Riferimenti

Per il blueprint completo del modello permessi (lista permessi astratti, mapping gruppi, decision tree), vedi `docs/AUTH_MODEL.md`.

---

## 2. Field-level authorization (R2/R3)

**Riferimento:** input di Roberto Pezzuto (4 maggio 2026) — concetto citato in un altro progetto IMC, da considerare standard per app gestionali con dati sensibili.

**Concetto:** la protezione di un endpoint controlla *se* l'utente può accederci. La field-level authorization controlla *cosa* l'utente vede della response. Sono due livelli complementari.

### Esempio pratico

Quando in R2 Helena (user, eventualmente PM) potrà chiamare `GET /api/progetti/{id}` perché PM del progetto, la response potrebbe contenere:
- `nome`, `cliente`, `data_inizio`, `data_fine`, `stato`, `fasi`, `task` — **OK per Helena**
- `valore_contratto`, `budget_ore`, `costo_ora_medio` — **non OK per Helena** (informazione "pruriginosa")

In R1 il problema non si pone perché `/api/progetti/{id}` è manager-only. In R2 con ABAC, **la response deve essere filtrata in base al ruolo del chiamante**.

### Pattern di implementazione

```python
def serializza_progetto(progetto: Progetto, user: Utente) -> dict:
    """Serializza un progetto rispettando i permessi del chiamante."""
    base = {
        "id": progetto.id,
        "nome": progetto.nome,
        "cliente": progetto.cliente,
    }
    if has_permission(user, "economia.read") or has_permission(user, "progetti.read_economia"):
        base["valore_contratto"] = progetto.valore_contratto
        base["budget_ore"] = progetto.budget_ore
    return base
```

### Campi che richiedono field-level authorization

| Entità | Campo | Visibile a |
|---|---|---|
| Progetto | `valore_contratto` | manager, amministrazione |
| Progetto | `budget_ore` | manager, amministrazione, PM del progetto |
| Progetto | `costo_medio_ora`, `margine_*` | manager, amministrazione |
| Dipendente | `costo_ora` | manager, amministrazione |
| Dipendente | `email` (privata) | self only o manager |
| Dipendente | `saturazione_pct` | self o manager |
| Consuntivo | `note` (campo libero) | self o manager |

**Stima implementazione:** ~1 giornata in R2 quando si introduce ABAC.

---

## 3. Auth — brute force su /login

### ✅ Implementato in R1
- Hash **bcrypt** per password (lento di proposito, ~200ms per tentativo, salt automatico per ogni password)
- JWT firmato **HS256** in cookie **httpOnly + SameSite=Lax + Secure(prod)**
- Durata token **8 ore**
- **Rate limiting per IP:** 5 tentativi/minuto su `/login` via slowapi
- **Rate limiting per email:** 5 tentativi/minuto sull'account (helper custom con sliding window in-memory). Difesa contro botnet che bombarda un singolo account da molti IP.
- Stesso messaggio "Credenziali non valide" per email-non-esistente vs password-sbagliata (anti **user enumeration**)
- SECRET_KEY in `.env`, `.env` in `.gitignore`

### ⏭ R2 / produzione

- **Account lockout temporaneo dopo N fallimenti consecutivi** (~2 ore)
- **CAPTCHA condizionale** dopo 3 tentativi falliti se app esposta a internet (~3-4 ore)
- **Logging dei tentativi falliti** per monitoring e audit (~1 ora)
- **Migrazione storage rate-limit a Redis** (oggi in-memory) — necessario con multi-worker o load balancer (~3 ore)

### 🔭 Long-term

- **Anomaly detection** (login da paese/orario insoliti, velocità non umana). Roba enterprise.

---

## 4. Auth — JWT

### ✅ Implementato in R1
- Token in cookie **httpOnly** (non leggibile da JavaScript → difesa contro XSS)
- **SameSite=Lax** (difesa CSRF di base)
- Durata **8 ore** (compromesso UX/sicurezza per uso lavorativo)
- SECRET_KEY in `.env`, `.env` in `.gitignore`

### ⏭ R2

- **CSRF token completo** (Synchronizer Token Pattern) oltre SameSite=Lax — necessario se l'app va su internet pubblico
- **RS256** se l'architettura diventa multi-servizio
- **Refresh token** se la durata 8h diventa scomoda
- **Migrazione `passlib` → `bcrypt` diretto** (passlib non più mantenuto da fine 2023)
- **Rotazione chiavi JWT** con finestra di transizione

### Versione mobile (R2 / R3)

Se l'app diventerà mobile (avatar vocale in auto, ecc.):
- **PWA**: i cookie httpOnly funzionano normalmente, nessuna modifica
- **App nativa**: token in keychain del dispositivo (più sicuro di httpOnly stesso). L'endpoint `/api/auth/login` resta lo stesso, cambia solo dove il client salva il token

---

## 5. Database

### ⏭ R2 / produzione
- **Encryption at rest** (SQLCipher per SQLite, o Postgres con TDE/pgcrypto)
- **Backup automatici cifrati** con rotazione
- **Audit log** di accessi a Economia/Configurazione/dati costo orario

---

## 6. HTTPS / deploy

### ⏭ Prima del primo deploy reale

- **HTTPS obbligatorio** (Let's Encrypt gratuito)
- **HSTS** header per forzare HTTPS lato browser
- **`COOKIE_SECURE=True`** in `.env` di produzione
- **CORS `allow_origins`** ristretto al dominio reale
- Esposizione del backend solo dietro reverse proxy (nginx/caddy/traefik)

---

## 7. Codice / processi

### ⏭ R2

- **Migrazione a Alembic** per gestire schema db senza `rm imcgroup.db && python seed.py`
- **Logging strutturato** (JSON, livelli, correlation ID)
- **Sanitizzazione esplicita** degli input testuali liberi (React di default escapa, ma `dangerouslySetInnerHTML` riapre la falla)
- **Validazione lato backend ovunque** ✅ già pratica adottata (Pydantic)

### ⏭ Pre-rilascio commerciale

- **Audit di sicurezza esterno** prima di esposizione pubblica
- **Penetration testing** mirato
- **Conformità GDPR** (dati dipendenti = dati personali)

---

## 8. Stress test / crash test

### ⚠️ Da pianificare in sessione dedicata prima di R1

Nota di Ludovica (4 maggio 2026): pensare a stress test "classici" su software simile.

**Strumenti candidati:** [Locust](https://locust.io) (Python, semplice) o [k6](https://k6.io) (JavaScript, più potente).

**Endpoint critici da testare sotto carico:**
- `/api/auth/login` — verifica comportamento del rate limiting sotto attacco distribuito
- `/api/gantt` e `/api/dipendenti` — letture pesanti, stress della cache contesto IA
- `/api/agent/chat` — Gemini latency + cache, costo per token
- `/api/scenario/simula` — operazione complessa, time budget

**Scenari da simulare:**
- 50 utenti concorrenti che chiamano `/api/gantt`
- 10 utenti concorrenti che fanno login con password sbagliata (verifica 429 scatta)
- 5 utenti che fanno scrittura concorrente sullo stesso progetto (SQLite locking)

**Metriche:** latency p50/p95/p99, throughput, errori 5xx, CPU/memoria.

**Da pianificare:** ~mezza giornata.

---

## 9. Layer semantico (R2)

Discussione del 29 aprile con Francesco: **promemoria/note di contesto a fianco mentre si pianifica un nuovo GANTT** è una feature che lui apprezza molto.

### Per R1
Cattura le note (campo "perché?" nei consuntivi, note progetto, lessons learned) come **testo libero** in db relazionale. Salva metadata di contesto (cliente, progetto_id, dipendente_id, data, tipo) in **colonne separate** per indicizzazione futura.

### Per R2 — opzioni considerate

- **A — Vector database con embeddings** (Chroma, Qdrant, pgvector + Gemini). Pro: integrazione naturale con Gemini, RAG. Contro: paradigma nuovo.
- **B — MongoDB / document database**. Pro: schema flessibile. Contro: meno potente per ricerca semantica.
- **C — Neo4J / knowledge graph**. Pro: navigazione relazioni complesse. Contro: complesso, infrastruttura aggiuntiva.

**Decisione:** ⚠️ rinviata. Ludovica vuole valutare anche MongoDB/Neo4J vs embeddings prima di decidere.

---

## 10. Continuità tra chat / handoff

Nota di Ludovica (4 maggio 2026): **il progetto attraversa molte chat con Claude per ragioni di token/contesto.**

**Pratiche adottate:**
- Handoff strutturato a fine giornata densa (`HANDOFF_v10.md`, `HANDOFF_v11.md`...)
- Prompt iniziale standardizzato per ogni nuova chat
- Documenti "vivi" committati su Git: `SECURITY_BACKLOG.md`, `HANDOFF_v*.md`, `docs/AUTH_MODEL.md`
- Decisioni di design importanti annotate **subito** mentre sono fresche

**Da fare:**
- Considerare un `DESIGN_DECISIONS.md` separato per le decisioni architetturali
- Considerare `SCRIPTS_README.md` in `backend/scripts/` quando ci sarà accumulo di script utility

---

## Notes

Sviluppatrice: Ludovica Di Cianni
Stakeholders di riferimento:
- **Vincenzo Carolla** (CEO, vision di prodotto)
- **Roberto Pezzuto** (Manager IT, input cybersecurity 21 aprile + multi-role groups + field-level authorization 4 maggio 2026)
- **Andrea Morstabilini** (input architettura 2 aprile 2026; "il dipendente deve vedere solo le sue cose")
- **Francesco Carolla** (Resp. amministrazione, input business model 28 aprile + 4 maggio 2026: bandi come tipologia di progetto, attività commerciale)

Storia del documento:
- 29 aprile 2026: prima versione (post sessione JWT 1-6)
- 4 maggio 2026 mattino: aggiunta sezione ABAC, stress test, layer semantico, continuità chat
- 4 maggio 2026 pomeriggio: filosofia Scenario B confermata, field-level authorization (Roberto), multi-role groups (R3), pattern self-or-manager implementato in R1

---

## Riferimenti

- `docs/AUTH_MODEL.md` — blueprint dettagliato modello permessi (R1 → R2 → R3)
- `HANDOFF_v11.md` — stato di consegna 29 aprile (verrà aggiornato a v12 oggi/domani)
- `backend/auth.py`, `backend/auth_routes.py`, `backend/deps.py` — implementazione R1
