"""
═══════════════════════════════════════════════════════════════════════════
backend/dataframes.py — Accessori ai DataFrame del modulo `data`
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone funzioni accessori ai DataFrame pandas mantenuti in `data.py`.
Le funzioni restituiscono **sempre il DataFrame corrente** (non una copia
statica) così dopo una scrittura + `_reload()` automatico vediamo i dati
aggiornati.

CONTENUTO
─────────
- `_DIPENDENTI()`  → DataFrame dipendenti
- `_PROGETTI()`    → DataFrame progetti
- `_TASKS()`       → DataFrame tasks
- `_CONSUNTIVI()`  → DataFrame consuntivi

PERCHÉ FUNZIONI (e non variabili)?
──────────────────────────────────
Se facessimo `DIPENDENTI = data_module.DIPENDENTI` (assegnazione diretta),
dopo un `_reload()` Python avrebbe ancora il riferimento al vecchio
DataFrame in memoria, non al nuovo. Le funzioni invece "leggono" il
modulo `data` ogni volta che vengono chiamate, garantendo dato fresco.

USO
───
```python
from dataframes import _DIPENDENTI, _PROGETTI, _TASKS, _CONSUNTIVI

# Ogni invocazione legge il DataFrame attuale
df_dip = _DIPENDENTI()
helena_row = df_dip[df_dip["id"] == "D004"].iloc[0]
```

DIPENDENZE
──────────
- `data` come `data_module` per accesso ai DataFrame.

STORIA
──────
Estratto da main.py il 6 maggio 2026 — usato precedentemente da molti
router che lo replicavano localmente.
═══════════════════════════════════════════════════════════════════════════
"""

import data as data_module


def _DIPENDENTI():
    """Restituisce il DataFrame dipendenti corrente."""
    return data_module.DIPENDENTI


def _PROGETTI():
    """Restituisce il DataFrame progetti corrente."""
    return data_module.PROGETTI


def _TASKS():
    """Restituisce il DataFrame tasks corrente."""
    return data_module.TASKS


def _CONSUNTIVI():
    """Restituisce il DataFrame consuntivi corrente."""
    return data_module.CONSUNTIVI
