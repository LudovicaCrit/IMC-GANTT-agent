"""
Il database si controlla all'avvio dell'applicazione, non all'import.

Cosa presidia (CLAUDE.md, regola 13):
  - `import main` funziona a database spento: importare non tocca il database;
  - all'avvio `attendi_database` ritenta finché Postgres non risponde, e alla
    fine si arrende con un messaggio che dice per quanto ha provato;
  - se manca lo schema si ferma subito, perché aspettando non arriva;
  - il lifespan di FastAPI fa il controllo e, con il database pronto, lascia
    partire l'applicazione.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from data import DatabaseIrraggiungibile, SchemaAssente, attendi_database

BACKEND = Path(__file__).resolve().parent.parent
# Una porta su cui non ascolta nessuno: la connessione viene rifiutata subito.
URL_SPENTO = "postgresql://nessuno:nessuna@127.0.0.1:1/gantt_test"


def test_import_main_a_database_spento():
    esito = subprocess.run(
        [sys.executable, "-c", "import main"], cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": URL_SPENTO},
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert esito.returncode == 0, esito.stderr[-2000:]


class _Verifica:
    """Una verifica finta: fallisce le prime `fallimenti` volte."""

    def __init__(self, fallimenti, errore=DatabaseIrraggiungibile):
        self.fallimenti, self.errore, self.chiamate = fallimenti, errore, 0

    def __call__(self):
        self.chiamate += 1
        if self.chiamate <= self.fallimenti:
            raise self.errore("Postgres non raggiungibile a (prova)")


def test_ritenta_finche_postgres_risponde():
    attese = []
    verifica = _Verifica(fallimenti=2)
    attendi_database(tentativi=5, attesa_s=7, verifica=verifica, dormi=attese.append)
    assert verifica.chiamate == 3
    assert attese == [7, 7]


def test_dopo_i_tentativi_si_arrende_e_dice_per_quanto():
    attese = []
    verifica = _Verifica(fallimenti=99)
    with pytest.raises(DatabaseIrraggiungibile, match="dopo 4 tentativi in circa 15 secondi"):
        attendi_database(tentativi=4, attesa_s=5, verifica=verifica, dormi=attese.append)
    assert verifica.chiamate == 4
    assert attese == [5, 5, 5]


def test_senza_schema_si_ferma_subito():
    attese = []
    verifica = _Verifica(fallimenti=99, errore=SchemaAssente)
    with pytest.raises(SchemaAssente):
        attendi_database(tentativi=5, attesa_s=5, verifica=verifica, dormi=attese.append)
    assert verifica.chiamate == 1
    assert attese == []


def test_il_lifespan_controlla_il_database_e_parte(db_test):
    """Con `with`, il TestClient esegue il lifespan: il controllo vero, sul
    gantt_test appena ricostruito, e poi una richiesta qualunque."""
    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app) as client:
        assert client.get("/api/auth/me").status_code in (401, 403)
