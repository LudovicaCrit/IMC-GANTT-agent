"""Configurazione comune dei test.

I moduli dell'applicazione (models, data_db_impl, scenario_engine…) stanno
direttamente in backend/ e si importano «piatti» (`from models import …`),
come fa uvicorn quando parte da backend/. Qui si aggiunge backend/ in testa a
sys.path, ricavandolo dalla posizione di questo file: funziona da qualunque
cartella si lanci pytest e su qualunque sistema operativo.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
