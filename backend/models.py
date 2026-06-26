"""
IMC-Group GANTT Agent — Modelli Database (SQLAlchemy)
Release 1 — Modello Fase consolidato

Gerarchia: Progetto → Fase → Task/Deliverable
Configurazione: Ruolo, Competenza, FaseStandard
Autenticazione: Utente con JWT (user/manager)

Funziona con SQLite (sviluppo) e PostgreSQL (produzione).
Cambiare solo DATABASE_URL per switchare.
"""

import os
from datetime import datetime, date
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, Date,
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint, JSON, SmallInteger,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ── Configurazione ──
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///imcgroup.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ══════════════════════════════════════════════════════════════════════
# ENUM APPLICATIVI — fonte di verità per gli stati ammessi
# ══════════════════════════════════════════════════════════════════════
# Step 2.1 D3 (13 mag 2026): CHECK constraint a livello DB allineato a queste
# costanti. Vedi migration c3d4e5f6a7b8 e handoff v15 §3.3.
#
# Modificare questi tuple richiede UNA migration Alembic che aggiorni il CHECK.

STATI_FASE = ("Da iniziare", "In corso", "Completata", "Sospesa", "Annullata")

# Handoff v15 §3.3: i 5 stati canonici. §3.5 punto 5 chiarisce: "Bozza = tutto
# ciò che non ha approvazione" (assorbe ciò che prima era "Vinto - Da
# pianificare" nel vecchio modello bandi, deprecato).
#
# Step 2.7-pre (20/05/2026): aggiunto "Da iniziare" — progetto APPROVATO dal
# cliente con fasi pianificate, ma con data_inizio futura (non ancora partito).
# La transizione "Da iniziare → In esecuzione" è MANUALE: il PM la conferma
# quando data_inizio <= oggi (handoff §3.5 "controllo non automazione").
# Vedi migration alembic d4e5f6a7b8c9.
STATI_PROGETTO = (
    "Bozza",
    "Da iniziare",
    "In esecuzione",
    "Sospeso",
    "Completato",
    "Annullato",
)
# Sottoinsieme "attivi": progetti visibili in GANTT e Cantiere "Progetti attivi"
# (handoff §3.3). Bozza vive solo in Cantiere "In cantiere", Completato/Annullato
# in Archivio. "Da iniziare" è in attesa di partire, gestito con alert Home.
STATI_PROGETTO_ATTIVI = ("In esecuzione", "Sospeso")

# Step 2.7-pre (20/05/2026): stati Task formalizzati. Prima il modello accettava
# qualsiasi stringa (no CHECK su task.stato). Sospeso e Annullato erano scritti
# a runtime dalla cascata Fase→Task (Step 2.4-bis B, commit 61795c5) e ora sono
# formalmente ammessi anche dal DB.
# Vedi migration alembic d4e5f6a7b8c9.
STATI_TASK = (
    "Da iniziare",
    "In corso",
    "Completato",
    "Bloccato",
    "Sospeso",
    "Annullato",
)

# Step 3.1 (25/05/2026): tipi di dipendenza tra task ammessi.
# Sostituiscono la vecchia colonna `Task.predecessore` (stringa singola, tipo
# non registrato — implicitamente FS) con la tabella-grafo `dipendenza_task`.
# - FS: Finish-to-Start  — il successore inizia quando il predecessore finisce (default storico)
# - SS: Start-to-Start   — il successore inizia quando il predecessore inizia
# - FF: Finish-to-Finish — il successore finisce quando il predecessore finisce
# - SF: Start-to-Finish  — il successore finisce quando il predecessore inizia (raro)
# CHECK constraint a livello DB: vedi migration alembic e5f6a7b8c9d0
# (ck_dipendenza_task_tipo). Anche nel modello, su DipendenzaTask.
TIPI_DIPENDENZA = ("FS", "SS", "FF", "SF")


# ══════════════════════════════════════════════════════════════════════
# CONFIGURAZIONE — Entità gestite dalla pagina admin
# ══════════════════════════════════════════════════════════════════════

class Ruolo(Base):
    """Ruoli aziendali censiti in Configurazione."""
    __tablename__ = "ruoli"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(80), nullable=False, unique=True)
    descrizione = Column(Text, nullable=True)
    attivo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dipendenti = relationship("Dipendente", back_populates="ruolo_rel")


