"""Baseline: lo schema intero in una migration sola

Sostituisce le 41 migration che portavano dal primo schema (e733e23ae7a1) a
c8d9e0f1a2b3. Quelle restano nella storia di git; qui c'è lo schema a cui
arrivavano: stesse tabelle, colonne, tipi, default, vincoli, indici, la vista
e la sequenza dei progetti (passo A1). Fino alla prima installazione presso un
cliente si modifica questo file invece di aggiungere migration (DECISIONI.md).

I NOMI DEI VINCOLI E DEGLI INDICI seguono la convenzione del modello
(`models.CONVENZIONE_NOMI`, passo B1): pk_<tabella>, fk_<tabella>_<colonna>_
<tabella riferita>, uq_<tabella>_<colonne>, ck_<tabella>_<nome breve>,
ix_<tabella>_<colonna>. Qui sono scritti per intero dentro `op.f()`, che li
marca come già convertiti: alembic applica la convenzione di `target_metadata`
anche agli oggetti di questa migration, e un nome di CHECK passato senza
`op.f()` diventerebbe ck_<tabella>_ck_<tabella>_…. Il test di allineamento
(tests/test_schema_allineato.py) verifica che coincidano con quelli del modello.

Le migration vecchie trasformavano database esistenti, con backfill e
travasi di dati. Un database nuovo non ne ha bisogno: parte da qui, e i dati
li porta il seed in sviluppo e la Configurazione presso il cliente.

L'ordine delle colonne è quello del database costruito dalla catena: dove una
migration aveva aggiunto una colonna, la colonna sta in fondo alla tabella.
Non conta per il codice, e tenerlo uguale rende il confronto senza eccezioni.

DATI DI RIFERIMENTO
Uno solo, il ruolo «PM» di tipo `funzionale`. Il codice non lo cerca per nome,
ma nessun cliente potrebbe crearselo: POST /api/config/ruoli crea solo ruoli
di tipo `base`, gli inquadramenti. Senza questa riga nessuno potrebbe ricoprire
il ruolo di PM in aggiunta all'inquadramento, e un task non potrebbe chiederlo
come profilo. Le aziende, gli inquadramenti, le competenze, i template di fasi
e gli utenti dipendono dal cliente e non stanno qui: il primo utente manager,
in più, porta una password, che in una migration non può stare.

IL DOWNGRADE non esiste: tornare indietro da una baseline vuol dire
ricostruire il database, e farlo con un DROP dentro una migration toglierebbe
tutti i dati senza una guardia che possa dire quali sono quelli giusti.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _in(colonna, valori, ammetti_null=False):
    """Il testo di un CHECK `colonna IN (...)`, come `_check_in` di models.py."""
    clausola = f"{colonna} IN ({', '.join(repr(v) for v in valori)})"
    return f"{colonna} IS NULL OR {clausola}" if ammetti_null else clausola


URGENZE = ("Bassa", "Medio-Bassa", "Medio-Alta", "Alta")


def upgrade() -> None:
    # ── Anagrafiche ───────────────────────────────────────────────────────
    op.create_table(
        "azienda",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_azienda")),
        sa.UniqueConstraint("nome", name=op.f("uq_azienda_nome")),
    )
    op.create_table(
        "ruoli",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("descrizione", sa.Text),
        sa.Column("attivo", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="base"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ruoli")),
        sa.UniqueConstraint("nome", name=op.f("uq_ruoli_nome")),
        sa.CheckConstraint(_in("tipo", ("base", "funzionale")), name=op.f("ck_ruoli_tipo")),
    )
    op.create_table(
        "competenze",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("attivo", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competenze")),
        sa.UniqueConstraint("nome", name=op.f("uq_competenze_nome")),
    )
    op.create_table(
        "fasi_standard",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("template_nome", sa.String(80), nullable=False),
        sa.Column("fase_nome", sa.String(80), nullable=False),
        sa.Column("ordine", sa.SmallInteger, nullable=False),
        sa.Column("percentuale_ore", sa.Float),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fasi_standard")),
    )
    op.create_table(
        "dipendenti",
        sa.Column("id", sa.String(10), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("ruolo_id", sa.Integer),
        sa.Column("ore_sett", sa.SmallInteger, nullable=False),
        sa.Column("costo_ora", sa.Float),
        sa.Column("sede", sa.String(40)),
        sa.Column("email", sa.String(120)),
        sa.Column("data_assunzione", sa.Date),
        sa.Column("attivo", sa.Boolean, nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("azienda_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dipendenti")),
        sa.ForeignKeyConstraint(["ruolo_id"], ["ruoli.id"],
                                name=op.f("fk_dipendenti_ruolo_id_ruoli")),
        sa.ForeignKeyConstraint(["azienda_id"], ["azienda.id"],
                                name=op.f("fk_dipendenti_azienda_id_azienda")),
    )
    op.create_table(
        "utenti",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("ruolo_app", sa.String(20), nullable=False),
        sa.Column("dipendente_id", sa.String(10)),
        sa.Column("attivo", sa.Boolean, nullable=False),
        sa.Column("ultimo_login", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_utenti")),
        sa.UniqueConstraint("email", name=op.f("uq_utenti_email")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_utenti_dipendente_id_dipendenti")),
        sa.CheckConstraint(_in("ruolo_app", ("manager", "pm", "user")),
                           name=op.f("ck_utenti_ruolo_app")),
    )
    op.create_table(
        "dipendenti_competenze",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("dipendente_id", sa.String(10), nullable=False),
        sa.Column("competenza_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dipendenti_competenze")),
        sa.UniqueConstraint("dipendente_id", "competenza_id", name=op.f("uq_dipendenti_competenze_dipendente_id_competenza_id")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"], ondelete="CASCADE",
                                name=op.f("fk_dipendenti_competenze_dipendente_id_dipendenti")),
        sa.ForeignKeyConstraint(["competenza_id"], ["competenze.id"], ondelete="CASCADE",
                                name=op.f("fk_dipendenti_competenze_competenza_id_competenze")),
    )
    op.create_table(
        "dipendenti_ruoli_aggiuntivi",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("dipendente_id", sa.String(10), nullable=False),
        sa.Column("ruolo_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dipendenti_ruoli_aggiuntivi")),
        sa.UniqueConstraint("dipendente_id", "ruolo_id", name=op.f("uq_dipendenti_ruoli_aggiuntivi_dipendente_id_ruolo_id")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"], ondelete="CASCADE",
                                name=op.f("fk_dipendenti_ruoli_aggiuntivi_dipendente_id_dipendenti")),
        sa.ForeignKeyConstraint(["ruolo_id"], ["ruoli.id"], ondelete="CASCADE",
                                name=op.f("fk_dipendenti_ruoli_aggiuntivi_ruolo_id_ruoli")),
    )

    # ── Progetti, fasi, task, sottotask ───────────────────────────────────
    op.create_table(
        "progetti",
        sa.Column("id", sa.String(10), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("cliente", sa.String(150)),
        sa.Column("stato", sa.String(30), nullable=False),
        sa.Column("tipologia", sa.String(20), nullable=False),
        sa.Column("priorita", sa.String(10), nullable=False),
        sa.Column("urgenza", sa.String(16), nullable=False, server_default="Medio-Bassa"),
        sa.Column("data_inizio", sa.Date),
        sa.Column("data_fine", sa.Date),
        sa.Column("budget_ore", sa.Integer),
        sa.Column("giornate_vendute", sa.Float),
        sa.Column("valore_contratto", sa.Float),
        sa.Column("descrizione", sa.Text),
        sa.Column("fase_corrente", sa.String(80)),
        sa.Column("sede", sa.String(40)),
        sa.Column("pm_id", sa.String(10)),
        sa.Column("scadenza_bando", sa.Date),
        sa.Column("motivo_sospensione", sa.Text),
        sa.Column("lezioni_apprese", sa.Text),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("area", sa.String(20)),
        sa.Column("azienda_id", sa.Integer),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_progetti")),
        sa.ForeignKeyConstraint(["pm_id"], ["dipendenti.id"], name=op.f("fk_progetti_pm_id_dipendenti")),
        sa.ForeignKeyConstraint(["azienda_id"], ["azienda.id"],
                                name=op.f("fk_progetti_azienda_id_azienda")),
        sa.CheckConstraint(_in("stato", ("Bozza", "Da iniziare", "In esecuzione",
                                         "Sospeso", "Completato", "Annullato")),
                           name=op.f("ck_progetti_stato_ammessi")),
        sa.CheckConstraint(_in("tipologia", ("ordinario", "bando", "interna")),
                           name=op.f("ck_progetti_tipologia")),
        sa.CheckConstraint(_in("urgenza", URGENZE), name=op.f("ck_progetti_urgenza")),
    )
    op.create_table(
        "fasi",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("progetto_id", sa.String(10), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("ordine", sa.SmallInteger, nullable=False),
        sa.Column("data_inizio", sa.Date),
        sa.Column("data_fine", sa.Date),
        sa.Column("ore_vendute", sa.Float),
        sa.Column("ore_pianificate", sa.Float),
        sa.Column("stato", sa.String(20), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("urgenza", sa.String(16)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fasi")),
        sa.ForeignKeyConstraint(["progetto_id"], ["progetti.id"], ondelete="CASCADE",
                                name=op.f("fk_fasi_progetto_id_progetti")),
        sa.CheckConstraint(_in("stato", ("Da iniziare", "In corso", "Completata",
                                         "Sospesa", "Annullata")),
                           name=op.f("ck_fasi_stato_ammessi")),
        sa.CheckConstraint(_in("urgenza", URGENZE, ammetti_null=True),
                           name=op.f("ck_fasi_urgenza")),
    )
    op.create_table(
        "task",
        sa.Column("id", sa.String(10), nullable=False),
        sa.Column("progetto_id", sa.String(10), nullable=False),
        sa.Column("fase_id", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ore_stimate", sa.Integer),
        sa.Column("ore_pianificate", sa.Float),
        sa.Column("data_inizio", sa.Date),
        sa.Column("data_fine", sa.Date),
        sa.Column("stato", sa.String(20), nullable=False),
        sa.Column("motivo_blocco", sa.Text),
        sa.Column("profilo_richiesto", sa.String(60)),
        sa.Column("ordine", sa.SmallInteger),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("dipendente_id", sa.String(10)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task")),
        sa.ForeignKeyConstraint(["progetto_id"], ["progetti.id"], ondelete="CASCADE",
                                name=op.f("fk_task_progetto_id_progetti")),
        sa.ForeignKeyConstraint(["fase_id"], ["fasi.id"], ondelete="RESTRICT",
                                name=op.f("fk_task_fase_id_fasi")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_task_dipendente_id_dipendenti")),
        sa.CheckConstraint(_in("stato", ("Da iniziare", "In corso", "Completato",
                                         "Bloccato", "Sospeso", "Annullato",
                                         "Eliminato")),
                           name=op.f("ck_task_stato_ammessi")),
    )
    op.create_table(
        "sottotask",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("task_id", sa.String(10), nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ore_stimate", sa.Integer),
        sa.Column("ordine", sa.SmallInteger),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("stato", sa.String(20), nullable=False),
        sa.Column("dipendente_id", sa.String(10)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sottotask")),
        # Bersaglio della FK composta di blocchi_ore: un blocco su un
        # sottotask deve stare sullo stesso task del sottotask.
        sa.UniqueConstraint("id", "task_id", name=op.f("uq_sottotask_id_task_id")),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="CASCADE",
                                name=op.f("fk_sottotask_task_id_task")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_sottotask_dipendente_id_dipendenti")),
        sa.CheckConstraint(_in("stato", ("Da iniziare", "Sospeso", "Annullato")),
                           name=op.f("ck_sottotask_stato_pianificazione")),
    )
    op.create_table(
        "dipendenza_task",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("task_predecessore_id", sa.String(10), nullable=False),
        sa.Column("task_successore_id", sa.String(10), nullable=False),
        sa.Column("tipo_dipendenza", sa.String(2), nullable=False, server_default="FS"),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dipendenza_task")),
        sa.UniqueConstraint("task_predecessore_id", "task_successore_id",
                            name=op.f("uq_dipendenza_task_task_predecessore_id_task_successore_id")),
        sa.ForeignKeyConstraint(["task_predecessore_id"], ["task.id"], ondelete="CASCADE",
                                name=op.f("fk_dipendenza_task_task_predecessore_id_task")),
        sa.ForeignKeyConstraint(["task_successore_id"], ["task.id"], ondelete="CASCADE",
                                name=op.f("fk_dipendenza_task_task_successore_id_task")),
        sa.CheckConstraint("task_predecessore_id <> task_successore_id",
                           name=op.f("ck_dipendenza_task_no_self")),
        sa.CheckConstraint(_in("tipo_dipendenza", ("FS", "SS", "FF", "SF")),
                           name=op.f("ck_dipendenza_task_tipo")),
    )
    op.create_table(
        "assegnazioni",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("task_id", sa.String(10), nullable=False),
        sa.Column("dipendente_id", sa.String(10), nullable=False),
        sa.Column("ore_assegnate", sa.Integer),
        sa.Column("ruolo", sa.String(20)),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assegnazioni")),
        sa.UniqueConstraint("task_id", "dipendente_id", name=op.f("uq_assegnazioni_task_id_dipendente_id")),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="CASCADE",
                                name=op.f("fk_assegnazioni_task_id_task")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_assegnazioni_dipendente_id_dipendenti")),
    )

    # ── Consuntivazione ───────────────────────────────────────────────────
    op.create_table(
        "consuntivi",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("task_id", sa.String(10), nullable=False),
        sa.Column("dipendente_id", sa.String(10), nullable=False),
        sa.Column("settimana", sa.Date, nullable=False),
        sa.Column("compilato", sa.Boolean, nullable=False),
        sa.Column("data_compilazione", sa.DateTime),
        sa.Column("nota", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("stato_dichiarato", sa.String(20)),
        sa.Column("presa_visione", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ore_stimate_residue", sa.Float),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consuntivi")),
        sa.UniqueConstraint("task_id", "dipendente_id", "settimana", name=op.f("uq_consuntivi_task_id_dipendente_id_settimana")),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="CASCADE",
                                name=op.f("fk_consuntivi_task_id_task")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_consuntivi_dipendente_id_dipendenti")),
    )
    op.create_table(
        "consuntivo_sottotask",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("sottotask_id", sa.Integer, nullable=False),
        sa.Column("dipendente_id", sa.String(10), nullable=False),
        sa.Column("settimana", sa.Date, nullable=False),
        sa.Column("stato_dichiarato", sa.String(20)),
        sa.Column("nota", sa.Text),
        sa.Column("compilato", sa.Boolean, nullable=False),
        sa.Column("data_compilazione", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("presa_visione", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ore_stimate_residue", sa.Float),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consuntivo_sottotask")),
        sa.UniqueConstraint("sottotask_id", "dipendente_id", "settimana",
                            name=op.f("uq_consuntivo_sottotask_sottotask_id_dipendente_id_settimana")),
        sa.ForeignKeyConstraint(["sottotask_id"], ["sottotask.id"], ondelete="CASCADE",
                                name=op.f("fk_consuntivo_sottotask_sottotask_id_sottotask")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_consuntivo_sottotask_dipendente_id_dipendenti")),
        sa.CheckConstraint(_in("stato_dichiarato", ("In corso", "Completato", "Bloccato"),
                               ammetti_null=True),
                           name=op.f("ck_consuntivo_sottotask_stato")),
    )
    op.create_table(
        "blocchi_ore",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("dipendente_id", sa.String(10), nullable=False),
        sa.Column("giorno", sa.Date, nullable=False),
        sa.Column("task_id", sa.String(10), nullable=False),
        sa.Column("sottotask_id", sa.Integer),
        sa.Column("ore", sa.Numeric(5, 2), nullable=False),
        sa.Column("fonte", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blocchi_ore")),
        # NULLS NOT DISTINCT: un blocco sul task (sottotask NULL) e lo stesso
        # giorno vanno contati come duplicati, non come righe diverse.
        sa.UniqueConstraint("dipendente_id", "giorno", "task_id", "sottotask_id",
                            name=op.f("uq_blocchi_ore_dipendente_id_giorno_task_id_sottotask_id"), postgresql_nulls_not_distinct=True),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_blocchi_ore_dipendente_id_dipendenti")),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="CASCADE",
                                name=op.f("fk_blocchi_ore_task_id_task")),
        sa.ForeignKeyConstraint(["sottotask_id", "task_id"],
                                ["sottotask.id", "sottotask.task_id"], ondelete="CASCADE",
                                name=op.f("fk_blocchi_ore_sottotask_id_sottotask")),
        sa.CheckConstraint(_in("fonte", ("manuale", "storico")),
                           name=op.f("ck_blocchi_ore_fonte")),
        sa.CheckConstraint("ore > 0", name=op.f("ck_blocchi_ore_positive")),
    )
    op.create_index(op.f("ix_blocchi_ore_task_id"), "blocchi_ore", ["task_id"])
    op.create_index(op.f("ix_blocchi_ore_sottotask_id"), "blocchi_ore", ["sottotask_id"])

    # ── Segnalazioni, interventi, note ────────────────────────────────────
    op.create_table(
        "segnalazioni",
        sa.Column("id", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("priorita", sa.String(10), nullable=False),
        sa.Column("dipendente_id", sa.String(10)),
        sa.Column("progetto_id", sa.String(10)),
        sa.Column("dettaglio", sa.Text, nullable=False),
        sa.Column("fonte", sa.String(20), nullable=False),
        sa.Column("stato", sa.String(20), nullable=False),
        sa.Column("destinatario", sa.String(60)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_segnalazioni")),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"],
                                name=op.f("fk_segnalazioni_dipendente_id_dipendenti")),
        sa.ForeignKeyConstraint(["progetto_id"], ["progetti.id"],
                                name=op.f("fk_segnalazioni_progetto_id_progetti")),
    )
    op.create_table(
        "interventi",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("segnalazione_id", sa.String(10)),
        sa.Column("opzione_scelta", sa.String(10)),
        sa.Column("descrizione_opzione", sa.Text),
        sa.Column("azioni_applicate", sa.JSON),
        sa.Column("approvato_da", sa.String(10)),
        sa.Column("esito", sa.String(40)),
        sa.Column("nota", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interventi")),
        sa.ForeignKeyConstraint(["segnalazione_id"], ["segnalazioni.id"],
                                name=op.f("fk_interventi_segnalazione_id_segnalazioni")),
        sa.ForeignKeyConstraint(["approvato_da"], ["dipendenti.id"],
                                name=op.f("fk_interventi_approvato_da_dipendenti")),
    )
    op.create_table(
        "note_progetto",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("progetto_id", sa.String(10), nullable=False),
        sa.Column("autore_id", sa.String(10)),
        sa.Column("titolo", sa.String(200)),
        sa.Column("testo", sa.Text, nullable=False),
        sa.Column("tipo", sa.String(40)),
        sa.Column("created_at", sa.DateTime),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_note_progetto")),
        sa.ForeignKeyConstraint(["progetto_id"], ["progetti.id"], ondelete="CASCADE",
                                name=op.f("fk_note_progetto_progetto_id_progetti")),
        sa.ForeignKeyConstraint(["autore_id"], ["dipendenti.id"],
                                name=op.f("fk_note_progetto_autore_id_dipendenti")),
    )

    # ── Fotografie economiche (SAL e bollettino) ──────────────────────────
    for tabella in ("sal_snapshot", "bollettino_economico"):
        op.create_table(
            tabella,
            sa.Column("id", sa.Integer, nullable=False),
            sa.Column("progetto_id", sa.String(10), nullable=False),
            sa.Column("data_snapshot", sa.DateTime, nullable=False,
                      server_default=sa.func.now()),
            sa.Column("consolidato_da", sa.String(10)),
            sa.Column("nota", sa.Text),
            sa.Column("stato", postgresql.JSONB, nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{tabella}")),
            sa.ForeignKeyConstraint(["progetto_id"], ["progetti.id"],
                                    name=op.f(f"fk_{tabella}_progetto_id_progetti")),
        )
        op.create_index(op.f(f"ix_{tabella}_progetto_id"), tabella, ["progetto_id"])

    # ── Indici sulle chiavi più lette (passo B2) ──────────────────────────
    # Le FK non portano un indice da sole. Questi servono le letture frequenti:
    # i task e le fasi di un progetto, i task e i pezzi di una persona, «da chi
    # dipende» un task, la settimana di una persona nei consuntivi. Non c'è un
    # indice blocchi_ore(dipendente_id, giorno): è il prefisso della UNIQUE, che
    # lo serve già. Né consuntivo_sottotask(dipendente_id, settimana): ogni
    # lettura filtra anche per sottotask, la prima colonna della sua UNIQUE.
    op.create_index(op.f("ix_fasi_progetto_id"), "fasi", ["progetto_id"])
    op.create_index(op.f("ix_task_progetto_id"), "task", ["progetto_id"])
    op.create_index(op.f("ix_task_fase_id"), "task", ["fase_id"])
    op.create_index(op.f("ix_task_dipendente_id"), "task", ["dipendente_id"])
    op.create_index(op.f("ix_sottotask_task_id"), "sottotask", ["task_id"])
    op.create_index(op.f("ix_sottotask_dipendente_id"), "sottotask", ["dipendente_id"])
    op.create_index(op.f("ix_dipendenza_task_task_successore_id"), "dipendenza_task",
                    ["task_successore_id"])
    op.create_index(op.f("ix_consuntivi_dipendente_id"), "consuntivi",
                    ["dipendente_id", "settimana"])

    # ── Vista: le ore per settimana, sommate dai blocchi ──────────────────
    # Stesso testo di models.py, che la crea per `create_all`.
    op.execute("""
