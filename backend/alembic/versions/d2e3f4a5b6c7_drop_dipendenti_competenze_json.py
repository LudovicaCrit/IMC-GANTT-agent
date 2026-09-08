"""drop `dipendenti.competenze`: la colonna JSON del doppione-competenze

Recisione del doppione (08/09/2026), passo finale. Le competenze di una persona
erano scritte in DUE posti: la colonna JSON `dipendenti.competenze` (testo
libero, accetta qualunque stringa) e la M2M `dipendenti_competenze` (FK verso il
catalogo `competenze`, quindi solo nomi censiti). Due sorgenti della stessa
verità che nessuno teneva allineate: al momento della recisione 4 dipendenti su
18 divergevano, e nessuno se n'era accorto per mesi.

PERCHÉ IL DROP È SICURO — verificato voce per voce, non a campione
──────────────────────────────────────────────────────────────────
Prima del drop, le 76 voci nella colonna JSON stavano così:

  67  presenti anche nella M2M          → nulla da perdere
   9  assenti dalla M2M, TUTTE previste → scarti decisi, non incidenti
        'IA'            (D011)  riconciliata in 'AI/ML' nella M2M
        'analisi'       (D010)  frammento, mai stato in catalogo
        'organizzazione'(D012)  frammento, mai stato in catalogo
        'archivio'      (D014)  frammento, mai stato in catalogo
        'PM'            (D002/D005/D006/D007/D013)  vedi sotto
   0  perdite non previste

'PM' NON ERA UNA COMPETENZA, ed è la ragione per cui questo drop ha aspettato.
Era una qualifica-ruolo parcheggiata nel catalogo delle abilità, e serviva a un
match che confrontava il `profilo_richiesto` di un task (un RUOLO) con le
competenze di una persona (un CATALOGO di abilità): due vocabolari diversi, in
cui 'PM' era l'unico valore che coincidesse — per omonimia, non per progetto.
Tolto quel match, la label non serviva più a nulla, ed era anche MENO completa
del dato che descriveva: la portavano 5 persone, ma i PM veri — quelli che
`Progetto.pm_id` indica — sono 7. La verità «chi dirige un progetto» sta in
`pm_id` e continua a starci; la label è stata rimossa dal catalogo insieme alle
sue 5 associazioni, prima di questa migration.

NESSUN LETTORE RESTA — verificato con grep su tutto il backend
──────────────────────────────────────────────────────────────
`get_dipendente` (data_db_impl) e `GET /api/dipendenti` leggono dalla M2M;
`routes/risorse.py` non legge più competenze affatto; i tre consumatori
frontend (Risorse, AnalisiInterventi, Pipeline) prendono il campo dal payload
di `/api/dipendenti`, quindi già dalla M2M. Gli ultimi tre accessi alla colonna
erano SCRITTORI (POST e PATCH in configurazione.py, più il seed) e hanno
smesso di scriverla nel passo precedente: la colonna è inerte da allora.

IL DOWNGRADE RICREA LA COLONNA, NON IL CONTENUTO
─────────────────────────────────────────────────
`op.add_column` restituisce una colonna vuota. Il contenuto è ricostruibile
dalla M2M — che è la sorgente completa — ma NON dal downgrade, e i 9 scarti
sopra non tornerebbero comunque: sono stati scartati per decisione, non per
incidente. Chi torna indietro torna allo schema, non ai dati.
"""
from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Guardia: il drop è irreversibile, quindi la verifica «nulla di
    # irrecuperabile» non si fida di essere già stata fatta fuori da qui.
    # Ogni voce JSON non coperta dalla M2M dev'essere uno degli scarti decisi;
    # qualunque altro nome ferma la migration invece di cancellarlo in silenzio.
    imprevisti = conn.execute(sa.text("""
        SELECT d.id, j.nome
        FROM dipendenti d
        CROSS JOIN LATERAL jsonb_array_elements_text(d.competenze::jsonb) AS j(nome)
        WHERE j.nome NOT IN ('IA', 'analisi', 'organizzazione', 'archivio', 'PM')
          AND NOT EXISTS (
              SELECT 1 FROM dipendenti_competenze dc
              JOIN competenze c ON c.id = dc.competenza_id
              WHERE dc.dipendente_id = d.id AND c.nome = j.nome
          )
    """)).fetchall()
    if imprevisti:
        righe = ", ".join(f"{r[0]}:{r[1]!r}" for r in imprevisti)
        raise RuntimeError(
            "DROP ANNULLATO: la colonna JSON contiene nomi che non sono nella "
            f"M2M e non sono fra gli scarti decisi -> {righe}. "
            "Censirli in `competenze` e associarli, oppure aggiungerli "
            "esplicitamente agli scarti previsti qui sopra."
        )

    op.drop_column("dipendenti", "competenze")
    print("✅ dipendenti.competenze (JSON) rimossa: la M2M "
          "`dipendenti_competenze` è l'unica sorgente delle competenze")


def downgrade() -> None:
    """Ricrea la colonna VUOTA. Vedi la nota in testa: lo schema torna, i dati no."""
    op.add_column(
        "dipendenti",
        sa.Column("competenze", sa.JSON(), nullable=True),
    )
    print("⚠ dipendenti.competenze ricreata VUOTA — il contenuto va "
          "ricostruito dalla M2M, il downgrade non lo ripristina")