class Competenza(Base):
    """Competenze censibili (ARIS, GRC, Python, ecc.). Lista piatta, senza categoria."""
    __tablename__ = "competenze"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(80), nullable=False, unique=True)
    attivo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dipendenti = relationship("DipendentiCompetenze", back_populates="competenza")


class DipendentiCompetenze(Base):
    """Tabella associativa M2M tra Dipendente e Competenza."""
    __tablename__ = "dipendenti_competenze"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id", ondelete="CASCADE"), nullable=False)
    competenza_id = Column(Integer, ForeignKey("competenze.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("dipendente_id", "competenza_id", name="uq_dip_comp"),
    )

    dipendente = relationship("Dipendente", back_populates="competenze_rel")
    competenza = relationship("Competenza", back_populates="dipendenti")


class FaseStandard(Base):
    """Template di fasi per tipo progetto. Usato per precompilare i GANTT in Pipeline."""
    __tablename__ = "fasi_standard"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_nome = Column(String(80), nullable=False)  # "Template DORA", "Template GRC"
    fase_nome = Column(String(80), nullable=False)       # "Analisi", "Design"
    ordine = Column(SmallInteger, nullable=False, default=1)
    percentuale_ore = Column(Float, nullable=True)        # 25.0 = 25% del budget
    created_at = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════
# AUTENTICAZIONE
# ══════════════════════════════════════════════════════════════════════

class Utente(Base):
    """Utente per login JWT. Collegato 1:1 a Dipendente."""
    __tablename__ = "utenti"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    ruolo_app = Column(String(20), nullable=False, default="user")  # "user" | "manager"
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    attivo = Column(Boolean, nullable=False, default=True)
    ultimo_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    dipendente = relationship("Dipendente", back_populates="utente")


# ══════════════════════════════════════════════════════════════════════
# ANAGRAFICA
# ══════════════════════════════════════════════════════════════════════

class Azienda(Base):
    """Aziende operative del Gruppo IMC (struttura multi-azienda).

    DESIGN_SEED_Innovation_Plaza §1 (26/06/2026). Nel seed modelliamo le 2
    s.r.l. operative vive: IMC-Improve (commesse/progetti) e Innovation Plaza
    (bandi). Struttura estensibile: un ramo futuro = una riga in più, non una
    migration. Vedi migration alembic a7b8c9d0e1f2 (uq_azienda_nome).
    """
    __tablename__ = "azienda"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)

    __table_args__ = (UniqueConstraint("nome", name="uq_azienda_nome"),)

    dipendenti = relationship("Dipendente", back_populates="azienda_rel")
    progetti = relationship("Progetto", back_populates="azienda_rel")


