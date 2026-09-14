"""storico: i consuntivi settimanali diventano blocchi_ore (fonte='storico')

Consuntivazione a ore, passo 1 — sotto-passo 3 di 3.

COSA FA
───────
Ogni riga di `consuntivi` con `ore_dichiarate > 0` diventa UN blocco:
  giorno       = la `settimana` della riga (è già il lunedì: verificato sotto)
  task_id      = lo stesso
  sottotask_id = NULL
  ore          = ore_dichiarate
  fonte        = 'storico'

IL LUNEDÌ È UNA CONVENZIONE, NON UN DATO. Il giorno vero in cui quelle ore sono
state lavorate non è mai stato registrato: la grana era la settimana. La fonte
'storico' lo dichiara, e chi leggerà le ore per giorno deve trattare questi
blocchi come «settimana intera», non come «lavorato il lunedì».

Le righe a ZERO ore non producono blocchi — «nessuna ora» è l'assenza del
blocco. La riga di `consuntivi` resta intatta: porta la dichiarazione (stato,
nota, compilato), e questa migration non la tocca. Nessuna colonna di
`consuntivi` viene modificata.

LE GUARDIE — tutte PRIMA di scrivere, e una DOPO
─────────────────────────────────────────────────
Prima, bloccano se:
  - esistono già blocchi 'storico' → la migration non va eseguita due volte;
  - una `settimana` non è un lunedì → il giorno non sarebbe la convenzione;
  - un valore ha più di 2 decimali o supera 999.99 → NUMERIC(5,2) lo
    arrotonderebbe o lo rifiuterebbe, e la somma non tornerebbe;
  - `consuntivo_sottotask` ha ore effettive → quelle ore sono già dentro
    `ore_dichiarate` del task, ma migrarle a livello task perderebbe il PEZZO a
    cui appartengono. Va deciso a mano, non in silenzio.
Dopo, il confronto: per ogni (task, dipendente, settimana) la vista
`ore_settimanali` deve dare ESATTAMENTE `ore_dichiarate`, al centesimo, in
entrambe le direzioni (nessuna chiave mancante, nessuna in più). Una sola
divergenza e la migration solleva: su Postgres il DDL è transazionale, quindi
non resta scritto nulla.

DATE DI CREAZIONE
─────────────────
`created_at` del blocco = quando la dichiarazione fu compilata
(`data_compilazione`, altrimenti `created_at` della riga), perché è l'unica data
vera che quel numero ha. `updated_at` = il momento della migrazione.

DOWNGRADE
─────────
Cancella i blocchi 'storico'. `consuntivi` non è mai stato toccato, quindi non
c'è nulla da ripristinare.
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def _conta(conn, sql):
    return conn.execute(sa.text(sql)).scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # ── Guardie prima di scrivere ────────────────────────────────────────
    problemi = []
    n = _conta(conn, "SELECT count(*) FROM blocchi_ore WHERE fonte = 'storico'")
    if n:
        problemi.append(f"{n} blocchi 'storico' già presenti (migration già eseguita?)")
    n = _conta(conn, "SELECT count(*) FROM consuntivi WHERE extract(isodow FROM settimana) <> 1")
    if n:
        problemi.append(f"{n} righe con `settimana` che non è un lunedì")
    n = _conta(conn, """
        SELECT count(*) FROM consuntivi
        WHERE ore_dichiarate > 0
          AND (ore_dichiarate * 100 <> round((ore_dichiarate * 100)::numeric)
               OR ore_dichiarate > 999.99)
    """)
    if n:
        problemi.append(f"{n} righe con più di 2 decimali o oltre 999.99 ore")
    n = _conta(conn, "SELECT count(*) FROM consuntivo_sottotask WHERE ore_effettive IS NOT NULL")
    if n:
        problemi.append(f"{n} dichiarazioni su sottotask con ore effettive (attribuzione al pezzo da decidere)")
    if problemi:
        raise RuntimeError("MIGRAZIONE STORICO ANNULLATA: " + "; ".join(problemi))

    attese = _conta(conn, "SELECT count(*) FROM consuntivi WHERE ore_dichiarate > 0")

    # ── Scrittura ────────────────────────────────────────────────────────
    inserite = conn.execute(sa.text("""
        INSERT INTO blocchi_ore
            (dipendente_id, giorno, task_id, sottotask_id, ore, fonte, created_at, updated_at)
        SELECT dipendente_id,
               settimana,
               task_id,
               NULL,
               ore_dichiarate::numeric(5, 2),
               'storico',
               coalesce(data_compilazione, created_at, now() AT TIME ZONE 'utc'),
               now() AT TIME ZONE 'utc'
        FROM consuntivi
        WHERE ore_dichiarate > 0
    """)).rowcount
    if inserite != attese:
        raise RuntimeError(f"MIGRAZIONE STORICO ANNULLATA: inseriti {inserite} blocchi, attesi {attese}")

    # ── Confronto al centesimo, nei due versi ────────────────────────────
    divergenze = conn.execute(sa.text("""
        SELECT coalesce(c.task_id, v.task_id), coalesce(c.dipendente_id, v.dipendente_id),
               coalesce(c.settimana, v.settimana), c.ore_dichiarate, v.ore
        FROM (SELECT task_id, dipendente_id, settimana, ore_dichiarate
              FROM consuntivi WHERE ore_dichiarate > 0) c
        FULL OUTER JOIN ore_settimanali v
          ON v.task_id = c.task_id AND v.dipendente_id = c.dipendente_id
         AND v.settimana = c.settimana
        WHERE c.task_id IS NULL OR v.task_id IS NULL
           OR round(c.ore_dichiarate::numeric, 2) <> v.ore
        LIMIT 10
    """)).fetchall()
    if divergenze:
        righe = "; ".join(f"{r[0]}/{r[1]}/{r[2]}: prima={r[3]} dopo={r[4]}" for r in divergenze)
        raise RuntimeError(f"MIGRAZIONE STORICO ANNULLATA: divergenze fra consuntivi e blocchi -> {righe}")

    print(f"✅ {inserite} blocchi 'storico' creati; ore_settimanali == ore_dichiarate "
          f"su tutte le {attese} chiavi, al centesimo")


def downgrade() -> None:
    n = op.get_bind().execute(sa.text("DELETE FROM blocchi_ore WHERE fonte = 'storico'")).rowcount
    print(f"⚠ {n} blocchi 'storico' cancellati (consuntivi mai modificato)")
