"""sottotask stato pianificazione

Aggiunge sottotask.stato: lo stato di PIANIFICAZIONE del sottotask, quello che
il PM governa dal Cantiere sulla definizione del pezzo di lavoro.

Step 2 dei sottotask (Cantiere backend). La colonna è il prerequisito delle
route CRUD: senza di essa il PM potrebbe solo creare ed eliminare, e
l'eliminazione di un sottotask con lavoro dichiarato sopra distruggerebbe dati
che vanno invece conservati (vedi "PERCHÉ SERVE" sotto).

DUE ASSI, NON UN DOPPIONE
-------------------------
  - sottotask.stato (questa colonna)         → Da iniziare | Sospeso | Annullato
    Il PM dice se il pezzo è da fare, in pausa o cancellato dal piano. Vive
    sulla DEFINIZIONE, condivisa da tutti i collaboratori del task.
  - consuntivo_sottotask.stato_dichiarato    → In corso | Completato | Bloccato
    Il dipendente dice a che punto è LUI su quel pezzo, in QUELLA settimana.

I tre stati dichiarabili NON sono replicati qui, deliberatamente. Su una
definizione condivisa "In corso" non significherebbe nulla — in corso per chi?
Sarebbe una seconda verità sull'avanzamento, senza autore né settimana:
esattamente il difetto che il commento su consuntivi.stato_dichiarato
(migration e1f2a3b4c5d6) descrive per task.stato, e che i sottotask non devono
ereditare. Per lo stesso motivo i tre di pianificazione non compaiono in
consuntivo_sottotask.stato_dichiarato, il cui CHECK (ck_consuntivo_sottotask_stato,
migration f2a3b4c5d6e7) ammette solo i dichiarabili. I due CHECK sono le due
metà dello stesso confine.

PERCHÉ SERVE — «SEGNALA, NON IMPONE»
------------------------------------
Un sottotask su cui qualcuno ha già dichiarato lavoro non si cancella: quel
lavoro è successo, e la storia serve (consuntivazione, SAL, IA-Archivio). Ma il
PM deve poter togliere dal piano un pezzo che non si farà più. "Annullato" è
la risposta: rimuove il pezzo dal piano CONSERVANDO le dichiarazioni. Senza
questa colonna l'unica uscita sarebbe il DELETE, cioè la perdita del dato.

NOT NULL SU TABELLA POPOLATA
----------------------------
Pattern di a7b8c9d0e1f2 (dipendenti.azienda_id): colonna nullable → riempimento
→ verifica che non restino NULL → alter a NOT NULL. Qui il riempimento lo fa il
server_default, essendo il valore un letterale costante e non una lookup.

Il server_default viene poi RIMOSSO: le colonne `stato` sorelle (task, fasi,
progetti, segnalazioni) sono tutte NOT NULL senza default a livello DB — il
default vive solo nel modello SQLAlchemy (`default="Da iniziare"`). Lasciarlo
qui creerebbe l'unica colonna stato del sistema con un default DB, cioè una
divergenza silenziosa da spiegare a chi legge lo schema domani.

Al 30/07/2026 la tabella è di fatto vuota (creata da f2a3b4c5d6e7, nessuna
route la scrive ancora), quindi backfill e verifica non hanno nulla da fare. Ci
sono comunque: la migration deve essere corretta anche riapplicata su un
database dove i sottotask esistono già.

Nessun diagnostico sui valori preesistenti (come fa d4e5f6a7b8c9 prima di
imporre ck_task_stato_ammessi): non serve, la colonna nasce adesso e ogni riga
può valere solo 'Da iniziare'.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-30 16:48:58.146149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copia locale e volutamente congelata di models.STATI_PIANIFICAZIONE_SOTTOTASK,
# come e5f6a7b8c9d0 fa con TIPI_DIPENDENZA: una migration è uno snapshot storico
# e deve emettere lo stesso DDL anche quando il modello evolve. Se domani la
# tupla cambia, serve una NUOVA migration che aggiorni il CHECK.
STATI_PIANIFICAZIONE = ("Da iniziare", "Sospeso", "Annullato")
STATO_DEFAULT = "Da iniziare"

CK_NAME = "ck_sottotask_stato_pianificazione"


def upgrade() -> None:
    """
    1. ADD COLUMN nullable con server_default (riempie le righe esistenti).
    2. Verifica che non resti alcun NULL prima di imporre il vincolo.
    3. ALTER a NOT NULL.
    4. Rimuove il server_default (allineamento alle colonne stato sorelle).
    5. CHECK sui tre stati di pianificazione.
    """
    conn = op.get_bind()

    # ── 1. ADD COLUMN ───────────────────────────────────────────────────
    op.add_column(
        'sottotask',
        sa.Column('stato', sa.String(length=20), nullable=True,
                  server_default=STATO_DEFAULT),
    )
    print(f"✅ Colonna sottotask.stato aggiunta (server_default '{STATO_DEFAULT}')")

    # ── 2. VERIFICA: nessun NULL residuo ────────────────────────────────
    # Il server_default ha riempito le righe preesistenti. Il controllo è il
    # presidio del pattern a7b8c9d0e1f2: non si impone NOT NULL a occhi chiusi.
    residui = conn.execute(sa.text(
        "SELECT COUNT(*) FROM sottotask WHERE stato IS NULL"
    )).scalar()
    if residui and residui > 0:
        raise RuntimeError(
            f"Migration a3b4c5d6e7f8 abortita: {residui} sottotask hanno stato "
            f"NULL dopo l'ADD COLUMN con server_default. Valorizzarli a mano "
            f"(UPDATE sottotask SET stato = '{STATO_DEFAULT}' WHERE stato IS NULL) "
            f"e riapplicare la migration."
        )

    n_righe = conn.execute(sa.text("SELECT COUNT(*) FROM sottotask")).scalar() or 0
    print(f"✅ Verifica NULL: nessun residuo ({n_righe} sottotask in tabella)")

    # ── 3. NOT NULL ─────────────────────────────────────────────────────
    op.alter_column('sottotask', 'stato',
                    existing_type=sa.String(length=20), nullable=False)
    print("✅ sottotask.stato ora NOT NULL")

    # ── 4. VIA IL server_default ─────────────────────────────────────────
    # Serviva solo a riempire le righe preesistenti. Da qui in avanti il default
    # è applicativo (models.Sottotask.stato), come per task/fasi/progetti.stato.
    op.alter_column('sottotask', 'stato',
                    existing_type=sa.String(length=20), server_default=None)
    print("✅ server_default rimosso (default applicativo, come le stato sorelle)")

    # ── 5. CHECK ────────────────────────────────────────────────────────
    valori = ", ".join(f"'{s}'" for s in STATI_PIANIFICAZIONE)
    op.create_check_constraint(CK_NAME, 'sottotask', f"stato IN ({valori})")
    print(f"✅ CHECK {CK_NAME} creato con {STATI_PIANIFICAZIONE}")


def downgrade() -> None:
    """Drop del CHECK, poi della colonna.

    Perde l'informazione su quali sottotask erano Sospesi o Annullati: tornando
    indietro tutti i pezzi del piano ridiventano indistinguibili. Le
    dichiarazioni in consuntivo_sottotask non vengono toccate.
    """
    op.drop_constraint(CK_NAME, 'sottotask', type_='check')
    print(f"✅ CHECK {CK_NAME} droppato")

    op.drop_column('sottotask', 'stato')
    print("✅ Colonna sottotask.stato droppata")
