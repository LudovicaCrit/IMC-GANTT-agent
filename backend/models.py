"""
IMC-Group GANTT Agent — Modelli Database (SQLAlchemy)
Funziona con SQLite (sviluppo) e PostgreSQL (produzione).
Cambiare solo DATABASE_URL per switchare.
"""

import os
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, Date,
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint, JSON,
    Numeric, SmallInteger, Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ── Configurazione ──
# SQLite per sviluppo, PostgreSQL per produzione
# Basta cambiare questa riga:
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///imcgroup.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ══════════════════════════════════════════════════════════════════════
# MODELLI
# ══════════════════════════════════════════════════════════════════════

class Dipendente(Base):
    __tablename__ = "dipendenti"

    id = Column(String(10), primary_key=True)  # "D001", "D002"...
    nome = Column(String(100), nullable=False)
    profilo = Column(String(60), nullable=False)
    ore_sett = Column(SmallInteger, nullable=False, default=40)
    costo_ora = Column(Float, nullable=True)
    competenze = Column(JSON, default=[])
    sede = Column(String(40), nullable=True)
    email = Column(String(120), nullable=True)
    data_assunzione = Column(Date, nullable=True)
    attivo = Column(Boolean, nullable=False, default=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relazioni
    assegnazioni = relationship("Assegnazione", back_populates="dipendente")
    consuntivi = relationship("Consuntivo", back_populates="dipendente")


class Progetto(Base):
    __tablename__ = "progetti"

    id = Column(String(10), primary_key=True)  # "P001", "P002"...
    nome = Column(String(150), nullable=False)
    cliente = Column(String(150), nullable=True)
    stato = Column(String(30), nullable=False, default="In esecuzione")
    tipo = Column(String(20), nullable=False, default="progetto")
    priorita = Column(String(10), nullable=False, default="media")
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    budget_ore = Column(Integer, nullable=True)
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

    # Relazioni
    task = relationship("Task", back_populates="progetto", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "task"

    id = Column(String(10), primary_key=True)  # "T001", "T002"...
    progetto_id = Column(String(10), ForeignKey("progetti.id", ondelete="CASCADE"), nullable=False)
    nome = Column(String(200), nullable=False)
    fase = Column(String(60), nullable=True)
    ore_stimate = Column(Integer, nullable=True)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    stato = Column(String(20), nullable=False, default="Da iniziare")
    profilo_richiesto = Column(String(60), nullable=True)
    predecessore = Column(String(10), nullable=True, default="")
    ordine = Column(SmallInteger, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relazioni
    progetto = relationship("Progetto", back_populates="task")
    assegnazioni = relationship("Assegnazione", back_populates="task", cascade="all, delete-orphan")
    consuntivi = relationship("Consuntivo", back_populates="task")

    # Campo legacy per compatibilità con data.py
    # In futuro le assegnazioni saranno SOLO nella tabella assegnazioni
    dipendente_id = Column(String(10), ForeignKey("dipendenti.id"), nullable=True)


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

    # Relazioni
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
    modalita = Column(String(10), nullable=True)  # "sede" / "remoto"
    motivo_fermo = Column(String(120), nullable=True)
    sottotask_nota = Column(Text, nullable=True)
    nota = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("task_id", "dipendente_id", "settimana", name="uq_consuntivo"),
    )

    # Relazioni
    task = relationship("Task", back_populates="consuntivi")
    dipendente = relationship("Dipendente", back_populates="consuntivi")


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
