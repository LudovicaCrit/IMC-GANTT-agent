"""via le tabelle `presenze_settimanali` e `spese` (passo 5.6)

Due tabelle che non sono mai entrate in funzione.

Nascevano col vecchio `POST /salva`: il suo body poteva portare giorni in
sede/remoto, ore di assenza, tipo e nota dell'assenza, e una lista di spese, e
`salva_consuntivo` le scriveva qui. Ma il form della pagina a cursore non le ha
MAI mandate — in `ConsuntivazioneUser.jsx` non c'era un campo assenze né un
campo spese — quindi le due tabelle erano raggiungibili solo da una POST
costruita a mano. Lettori: nessuno, mai. Righe in database: zero.

Il motore che le scriveva è uscito al passo 5.4, e da allora i due nomi non
compaiono più in nessun punto del backend fuori da `models.py`.

LA DECISIONE, perché non è solo tecnica
───────────────────────────────────────
Erano il dubbio C-1 della ricognizione: buttarle o tenerle vuote in attesa di
rifare assenze e spese nella griglia? Deciso di buttarle. Due tabelle vuote in
uno schema sono un invito a credere che la funzionalità esista: chi arriva dopo
le trova, le legge, e progetta sopra qualcosa che non è mai stato costruito.
Se le assenze serviranno — e probabilmente serviranno, perché una settimana di
ferie oggi non si sa dire — andranno ridisegnate con la grana della griglia, a
ore e per giorno, non con quella di un form che non c'è più.

LA GUARDIA — ZERO RIGHE
───────────────────────
Prima del DROP TABLE si contano le righe: devono essere zero. Un DROP TABLE su
dati veri non è un errore da correggere dopo, e queste due non hanno nemmeno
l'attenuante della copia derivabile — quello che c'è dentro non sta da nessuna
altra parte. Se una delle due ha righe, la migration si ferma e le mostra.

IL DOWNGRADE ricrea le due tabelle nella forma esatta di `models.py` al
23/09/2026, vincoli compresi. Vuote: quello che contenevano — niente — torna
identico.
"""
from alembic import op
import sqlalchemy as sa

revision = "a6b7c8d9e0f1"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None

TABELLE = ("presenze_settimanali", "spese")


def upgrade() -> None:
    conn = op.get_bind()
    for tab in TABELLE:
        n = conn.execute(sa.text(f"SELECT count(*) FROM {tab}")).scalar()
        print(f"guardia: {tab} → {n} righe")
        if n:
            esempi = conn.execute(sa.text(
                f"SELECT * FROM {tab} ORDER BY id LIMIT 5")).fetchall()
            raise RuntimeError(
                f"DROP NON ESEGUITO: la tabella {tab} ha {n} righe, e un DROP TABLE "
                f"se le porterebbe via per sempre → {esempi}. "
                f"Decidere cosa farne prima di rieseguire."
            )

    for tab in TABELLE:
        op.drop_table(tab)
    print(f"✅ droppate le tabelle {', '.join(TABELLE)}")


def downgrade() -> None:
    op.create_table(
        "presenze_settimanali",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dipendente_id", sa.String(length=10), nullable=False),
        sa.Column("settimana", sa.Date(), nullable=False),
        sa.Column("giorni_sede", sa.SmallInteger(), nullable=True),
        sa.Column("giorni_remoto", sa.SmallInteger(), nullable=True),
        sa.Column("ore_assenza", sa.Float(), nullable=True),
        sa.Column("tipo_assenza", sa.String(length=60), nullable=True),
        sa.Column("nota_assenza", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dipendente_id", "settimana", name="uq_presenza"),
    )
    op.create_table(
        "spese",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dipendente_id", sa.String(length=10), nullable=False),
        sa.Column("settimana", sa.Date(), nullable=False),
        sa.Column("descrizione", sa.String(length=200), nullable=False),
        sa.Column("importo", sa.Float(), nullable=False),
        sa.Column("categoria", sa.String(length=60), nullable=True),
        sa.Column("progetto_id", sa.String(length=10), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"]),
        sa.ForeignKeyConstraint(["progetto_id"], ["progetti.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    print("↩ ricreate presenze_settimanali e spese (vuote)")
