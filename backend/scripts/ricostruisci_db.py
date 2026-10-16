"""
ricostruisci_db.py — ricostruisce da zero un database del GANTT.

La procedura è una sola, e vive qui: schema `public` vuoto, `alembic upgrade
head`, `seed.py` con il lunedì della settimana corrente, così le date del seed
slittano a oggi (vedi seed.py). La usano chi lavora (da riga di comando) e i test
(`tests/conftest.py`, fixture `db_test`), così non esistono due copie che
possano divergere.

GUARDIE
  - il nome del database deve stare in NOMI_AMMESSI, e il server deve
    rispondere con lo stesso nome a `SELECT current_database()`;
  - la conferma è esplicita: chi chiama ripete il nome del database. Da riga
    di comando lo si scrive con --conferma o lo si digita quando chiesto.

L'impronta dei dipendenti si stampa prima e dopo: è il controllo che la
ricostruzione ha riportato le stesse persone (vedi CLAUDE.md).

Uso (dalla cartella backend/):
    python scripts/ricostruisci_db.py                  # il database di DATABASE_URL
    python scripts/ricostruisci_db.py --database gantt_test
    python scripts/ricostruisci_db.py --conferma gantt_db
"""

import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parent.parent
NOMI_AMMESSI = ("gantt_db", "gantt_test")

# La formula di CLAUDE.md: solo i campi di significato, senza id né date
# tecniche, con i numeri a due decimali fissi. Così non cambia quando il
# database si ricostruisce, né quando una colonna numerica cambia tipo.
SQL_IMPRONTA = """
SELECT md5(string_agg(r::text, '|' ORDER BY r.nome, r::text))
FROM (SELECT d.nome, ru.nome AS inquadramento,
             round(d.ore_sett::numeric, 2) AS ore_sett,
             round(d.costo_ora::numeric, 2) AS costo_ora,
             a.nome AS societa, d.attivo
      FROM dipendenti d
      LEFT JOIN ruoli ru ON ru.id = d.ruolo_id
      JOIN azienda a ON a.id = d.azienda_id) r
"""


class RicostruzioneRifiutata(Exception):
    """Una guardia ha fermato la ricostruzione prima di toccare il database."""


def nome_database(url: str) -> str:
    return make_url(url).database


def controlla_nome(url: str, conferma: str) -> str:
    """Le due guardie che non chiedono il database: nome ammesso e conferma
    uguale al nome. Restituisce il nome."""
    nome = nome_database(url)
    if nome not in NOMI_AMMESSI:
        raise RicostruzioneRifiutata(
            f"il database «{nome}» non è fra quelli ricostruibili: {', '.join(NOMI_AMMESSI)}")
    if conferma != nome:
        raise RicostruzioneRifiutata(
            f"conferma mancante o diversa: per ricostruire «{nome}» va ripetuto il suo nome")
    return nome


def impronta_dipendenti(url: str) -> str | None:
    """L'impronta dei dipendenti, o None se la tabella non c'è (database vuoto)."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if not inspect(conn).has_table("dipendenti"):
                return None
            return conn.execute(text(SQL_IMPRONTA)).scalar()
    finally:
        engine.dispose()


def _esegui(url: str, *argomenti: str, schema: str | None = None) -> str:
    """Un comando Python del backend in un processo figlio, con DATABASE_URL
    puntato al database da ricostruire. Processo separato perché alembic
    riconfigura il logging alla sua maniera, e il chiamante non deve subirlo.

    `schema` sposta il lavoro in uno schema diverso da public, con il
    search_path passato a libpq da PGOPTIONS: nell'URL andrebbe codificato
    con un «%», che il configparser di alembic leggerebbe come interpolazione."""
    ambiente = {**os.environ, "DATABASE_URL": url}
    if schema is not None:
        ambiente["PGOPTIONS"] = f"-c search_path={schema}"
    esito = subprocess.run(
        [sys.executable, *argomenti], cwd=BACKEND, env=ambiente,
        capture_output=True, text=True, encoding="utf-8",
    )
    if esito.returncode != 0:
        raise RuntimeError(f"`{' '.join(argomenti)}` fallito:\n{esito.stdout}\n{esito.stderr}")
    return esito.stdout


def applica_migration(url: str, schema: str | None = None) -> None:
    """`alembic upgrade head` sul database di `url`, nello schema public o in
    `schema`. Lo usa anche il test di allineamento fra baseline e modello."""
    _esegui(url, "-m", "alembic", "upgrade", "head", schema=schema)


def lunedi_corrente() -> date:
    oggi = date.today()
    return oggi - timedelta(days=oggi.weekday())


def carica_seed(url: str, lunedi_riferimento: date, schema: str | None = None) -> str:
    """`seed.py` sul database di `url`, con le date spostate al lunedì dato.
    Restituisce la riga in cui il seed dice di quanto le ha spostate."""
    uscita = _esegui(url, "seed.py", "--lunedi", lunedi_riferimento.isoformat(), schema=schema)
    return next((r.strip() for r in uscita.splitlines() if "date spostate" in r), "")


def ricostruisci(url: str, conferma: str,
                 lunedi_riferimento: date | None = None) -> tuple[str | None, str | None, str]:
    """Svuota lo schema public, applica le migration e carica il seed con le
    date spostate al lunedì di riferimento (assente: quello corrente).
    Restituisce l'impronta dei dipendenti prima e dopo, e lo spostamento."""
    nome = controlla_nome(url, conferma)
    prima = impronta_dipendenti(url)

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            risponde = conn.execute(text("SELECT current_database()")).scalar()
            if risponde != nome:
                raise RicostruzioneRifiutata(
                    f"l'URL dice «{nome}», il server risponde «{risponde}»")
            conn.execute(text("DROP SCHEMA public CASCADE"))
            # Lo schema si ricrea com'era: proprietario pg_database_owner e
            # USAGE a tutti. Il database non si droppa mai: chi lavora può non
            # avere il permesso di ricrearlo.
            conn.execute(text("CREATE SCHEMA public AUTHORIZATION pg_database_owner"))
            conn.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    finally:
        engine.dispose()

    applica_migration(url)
    spostamento = carica_seed(url, lunedi_riferimento or lunedi_corrente())
    return prima, impronta_dipendenti(url), spostamento


def main() -> int:
    parser = argparse.ArgumentParser(description="Ricostruisce un database del GANTT da migration e seed.")
    parser.add_argument("--database", help="nome del database, sullo stesso server di DATABASE_URL")
    parser.add_argument("--conferma", help="il nome del database, per confermare senza domanda")
    argomenti = parser.parse_args()

    load_dotenv(BACKEND / ".env", encoding="utf-8")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL non impostata (né nell'ambiente né in backend/.env).")
        return 2
    if argomenti.database:
        url = make_url(url).set(database=argomenti.database).render_as_string(hide_password=False)

    nome = nome_database(url)
    conferma = argomenti.conferma
    if conferma is None:
        conferma = input(f"Il database «{nome}» verrà svuotato e ricostruito. "
                         f"Scrivi il suo nome per confermare: ").strip()
    try:
        prima, dopo, spostamento = ricostruisci(url, conferma)
    except RicostruzioneRifiutata as e:
        print(f"RIFIUTATO: {e}")
        return 3
    print(f"«{nome}» ricostruito.")
    print(f"  seed: {spostamento}")
    print(f"  impronta dei dipendenti prima: {prima or '— (nessuna tabella dipendenti)'}")
    print(f"  impronta dei dipendenti dopo:  {dopo}")
    if prima is not None and prima != dopo:
        print("  ATTENZIONE: l'impronta è cambiata.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
