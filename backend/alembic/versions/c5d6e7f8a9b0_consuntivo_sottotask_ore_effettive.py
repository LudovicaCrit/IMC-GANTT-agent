"""consuntivo_sottotask ore_effettive — le ore reali, quando la derivata non basta

Aggiunge consuntivo_sottotask.ore_effettive: le ore che il dipendente registra a
mano su un pezzo, in una settimana, quando l'avanzamento dichiarato non le
cattura.

Step 4 dei sottotask — STRATO 2 del motore ore-derivate. Lo strato 1 (migration
b4c5d6e7f8a9 e commit 497617e) deriva le ore dall'avanzamento:
Δpct × Sottotask.ore_stimate. Regge il caso normale e non regge tre casi reali:

  - PEZZO FERMO. Bloccato da un fornitore, da un'attesa, da un altro task. La
    percentuale non si muove, Δ=0, la derivata dice zero ore — ma la settimana
    è costata tempo davvero (solleciti, riunioni, tentativi).
  - DIVERGENZA DALLA STIMA. Il pezzo è finito, la percentuale è arrivata a 100
    e la derivata restituisce esattamente `ore_stimate`. Se ne è costate il
    doppio, quel doppio non esiste da nessuna parte: la derivata non può, per
    costruzione, dire più della stima.
  - SOCCORSO (futuro). Qualcuno che non è l'assegnatario ci mette ore.

SOSTITUISCE, NON SI SOMMA
-------------------------
Quando `ore_effettive` è valorizzata, il motore usa QUELLA al posto della
derivata per quel sottotask in quella settimana. Non è un'aggiunta: sono due
risposte alla stessa domanda — «quante ore è costato questo pezzo, questa
settimana» — e quella dichiarata da chi ha lavorato vince su quella calcolata da
una percentuale. Sommarle conterebbe due volte lo stesso lavoro.

SEMANTICA DEL NULL — di nuovo informazione, non lacuna
------------------------------------------------------
  NULL → nessuna ora effettiva dichiarata: si deriva. È il caso NORMALE.
  0.0  → «zero ore effettive», e lo dice il dipendente: la derivazione è spenta
         e il pezzo costa zero questa settimana.
Sono due cose diverse, ed è la ragione per cui la colonna è nullable mentre la
sorella `consuntivi.ore_dichiarate` è NOT NULL DEFAULT 0. Un default a 0 qui
spegnerebbe la derivazione su ogni riga: ogni sottotask risulterebbe costato
zero ore, silenziosamente, e lo strato 1 smetterebbe di funzionare senza che
nessuna query fallisca.

PER SETTIMANA, NON CUMULATIVA
-----------------------------
8h questa settimana e 5h la prossima si scrivono 8 e poi 5, non 8 e poi 13. È
la grana di `consuntivi.settimana`, di `presenze_settimanali`, di `spese`: gli
11 lettori di `Consuntivo.ore_dichiarate` sommano già per settimana, e una
colonna cumulativa in mezzo a colonne incrementali sarebbe una trappola per
chiunque scriva la dodicesima query.

NESSUN CHECK SUL SEGNO — e non è una svista
-------------------------------------------
La colonna sorella `percentuale` ha un CHECK (0-100) perché il suo dominio è
chiuso e definito. Qui il precedente giusto è `consuntivi.ore_dichiarate`, che
di CHECK non ne ha: le ore non hanno un massimo. Il minimo (non negativo) è
imposto nel DTO della route, dove produce un 400 parlante invece di un
IntegrityError 500 — stessa scelta, e stessa motivazione, del range 0-100
dell'avanzamento.

NESSUN BACKFILL
---------------
Al 06/08/2026 la tabella è vuota (0 righe). Ma anche su un database con
dichiarazioni già scritte NON ci sarebbe nulla da riempire: quelle righe sono
state derivate, e il loro «non dichiarate» è esattamente il NULL. Riempirle
spegnerebbe la derivazione retroattivamente su tutta la storia.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-06 15:34:07.912885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ADD COLUMN nullable, senza server_default: il NULL è il valore giusto."""
    conn = op.get_bind()

    op.add_column(
        'consuntivo_sottotask',
        sa.Column('ore_effettive', sa.Float(), nullable=True),
    )
    n_righe = conn.execute(
        sa.text("SELECT COUNT(*) FROM consuntivo_sottotask")
    ).scalar() or 0
    print(f"✅ Colonna consuntivo_sottotask.ore_effettive aggiunta "
          f"({n_righe} dichiarazioni in tabella, tutte in derivazione)")


def downgrade() -> None:
    """Drop della colonna.

    Perde le ore dichiarate a mano, e con esse i tre casi che la derivata non
    sa raccontare: le settimane bloccate tornano a costare zero, e i pezzi
    sforati tornano a costare esattamente la stima. Le percentuali non vengono
    toccate, quindi la derivazione riprende da sola — dicendo però una cosa
    diversa da quella che il dipendente aveva scritto.
    """
    op.drop_column('consuntivo_sottotask', 'ore_effettive')
    print("✅ Colonna consuntivo_sottotask.ore_effettive droppata")
