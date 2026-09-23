"""consuntivi: via `motivo_fermo` — e questa porta un dato (passo 5.6)

`motivo_fermo` è l'unica colonna condannata di `consuntivi` che NON è vuota.
Zero lettori — nessun payload, nessun serializzatore, nessuna query — ma una
riga con un valore, e un drop che porta via un valore è una perdita di dati
anche quando il valore non serve a nessuno.

COS'È QUEL VALORE, per chi deve decidere
────────────────────────────────────────
Non è testo scritto da una persona: è una stringa GENERATA dal vecchio motore a
cursore, che la scriveva da sé quando il dipendente marcava un'unità come
bloccata («Segnalato come bloccato dal dipendente» e simili). Il motivo VERO —
quello che il dipendente ha scritto con le sue parole — sta in `nota`, che
questa migration non tocca. Sulla riga nota al 23/09/2026 (id 2645, T024/D004,
settimana 2026-07-20) la coppia è:

    motivo_fermo : «Segnalato come bloccato dal dipendente»   ← si perde
    nota         : «Il provider ha continui disservizi.»      ← resta

LA GUARDIA — NON DECIDE AL POSTO TUO
────────────────────────────────────
Le altre colonne di questo passo hanno una guardia-vuoto: se trovano qualcosa
si fermano, perché un valore inatteso vuol dire che qualcuno le scrive ancora.
Qui invece il valore È atteso, e una guardia-vuoto si limiterebbe a fallire
sempre. Ma nemmeno può ignorarlo: sarebbe una migration che distrugge un dato
in silenzio perché «tanto lo sapevamo».

Allora: la migration STAMPA le righe che sta per perdere e si FERMA, a meno che
non le si dica esplicitamente di procedere.

    alembic -x motivo_fermo=butta upgrade head

Chi esegue vede cosa sparisce PRIMA che sparisca, e lo decide. Non c'è un
numero-soglia scritto qui dentro («accetta se sono ≤ 1»): su un altro database
il conteggio sarebbe un altro, e una soglia cablata su questo trasformerebbe la
guardia in un timbro.

IL DOWNGRADE ricrea la colonna vuota. Quel valore non torna: è il motivo per
cui la migration lo mostra prima.
"""
from alembic import op, context
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

TABELLA = "consuntivi"
COLONNA = "motivo_fermo"
FLAG = "motivo_fermo"


def upgrade() -> None:
    conn = op.get_bind()
    righe = conn.execute(sa.text(
        f"SELECT id, task_id, dipendente_id, settimana, {COLONNA}, nota "
        f"FROM {TABELLA} WHERE {COLONNA} IS NOT NULL ORDER BY id")).fetchall()
    print(f"guardia: {TABELLA}.{COLONNA} → {len(righe)} valori non-NULL")

    if righe:
        print(f"  queste righe perderebbero `{COLONNA}` (la `nota` resta):")
        for r in righe[:20]:
            print(f"    #{r[0]} {r[1]}/{r[2]} {r[3]}")
            print(f"        {COLONNA} = {r[4]!r}   ← si perde")
            print(f"        nota         = {r[5]!r}   ← resta")
        if len(righe) > 20:
            print(f"    …e altre {len(righe) - 20}")

        if context.get_x_argument(as_dictionary=True).get(FLAG) is None:
            raise RuntimeError(
                f"DROP NON ESEGUITO: {TABELLA}.{COLONNA} ha {len(righe)} valori che "
                f"il drop distruggerebbe (elencati qui sopra). Se vanno bene così, "
                f"rieseguire con:  alembic -x {FLAG}=butta upgrade head"
            )
        print(f"  ({FLAG} confermato da chi esegue: si procede)")

    op.drop_column(TABELLA, COLONNA)
    print(f"✅ {TABELLA}: droppata {COLONNA}")


def downgrade() -> None:
    op.add_column(TABELLA, sa.Column(COLONNA, sa.String(length=120), nullable=True))
    print(f"↩ {TABELLA}: ricreata {COLONNA} (vuota — i valori di prima non tornano)")
