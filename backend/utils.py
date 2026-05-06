"""
═══════════════════════════════════════════════════════════════════════════
backend/utils.py — Helper utility condivise
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Contiene helper di utility generale, condivise da più router e moduli del
backend. Estratto da main.py il 6 maggio 2026 nell'ambito della pulizia
post-refactoring (chore: estrazione helper condivisi).

CONTENUTO
─────────
- `get_oggi()` — clock corrente, restituisce datetime.now()
   Funzione triviale ma centralizzata per facilitare:
   - testing (in futuro mockable)
   - eventuale fuso orario fisso (UTC, Europe/Rome, ecc. — R2)
   - eventuale "data congelata" per demo

📌 TODO R2: introdurre supporto per fuso orario esplicito (oggi
   `datetime.now()` usa il fuso del sistema, va bene per IMC ma
   potrebbe scocciare in deployment cloud).

STORIA
──────
Estratto da main.py il 6 maggio 2026 — usato precedentemente da molti
router che lo replicavano localmente (debito tecnico segnalato negli
header dei router stessi come "TODO: estrarre in moduli condivisi").
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime


def get_oggi():
    """Restituisce datetime.now() — clock corrente del sistema.

    Centralizzato qui per facilitare testing futuro (mocking) e
    eventuale gestione fuso orario esplicita in R2.
    """
    return datetime.now()
