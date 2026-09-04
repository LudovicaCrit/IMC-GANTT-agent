"""ore_stimate_residue su consuntivi e consuntivo_sottotask

Consuntivazione A (04/09/2026). «Quante ore mancano ancora per finire questa
unità di lavoro», dichiarate da chi ci sta lavorando, nella settimana in cui lo
dice.

PERCHÉ NON BASTA `ore_rimanenti` CHE GIÀ ESISTE
-----------------------------------------------
`/me` espone già `ore_rimanenti` per ogni task: `ore_pianificate` meno il
consumato totale. È aritmetica sul PIANO — dice quanto budget avanza, non
quanto lavoro manca. Le due cose coincidono solo se la stima iniziale era
giusta, cioè nel caso che non ha bisogno di nessuno strumento.

Chi sta lavorando sa la seconda, e oggi non ha dove scriverla. Un task
pianificato 40h, consumate 38, che ne richiederà altre 30: il piano dice
«mancano 2h», la persona sa che ne mancano 30, e quel numero non esiste da
nessuna parte finché non sfora. È il dato che manca per ri-stanziare PRIMA
dello sforamento invece di constatarlo dopo.

IL QUANTO QUI, IL COSA NELLA NOTA
----------------------------------
Questa colonna porta solo il numero. Il perché — «manca l'integrazione col
gestionale del cliente» — va in `nota`, che esiste già su entrambe le tabelle e
non richiede nulla di nuovo. Due campi e non uno perché sono due usi diversi: il
numero si aggrega e si somma, il testo si legge. Metterli insieme li renderebbe
entrambi inservibili — un numero dentro una frase non si somma, una frase dentro
un numero non si scrive.

PER SETTIMANA, NON CUMULATIVA
------------------------------
Stessa grana di `ore_effettive` e `percentuale`: la dichiarazione di QUELLA
settimana. «Ne mancano 30» lunedì e «ne mancano 22» il lunedì dopo sono due
righe, non un aggiornamento della prima — ed è la serie storica a raccontare se
la stima sta convergendo o scappando, che è l'informazione vera. Un campo
sovrascritto perderebbe esattamente quella.

INERTE — NON ENTRA NEL CALCOLO DELLE ORE
-----------------------------------------
Differenza sostanziale da `ore_effettive`, che le somiglia per forma: quella
SOSTITUISCE la derivata in `_aggrega_ore_unita` ed è dentro il motore. Questa
non tocca nulla — né le ore derivate, né `ore_dichiarate`, né `Task.stato`. Si
scrive, si rilegge, e per ora nessuno la consuma: i consumatori (ri-stanziamento,
aggregazione-PM, IA) sono lavori futuri che si appoggeranno a questo dato.
È un campo-ingrediente, come `Progetto.urgenza` prima che qualcuno la leggesse.

LA COLONNA — gemella esatta sulle due tabelle
----------------------------------------------
Float, nullable, NESSUN server_default e NESSUN backfill. La scelta è la stessa
di `ore_effettive` (migration c5d6e7f8a9b0) e per la stessa ragione, che qui è
persino più netta:

    NULL  = «non l'ho stimato» — non so, non mi sono espresso
    0.0   = «non manca niente, ho finito» — un'affermazione, e forte

Un `server_default='0'` scriverebbe «ho finito» su ogni riga esistente e su ogni
riga futura non compilata: 2.128 dichiarazioni che affermano il completamento di
un lavoro senza che nessuno l'abbia detto. Il NULL è il valore giusto perché è
l'unico che non mente.

Float e non Integer come `Sottotask.ore_stimate`: qui si dichiara a mezze
giornate e quarti d'ora, come in `ore_effettive` e `ore_dichiarate`.

UNA MIGRATION PER DUE TABELLE, sul modello di e7f8a9b0c1d2 (presa_visione): il
ciclo sui nomi tiene le due colonne allineate per costruzione. `ore_effettive`
fu fatta in due migration separate (d6e7f8a9b0c1 e c5d6e7f8a9b0, a un mese di
distanza) e nel frattempo le due tabelle non erano gemelle — un disallineamento
che è costato letture con un ramo in più.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = 'a9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABELLE = ('consuntivi', 'consuntivo_sottotask')
COLONNA = 'ore_stimate_residue'


def upgrade() -> None:
    """ADD COLUMN nullable su entrambe. Additiva: nessuna riga cambia valore."""
    conn = op.get_bind()
    for tabella in TABELLE:
        n = conn.execute(sa.text(f"SELECT COUNT(*) FROM {tabella}")).scalar() or 0
        op.add_column(tabella, sa.Column(COLONNA, sa.Float(), nullable=True))
        print(f"✅ {tabella}.{COLONNA} aggiunta "
              f"({n} dichiarazioni esistenti, tutte NULL = «non stimato»)")


def downgrade() -> None:
    """Toglie la colonna da entrambe.

    Reversibile senza toccare nulla d'altro: ore, percentuali, note, stati e
    prese-visione restano dove sono. Si perdono le stime-residue dichiarate nel
    frattempo — cioè le uniche righe che dicevano «quanto manca davvero» — e il
    sistema torna a saperlo solo dopo lo sforamento. È il ripristino esatto del
    comportamento precedente.
    """
    for tabella in TABELLE:
        op.drop_column(tabella, COLONNA)
        print(f"✅ {tabella}.{COLONNA} rimossa")