CREATE VIEW ore_settimanali AS
SELECT task_id,
       dipendente_id,
       (date_trunc('week', giorno))::date AS settimana,
       sum(ore) AS ore
FROM blocchi_ore
GROUP BY task_id, dipendente_id, (date_trunc('week', giorno))::date
""")

    # ── Sequenza del numero dei progetti (models.SEQUENZA_NUMERO_PROGETTO) ─
    op.execute("CREATE SEQUENCE progetti_numero_seq AS bigint START WITH 1 MINVALUE 1")

    # ── Dato di riferimento: il ruolo funzionale PM (vedi la docstring) ───
    op.execute(sa.text(
        "INSERT INTO ruoli (nome, descrizione, tipo, attivo) "
        "VALUES (:nome, :descrizione, 'funzionale', true)"
    ).bindparams(
        nome="PM",
        descrizione=(
            "Project Manager: dirige uno o più progetti. Ruolo funzionale, si "
            "ricopre IN AGGIUNTA all'inquadramento (un Senior Consultant può "
            "essere PM). Chi lo ricopre su uno specifico progetto resta "
            "Progetto.pm_id."
        ),
    ))


def downgrade() -> None:
    raise RuntimeError(
        "La baseline non si annulla: per tornare indietro si ricostruisce il "
        "database (schema public vuoto, alembic upgrade head, seed)."
    )
