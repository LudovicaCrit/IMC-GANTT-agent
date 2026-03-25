-- ══════════════════════════════════════════════════════════════════════
-- IMC-Group GANTT Agent — Schema Database PostgreSQL
-- Versione: 1.0 — 25 marzo 2026
-- 
-- Principi:
--   • Schema ricco (meglio campi vuoti che ristrutturare dopo)
--   • Il frontend non cambia — cambia solo la sorgente dati nel backend
--   • carico_settimanale_dipendente resta calcolo al volo (sufficiente per ~15 persone)
--   • Le competenze sono JSON array (non vale normalizzare per team piccolo)
-- ══════════════════════════════════════════════════════════════════════

-- ── TIPI ENUM ────────────────────────────────────────────────────────

CREATE TYPE stato_progetto AS ENUM (
    'In bando',
    'Vinto - Da pianificare',
    'In esecuzione',
    'Sospeso',
    'Completato'
);

CREATE TYPE priorita_livello AS ENUM ('alta', 'media', 'bassa');

CREATE TYPE stato_task AS ENUM (
    'Da iniziare',
    'In corso',
    'Completato',
    'Sospeso'
    -- NOTA: "Bloccato" non è qui. Lo stato task-settimana si traccia
    -- nei consuntivi (campo motivo_fermo). Vedi nota G4 nel vademecum.
);

CREATE TYPE tipo_dipendenza AS ENUM ('FS', 'SS', 'FF');
-- FS = Finish-to-Start (B inizia dopo che A finisce) — default
-- SS = Start-to-Start (B inizia quando inizia A) — parallelismo
-- FF = Finish-to-Finish (B finisce quando finisce A)
-- SF omesso: rarissimo, la struttura lo supporta se servisse

CREATE TYPE fonte_segnalazione AS ENUM ('chatbot', 'manuale', 'simulazione', 'sistema');

CREATE TYPE stato_segnalazione AS ENUM ('aperta', 'in_analisi', 'risolta', 'archiviata');

CREATE TYPE modalita_lavoro AS ENUM ('sede', 'remoto');

CREATE TYPE tipo_progetto AS ENUM ('progetto', 'bando');

CREATE TYPE ruolo_assegnazione AS ENUM ('responsabile', 'supporto');


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: dipendenti
-- ══════════════════════════════════════════════════════════════════════
-- Anagrafica del team. ~15 persone oggi, scalabile.
-- Le competenze sono JSON array: ["sviluppo", "AI/ML", "cloud"]
-- Il campo 'attivo' gestisce chi esce senza cancellare dati storici.

