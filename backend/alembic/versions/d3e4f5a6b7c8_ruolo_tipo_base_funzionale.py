"""ruoli.tipo: distingue l'inquadramento dal ruolo funzionale

Multiruolo, passo A1 (08/09/2026). La tabella `ruoli` ha sempre avuto due
mestieri e nessun modo di distinguerli:

  base       — l'INQUADRAMENTO della persona ("Senior Consultant", "AD"), uno
               solo, in `Dipendente.ruolo_id`.
  funzionale — un ruolo RICOPERTO IN AGGIUNTA ("PM"), zero o più, che dal passo
               B vivrà in una M2M dedicata.

PERCHÉ QUESTA MIGRATION VIENE PRIMA DI 'PM'
────────────────────────────────────────────
`GET /api/config/ruoli` è letto da tre punti: il select-inquadramento del form
dipendente, la tendina «profilo richiesto» dei task in Cantiere, e il CRUD del
catalogo in Configurazione. Solo il primo deve NON vedere i ruoli funzionali —
un funzionale scelto come inquadramento è precisamente il dato malformato che
il multiruolo esiste per evitare.

Aggiungere 'PM' ai ruoli senza avere prima il discriminante aprirebbe una
finestra — lunga quanto il passo successivo — in cui il form lo propone fra gli
inquadramenti. Basta un salvataggio in quella finestra per creare il dato
sbagliato, e sarebbe indistinguibile da una scelta deliberata. Il costo di
separare i due passi è una migration in più; il costo di non separarli è un
dato da riconciliare a mano, che è esattamente il lavoro da cui veniamo.

I 9 RUOLI ESISTENTI SONO TUTTI INQUADRAMENTI
─────────────────────────────────────────────
AD, Manager IT, Senior IT Consultant, IT Consultant, Senior Consultant,
Consultant, Manager HR, Responsabile amministrazione, Addetto amministrazione.
Nessuno di questi è un ruolo funzionale, quindi il backfill è `tipo='base'` per
tutti — che è anche il default della colonna: una riga scritta da codice che
non conosce il campo nasce inquadramento, cioè nel modo conservativo.

IL CHECK STA ANCHE NEL MODELLO
───────────────────────────────
`ck_ruoli_tipo` è dichiarato in `__table_args__` di `Ruolo`, non solo qui. È la
lezione della migration f8a9b0c1d2e3, che ha dovuto RICREARE tre CHECK
dichiarati dalle migration ma ASSENTI dal database: un `Base.metadata.
create_all()` dei vincoli scritti nelle sole migration non sa nulla, e un CHECK
che si crede attivo e non c'è è peggio di un CHECK che non c'è.
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default: i 9 ruoli esistenti diventano 'base' nello stesso
    # statement che aggiunge la colonna, senza una UPDATE separata e senza una
    # finestra in cui la colonna è NULL su righe NOT NULL.
    op.add_column(
        "ruoli",
        sa.Column("tipo", sa.String(20), nullable=False, server_default="base"),
    )
    op.create_check_constraint(
        "ck_ruoli_tipo", "ruoli", "tipo IN ('base', 'funzionale')"
    )

    conn = op.get_bind()
    righe = conn.execute(sa.text(
        "SELECT tipo, count(*) FROM ruoli GROUP BY tipo ORDER BY tipo"
    )).fetchall()
    print("✅ ruoli.tipo aggiunta + ck_ruoli_tipo: " +
          ", ".join(f"{t}={n}" for t, n in righe))


def downgrade() -> None:
    """Toglie il vincolo e la colonna.

    Reversibile SENZA perdita finché tutti i ruoli sono 'base' — cioè finché il
    passo A2 non ha inserito 'PM'. Dopo, il downgrade fa sparire l'informazione
    «questo ruolo è funzionale» e i ruoli funzionali diventano indistinguibili
    dagli inquadramenti: il form tornerebbe a offrirli come profilo-base. Chi
    torna indietro da qui deve prima togliere i ruoli funzionali, non solo la
    colonna che li marca.
    """
    op.drop_constraint("ck_ruoli_tipo", "ruoli", type_="check")
    op.drop_column("ruoli", "tipo")
    print("⚠ ruoli.tipo rimossa — inquadramenti e funzionali non sono più distinguibili")
