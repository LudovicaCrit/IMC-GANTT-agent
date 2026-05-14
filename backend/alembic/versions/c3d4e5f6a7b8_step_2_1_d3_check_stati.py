"""step_2_1_d3_check_stati_fase_e_progetto

Step 2.1 D3 (handoff v15 §2.1, §3.3, §3.5 punto 3 e 5).

Introduce CHECK constraint a livello DB sugli stati di Fase e Progetto,
normalizzando preventivamente i dati esistenti per allinearli al design.

Stati FASE ammessi (al maschile/femminile per coerenza grammaticale):
  - "Da iniziare"
  - "In corso"
  - "Completata"
  - "Sospesa"
  - "Annullata"

Stati PROGETTO ammessi (handoff v15 §3.3 e §3.5 punto 3 — i 5 stati canonici):
  - "Bozza"            (handoff §3.5.5: "tutto ciò che non ha approvazione")
  - "In esecuzione"
  - "Sospeso"
  - "Completato"
  - "Annullato"

Normalizzazione dati (verificata da diagnostico_d3.py al 13 mag 2026):

  FASI:
  - "Completato" (3 righe) → "Completata" (coerenza grammaticale)

  PROGETTI:
  - "Vinto - Da pianificare" (1 riga, P007) → "Bozza"
    Era un residuo del vecchio modello bandi (quando i bandi erano entità
    separate dai progetti). Con il modello attuale, un progetto vinto ma
    non ancora pianificato è per definizione una Bozza (§3.5 punto 5).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-13 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATI_FASE_AMMESSI = ("Da iniziare", "In corso", "Completata", "Sospesa", "Annullata")
STATI_PROGETTO_AMMESSI = ("Bozza", "In esecuzione", "Sospeso", "Completato", "Annullato")


def upgrade() -> None:
    """Normalizza dati esistenti + aggiunge CHECK constraint."""
    conn = op.get_bind()

    # ── 1. Normalizzazione Fase.stato ──────────────────────────────────
    # "Completato" → "Completata" (3 righe al 13 mag 2026)
    conn.execute(sa.text(
        "UPDATE fasi SET stato = 'Completata' WHERE stato = 'Completato'"
    ))

    # ── 2. Normalizzazione Progetto.stato ─────────────────────────────
    # "Vinto - Da pianificare" → "Bozza" (residuo vecchio modello bandi,
    # handoff §3.5 punto 5: bozza = tutto ciò che non ha approvazione)
    conn.execute(sa.text(
        "UPDATE progetti SET stato = 'Bozza' WHERE stato = 'Vinto - Da pianificare'"
    ))

    # ── 3. Safety: verifica nessun valore fuori dall'enum ─────────────
    bad_fase = conn.execute(sa.text(
        "SELECT DISTINCT stato FROM fasi "
        f"WHERE stato NOT IN {STATI_FASE_AMMESSI}"
    )).fetchall()
    if bad_fase:
        raise RuntimeError(
            f"Stati Fase non normalizzati: {[r[0] for r in bad_fase]}. "
            "Normalizzarli prima di proseguire."
        )

    bad_prog = conn.execute(sa.text(
        "SELECT DISTINCT stato FROM progetti "
        f"WHERE stato NOT IN {STATI_PROGETTO_AMMESSI}"
    )).fetchall()
    if bad_prog:
        raise RuntimeError(
            f"Stati Progetto non normalizzati: {[r[0] for r in bad_prog]}. "
            "Normalizzarli prima di proseguire."
        )

    # ── 4. CHECK constraint Fase.stato ────────────────────────────────
    valori_fase = ", ".join(f"'{s}'" for s in STATI_FASE_AMMESSI)
    op.create_check_constraint(
        "ck_fasi_stato_ammessi",
        "fasi",
        f"stato IN ({valori_fase})"
    )

    # ── 5. CHECK constraint Progetto.stato ────────────────────────────
    valori_prog = ", ".join(f"'{s}'" for s in STATI_PROGETTO_AMMESSI)
    op.create_check_constraint(
        "ck_progetti_stato_ammessi",
        "progetti",
        f"stato IN ({valori_prog})"
    )


def downgrade() -> None:
    """Rimuove CHECK e ripristina valori storici."""
    op.drop_constraint("ck_progetti_stato_ammessi", "progetti", type_="check")
    op.drop_constraint("ck_fasi_stato_ammessi", "fasi", type_="check")

    conn = op.get_bind()
    # NOTA: il downgrade NON ripristina "Vinto - Da pianificare" su P007
    # perché non sappiamo per certo quale progetto era. Lascia "Bozza".
    # Il downgrade ripristina solo "Completato" sulle fasi (per simmetria).
    conn.execute(sa.text(
        "UPDATE fasi SET stato = 'Completato' WHERE stato = 'Completata'"
    ))
