"""consuntivi: via `ore_dichiarate` — la colonna piena che nessuno legge (5.6)

È la colonna delle ore della vecchia Consuntivazione: 2.249 righe valorizzate,
17.535 ore in tutto. Dal passo 2 della Consuntivazione a ore le ore vere stanno
in `blocchi_ore` e si sommano dalla vista `ore_settimanali`; questa colonna è
rimasta come SPECCHIO, riallineata a ogni salvataggio (doppia scrittura N9) per
il caso in cui un lettore nascosto la interrogasse ancora. Al passo 5.5 la
doppia scrittura è stata tolta, e da allora la colonna è ferma ai valori di
allora.

PERCHÉ QUI LA GUARDIA È DIVERSA
───────────────────────────────
Le altre colonne di questo passo si difendono col VUOTO: se c'è un valore,
qualcuno scrive, e ci si ferma. Qui non funziona — la colonna è piena per
costruzione, e una guardia-vuoto fallirebbe sempre.

Non funziona nemmeno la guardia-SPECCHIO («coincide con la vista?»): era vera
finché la doppia scrittura girava, e il passo 5.5 l'ha tolta apposta. Ogni ora
dichiarata da allora è nei blocchi e non qui: pretendere la coincidenza
fallirebbe sul lavoro fatto dopo il 5.5, cioè sulla parte più recente.

La sicurezza di questo drop non sta in un conteggio: sta nel fatto che NESSUNO
LEGGE. È stato verificato in due modi che restano ripetibili:
  · grep (passo 5.5): zero usi vivi di `Consuntivo.ore_dichiarate` in tutto il
    backend — le occorrenze rimaste sono commenti, più il campo omonimo di
    `seed_data.json`, che è un altro oggetto (da lì escono le ore dei blocchi);
  · `e2e/letture-intatte.spec.js`: un colpo su tutte le letture
    dell'applicazione — GANTT, Economia, SAL, /me, /settimana, fasi, tasks,
    home, risorse. Se un serializzatore leggesse ancora questa colonna, dopo il
    drop quello spec diventa rosso. È il presidio, e va eseguito DOPO.

La guardia che resta qui è un CONTROLLO DI NON-SORPRESA: stampa quante righe e
quante ore stanno per sparire, e verifica che le stesse ore siano recuperabili
dai blocchi — non per autorizzare il drop, ma perché chi lo esegue veda nero su
bianco che il dato non se ne va dal sistema, se ne va da QUESTA colonna.

IL DOWNGRADE RICOSTRUISCE, non azzera
─────────────────────────────────────
Ricreare la colonna a zero darebbe una colonna che mente. Il downgrade la
ricrea nullable, la riempie DALLA VISTA — che è la sorgente vera delle ore — e
poi la rimette NOT NULL. Chi torna indietro ritrova uno specchio fedele, non un
guscio: più fedele dell'originale, che dal 5.5 era congelato.
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

TABELLA = "consuntivi"
COLONNA = "ore_dichiarate"


def upgrade() -> None:
    conn = op.get_bind()
    righe, ore = conn.execute(sa.text(
        f"SELECT count(*) FILTER (WHERE {COLONNA} <> 0), "
        f"       coalesce(sum({COLONNA}), 0) FROM {TABELLA}")).one()
    blocchi, ore_blocchi = conn.execute(sa.text(
        "SELECT count(*), coalesce(sum(ore), 0) FROM blocchi_ore")).one()
    print(f"guardia (non-sorpresa): {TABELLA}.{COLONNA} → {righe} righe valorizzate, "
          f"{float(ore):.2f} ore")
    print(f"  le ore restano in blocchi_ore: {blocchi} blocchi, {float(ore_blocchi):.2f} ore")
    print("  il drop toglie la COPIA, non il dato. Il presidio è e2e/letture-intatte.")

    op.drop_column(TABELLA, COLONNA)
    print(f"✅ {TABELLA}: droppata {COLONNA}")


def downgrade() -> None:
    op.add_column(TABELLA, sa.Column(COLONNA, sa.Float(), nullable=True))
    conn = op.get_bind()
    # Si riempie DALLA VISTA: è la sorgente vera delle ore, e ricostruisce uno
    # specchio fedele invece di un guscio a zero.
    conn.execute(sa.text(f"""
        UPDATE {TABELLA} c
           SET {COLONNA} = coalesce(v.ore, 0)
          FROM (SELECT task_id, dipendente_id, settimana, ore FROM ore_settimanali) v
         WHERE v.task_id = c.task_id
           AND v.dipendente_id = c.dipendente_id
           AND v.settimana = c.settimana
    """))
    conn.execute(sa.text(f"UPDATE {TABELLA} SET {COLONNA} = 0 WHERE {COLONNA} IS NULL"))
    op.alter_column(TABELLA, COLONNA, nullable=False)
    n = conn.execute(sa.text(
        f"SELECT count(*) FROM {TABELLA} WHERE {COLONNA} <> 0")).scalar()
    print(f"↩ {TABELLA}: ricreata {COLONNA} e riempita dalla vista ({n} righe con ore)")
