"""popola task.ordine — materializza l'ordine implicito, senza cambiarlo

Scansione del 07/09/2026: `task.ordine` è NULL su 114 task su 114. La colonna
esiste, due lettori la usano — la relationship `Fase.task`
(`order_by="Task.ordine, Task.id"`) e il serializzatore SAL
(`data_db_impl.py:3840`, stesso `ORDER BY`) — ma NESSUNO la scrive. L'ordine
cade quindi sempre sul secondo criterio, `Task.id`.

PERCHÉ VA POPOLATA
──────────────────
È il residuo del BUG-3 (i task di una fase si riordinavano da soli dopo ogni
modifica). Il sintomo fu curato aggiungendo `Task.id` come secondo criterio: con
`ordine` tutta NULL, l'`ORDER BY` non aveva un discriminante e Postgres
restituiva l'ordine FISICO delle righe, che dopo un UPDATE cambia (MVCC scrive
una versione nuova in coda). La causa — la colonna vuota — è rimasta.

Finché resta NULL, `ordine` è una promessa non mantenuta: chiunque legga il
modello crede che l'ordine dei task sia governabile, e non lo è. Il primo che
proverà a implementare un riordino (come è già stato fatto per i sottotask,
`PUT /api/sottotask/{task_id}/riordina`) troverà 114 NULL e dovrà decidere lì,
di corsa, cosa fare dei task esistenti.

⚠ NON CAMBIA L'ORDINE VISIBILE — è il vincolo di questa migration
─────────────────────────────────────────────────────────────────
`ROW_NUMBER() OVER (PARTITION BY fase_id ORDER BY id)` assegna a ogni task la
sua posizione ATTUALE, quella che l'app già mostra. Dopo, ordinare per
`(ordine, id)` dà esattamente la stessa sequenza di prima — perché `ordine` è
stato costruito da quell'ordinamento.

Tre fatti verificati sul dato prima di scriverla, e sono le tre cose che
avrebbero potuto far cambiare l'ordine:

  1. PARTIZIONE PER FASE. Entrambi i lettori guardano i task di UNA fase alla
     volta (la relationship è per-fase, il serializzatore SAL filtra per
     `fase_id`). Numerare per fase è quindi la stessa grana della lettura;
     numerare globalmente avrebbe funzionato lo stesso, ma per caso.
  2. ID DI LUNGHEZZA UNIFORME — 4 caratteri su tutti i 114 task ('T001'…'T114').
     È ciò che rende l'ordinamento-stringa uguale a quello numerico: con id
     misti ('T99' e 'T100') l'ORDER BY di prima metteva 'T100' PRIMA di 'T99',
     e materializzare quell'ordine avrebbe congelato l'anomalia invece di
     lasciarla emergere.
  3. NESSUN TASK ORFANO — 0 righe con `fase_id IS NULL`, che sarebbero finite
     tutte in una partizione sola.

L'ORDINAMENTO LO FA POSTGRES, non Python: `ORDER BY id` dentro la window
function usa la STESSA collation dell'`ORDER BY` dell'applicazione. Ordinare in
Python avrebbe introdotto un secondo criterio di confronto che in teoria può
divergere da quello del database.

BASE 1 e non 0: `ordine` è una posizione leggibile da un umano nel Cantiere, non
un indice di array. `Fase.ordine` usa già la stessa convenzione.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Numera i task dentro ogni fase secondo l'ordine che hanno GIÀ."""
    conn = op.get_bind()

    prima = conn.execute(sa.text(
        "SELECT count(*) FILTER (WHERE ordine IS NULL), count(*) FROM task"
    )).first()
    print(f"   pre-flight: {prima[0]}/{prima[1]} task con ordine NULL")

    # Solo i NULL: se un giorno qualcuno avrà ordinato dei task a mano, questa
    # migration non deve sovrascriverlo. Oggi sono tutti, domani forse no.
    conn.execute(sa.text("""
        UPDATE task AS t
        SET ordine = n.pos
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY fase_id ORDER BY id) AS pos
            FROM task
            WHERE ordine IS NULL
        ) AS n
        WHERE t.id = n.id AND t.ordine IS NULL
    """))

    dopo = conn.execute(sa.text(
        "SELECT count(*) FILTER (WHERE ordine IS NULL), count(*) FROM task"
    )).first()
    print(f"✅ task.ordine popolata: {dopo[0]}/{dopo[1]} ancora NULL "
          f"(atteso 0), numerazione per fase a partire da 1")


def downgrade() -> None:
    """Riporta `ordine` a NULL su tutti i task.

    Reversibile SENZA perdita: l'ordine visibile non cambia né andando avanti né
    tornando indietro, perché `(ordine, id)` con `ordine` tutta NULL e `(ordine,
    id)` con `ordine` materializzata da quello stesso `id` producono la stessa
    sequenza. Si torna solo a non avere il discriminante.

    ⚠ Azzera anche eventuali riordini fatti a mano DOPO questa migration: se un
    giorno esisterà un riordino-task, il downgrade li perde. Oggi non esiste —
    `Task.ordine` non è scritta da nessun punto del codice — quindi non c'è
    niente da perdere.
    """
    op.execute("UPDATE task SET ordine = NULL")
    print("✅ task.ordine riportata a NULL")