class Dipendente(Base):
    __tablename__ = "dipendenti"

    id = Column(String(10), primary_key=True)
    nome = Column(String(100), nullable=False)
    profilo = Column(String(60), nullable=False)  # legacy, resta per compatibilità
    # azienda_id: ogni persona appartiene a un'azienda del gruppo (obbligatorio).
    # Vedi migration a7b8c9d0e1f2 + DESIGN_SEED_Innovation_Plaza §1-§2.
    azienda_id = Column(Integer, ForeignKey("azienda.id"), nullable=False)
    ruolo_id = Column(Integer, ForeignKey("ruoli.id"), nullable=True)
    ore_sett = Column(SmallInteger, nullable=False, default=40)
    costo_ora = Column(Float, nullable=True)
    competenze = Column(JSON, default=[])  # legacy JSON, le competenze M2M sono in dipendenti_competenze
    sede = Column(String(40), nullable=True)
    email = Column(String(120), nullable=True)
    data_assunzione = Column(Date, nullable=True)
    attivo = Column(Boolean, nullable=False, default=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    azienda_rel = relationship("Azienda", back_populates="dipendenti")
    ruolo_rel = relationship("Ruolo", back_populates="dipendenti")
    competenze_rel = relationship("DipendentiCompetenze", back_populates="dipendente")
    assegnazioni = relationship("Assegnazione", back_populates="dipendente")
    consuntivi = relationship("Consuntivo", back_populates="dipendente")
    utente = relationship("Utente", back_populates="dipendente", uselist=False)


# ══════════════════════════════════════════════════════════════════════
# GERARCHIA — Progetto → Fase → Task/Deliverable
# ══════════════════════════════════════════════════════════════════════

class Progetto(Base):
    __tablename__ = "progetti"

    id = Column(String(10), primary_key=True)
    nome = Column(String(150), nullable=False)
    cliente = Column(String(150), nullable=True)
    # stato: "Bozza" | "Da iniziare" | "In esecuzione" | "Sospeso" | "Completato" | "Annullato"
    # Vedi handoff v15 §3.3 + Step 2.7-pre (20/05/2026) per "Da iniziare".
    # Una bozza è un progetto a tutti gli effetti, distinto solo dallo stato
    # (Step 2.0 della roadmap, 13 mag 2026).
    # CHECK constraint sui valori ammessi: vedi alembic c3d4e5f6a7b8 + d4e5f6a7b8c9.
    stato = Column(String(30), nullable=False, default="In esecuzione")
    # tipologia: distingue progetti commerciali da bandi (decisione Francesco 4 mag 2026).
    # Per i bandi, il modello prevede 3 fasi standard fisse (Monitoraggio, Proposal, PM)
    # di cui solo PM ha ore vendute. Le ore "a sentimento" (Monitoraggio/Proposal/prevendita)
    # si consuntivano come "Attività commerciale" sotto Attività Interne.
    # Era "tipo" con default "progetto" inutilizzato; rinominato per chiarezza.
    # CHECK constraint sui valori ammessi: vedi alembic f6a7b8c9d0e1 (Step 3.2,
    # 03/06/2026) — ck_progetti_tipologia. Valore "interna" aggiunto per le
    # attività interne non fatturabili (ex contenitore-unico P010, ora
    # spacchettato in N progetti distinti: mansioni continuative, corsi, innovazione).
    tipologia = Column(String(20), nullable=False, default="ordinario")  # "ordinario" | "bando" | "interna"
    priorita = Column(String(10), nullable=False, default="media")
    ritardabilita = Column(String(10), nullable=True, default="media")
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    budget_ore = Column(Integer, nullable=True)
    giornate_vendute = Column(Float, nullable=True)
    valore_contratto = Column(Float, nullable=True)
    descrizione = Column(Text, nullable=True)
    fase_corrente = Column(String(80), nullable=True)
    sede = Column(String(40), nullable=True)
    # pm_id: il Project Manager del progetto. FK a Dipendente, nullable.
    # Era "responsabile_id"; rinominato per coerenza con linguaggio Vincenzo/Francesco
    # e prep R2 (ABAC: solo il PM potrà modificare il proprio progetto).
    pm_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    # azienda_id: nullable. Obbligatoria per commerciali/bandi (garantita nel
    # seed / futuro CHECK condizionato), NULL ammesso per gli interni (attività
    # trasversale). Vedi migration a7b8c9d0e1f2 + DESIGN §1.
    azienda_id = Column(Integer, ForeignKey("azienda.id"), nullable=True)
    # area: valorizzata SOLO per i bandi Innovation ("PA" | "Imprese"), NULL
    # altrove. Spezza Innovation tra le due aree (Ida=PA, Domenica=Imprese).
    area = Column(String(20), nullable=True)
    scadenza_bando = Column(Date, nullable=True)
    motivo_sospensione = Column(Text, nullable=True)
    lezioni_apprese = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    azienda_rel = relationship("Azienda", back_populates="progetti")
    fasi = relationship("Fase", back_populates="progetto", cascade="all, delete-orphan",
                        order_by="Fase.ordine")
    task = relationship("Task", back_populates="progetto", cascade="all, delete-orphan")

    @property
    def stato_derivato(self) -> str:
        """Stato calcolato dalla composizione delle fasi.

        Step 2.1 D3 (handoff v15 §3.3). Regole:
          - "Bozza": nessuna fase
          - "Completato": tutte le fasi in "Completata"
          - "In esecuzione": almeno una fase "In corso"
          - "Sospeso": ci sono fasi ma nessuna in corso e non sono tutte completate

        Questa property NON sostituisce `Progetto.stato` (scrivibile dal manager).
        Le due possono divergere: il manager può forzare uno stato (es. "Annullato")
        anche se le fasi non lo riflettono. Quando divergono, è informazione utile
        per la dashboard ("progetto sospeso dal manager, ma il piano avrebbe fasi
        attive").
        """
        if not self.fasi:
            return "Bozza"
        stati = {f.stato for f in self.fasi}
        if stati == {"Completata"}:
            return "Completato"
        if "In corso" in stati:
            return "In esecuzione"
        return "Sospeso"


class Fase(Base):
    """Fase di un progetto. Le ore nascono qui, i deliverable le dettagliano."""
    __tablename__ = "fasi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id", ondelete="CASCADE"), nullable=False)
    nome = Column(String(100), nullable=False)
    ordine = Column(SmallInteger, nullable=False, default=1)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    # ═════════════════════════════════════════════════════════════════════
    # MODELLO ORE FASE — Step 2.1 D4 (handoff v15 §2.1)
    # ═════════════════════════════════════════════════════════════════════
    # ore_vendute: ore vendute al cliente per questa fase (dalla proposta
    #   commerciale / contratto). È il budget commerciale FISSO della fase.
    # ore_pianificate: somma delle ore_pianificate dei task figli. Riflette
    #   come il PM ha distribuito le ore vendute sui task. Tipicamente
    #   ore_pianificate <= ore_vendute (se >, sforamento di piano).
    # ore_consumate (NON in colonna): si calcola aggregando Consuntivo dei
    #   task della fase. Vedi routes/fasi.lista_fasi_progetto.
    # ore_rimanenti (NON in colonna): ore_vendute - ore_consumate, derivata.
    # stato: vedi STATI_FASE in cima al modulo. CHECK a livello DB.
    ore_vendute = Column(Float, nullable=True)
    ore_pianificate = Column(Float, nullable=True)
    stato = Column(String(20), nullable=False, default="Da iniziare")
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    progetto = relationship("Progetto", back_populates="fasi")
    task = relationship("Task", back_populates="fase_rel", cascade="all, delete-orphan",
                        order_by="Task.ordine")


