"""presa_visione su consuntivi e consuntivo_sottotask

Nodo F-2 (02/09/2026). Il gesto «l'ho guardato, è ancora fermo, non è avanzato»
— una traccia SENZA avanzamento, che fa contare l'unità come dichiarata nel
contatore della Consuntivazione (nodo F-1) senza costringere chi compila a
inventare un progresso che non c'è.

PERCHÉ UNA COLONNA E NON IL RIUSO DI `compilato`
------------------------------------------------
`compilato` sembra la risposta — esiste, è booleana, si scrive a ogni
salvataggio e significa «questa riga è stata toccata questa settimana». Ma la
presa-visione non è «toccata»: è un'AFFERMAZIONE precisa, «confermo che è ferma».
Il riuso è stato verificato e scartato per due collisioni che esistono GIÀ nel
codice, non in teoria:

  1. LA RIGA-PADRE DI UN TASK SCOMPOSTO. `salva_consuntivo` fonde le ore
     derivate in quelle dichiarate (`ore_per_task = {**ore_per_task,
     **derivate_per_task}`). Un task i cui pezzi non sono avanzati deriva 0.0
     ore, supera la guardia e scrive una riga con `compilato=True` e
     `percentuale`/`nota`/`stato_dichiarato` tutti NULL. È voluto — «Δ=0 vuol
     dire questa settimana il pezzo non è avanzato, che è una dichiarazione,
     non un silenzio» — ma significa «la derivazione è passata di qui», non
     «l'ho guardato io».

  2. LA NOTA CANCELLATA SU UN PEZZO, ed è raggiungibile dal form. `_nota_task`
     normalizza la stringa vuota a NULL: chi svuota la nota di un sottotask
     senza toccare altro produce una riga vuota con `compilato=True`, che vuol
     dire «ho tolto quello che avevo scritto».

Quindi «compilato=True + tutto il resto vuoto» è un pattern già occupato da due
significati diversi, e appoggiarci sopra la presa-visione la renderebbe
indistinguibile da entrambi. In più le due affermazioni devono poter CONVIVERE:
chi prende visione e poi nella stessa settimana scrive anche una nota resta
`compilato=True` in entrambi i casi, e senza un campo proprio la presa-visione
sparirebbe dentro quel True.

(Le 383 righe con `compilato=False` e tutti i campi vuoti sono del seed e non
c'entrano: non collidono perché il flag è False.)

LA COLONNA — gemella esatta sulle due tabelle
---------------------------------------------
  presa_visione  Boolean  NOT NULL  DEFAULT false

Le due grane sono isomorfe (`consuntivi` UNIQUE su task+dipendente+settimana,
`consuntivo_sottotask` su sottotask+dipendente+settimana) e ogni colonna della
dichiarazione esiste su entrambe: `percentuale`, `ore_effettive`,
`stato_dichiarato`, `nota`, `compilato`, `data_compilazione`. Aggiungerla a una
sola delle due rifarebbe l'asimmetria che la migration d6e7f8a9b0c1 è servita a
togliere: «a che punto sei» si risponderebbe di nuovo in due modi diversi a
seconda che qualcuno abbia scomposto il lavoro.

NOT NULL e non nullable, di proposito. Su un flag il NULL sarebbe un terzo
stato senza significato — «non so se l'ha guardato» non è una cosa che questo
dato debba poter dire. È la stessa forma di `compilato`
(`Boolean, nullable=False, default=False`).

`server_default='false'` serve tecnicamente (una colonna NOT NULL aggiunta a
una tabella popolata non può nascere senza default) e si TIENE anche dopo:
`compilato` ha solo il default lato Python, quindi un INSERT che non passasse
dall'ORM lo lascerebbe scoperto. Qui il default vive nel DB e regge comunque.

NESSUN BACKFILL, e il default È la risposta giusta
--------------------------------------------------
Le righe esistenti (2635 su `consuntivi`, 0 su `consuntivo_sottotask`) nascono
con `false`, ed è corretto: sono dichiarazioni fatte quando la presa-visione non
esisteva come gesto. Nessuna di esse È una presa-visione, e marcarne qualcuna
retroattivamente — per esempio quelle vuote — attribuirebbe a delle persone una
conferma che non hanno mai dato. Il contatore di F-1 le tratterà come oggi.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABELLE = ('consuntivi', 'consuntivo_sottotask')


def upgrade() -> None:
    """Aggiunge `presa_visione` a entrambe le tabelle delle dichiarazioni."""
    for tabella in TABELLE:
        op.add_column(
            tabella,
            sa.Column(
                'presa_visione',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        print(f"✅ {tabella}.presa_visione aggiunta (NOT NULL, default false)")


def downgrade() -> None:
    """Toglie la colonna da entrambe.

    Reversibile SENZA perdita di dichiarazioni: ore, percentuali, note e stati
    restano dove sono. Si perdono le prese-visione registrate nel frattempo —
    cioè le conferme «l'ho guardato, è fermo» — e le unità che avevano SOLO
    quella tornano a risultare non dichiarate nel contatore. È il ripristino
    esatto del comportamento precedente, non un danno collaterale.
    """
    for tabella in TABELLE:
        op.drop_column(tabella, 'presa_visione')
        print(f"✅ {tabella}.presa_visione rimossa")
