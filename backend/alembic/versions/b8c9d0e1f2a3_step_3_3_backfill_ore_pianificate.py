"""step_3_3_backfill_ore_pianificate_task

Migration #3 — passo 1 (PIANO_3 §3.3, prerequisito SAL — DESIGN_SAL §6).

CONTESTO
--------
La distinzione tra le due colonne ore di Task è già nel modello (commenti in
models.Task), ma `Task.ore_pianificate` è finora rimasta DORMIENTE: il seed non
la valorizza e nessun codice la legge/scrive a livello task (la usa solo la
Fase). Risultato: 113/113 task con `ore_pianificate` NULL, mentre `ore_stimate`
è popolata su tutti.

Semantica che si vuole consolidare (NON si fondono i campi):
  - ore_stimate    : stima INIZIALE, si congela dopo l'avvio. Memoria storica
                     (IA-Archivio, confronti ex-post). NON si tocca qui.
  - ore_pianificate: piano CORRENTE, aggiornabile dal PM. È il prerequisito del
                     SAL, che lavora sul piano corrente.

Questa migration è un BACKFILL puro (le colonne esistono già, nessun DDL):
fa partire `ore_pianificate` dal valore di `ore_stimate` dove è ancora NULL, così
il piano corrente nasce uguale alla stima iniziale e poi può divergere.

SCOPE
-----
Solo `task`. La `fasi.ore_pianificate` è già piena (0 NULL) e la Fase non ha
`ore_stimate`: non si tocca.

SAFETY / SIMMETRIA
------------------
- upgrade: backfilla solo le righe NULL (idempotente: rilanciandolo non cambia
  nulla, perché dopo non ci sono più NULL).
- downgrade: re-NULL MIRATO — annulla solo le righe la cui `ore_pianificate`
  coincide ancora con `ore_stimate` (la "firma" del backfill). I piani che il PM
  avesse nel frattempo fatto divergere (ore_pianificate != ore_stimate) NON
  vengono toccati: il downgrade non distrugge lavoro di pianificazione.

NOTA SORGENTE: nello stesso commit `seed.py` valorizza `Task.ore_pianificate =
ore_stimate` all'insert, così un re-seed da zero nasce con 0 NULL senza dover
riapplicare questo backfill. Vedi PIANO_3 §3.3 (disciplina debito silenzioso).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill: piano corrente = stima iniziale, dove non ancora valorizzato.
    op.execute(
        "UPDATE task SET ore_pianificate = ore_stimate "
        "WHERE ore_pianificate IS NULL"
    )


def downgrade() -> None:
    # Re-NULL mirato: annulla solo la firma del backfill (pianificate == stimate),
    # preservando eventuali piani divergenti creati dopo la migration.
    op.execute(
        "UPDATE task SET ore_pianificate = NULL "
        "WHERE ore_pianificate = ore_stimate"
    )
