"""
IMC-Group GANTT Agent — Data Layer (router)

Se il database SQLite esiste e ha dati → usa il db (persistente).
Altrimenti → fallback su data_legacy.py (in memoria, si resetta al riavvio).

Per attivare la persistenza:
  python models.py   # crea le tabelle
  python seed.py     # popola con dati fittizi

Interfaccia pubblica (stessa firma in entrambi i modi):
  DIPENDENTI, PROGETTI, TASKS, CONSUNTIVI  — DataFrame pandas
  get_dipendente, get_progetto, get_tasks_progetto, ...
  aggiungi_task, modifica_task, cambia_stato_progetto, calcola_impatto_saturazione
  get_segnalazioni, aggiungi_segnalazione
"""

import os
from pathlib import Path

# ── Prova il database ──
_DB_OK = False
try:
    from models import get_session, Dipendente as _DipModel
    _s = get_session()
    _DB_OK = _s.query(_DipModel).count() > 0
    _s.close()
except Exception:
    pass

if _DB_OK:
    print("✓ Database attivo — dati persistenti")
    # Importa TUTTO dal modulo database
    from data_db_impl import *
else:
    print("⚠ Database non disponibile — fallback in memoria (esegui: python seed.py)")
    # Importa TUTTO dal modulo legacy
    from data_legacy import *