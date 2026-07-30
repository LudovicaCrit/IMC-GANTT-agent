"""sottotask e consuntivo_sottotask

Punto 1 dei SOTTOTASK (DESIGN_SOTTOTASK.md): solo le due tabelle. Le route, il
motore ore-derivate e il frontend arrivano nei passi successivi — questa
migration non li anticipa in nessun modo.

DUE ENTITÀ, DUE MESTIERI
------------------------
`sottotask` è la DEFINIZIONE del PM: il pezzo in cui scompone un task.
Condiviso, uguale per tutti i collaboratori del task. Non ha date proprie
(eredita la finestra del task) né assegnatario proprio (chi collabora al task
vede la stessa lista).
  - id PK
  - task_id     String(10) FK → task.id ON DELETE CASCADE  (muore col padre,
                come consuntivi.task_id)
  - nome        String(200) NOT NULL
  - ore_stimate Integer nullable — stessa filosofia di task.ore_stimate
                (convenzione R1: budget storico del PM, ore intere). Il nome è
                deliberatamente ALLINEATO a quello del task, non "stima_ore".
  - ordine      SmallInteger nullable — stesso tipo di task.ordine. Il default
                alla creazione (max(ordine)+1) è della route, non della colonna.
  - created_at / updated_at DateTime

`consuntivo_sottotask` è la DICHIARAZIONE del dipendente, speculare a
`consuntivi`: quella è una riga per (task, dipendente, settimana), questa una
riga per (sottotask, dipendente, settimana). Una per persona, perché più
collaboratori lavorano allo stesso task facendo cose diverse.
  - id PK
  - sottotask_id      Integer FK → sottotask.id ON DELETE CASCADE
  - dipendente_id     String(10) FK → dipendenti.id (senza cascade, come
                      consuntivi.dipendente_id: la persona non si cancella
                      portandosi via la storia)
  - settimana         Date NOT NULL — lunedì normalizzato, come consuntivi
  - stato_dichiarato  String(20) nullable, CHECK sui valori dichiarabili
  - percentuale       Integer nullable, CHECK 0-100
  - nota              Text nullable
  - compilato         Boolean NOT NULL (default applicativo, come consuntivi)
  - data_compilazione DateTime nullable
  - created_at        DateTime
  - UNIQUE (sottotask_id, dipendente_id, settimana) → uq_consuntivo_sottotask
    (speculare a uq_consuntivo)

PERCHÉ percentuale È Integer E NULLABLE
---------------------------------------
Integer 0-100: lo slider è a passi interi. Un Float renderebbe rappresentabile
un 37.428 che nessuna UI produce e nessun utente intende — falsa precisione su
un dato già soggettivo, più il rumore binario in un confronto tipo
`percentuale = 100`. Float nel modello resta riservato a ore e importi, dove i
decimali sono reali.

nullable=True è INTENZIONALE e centrale: se il dipendente non muove lo slider la
colonna resta NULL e il sistema NON inventa un default. Sarà il motore
ore-derivate (passo successivo) a derivare l'avanzamento dallo STATO quando
questa è NULL. Un default 0 direbbe «ha dichiarato zero», che è una cosa
diversa da «non si è espresso» — la stessa distinzione che regge
consuntivi.stato_dichiarato in e1f2a3b4c5d6.

I DUE CHECK
-----------
  - ck_consuntivo_sottotask_stato: stato_dichiarato IS NULL OR IN (...)
  - ck_consuntivo_sottotask_percentuale: percentuale IS NULL OR BETWEEN 0 AND 100

Entrambi ammettono esplicitamente NULL: qui NULL non è un dato mancante, è
«non si è espresso». Vivono nella migration e non nel modello, come
ck_task_stato_ammessi.

Nota di coerenza con e1f2a3b4c5d6: quella migration motivava l'ASSENZA di un
CHECK su consuntivi.stato_dichiarato col fatto che la colonna «dovrà accogliere
le dichiarazioni sui sottotask, dove la lista potrebbe non coincidere». Quel
timore decade proprio qui: le dichiarazioni sui sottotask hanno ora una tabella
propria, e su di essa la lista è nota e uguale a quella del task (STATI_DICHIARABILI
è «una proprietà della DICHIARAZIONE, non dell'entità» — models.py righe 87-88).
consuntivi.stato_dichiarato resta senza CHECK, com'è: questa migration non la tocca.

La lista degli stati è ricopiata qui sotto invece di essere importata da
models.STATI_DICHIARABILI, come fa e5f6a7b8c9d0 con TIPI_DIPENDENZA: una
migration è uno snapshot storico e deve continuare a produrre lo stesso DDL
anche quando il modello evolve. Se domani la tupla nel modello cambia, serve una
NUOVA migration che aggiorni il CHECK — non una rilettura silenziosa di questa.

FUORI PERIMETRO
---------------
La colonna legacy `consuntivi.sottotask_nota` (Text, dove oggi finisce la nota
scritta a mano libera) NON viene toccata: è un debito separato, con dati dentro,
e va affrontata con una migration sua. La nota-sottotask nuova vive in
consuntivo_sottotask.nota, attaccata al pezzo che descrive.

ORDINE
------
upgrade() crea `sottotask` PRIMA di `consuntivo_sottotask`, che ha la FK verso
la prima. downgrade() droppa in ordine inverso. Nessun backfill: sono due
tabelle nuove e vuote, non c'è nulla da cui derivare sottotask preesistenti
(spaccare a posteriori le note libere di sottotask_nota sarebbe inventare dati).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-30 15:24:01.514205

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copia locale e volutamente congelata di models.STATI_DICHIARABILI — vedi la
# nota "I DUE CHECK" nel docstring.
STATI_DICHIARABILI = ("In corso", "Completato", "Bloccato")


def upgrade() -> None:
    """Crea sottotask, poi consuntivo_sottotask (che ha la FK verso la prima)."""

    # ── 1. sottotask — la definizione del PM ───────────────────────────
    op.create_table(
        'sottotask',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=10), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('ore_stimate', sa.Integer(), nullable=True),
        sa.Column('ordine', sa.SmallInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    print("✅ Tabella sottotask creata")

    # ── 2. consuntivo_sottotask — la dichiarazione del dipendente ──────
    stati_str = ", ".join(f"'{s}'" for s in STATI_DICHIARABILI)
    op.create_table(
        'consuntivo_sottotask',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sottotask_id', sa.Integer(), nullable=False),
        sa.Column('dipendente_id', sa.String(length=10), nullable=False),
        sa.Column('settimana', sa.Date(), nullable=False),
        sa.Column('stato_dichiarato', sa.String(length=20), nullable=True),
        sa.Column('percentuale', sa.Integer(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('compilato', sa.Boolean(), nullable=False),
        sa.Column('data_compilazione', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sottotask_id'], ['sottotask.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dipendente_id'], ['dipendenti.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'sottotask_id', 'dipendente_id', 'settimana',
            name='uq_consuntivo_sottotask',
        ),
        # NULL ammesso: «non si è espresso sullo stato».
        sa.CheckConstraint(
            f"stato_dichiarato IS NULL OR stato_dichiarato IN ({stati_str})",
            name='ck_consuntivo_sottotask_stato',
        ),
        # NULL ammesso: «non ha mosso lo slider» — lo deriverà lo stato.
        sa.CheckConstraint(
            "percentuale IS NULL OR (percentuale >= 0 AND percentuale <= 100)",
            name='ck_consuntivo_sottotask_percentuale',
        ),
    )
    print("✅ Tabella consuntivo_sottotask creata (2 CHECK + uq_consuntivo_sottotask)")


def downgrade() -> None:
    """Droppa in ordine inverso: prima la figlia, poi la madre.

    Le due tabelle sono additive: il downgrade non deve riparare nulla altrove.
    Perde però le dichiarazioni sui sottotask e la scomposizione dei task, che
    non sono ricostruibili da nessun'altra parte — da tenere presente prima di
    eseguirlo.
    """
    op.drop_table('consuntivo_sottotask')
    print("✅ Tabella consuntivo_sottotask droppata")

    op.drop_table('sottotask')
    print("✅ Tabella sottotask droppata")
