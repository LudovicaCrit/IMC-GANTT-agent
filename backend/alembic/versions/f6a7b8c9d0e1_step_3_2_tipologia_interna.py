"""step_3_2_tipologia_interna

Step 3.2 (PIANO_3, 03/06/2026). Introduce la tipologia 'interna' per i progetti
e formalizza il CHECK constraint su progetti.tipologia.

CONTESTO
--------
Finora il campo progetti.tipologia era uno String(20) LIBERO: nessun CHECK a
livello DB (verificato: lo schema iniziale e733e23ae7a1 crea la colonna senza
constraint). I valori d'uso erano 'ordinario' e 'bando' per convenzione, non
per vincolo.

Il redesign del seed (03/06/2026) spacchetta il vecchio contenitore-unico P010
("Attività Interne" trattato come un progetto ordinario) in N progetti distinti
di tipologia 'interna': mansioni continuative, corsi/formazione, progetti di
innovazione. Da qui la necessità di:
  1. ammettere ufficialmente 'interna' tra le tipologie;
  2. formalizzare il CHECK perché d'ora in poi un typo (es. 'interno',
     'Interna') venga rifiutato dal DB invece di entrare silenziosamente.

Tipologie ammesse DOPO questa migration:
  'ordinario' | 'bando' | 'interna'

SAFETY (pattern debito silenzioso, PIANO_3 §2)
----------------------------------------------
Prima di applicare il CHECK, la migration NORMALIZZA eventuali valori fuori
lista presenti nel DB live, per evitare che il CHECK fallisca all'applicazione
su dati pre-esistenti. In particolare:
  - 'interno'/'Interna'/'INTERNA'  -> 'interna'
  - qualsiasi NULL o stringa vuota -> 'ordinario' (default storico)
  - il vecchio P010, se ancora 'ordinario', viene portato a 'interna'.
Se restano valori non riconducibili, la migration alza RuntimeError indicando
il valore, da sistemare a mano prima di riprovare (coerente con lo stile della
migration d4e5f6a7b8c9).

NOTA SORGENTE: data_legacy.py è già stato aggiornato nello stesso commit
(P010 spacchettato, tutti i progetti interni con tipologia='interna'). Un
re-seed da zero produce direttamente lo stato corretto. Vedi PIANO_3 §2 punto 1.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIPOLOGIE_AMMESSE = ('ordinario', 'bando', 'interna')
CK_NAME = 'ck_progetti_tipologia'


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Normalizzazione difensiva dei valori esistenti -------------------
    # mappa varianti note -> valore canonico
    op.execute(
        "UPDATE progetti SET tipologia = 'interna' "
        "WHERE LOWER(TRIM(tipologia)) IN ('interna', 'interno', 'internal')"
    )
    op.execute(
        "UPDATE progetti SET tipologia = 'ordinario' "
        "WHERE tipologia IS NULL OR TRIM(tipologia) = ''"
    )
    # il vecchio contenitore P010, se ancora ordinario, diventa interna
    op.execute(
        "UPDATE progetti SET tipologia = 'interna' WHERE id = 'P010'"
    )

    # 2) Verifica che non restino valori fuori lista ----------------------
    rows = bind.execute(
        sa.text("SELECT DISTINCT tipologia FROM progetti")
    ).fetchall()
    fuori = [r[0] for r in rows if r[0] not in TIPOLOGIE_AMMESSE]
    if fuori:
        raise RuntimeError(
            f"Migration f6a7b8c9d0e1: valori di tipologia non ammessi ancora "
            f"presenti: {fuori}. Normalizzare a {TIPOLOGIE_AMMESSE} prima di "
            f"riapplicare la migration."
        )

    # 3) Applica il CHECK constraint --------------------------------------
    # batch_alter_table per compatibilità SQLite (ALTER ADD CONSTRAINT non
    # supportato nativamente) oltre a Postgres.
    valori_sql = ", ".join(f"'{t}'" for t in TIPOLOGIE_AMMESSE)
    with op.batch_alter_table('progetti', schema=None) as batch_op:
        batch_op.create_check_constraint(
            CK_NAME,
            f"tipologia IN ({valori_sql})",
        )


def downgrade() -> None:
    # Rimuove il CHECK. NON tocca i dati: i progetti 'interna' restano tali,
    # semplicemente il campo torna a essere una stringa libera.
    with op.batch_alter_table('progetti', schema=None) as batch_op:
        batch_op.drop_constraint(CK_NAME, type_='check')