class Task(Base):
    """Task/Deliverable dentro una fase. Unità operativa."""
    __tablename__ = "task"

    id = Column(String(10), primary_key=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id", ondelete="CASCADE"), nullable=False)
    # fase_id: FK NOT NULL alla tabella `fasi`. Step 2.1 D1 (13 mag 2026):
    # eliminata la doppia rappresentazione (prima esistevano sia fase_id che
    # fase stringa "legacy"). Ora il nome della fase si legge tramite
    # `task.fase_rel.nome` o, nel DataFrame loader, tramite la chiave "fase"
    # (derivata, esposta per retrocompatibilità con i router e il frontend).
    fase_id = Column(Integer, ForeignKey("fasi.id", ondelete="RESTRICT"), nullable=False)
    nome = Column(String(200), nullable=False)
    # ═════════════════════════════════════════════════════════════════════
    # MODELLO ORE TASK — Step 2.1 D4 (handoff v15 §2.1)
    # ═════════════════════════════════════════════════════════════════════
    # ore_stimate: stima INIZIALE del PM al momento della creazione del task.
    #   - In ore intere.
    #   - Convenzione R1: NON si modifica dopo l'avvio del progetto
    #     (è il "budget storico" del task, usato per confronti ex-post).
    #     Se servono adeguamenti, il PM crea un nuovo task o usa note.
    # ore_pianificate: ore allocate nel piano corrente (può differire da
    #   ore_stimate se il PM ha rivisto la pianificazione mantenendo lo
    #   storico).
    # ore_consumate: somma dei consuntivi (Consuntivo.ore_dichiarate) dei
    #   dipendenti assegnati al task. NON va aggiornata a mano: è derivata
    #   ma denormalizzata per performance (un trigger o un job può
    #   ricalcolarla; al 13 mag 2026 viene aggiornata applicativamente in
    #   data_db_impl.modifica_consuntivo). 📌 TODO Blocco 3: rendere
    #   l'aggiornamento sistematico e testato.
    # ore_rimanenti: ore_pianificate - ore_consumate. Denormalizzata come sopra.
    ore_stimate = Column(Integer, nullable=True)
    ore_consumate = Column(Float, nullable=True, default=0)
    ore_rimanenti = Column(Float, nullable=True)
    ore_pianificate = Column(Float, nullable=True)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    # stato: vedi STATI_TASK in cima al modulo (Step 2.7-pre, 20/05/2026).
    # Valori: "Da iniziare" | "In corso" | "Completato" | "Bloccato" | "Sospeso" | "Annullato".
    # CHECK constraint: vedi alembic d4e5f6a7b8c9. Sospeso/Annullato sono scritti
    # dalla cascata Fase→Task (Step 2.4-bis B, commit 61795c5).
    stato = Column(String(20), nullable=False, default="Da iniziare")
    motivo_blocco = Column(Text, nullable=True)  # "Perché?" quando Bloccato/In ritardo
    profilo_richiesto = Column(String(60), nullable=True)
    # Step 3.1 (25/05/2026): rimossa colonna `predecessore` String singola.
    # Le dipendenze tra task vivono ora nella tabella `dipendenza_task`
    # (modello-grafo: dipendenze multiple e tipizzate FS/SS/FF/SF).
    # Per leggerle: usare le relationship `dipendenze_entranti` (questo task
    # è successore → i suoi predecessori sono lì) e `dipendenze_uscenti`
    # (questo task è predecessore → lista dei suoi successori).
    # Vedi alembic e5f6a7b8c9d0.
    ordine = Column(SmallInteger, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    progetto = relationship("Progetto", back_populates="task")
    fase_rel = relationship("Fase", back_populates="task")
    assegnazioni = relationship("Assegnazione", back_populates="task", cascade="all, delete-orphan")
    consuntivi = relationship("Consuntivo", back_populates="task")
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)

    # Dipendenze entranti: righe di DipendenzaTask in cui questo task è
    # successore (cioè i suoi predecessori). Dipendenze uscenti: dove è
    # predecessore (cioè i suoi successori). Cascade delete: rimuovendo il
    # task spariscono anche le sue dipendenze, allineato alla FK ON DELETE
    # CASCADE definita in alembic e5f6a7b8c9d0.
    dipendenze_entranti = relationship(
        "DipendenzaTask",
        foreign_keys="DipendenzaTask.task_successore_id",
        back_populates="successore",
        cascade="all, delete-orphan",
    )
    dipendenze_uscenti = relationship(
        "DipendenzaTask",
        foreign_keys="DipendenzaTask.task_predecessore_id",
        back_populates="predecessore",
        cascade="all, delete-orphan",
    )


class DipendenzaTask(Base):
    """Dipendenza tra task (modello-grafo).

    Step 3.1 (25/05/2026, alembic e5f6a7b8c9d0): sostituisce la vecchia colonna
    `Task.predecessore` (stringa singola). Permette dipendenze MULTIPLE e
    tipizzate FS/SS/FF/SF — vedi TIPI_DIPENDENZA in cima al modulo.

      - task_predecessore_id: il task da cui dipende
      - task_successore_id:   il task che dipende
      - tipo_dipendenza:      'FS' (default), 'SS', 'FF', 'SF'

    Vincoli (a livello DB e modello — vedi migration alembic e5f6a7b8c9d0):
      UNIQUE (task_predecessore_id, task_successore_id) → uq_dipendenza_task
      CHECK  (task_predecessore_id != task_successore_id) → ck_dipendenza_task_no_self
      CHECK  (tipo_dipendenza IN TIPI_DIPENDENZA)         → ck_dipendenza_task_tipo
    """
    __tablename__ = "dipendenza_task"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_predecessore_id = Column(
        String(10),
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_successore_id = Column(
        String(10),
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_dipendenza = Column(String(2), nullable=False, default="FS")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "task_predecessore_id", "task_successore_id",
            name="uq_dipendenza_task",
        ),
        CheckConstraint(
            "task_predecessore_id <> task_successore_id",
            name="ck_dipendenza_task_no_self",
        ),
        CheckConstraint(
            "tipo_dipendenza IN (" + ", ".join(f"'{t}'" for t in TIPI_DIPENDENZA) + ")",
            name="ck_dipendenza_task_tipo",
        ),
    )

    predecessore = relationship(
        "Task",
        foreign_keys=[task_predecessore_id],
        back_populates="dipendenze_uscenti",
    )
    successore = relationship(
        "Task",
        foreign_keys=[task_successore_id],
        back_populates="dipendenze_entranti",
    )


# ══════════════════════════════════════════════════════════════════════
# RELAZIONI OPERATIVE
# ══════════════════════════════════════════════════════════════════════

class Assegnazione(Base):
    __tablename__ = "assegnazioni"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(10), ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=False)
    ore_assegnate = Column(Integer, nullable=True)
    ruolo = Column(String(20), default="responsabile")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("task_id", "dipendente_id", name="uq_assegnazione"),
    )

    task = relationship("Task", back_populates="assegnazioni")
    dipendente = relationship("Dipendente", back_populates="assegnazioni")