CREATE TABLE dipendenti (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(100) NOT NULL,
    profilo         VARCHAR(60)  NOT NULL,        -- "Tecnico Senior", "Project Manager", ecc.
    ore_sett        SMALLINT     NOT NULL DEFAULT 40,
    costo_ora       NUMERIC(8,2),                 -- riservato management / economia
    competenze      JSONB        DEFAULT '[]',    -- ["sviluppo", "cloud", "AI/ML"]
    sede            VARCHAR(40),                  -- "Milano", "Puglia"
    email           VARCHAR(120),
    data_assunzione DATE,
    attivo          BOOLEAN      NOT NULL DEFAULT TRUE,
    note            TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dipendenti_attivo ON dipendenti (attivo);
CREATE INDEX idx_dipendenti_profilo ON dipendenti (profilo);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: progetti
-- ══════════════════════════════════════════════════════════════════════
-- Ciclo di vita: In bando → Vinto → In esecuzione → Completato/Sospeso
-- Il campo priorità è decisione del management, non calcolato.
-- responsabile_id = il PM di riferimento del progetto.

CREATE TABLE progetti (
    id                  SERIAL PRIMARY KEY,
    nome                VARCHAR(150) NOT NULL,
    cliente             VARCHAR(150),
    stato               stato_progetto   NOT NULL DEFAULT 'In esecuzione',
    tipo                tipo_progetto    NOT NULL DEFAULT 'progetto',
    priorita            priorita_livello NOT NULL DEFAULT 'media',
    data_inizio         DATE,
    data_fine            DATE,
    budget_ore          INTEGER,                  -- ore totali previste
    valore_contratto    NUMERIC(12,2),            -- € — riservato management
    descrizione         TEXT,
    fase_corrente       VARCHAR(80),              -- "Sviluppo", "Design", "Preparazione bando"
    sede                VARCHAR(40),              -- sede principale del progetto
    responsabile_id     INTEGER REFERENCES dipendenti(id),
    scadenza_bando      DATE,                     -- solo per tipo='bando'
    motivo_sospensione  TEXT,                     -- solo per stato='Sospeso'
    lezioni_apprese     TEXT,                     -- per archivio / knowledge base
    note                TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_progetti_stato ON progetti (stato);
CREATE INDEX idx_progetti_tipo ON progetti (tipo);
CREATE INDEX idx_progetti_responsabile ON progetti (responsabile_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: task
-- ══════════════════════════════════════════════════════════════════════
-- L'unità di lavoro dentro un progetto.
-- L'assegnazione delle persone NON è qui — è nella tabella assegnazioni
-- (per supportare multi-persona, punto I3 del vademecum).
-- Le dipendenze NON sono qui — sono nella tabella dipendenze_task
-- (per supportare dipendenze multiple e tipi FS/SS/FF).

CREATE TABLE task (
    id              SERIAL PRIMARY KEY,
    progetto_id     INTEGER      NOT NULL REFERENCES progetti(id) ON DELETE CASCADE,
    nome            VARCHAR(200) NOT NULL,
    fase            VARCHAR(60),                  -- "Analisi", "Design", "Sviluppo", "Testing", ecc.
    ore_stimate     INTEGER,
    data_inizio     DATE,
    data_fine       DATE,
    stato           stato_task   NOT NULL DEFAULT 'Da iniziare',
    profilo_richiesto VARCHAR(60),                -- profilo ideale, non vincolo rigido
    ordine          SMALLINT,                     -- per ordinamento nella visualizzazione
    note            TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_progetto ON task (progetto_id);
CREATE INDEX idx_task_stato ON task (stato);
CREATE INDEX idx_task_date ON task (data_inizio, data_fine);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: dipendenze_task
-- ══════════════════════════════════════════════════════════════════════
-- Relazione: task_id dipende da predecessore_id con un tipo (FS/SS/FF).
-- Un task può avere più predecessori (dipendenze multiple).
-- Vincolo UNIQUE per evitare duplicati.

CREATE TABLE dipendenze_task (
    id              SERIAL PRIMARY KEY,
    task_id         INTEGER         NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    predecessore_id INTEGER         NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    tipo            tipo_dipendenza NOT NULL DEFAULT 'FS',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_dipendenza UNIQUE (task_id, predecessore_id),
    CONSTRAINT chk_no_self_dep CHECK (task_id <> predecessore_id)
);

CREATE INDEX idx_dipendenze_task ON dipendenze_task (task_id);
CREATE INDEX idx_dipendenze_pred ON dipendenze_task (predecessore_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: assegnazioni
-- ══════════════════════════════════════════════════════════════════════
-- Collega task a dipendenti. Supporta multi-persona (punto I3).
-- ore_assegnate: quante ore di quel task sono a carico di questa persona
--   (es. task da 200h con 2 persone → 100h ciascuna)
-- ruolo: "responsabile" o "supporto" (opzionale, utile per l'agente)

CREATE TABLE assegnazioni (
    id              SERIAL PRIMARY KEY,
    task_id         INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    dipendente_id   INTEGER NOT NULL REFERENCES dipendenti(id) ON DELETE CASCADE,
    ore_assegnate   INTEGER,                      -- NULL = tutte le ore del task
    ruolo           ruolo_assegnazione DEFAULT 'responsabile',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_assegnazione UNIQUE (task_id, dipendente_id)
);

CREATE INDEX idx_assegnazioni_task ON assegnazioni (task_id);
CREATE INDEX idx_assegnazioni_dipendente ON assegnazioni (dipendente_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: consuntivi
-- ══════════════════════════════════════════════════════════════════════
-- Ore effettivamente lavorate, dichiarate dal dipendente.
-- Una riga = un task × un dipendente × una settimana.
-- modalita: sede/remoto (per smart working e buoni pasto).
-- motivo_fermo: perché non si è lavorato (se ore = 0).
--   Sostituisce il confuso "Bloccato" con motivazioni esplicite (nota G4).
-- sottotask_nota: cosa è stato fatto concretamente (nota K1).
--   Es. "Fixato bug autenticazione, refactor endpoint /patients"

CREATE TABLE consuntivi (
    id                  SERIAL PRIMARY KEY,
    task_id             INTEGER      NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    dipendente_id       INTEGER      NOT NULL REFERENCES dipendenti(id),
    settimana           DATE         NOT NULL,     -- lunedì della settimana
    ore_dichiarate      NUMERIC(5,1) NOT NULL DEFAULT 0,
    compilato           BOOLEAN      NOT NULL DEFAULT FALSE,
    data_compilazione   TIMESTAMPTZ,
    modalita            modalita_lavoro,           -- sede / remoto
    motivo_fermo        VARCHAR(120),              -- "Priorità su altro progetto", "In attesa input cliente", ecc.
    sottotask_nota      TEXT,                      -- log di cosa è stato fatto concretamente
    nota                TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_consuntivo UNIQUE (task_id, dipendente_id, settimana)
);

CREATE INDEX idx_consuntivi_dipendente ON consuntivi (dipendente_id);
CREATE INDEX idx_consuntivi_settimana ON consuntivi (settimana);
CREATE INDEX idx_consuntivi_task ON consuntivi (task_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: presenze_settimanali
-- ══════════════════════════════════════════════════════════════════════
-- Dati settimanali NON legati a un task specifico:
-- smart working, assenze, spese.
-- Una riga = un dipendente × una settimana.

CREATE TABLE presenze_settimanali (
    id              SERIAL PRIMARY KEY,
    dipendente_id   INTEGER NOT NULL REFERENCES dipendenti(id),
    settimana       DATE    NOT NULL,              -- lunedì della settimana
    giorni_sede     SMALLINT DEFAULT 0,            -- giorni lavorati in sede
    giorni_remoto   SMALLINT DEFAULT 0,            -- giorni in smart working
    ore_assenza     NUMERIC(5,1) DEFAULT 0,
    tipo_assenza    VARCHAR(60),                   -- "Malattia", "Ferie", "Permesso", "ROL"
    nota_assenza    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_presenza UNIQUE (dipendente_id, settimana)
);

CREATE INDEX idx_presenze_dipendente ON presenze_settimanali (dipendente_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: spese
-- ══════════════════════════════════════════════════════════════════════
-- Spese aziendali dichiarate dal dipendente.
-- Separate dai consuntivi perché una spesa può non essere legata a un task.

CREATE TABLE spese (
    id              SERIAL PRIMARY KEY,
    dipendente_id   INTEGER      NOT NULL REFERENCES dipendenti(id),
    settimana       DATE         NOT NULL,
    descrizione     VARCHAR(200) NOT NULL,
    importo         NUMERIC(10,2) NOT NULL,
    categoria       VARCHAR(60),                  -- "Trasporto", "Materiale", "Licenza", ecc.
    progetto_id     INTEGER REFERENCES progetti(id),  -- opzionale
    nota            TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_spese_dipendente ON spese (dipendente_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: segnalazioni
-- ══════════════════════════════════════════════════════════════════════
-- Le segnalazioni generate dal chatbot, dal management, o dal sistema.
-- Oggi vivono in SEGNALAZIONI_STORE (lista Python in memoria).

CREATE TABLE segnalazioni (
    id              SERIAL PRIMARY KEY,
    tipo            VARCHAR(60)  NOT NULL,         -- "blocco_task", "sovraccarico", "richiesta_supporto", ecc.
    priorita        priorita_livello NOT NULL DEFAULT 'media',
    dipendente_id   INTEGER REFERENCES dipendenti(id),   -- chi ha generato/è coinvolto
    progetto_id     INTEGER REFERENCES progetti(id),     -- progetto coinvolto (opzionale)
    dettaglio       TEXT         NOT NULL,
    fonte           fonte_segnalazione NOT NULL DEFAULT 'chatbot',
    stato           stato_segnalazione NOT NULL DEFAULT 'aperta',
    destinatario    VARCHAR(60),                  -- "PM", "HR", "management", "amministrazione"
    risolta_da      INTEGER REFERENCES dipendenti(id),   -- chi l'ha risolta
    risolta_il      TIMESTAMPTZ,
    nota_risoluzione TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_segnalazioni_stato ON segnalazioni (stato);
CREATE INDEX idx_segnalazioni_priorita ON segnalazioni (priorita);
CREATE INDEX idx_segnalazioni_dipendente ON segnalazioni (dipendente_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: interventi
-- ══════════════════════════════════════════════════════════════════════
-- Storico delle azioni applicate dall'agente.
-- Quando il bottone "Applica" funzionerà, ogni azione viene registrata qui.

CREATE TABLE interventi (
    id                  SERIAL PRIMARY KEY,
    segnalazione_id     INTEGER REFERENCES segnalazioni(id),
    opzione_scelta      VARCHAR(10),              -- "A", "B", "C"
    descrizione_opzione TEXT,                     -- sintesi dell'opzione scelta
    azioni_applicate    JSONB,                    -- dettaglio JSON delle modifiche
    -- Es: [{"tipo": "riassegnazione", "task_id": 5, "da": 3, "a": 7},
    --       {"tipo": "posticipo", "task_id": 12, "giorni": 5}]
    approvato_da        INTEGER REFERENCES dipendenti(id),
    esito               VARCHAR(40),              -- "applicato", "annullato", "parziale"
    nota                TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_interventi_segnalazione ON interventi (segnalazione_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: pianificazioni_bozza
-- ══════════════════════════════════════════════════════════════════════
-- Salvataggio bozza di pianificazione GANTT in corso (punto I5).
-- dati_json contiene lo stato completo della tabella task in Pipeline.
-- Sostituisce localStorage quando c'è il db.

CREATE TABLE pianificazioni_bozza (
    id          SERIAL PRIMARY KEY,
    progetto_id INTEGER NOT NULL REFERENCES progetti(id) ON DELETE CASCADE,
    dati_json   JSONB   NOT NULL,                 -- snapshot completo della pianificazione
    creato_da   INTEGER REFERENCES dipendenti(id),
    nota        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bozze_progetto ON pianificazioni_bozza (progetto_id);


-- ══════════════════════════════════════════════════════════════════════
-- TABELLA: note_progetto
-- ══════════════════════════════════════════════════════════════════════
-- Note testuali libere legate a un progetto.
-- Per l'archivio e la knowledge base (lezioni apprese, note di retrospettiva).

CREATE TABLE note_progetto (
    id          SERIAL PRIMARY KEY,
    progetto_id INTEGER NOT NULL REFERENCES progetti(id) ON DELETE CASCADE,
    autore_id   INTEGER REFERENCES dipendenti(id),
    titolo      VARCHAR(200),
    testo       TEXT NOT NULL,
    tipo        VARCHAR(40) DEFAULT 'nota',       -- "nota", "lezione_appresa", "retrospettiva"
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_note_progetto ON note_progetto (progetto_id);


-- ══════════════════════════════════════════════════════════════════════
-- TRIGGER: updated_at automatico
-- ══════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trigger_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dipendenti_updated
    BEFORE UPDATE ON dipendenti
    FOR EACH ROW EXECUTE FUNCTION trigger_updated_at();

CREATE TRIGGER trg_progetti_updated
    BEFORE UPDATE ON progetti
    FOR EACH ROW EXECUTE FUNCTION trigger_updated_at();

CREATE TRIGGER trg_task_updated
    BEFORE UPDATE ON task
    FOR EACH ROW EXECUTE FUNCTION trigger_updated_at();

CREATE TRIGGER trg_segnalazioni_updated
    BEFORE UPDATE ON segnalazioni
    FOR EACH ROW EXECUTE FUNCTION trigger_updated_at();

CREATE TRIGGER trg_bozze_updated
    BEFORE UPDATE ON pianificazioni_bozza
    FOR EACH ROW EXECUTE FUNCTION trigger_updated_at();


-- ══════════════════════════════════════════════════════════════════════
-- VIEW: saturazione_settimanale
-- ══════════════════════════════════════════════════════════════════════
-- Vista che calcola la saturazione settimanale per ogni dipendente.
-- Equivalente SQL di carico_settimanale_dipendente() in data.py.
-- Non è materializzata (per 15 persone il calcolo al volo è sufficiente).

CREATE OR REPLACE VIEW v_saturazione_settimanale AS
WITH settimane AS (
    -- Genera 26 settimane a partire da oggi
    SELECT generate_series(
        date_trunc('week', CURRENT_DATE)::date,
        (date_trunc('week', CURRENT_DATE) + interval '25 weeks')::date,
        '1 week'::interval
    )::date AS lunedi
),
carichi AS (
    SELECT
        d.id AS dipendente_id,
        d.nome,
        d.profilo,
        d.ore_sett,
        s.lunedi,
        COALESCE(SUM(
            CASE
                WHEN t.data_inizio <= s.lunedi + 4
                 AND t.data_fine >= s.lunedi
                 AND t.stato NOT IN ('Completato', 'Sospeso')
                THEN
                    -- ore_stimate distribuite sulle settimane del task
                    -- Se multi-persona, usa ore_assegnate dall'assegnazione
                    COALESCE(a.ore_assegnate, t.ore_stimate)::numeric
                    / GREATEST(1, CEIL((t.data_fine - t.data_inizio)::numeric / 7))
                ELSE 0
            END
        ), 0) AS ore_caricate
    FROM dipendenti d
    CROSS JOIN settimane s
    LEFT JOIN assegnazioni a ON a.dipendente_id = d.id
    LEFT JOIN task t ON t.id = a.task_id
    WHERE d.attivo = TRUE
    GROUP BY d.id, d.nome, d.profilo, d.ore_sett, s.lunedi
)
SELECT
    dipendente_id,
    nome,
    profilo,
    ore_sett,
    lunedi,
    ROUND(ore_caricate, 1) AS ore_caricate,
    ROUND(ore_caricate / ore_sett * 100) AS saturazione_pct
FROM carichi;


-- ══════════════════════════════════════════════════════════════════════
-- NOTE ARCHITETTURALI
-- ══════════════════════════════════════════════════════════════════════
--
-- MIGRAZIONE DA data.py:
--   • Le funzioni helper (get_dipendente, get_tasks_progetto, ecc.)
--     diventano query SQL semplici o metodi SQLAlchemy
--   • carico_settimanale_dipendente → usa v_saturazione_settimanale
--   • Il frontend NON cambia — parla solo con le API REST
--   • Il backend cambia solo la sorgente dati, non la logica
--
-- CAMPI ID:
--   • data.py usa stringhe ("D001", "P003", "T042")
--   • PostgreSQL usa SERIAL (interi auto-incrementanti)
--   • Il backend dovrà mappare i vecchi ID durante la migrazione iniziale
--   • Dopo la migrazione, tutto usa interi
--
-- MULTI-TENANT (futuro):
--   • Per vendere il prodotto, aggiungere tenant_id a tutte le tabelle
--   • Row Level Security di PostgreSQL gestisce l'isolamento
--   • Non implementato ora — lo schema lo supporta aggiungendo una colonna
--
-- INDICI:
--   • Creati sulle colonne più usate nei filtri e nei JOIN
--   • Per 15 persone e ~60 task sono più che sufficienti
--   • Aggiungere indici composti se emergono query lente
--
-- ══════════════════════════════════════════════════════════════════════