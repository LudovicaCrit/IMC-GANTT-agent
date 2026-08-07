"""consuntivi: percentuale + ore_effettive, drop sottotask_nota

Porta sulla dichiarazione di TASK le due colonne che la dichiarazione di
SOTTOTASK ha già, e toglie di mezzo un moncone.

Step 4 — avanzamento uniforme (07/08/2026). È il fondamento dati della
generalizzazione del motore ore-derivate da «sottotask» a «unità di lavoro»:
oggi un task scomposto ha una percentuale (sui suoi pezzi) e un task non
scomposto no, quindi «a che punto sei» si risponde in due modi diversi a
seconda che qualcuno abbia scomposto il lavoro. Le due colonne rendono il task
dichiarabile ESATTAMENTE come un pezzo.

PERCHÉ QUI E NON IN UNA TABELLA NUOVA
-------------------------------------
Le due grane sono già isomorfe: `consuntivi` è UNIQUE su
(task_id, dipendente_id, settimana), `consuntivo_sottotask` su
(sottotask_id, dipendente_id, settimana). Identiche a meno del nome della
colonna-entità. E delle quattro colonne che servono a una dichiarazione,
`consuntivi` ne ha già due: `stato_dichiarato` (migration e1f2a3b4c5d6) e
`nota`. Mancano solo queste.

LE DUE COLONNE — gemelle esatte, non "simili"
---------------------------------------------
  percentuale   Integer  nullable  + CHECK 0-100
      Gemella di consuntivo_sottotask.percentuale (migration f2a3b4c5d6e7). Il
      CHECK ha la stessa forma e ammette esplicitamente NULL: qui NULL non è un
      dato mancante, è «non si è espresso sull'avanzamento», che è diverso da 0
      («l'ho guardato e non è avanzato»).

  ore_effettive Float    nullable  senza CHECK
      Gemella di consuntivo_sottotask.ore_effettive (migration c5d6e7f8a9b0).
      Nessun CHECK sul segno, per la stessa ragione: il precedente giusto è
      `ore_dichiarate`, che di CHECK non ne ha — le ore non hanno un massimo, e
      il minimo (non negativo) è imposto nel DTO della route, dove produce un
      400 leggibile invece di un IntegrityError. La colonna sorella
      `percentuale` ha un CHECK perché il suo dominio è chiuso; questa no.

IL DROP — `sottotask_nota`
--------------------------
Colonna Text creata dallo schema iniziale (e733e23ae7a1) e mai usata: nessuno
la legge, nessuno la scrive, in nessun punto del repo. Verificato prima del
drop su gantt_db: 2636 righe in tabella, **0 con valore non-NULL**.

Va via ADESSO e non in una pulizia futura perché il nome è a un passo da
`consuntivo_sottotask.nota`, che è quella vera e viene scritta dal motore. Due
colonne quasi omonime nella stessa area del modello, una viva e una morta, sono
una trappola per chi scriverà la prossima query — e questa migration è
esattamente il momento in cui qualcuno guarda quella tabella.

NESSUN BACKFILL
---------------
Le 2636 righe esistenti restano con `percentuale` e `ore_effettive` a NULL, che
è il valore giusto: sono dichiarazioni fatte quando l'avanzamento del task non
si dichiarava. Riempirle inventerebbe una percentuale che nessuno ha detto.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-07 11:52:33.407812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CK_PERCENTUALE = "ck_consuntivi_percentuale"


def upgrade() -> None:
    """
    1. ADD percentuale + il suo CHECK (gemello di quello sui sottotask).
    2. ADD ore_effettive.
    3. DROP sottotask_nota — verificato vuoto prima di procedere.
    """
    conn = op.get_bind()

    # ── 1. percentuale ──────────────────────────────────────────────────
    op.add_column(
        'consuntivi',
        sa.Column('percentuale', sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        CK_PERCENTUALE,
        'consuntivi',
        "percentuale IS NULL OR (percentuale >= 0 AND percentuale <= 100)",
    )
    print(f"✅ consuntivi.percentuale aggiunta (CHECK {CK_PERCENTUALE})")

    # ── 2. ore_effettive ────────────────────────────────────────────────
    op.add_column(
        'consuntivi',
        sa.Column('ore_effettive', sa.Float(), nullable=True),
    )
    print("✅ consuntivi.ore_effettive aggiunta")

    # ── 3. DROP sottotask_nota ──────────────────────────────────────────
    # Guardia prima di distruggere: se su un altro database quella colonna
    # avesse dati, li si perderebbe in silenzio. Meglio abortire e farsi
    # guardare in faccia.
    residui = conn.execute(sa.text(
        "SELECT COUNT(*) FROM consuntivi WHERE sottotask_nota IS NOT NULL"
    )).scalar() or 0
    if residui:
        raise RuntimeError(
            f"Migration d6e7f8a9b0c1 abortita: {residui} righe hanno "
            f"`consuntivi.sottotask_nota` valorizzata. La colonna risultava un "
            f"moncone mai scritto — su questo database non lo è. Verificare il "
            f"contenuto e decidere dove migrarlo prima di rilanciare."
        )

    op.drop_column('consuntivi', 'sottotask_nota')
    print("✅ consuntivi.sottotask_nota droppata (era vuota, 0 righe)")


def downgrade() -> None:
    """Ripristina sottotask_nota (vuota, com'era) e toglie le due colonne nuove.

    Reversibile senza perdita: `sottotask_nota` torna nella stessa forma (Text
    nullable) e con lo stesso contenuto che aveva, cioè nessuno. Si perdono
    invece le percentuali e le ore effettive dichiarate sui task nel frattempo:
    tornando indietro, quei task non hanno più un modo di dire quanto sono
    avanti, e le ore che il motore ne aveva derivato restano su
    `ore_dichiarate` senza più la dichiarazione che le spiegava.
    """
    op.add_column(
        'consuntivi',
        sa.Column('sottotask_nota', sa.Text(), nullable=True),
    )
    print("✅ consuntivi.sottotask_nota ripristinata (Text nullable, vuota)")

    op.drop_constraint(CK_PERCENTUALE, 'consuntivi', type_='check')
    op.drop_column('consuntivi', 'ore_effettive')
    op.drop_column('consuntivi', 'percentuale')
    print("✅ consuntivi.percentuale e ore_effettive droppate")
