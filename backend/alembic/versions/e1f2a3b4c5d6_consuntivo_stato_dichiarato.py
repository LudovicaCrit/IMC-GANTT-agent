"""consuntivo_stato_dichiarato

Aggiunge consuntivi.stato_dichiarato: lo stato che il DIPENDENTE ha dichiarato
in quella settimana su quel task.

CONTESTO
--------
Lo stato dichiarato in Consuntivazione viene propagato su Task.stato (via
data.modifica_task, la stessa porta del Cantiere) e lì si ferma: Task.stato è
un campo a sovrascrittura, senza autore né data. Guardandolo non si distingue

    «Helena ha dichiarato In corso questa settimana»

da

    «il task è In corso perché il PM l'ha creato così e nessuno l'ha toccato».

Il frontend, non avendo altro su cui basarsi, finisce per attribuire al
dipendente scelte che non ha mai fatto. La dichiarazione va quindi registrata
dove ha senso: sulla riga della settimana in cui è stata fatta, che ha già
dipendente_id, settimana e data_compilazione.

Il flag `dichiarato` esposto da /api/consuntivi/me (derivato da
consuntivi.compilato) dice SE il dipendente si è espresso; questa colonna dice
CHE COSA ha dichiarato. Restano tre assi distinti e non ricavabili l'uno
dall'altro:
  - Task.stato               → a che punto è il task, oggi
  - consuntivi.compilato     → il dipendente ha compilato questa settimana
  - consuntivi.stato_dichiarato → che stato ha dichiarato, se si è espresso

NULLABLE, NESSUN DEFAULT, NESSUN BACKFILL
-----------------------------------------
NULL ha un significato pieno: «il dipendente non si è espresso sullo stato».
Vale per le righe già in tabella (scritte prima che questa colonna esistesse) e
per quelle che nascono da una compilazione di sole ore o di sola nota — casi
normali, non dati mancanti da riparare. Un default (es. 'In corso') inventerebbe
una dichiarazione mai fatta, cioè esattamente il problema che la colonna nasce
per risolvere. Per lo stesso motivo NON si fa backfill da Task.stato: quello è
lo stato di OGGI, non ciò che il dipendente disse in quella settimana, e
copiarlo all'indietro riscriverebbe la storia con dati inventati.

String(20): stessa misura di task.stato, di cui la colonna ospita gli stessi
valori (il sottoinsieme dichiarabile — models.STATI_DICHIARABILI).

Nessun CHECK constraint: il vincolo sui valori ammessi è più stretto di quello
di task.stato (solo In corso / Completato / Bloccato) ed è già applicato nel DTO
della route, prima che si scriva. Metterlo anche qui vincolerebbe al presente
una colonna che dovrà accogliere le dichiarazioni sui sottotask, dove la lista
potrebbe non coincidere.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'consuntivi',
        sa.Column('stato_dichiarato', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    # La colonna è additiva e nullable: il downgrade la rimuove e basta.
    # Perde le dichiarazioni registrate, che però non sono ricostruibili da
    # nessun'altra parte — da tenere presente prima di eseguirlo.
    op.drop_column('consuntivi', 'stato_dichiarato')
