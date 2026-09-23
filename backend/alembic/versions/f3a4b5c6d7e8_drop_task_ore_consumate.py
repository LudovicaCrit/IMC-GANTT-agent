"""task: via `ore_consumate` — la testimone che non guardava più (passo 5.6)

`Task.ore_consumate` era la somma delle ore dichiarate sul task,
denormalizzata. Nessuno l'ha più aggiornata da quando le ore vengono dai
blocchi: al 23/09/2026 valeva 0 su tutti e 114 i task, con 2.249 blocchi e
17.535 ore in database.

PERCHÉ QUESTO DROP ARRIVA DOPO UN FIX, E NON PRIMA
──────────────────────────────────────────────────
Fino al passo 5.0 questa colonna aveva un lettore, e per giunta importante:
`PATCH /api/fasi/{id}` la interrogava per rifiutare il ritorno di una fase a
«Da iniziare» quando sui suoi task c'erano ore dichiarate. Siccome valeva zero
ovunque, quella guardia non aveva mai rifiutato niente in un anno: la regola
c'era, la query girava, e non poteva funzionare. Il passo 5.0 l'ha riportata a
leggere la vista `ore_settimanali`.

Droppare la colonna PRIMA di quel fix avrebbe cancellato la guardia insieme
alla colonna, in silenzio, e nessun test se ne sarebbe accorto — perché non
c'era nessun test che la vedesse scattare. È l'unico motivo per cui il 5.0
viene prima di tutto il resto della rimozione.

LA GUARDIA — VUOTO, più un controllo sul lettore
────────────────────────────────────────────────
1. nessun valore diverso da zero: se ce ne fossero, qualcuno la aggiorna e il
   drop butterebbe via un dato;
2. e — perché il caso storico non si ripeta — si verifica che `routes/fasi.py`
   non LEGGA più questa colonna. Un controllo sul CODICE dentro una migration è
   inusuale, e sta qui proprio perché il guasto che previene è già successo una
   volta: una colonna letta da una guardia che nessun test copre sparisce senza
   far rumore.

   Il controllo si fa sull'ALBERO SINTATTICO, non cercando la stringa: nel file
   il nome compare due volte in commenti e docstring, che raccontano da dove la
   guardia leggeva prima del fix 5.0 e vanno lasciati stare. Un accesso VERO è
   un attributo `Task.ore_consumate` dentro un'espressione — quello `ast` lo
   distingue e una ricerca testuale no.

IL DOWNGRADE ricrea la colonna a zero, cioè il valore che aveva su ogni riga.
"""
from alembic import op
import sqlalchemy as sa
import ast
from pathlib import Path

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

TABELLA = "task"
COLONNA = "ore_consumate"


def upgrade() -> None:
    conn = op.get_bind()
    n = conn.execute(sa.text(
        f"SELECT count(*) FROM {TABELLA} WHERE coalesce({COLONNA}, 0) <> 0")).scalar()
    print(f"guardia 1/2: {TABELLA}.{COLONNA} → {n} valori diversi da zero")
    if n:
        esempi = conn.execute(sa.text(
            f"SELECT id, nome, {COLONNA} FROM {TABELLA} "
            f"WHERE coalesce({COLONNA}, 0) <> 0 ORDER BY id LIMIT 10")).fetchall()
        raise RuntimeError(
            f"DROP NON ESEGUITO: {TABELLA}.{COLONNA} ha {n} valori non nulli → "
            f"{', '.join(f'{r[0]} «{r[1]}» = {r[2]}' for r in esempi)}. "
            f"Qualcuno la aggiorna: capire chi prima di buttarla."
        )

    fasi = Path(__file__).resolve().parents[2] / "routes" / "fasi.py"
    usi = []
    if fasi.exists():
        albero = ast.parse(fasi.read_text(encoding="utf-8"))
        usi = [n.lineno for n in ast.walk(albero)
               if isinstance(n, ast.Attribute) and n.attr == COLONNA
               and isinstance(n.value, ast.Name) and n.value.id == "Task"]
    print(f"guardia 2/2: routes/fasi.py → {len(usi)} accessi a Task.{COLONNA} "
          f"nel codice (commenti e docstring esclusi)")
    if usi:
        raise RuntimeError(
            f"DROP NON ESEGUITO: routes/fasi.py legge ancora Task.{COLONNA} "
            f"(righe {usi}). È la guardia del ritorno a «Da iniziare»: va "
            f"spostata sulla vista `ore_settimanali` (passo 5.0) prima di droppare."
        )

    op.drop_column(TABELLA, COLONNA)
    print(f"✅ {TABELLA}: droppata {COLONNA}")


def downgrade() -> None:
    op.add_column(TABELLA, sa.Column(COLONNA, sa.Float(), nullable=True))
    op.get_bind().execute(sa.text(f"UPDATE {TABELLA} SET {COLONNA} = 0"))
    print(f"↩ {TABELLA}: ricreata {COLONNA} a zero (il valore che aveva ovunque)")
