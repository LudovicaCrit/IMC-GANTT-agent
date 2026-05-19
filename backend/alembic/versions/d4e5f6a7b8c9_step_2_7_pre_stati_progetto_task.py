"""step_2_7_pre_stati_progetto_task

Step 2.7-pre (handoff v18, decisione 19/05/2026 pom).

Prepara il modello stati Progetto e Task per la pagina Cantiere (Step 2.7):

  PROGETTI — Aggiunge "Da iniziare":
  Stati ammessi prima:  Bozza, In esecuzione, Sospeso, Completato, Annullato
  Stati ammessi dopo:   Bozza, Da iniziare, In esecuzione, Sospeso, Completato, Annullato

  Semantica "Da iniziare": progetto APPROVATO dal cliente con fasi e (opz.)
  task pianificati, ma con data_inizio futura — non ancora partito.
  La transizione "Da iniziare → In esecuzione" è MANUALE (decisione PM,
  vedi handoff §3.5 "controllo non automazione"). Si propone via Home
  alert quando data_inizio <= oggi (futuro Blocco 3).

  TASK — Formalizza stati con CHECK constraint:
  Stati ammessi prima:  (nessun CHECK — qualsiasi stringa accettata)
  Stati ammessi dopo:   Da iniziare, In corso, Completato, Bloccato, Sospeso, Annullato

  Aggiunti Sospeso e Annullato perché la cascata Fase→Task (Step 2.4-bis B,
  commit 61795c5) li scrive già a runtime quando una fase viene sospesa o
  annullata. Finora il DB li accettava per assenza di CHECK; ora li ammette
  formalmente.

Pre-condizioni e safety:
  - DIAGNOSTICO TASK: prima di applicare il CHECK su task.stato, verifico
    che TUTTI i task abbiano stato ∈ {Da iniziare, In corso, Completato,
    Bloccato, Sospeso, Annullato}. Se ce ne sono di "strani" (es. "Da fare"
    visto in _costanti.js riga 23 come colore fantasma) la migration alza
    RuntimeError indicando il valore problematico, da normalizzare prima.
  - NESSUN UPDATE retroattivo: la migration NON converte progetti esistenti
    a "Da iniziare". Lo stato "Da iniziare" sarà usato solo per i nuovi
    progetti creati via Wizard Cantiere (Step 2.7). Decisione consapevole:
    i dati esistenti sono coerenti con la semantica corrente, non vanno
    riclassificati automaticamente (futuri dati pilota verranno popolati
    correttamente al ridisegno DB).

Coerenza frontend:
  Dopo questa migration, AGGIORNARE _costanti.js per allineare:
    STATI_TASK = ['Da iniziare', 'In corso', 'Completato', 'Bloccato', 'Sospeso', 'Annullato']
    STATI_PROGETTO = ['Bozza', 'Da iniziare', 'In esecuzione', 'Sospeso', 'Completato', 'Annullato']
  (sono allegati i file aggiornati nel commit).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-20 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Nuovi stati canonici (allineati a _costanti.js dopo questa migration)
STATI_PROGETTO_AMMESSI_NUOVI = (
    "Bozza",
    "Da iniziare",          # NUOVO
    "In esecuzione",
    "Sospeso",
    "Completato",
    "Annullato",
)
STATI_TASK_AMMESSI_NUOVI = (
    "Da iniziare",
    "In corso",
    "Completato",
    "Bloccato",
    "Sospeso",              # NUOVO formalizzato
    "Annullato",            # NUOVO formalizzato
)

# Vecchio set ammessi per il downgrade (5 stati progetto pre-migration)
STATI_PROGETTO_AMMESSI_VECCHI = (
    "Bozza",
    "In esecuzione",
    "Sospeso",
    "Completato",
    "Annullato",
)


def upgrade() -> None:
    """
    1. Diagnostico task: verifica nessun task ha stato "strano"
    2. Drop CHECK progetto esistente + ricreazione con "Da iniziare" aggiunto
    3. Crea CHECK task ex-novo con 6 stati formali
    """
    conn = op.get_bind()

    # ── 1. DIAGNOSTICO TASK — verifica valori esistenti ────────────────
    # I task del seed avevano stati in {Da iniziare, In corso, Completato,
    # Bloccato}. Dopo l'uso dell'app via cascata 2.4-bis B potrebbero esserci
    # task con Sospeso/Annullato. Tutti questi sono ammessi nel nuovo CHECK.
    # Eventuali valori fuori (es. "Da fare", "Eliminato" non-soft-deleted)
    # fanno alzare un errore informativo.
    valori_strani = conn.execute(sa.text(
        "SELECT DISTINCT stato, COUNT(*) as n FROM task "
        f"WHERE stato NOT IN {STATI_TASK_AMMESSI_NUOVI} "
        "GROUP BY stato"
    )).fetchall()

    if valori_strani:
        descrizione = ", ".join(f"'{v[0]}' ({v[1]} task)" for v in valori_strani)
        raise RuntimeError(
            f"Migration Step 2.7-pre abortita: trovati stati task non ammessi: "
            f"{descrizione}. "
            f"Stati ammessi: {STATI_TASK_AMMESSI_NUOVI}. "
            f"Normalizzare manualmente con UPDATE prima di rilanciare la migration. "
            f"Esempio: UPDATE task SET stato = 'Da iniziare' WHERE stato = 'Da fare';"
        )

    print(f"✅ Diagnostico task: tutti i task hanno stato in {STATI_TASK_AMMESSI_NUOVI}")

    # ── 2. PROGETTI — aggiorna CHECK constraint ────────────────────────
    # In Postgres non si può "alterare" un CHECK: si droppa e si ricrea.
    op.drop_constraint("ck_progetti_stato_ammessi", "progetti", type_="check")

    valori_prog = ", ".join(f"'{s}'" for s in STATI_PROGETTO_AMMESSI_NUOVI)
    op.create_check_constraint(
        "ck_progetti_stato_ammessi",
        "progetti",
        f"stato IN ({valori_prog})"
    )
    print(f"✅ Progetti: CHECK constraint aggiornato con {STATI_PROGETTO_AMMESSI_NUOVI}")

    # ── 3. TASK — crea CHECK constraint ex-novo ────────────────────────
    # Non esisteva CHECK su task.stato prima di oggi (Step 2.1 D3 ha messo
    # CHECK solo su fasi e progetti). Aggiungiamo il presidio.
    valori_task = ", ".join(f"'{s}'" for s in STATI_TASK_AMMESSI_NUOVI)
    op.create_check_constraint(
        "ck_task_stato_ammessi",
        "task",
        f"stato IN ({valori_task})"
    )
    print(f"✅ Task: CHECK constraint creato con {STATI_TASK_AMMESSI_NUOVI}")

    # NESSUN UPDATE retroattivo. I dati esistenti restano com'erano:
    # gli stati attuali sono coerenti con la semantica.


def downgrade() -> None:
    """
    Rollback:
    1. Drop CHECK task creato qui
    2. Drop CHECK progetto (con 6 stati) e ricrea con 5 (senza "Da iniziare")
    3. NOTA: se ci sono progetti con stato="Da iniziare" il downgrade fallisce
       (è giusto: in rollback si vede che ce ne sono e si decide caso per caso)
    """
    conn = op.get_bind()

    # ── 1. Drop CHECK task ─────────────────────────────────────────────
    op.drop_constraint("ck_task_stato_ammessi", "task", type_="check")

    # ── 2. Safety: nessun progetto con "Da iniziare" prima del downgrade ─
    conta_da_iniziare = conn.execute(sa.text(
        "SELECT COUNT(*) FROM progetti WHERE stato = 'Da iniziare'"
    )).scalar()
    if conta_da_iniziare and conta_da_iniziare > 0:
        raise RuntimeError(
            f"Downgrade Step 2.7-pre abortito: {conta_da_iniziare} progetti hanno "
            f"stato 'Da iniziare', non più ammesso nello stato precedente della migration. "
            f"Riclassificarli manualmente (es. 'In esecuzione' o 'Bozza') prima del downgrade."
        )

    # ── 3. Ricrea CHECK progetto con 5 stati (rimuove "Da iniziare") ───
    op.drop_constraint("ck_progetti_stato_ammessi", "progetti", type_="check")
    valori_prog_vecchi = ", ".join(f"'{s}'" for s in STATI_PROGETTO_AMMESSI_VECCHI)
    op.create_check_constraint(
        "ck_progetti_stato_ammessi",
        "progetti",
        f"stato IN ({valori_prog_vecchi})"
    )
