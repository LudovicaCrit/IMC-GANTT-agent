"""
Colori ed etichette degli stati di progetto, fase e task.

La fonte è condiviso/stati.json, nella radice del repo: lo stesso file che il
frontend importa (src/components/_shared/statiColori.js) e che Vite incorpora
nel bundle alla build. Il backend lo legge dal disco a ogni richiesta: è
piccolo, e così una modifica vale senza riavviare.
"""

import json
from pathlib import Path

FILE_STATI = Path(__file__).resolve().parent.parent / "condiviso" / "stati.json"


def carica_stati() -> dict:
    """Il contenuto del file: {"progetto": {...}, "fase": {...}, "task": {...},
    "ignoto": {"colore": ...}}, con ogni stato → {"colore": "#rrggbb",
    "etichetta": ...}. L'ordine delle chiavi è quello della legenda."""
    return json.loads(FILE_STATI.read_text(encoding="utf-8"))


def colore_stato(stati: dict, livello: str, stato: str) -> str:
    """Il colore esadecimale di uno stato, «#rrggbb». Uno stato ignoto prende
    il colore neutro, come nel frontend: meglio una barra neutra di un buco."""
    voce = stati.get(livello, {}).get(stato)
    return voce["colore"] if voce else stati["ignoto"]["colore"]