class Consuntivo(Base):
    __tablename__ = "consuntivi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(10), ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=False)
    settimana = Column(Date, nullable=False)
    ore_dichiarate = Column(Float, nullable=False, default=0)
    compilato = Column(Boolean, nullable=False, default=False)
    data_compilazione = Column(DateTime, nullable=True)
    modalita = Column(String(10), nullable=True)
    motivo_fermo = Column(String(120), nullable=True)
    sottotask_nota = Column(Text, nullable=True)
    nota = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("task_id", "dipendente_id", "settimana", name="uq_consuntivo"),
    )

    task = relationship("Task", back_populates="consuntivi")
    dipendente = relationship("Dipendente", back_populates="consuntivi")


# ══════════════════════════════════════════════════════════════════════
# SUPPORTO
# ══════════════════════════════════════════════════════════════════════

class Segnalazione(Base):
    __tablename__ = "segnalazioni"

    id = Column(String(10), primary_key=True)
    tipo = Column(String(60), nullable=False)
    priorita = Column(String(10), nullable=False, default="media")
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id"), nullable=True)
    dettaglio = Column(Text, nullable=False)
    fonte = Column(String(20), nullable=False, default="chatbot")
    stato = Column(String(20), nullable=False, default="aperta")
    destinatario = Column(String(60), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotaProgetto(Base):
    __tablename__ = "note_progetto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id", ondelete="CASCADE"), nullable=False)
    autore_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    titolo = Column(String(200), nullable=True)
    testo = Column(Text, nullable=False)
    tipo = Column(String(40), default="nota")
    created_at = Column(DateTime, default=datetime.utcnow)


