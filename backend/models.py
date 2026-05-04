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
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, Date,
    DateTime, ForeignKey, UniqueConstraint, JSON, SmallInteger,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ── Configurazione ──
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///imcgroup.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


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

class Dipendente(Base):
    __tablename__ = "dipendenti"

    id = Column(String(10), primary_key=True)
    nome = Column(String(100), nullable=False)
    profilo = Column(String(60), nullable=False)  # legacy, resta per compatibilità
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
    stato = Column(String(30), nullable=False, default="In esecuzione")
    tipo = Column(String(20), nullable=False, default="progetto")
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
    responsabile_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    scadenza_bando = Column(Date, nullable=True)
    motivo_sospensione = Column(Text, nullable=True)
    lezioni_apprese = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fasi = relationship("Fase", back_populates="progetto", cascade="all, delete-orphan",
                        order_by="Fase.ordine")
    task = relationship("Task", back_populates="progetto", cascade="all, delete-orphan")


class Fase(Base):
    """Fase di un progetto. Le ore nascono qui, i deliverable le dettagliano."""
    __tablename__ = "fasi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id", ondelete="CASCADE"), nullable=False)
    nome = Column(String(100), nullable=False)
    ordine = Column(SmallInteger, nullable=False, default=1)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
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
    fase_id = Column(Integer, ForeignKey("fasi.id", ondelete="SET NULL"), nullable=True)
    nome = Column(String(200), nullable=False)
    fase = Column(String(60), nullable=True)  # legacy stringa
    ore_stimate = Column(Integer, nullable=True)        # "Iniziale"
    ore_consumate = Column(Float, nullable=True, default=0)
    ore_rimanenti = Column(Float, nullable=True)
    ore_pianificate = Column(Float, nullable=True)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    stato = Column(String(20), nullable=False, default="Da iniziare")
    motivo_blocco = Column(Text, nullable=True)  # "Perché?" quando Bloccato/In ritardo
    profilo_richiesto = Column(String(60), nullable=True)
    predecessore = Column(String(10), nullable=True, default="")
    ordine = Column(SmallInteger, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    progetto = relationship("Progetto", back_populates="task")
    fase_rel = relationship("Fase", back_populates="task")
    assegnazioni = relationship("Assegnazione", back_populates="task", cascade="all, delete-orphan")
    consuntivi = relationship("Consuntivo", back_populates="task")
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)


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


class PianificazioneBozza(Base):
    __tablename__ = "pianificazioni_bozza"

    id = Column(Integer, primary_key=True, autoincrement=True)
    progetto_id = Column(String(10), ForeignKey("progetti.id", ondelete="CASCADE"), nullable=False)
    dati_json = Column(JSON, nullable=False)
    creato_da = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)
    nota = Column(Text, nullable=True)
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