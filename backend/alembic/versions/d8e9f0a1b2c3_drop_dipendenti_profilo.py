"""drop `dipendenti.profilo`: la colonna-stringa del doppione ruolo

Multiruolo, passo F — ultimo. Chiude il doppione `ruolo_id` / `profilo`.

IL DOPPIONE CHE CHIUDE
───────────────────────
L'inquadramento di una persona era scritto in DUE posti: la FK `ruolo_id` verso
`ruoli`, e la stringa `profilo` che ne copiava il nome. Le scriveva entrambe un
solo form, sempre in coppia — ed è l'unica ragione per cui non sono mai
divergute: nessun vincolo le teneva allineate, e qualunque altro client avrebbe
potuto scriverle incoerenti. Il match dei task, per giunta, usava la stringa:
la sorgente debole governava la logica, la FK non la leggeva nessuno.

È lo stesso difetto della colonna JSON `competenze` (migration d2e3f4a5b6c7), un
livello più in là. Con una differenza che vale la pena registrare: là il
doppione aveva già fatto danno — 4 divergenze silenziose e un match rotto — qui
no. Le due sorgenti erano allineate 18/18 al momento del taglio. Questa è
manutenzione preventiva, non riparazione.

PERCHÉ IL DROP È SICURO — verificato riga per riga
───────────────────────────────────────────────────
Prima del drop, tutti e 18 i dipendenti avevano `profilo` == `Ruolo.nome` del
proprio `ruolo_id`: zero divergenti, zero con `profilo` valorizzato ma senza
ruolo. Ogni valore della colonna è quindi ricostruibile dalla FK, che resta.

  SELECT r.nome FROM ruoli r WHERE r.id = d.ruolo_id   -- è il vecchio profilo

La guardia qui sotto lo riverifica in SQL invece di fidarsi: un drop
irreversibile che si appoggia a un controllo fatto altrove è un drop che prima o
poi cancella qualcosa. Blocca su due casi, entrambi PERDITE non ricostruibili:
  - `profilo` diverso dal nome del ruolo → quale dei due era la verità?
  - `profilo` valorizzato ma `ruolo_id` NULL → non c'è nulla da cui ricostruirlo.
`profilo` NULL non blocca: è il caso normale dopo il passo E, che ha smesso di
scrivere la colonna.

NESSUN LETTORE, NESSUNO SCRITTORE
──────────────────────────────────
Passo D: i ~13 lettori ORM leggono `ruolo_rel.nome`; i payload continuano a
esporre un campo `profilo` con lo stesso testo, quindi il frontend non vede
alcuna differenza. Passo E: form, backend e seed hanno smesso di scriverla, e la
migration c7d8e9f0a1b2 l'ha resa nullable perché la creazione potesse funzionare
senza. Da allora la colonna è un guscio.

IL DOWNGRADE RICREA LA COLONNA, NON IL CONTENUTO
─────────────────────────────────────────────────
`op.add_column` restituisce una colonna vuota e nullable. Il contenuto è
ricostruibile dai ruoli — la query è quella sopra, e la migration la stampa nel
downgrade — ma il downgrade non la esegue: riempire dati lì darebbe l'illusione
che il ritorno indietro sia gratuito.
"""
from alembic import op
import sqlalchemy as sa

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    perdite = conn.execute(sa.text("""
        SELECT d.id, d.profilo, r.nome
        FROM dipendenti d
        LEFT JOIN ruoli r ON r.id = d.ruolo_id
        WHERE d.profilo IS NOT NULL
          AND (r.nome IS NULL OR r.nome <> d.profilo)
    """)).fetchall()
    if perdite:
        righe = ", ".join(f"{r[0]}: profilo={r[1]!r} ruolo={r[2]!r}" for r in perdite)
        raise RuntimeError(
            "DROP ANNULLATO: la colonna `profilo` contiene valori che NON sono "
            f"ricostruibili da `ruolo_id` -> {righe}. Riconciliare prima "
            "(allineare il ruolo, o accettare esplicitamente la perdita "
            "azzerando quei `profilo`), poi rieseguire."
        )

    n = conn.execute(sa.text("SELECT count(*) FROM dipendenti")).scalar()
    op.drop_column("dipendenti", "profilo")
    print(f"✅ dipendenti.profilo rimossa ({n} dipendenti verificati, tutti "
          f"ricostruibili da ruolo_id): `ruoli` è l'unica sorgente "
          f"dell'inquadramento")


def downgrade() -> None:
    """Ricrea la colonna VUOTA e nullable. Lo schema torna, i dati no."""
    op.add_column("dipendenti", sa.Column("profilo", sa.String(length=60), nullable=True))
    print("⚠ dipendenti.profilo ricreata VUOTA. Per ripopolarla dai ruoli:\n"
          "    UPDATE dipendenti d SET profilo = r.nome\n"
          "      FROM ruoli r WHERE r.id = d.ruolo_id;")
