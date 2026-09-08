"""dipendenti.profilo diventa NULLABLE: nessuno la scrive più

Multiruolo, passo E (08/09/2026). Passo intermedio NON previsto dal piano, e
necessario: senza, il passo E non è eseguibile.

PERCHÉ SERVE
────────────
`Dipendente.profilo` era la copia-stringa di `Ruolo.nome`, scritta dal form
insieme a `ruolo_id`. Il passo E toglie quella scrittura — l'inquadramento si
dichiara con la FK e basta — ma la colonna è NOT NULL: la prima creazione di un
dipendente dopo E fallirebbe con

    NotNullViolation: null value in column "profilo" of relation "dipendenti"

e fallirebbe SOLO in creazione, non in modifica (dove la riga esiste già e la
colonna conserva il vecchio valore). Sarebbe quindi un guasto asimmetrico:
«modificare un dipendente funziona, crearne uno no», che è il genere di rottura
che si scopre dall'utente e non dai test.

Rendere la colonna nullable è il minimo che rende E eseguibile, e prepara F: il
drop vero e proprio resta il passo successivo. Fra E ed F la colonna è un
guscio — non più scritta (E), non più letta (D) — e i valori già presenti
restano lì, fossili, senza fare danno.

NON TOCCA I DATI. I 18 dipendenti conservano il loro `profilo` attuale, che è
allineato al rispettivo `Ruolo.nome` (verificato 18/18 prima del passo D).
Cambia solo cosa il database ACCETTA da qui in avanti.
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("dipendenti", "profilo",
                    existing_type=sa.String(length=60), nullable=True)
    n_null, n_tot = op.get_bind().execute(sa.text(
        "SELECT count(*) FILTER (WHERE profilo IS NULL), count(*) FROM dipendenti"
    )).first()
    print(f"✅ dipendenti.profilo ora NULLABLE ({n_null}/{n_tot} NULL — i valori "
          f"esistenti non sono stati toccati)")


def downgrade() -> None:
    """Ripristina il NOT NULL.

    ⚠ FALLISCE se nel frattempo è stato creato un dipendente senza `profilo` —
    cioè da qualunque creazione avvenuta dopo il passo E, che non scrive più
    quella colonna. Non è un difetto del downgrade: è il vincolo che dice la
    verità, cioè che quei dati non soddisfano più la vecchia regola. Per tornare
    indietro davvero bisogna prima ripopolare la colonna dai ruoli:

        UPDATE dipendenti d SET profilo = r.nome
          FROM ruoli r WHERE r.id = d.ruolo_id AND d.profilo IS NULL;

    Non lo fa questa migration: riempire dati in un downgrade nasconderebbe
    esattamente il fatto che rende il ritorno indietro non banale.
    """
    op.alter_column("dipendenti", "profilo",
                    existing_type=sa.String(length=60), nullable=False)
    print("⚠ dipendenti.profilo di nuovo NOT NULL")