class Intervento(Base):
    __tablename__ = "interventi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    segnalazione_id = Column(String(10), ForeignKey("segnalazioni.id"), nullable=True)
    opzione_scelta = Column(String(10), nullable=True)
    descrizione_opzione = Column(Text, nullable=True)
    azioni_applicate = Column(JSON, nullable=True)
    approvato_da = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    esito = Column(String(40), nullable=True)
    nota = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PresenzaSettimanale(Base):
    __tablename__ = "presenze_settimanali"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=False)
    settimana = Column(Date, nullable=False)
    giorni_sede = Column(SmallInteger, default=0)
    giorni_remoto = Column(SmallInteger, default=0)
    ore_assenza = Column(Float, default=0)
    tipo_assenza = Column(String(60), nullable=True)
    nota_assenza = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("dipendente_id", "settimana", name="uq_presenza"),
    )


class Spesa(Base):
    __tablename__ = "spese"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=False)
    settimana = Column(Date, nullable=False)
    descrizione = Column(String(200), nullable=False)
    importo = Column(Float, nullable=False)
    categoria = Column(String(60), nullable=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id"), nullable=True)
    nota = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════
# SAL — snapshot storico del GANTT (DESIGN_SAL.md)
# ══════════════════════════════════════════════════════════════════════

class SalSnapshot(Base):
    """Fotografia IMMUTABILE e AUTOCONTENUTA dello stato completo di un progetto
    in un istante (DESIGN_SAL §3). Lo stato (progetto + fasi + task + ore + date
    + dipendenze tipizzate) è serializzato in JSONB; le colonne sono i metadati.

    Durabilità (vedi migration c9d0e1f2a3b4):
      - progetto_id FK senza CASCADE: la storia non si cancella col progetto.
      - consolidato_da è l'id dipendente come stringa SENZA FK: lo snapshot
        resta leggibile anche se quella persona viene rimossa (coerente con i
        nomi denormalizzati dentro il JSONB).
    """
    __tablename__ = "sal_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id"), nullable=False)
    data_snapshot = Column(DateTime, nullable=False, server_default=func.now())
    consolidato_da = Column(String(10), nullable=True)  # id dipendente, no FK (durabilità)
    nota = Column(Text, nullable=True)
    stato = Column(JSONB, nullable=False)  # stato completo serializzato


# ══════════════════════════════════════════════════════════════════════
# CREAZIONE TABELLE
# ══════════════════════════════════════════════════════════════════════

def create_tables():
    """Crea tutte le tabelle nel database."""
    Base.metadata.create_all(engine)


def get_session():
    """Restituisce una sessione database."""
    return SessionLocal()


if __name__ == "__main__":
    create_tables()
    print(f"Database creato: {DATABASE_URL}")
    print(f"Tabelle: {', '.join(Base.metadata.tables.keys())}")