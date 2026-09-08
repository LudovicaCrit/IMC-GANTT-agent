"""dipendenti_ruoli_aggiuntivi: la M2M dei ruoli funzionali

Multiruolo, passo B (08/09/2026). La casella che mancava al modello.

IL PROBLEMA CHE CHIUDE
───────────────────────
`Dipendente.ruolo_id` tiene UN ruolo, e quel posto è occupato
dall'inquadramento contrattuale ("Senior Consultant"). Non c'era quindi modo di
dire «questa persona è anche PM» — e la mancanza non è rimasta teorica: 'PM' era
finito nel CATALOGO DELLE COMPETENZE, accanto ad 'ARIS' e 'python', perché era
l'unico elenco multi-valore agganciato a una persona. Da lì derivava il match
dei task che confrontava un RUOLO con delle ABILITÀ e funzionava per omonimia su
un solo valore.

Questa tabella è la casella giusta: zero o più ruoli `funzionale` per persona,
accanto all'inquadramento e senza toccarlo.

RICALCA `dipendenti_competenze`, CHE FUNZIONA
──────────────────────────────────────────────
Stessa forma, e ogni pezzo ha la sua ragione:
  - `id` proprio        → è un ASSOCIATION OBJECT, non una secondary nuda:
                          `data_nomina`, `livello` o il progetto di riferimento
                          si aggiungerebbero come colonne senza migrare la
                          relationship di chi la usa. Non ce ne sono ora.
  - FK ON DELETE CASCADE su ENTRAMBI i lati → cancellare una persona o un ruolo
                          non lascia righe orfane che puntano nel vuoto.
  - UNIQUE (dipendente_id, ruolo_id) → la stessa persona non può ricoprire due
                          volte lo stesso ruolo. È il doppione più stupido, ed è
                          il più facile da introdurre con una doppia submit.
  - `created_at`        → da quando lo sappiamo. Non è la data di nomina (che
                          sarebbe un attributo del fatto, non della riga).

COSA QUESTA MIGRATION NON FA
─────────────────────────────
NON POPOLA NULLA: nasce a zero righe. Le associazioni delle 7 persone che il PM
lo fanno davvero arrivano al passo C, e vengono dai fatti (`Progetto.pm_id`),
non dalla vecchia label-competenza che ne copriva solo 5.

NON VINCOLA `ruolo_id` A ESSERE `tipo='funzionale'`. La FK garantisce che il
ruolo esista, non che sia della specie giusta: dirlo in SQL richiederebbe una FK
composita verso una chiave `(id, tipo)` o un trigger — complicare lo schema per
un vincolo che il codice di scrittura applica meglio, perché può SEGNALARE lo
scarto invece di sollevare un errore di integrità opaco. È l'equilibrio già
scelto per `_associa_competenze`, dove un nome fuori catalogo non viene
associato ma viene detto. Finché quel codice non esiste (passi C ed E), la
tabella accetta qualunque ruolo valido — inquadramenti compresi.
"""
from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dipendenti_ruoli_aggiuntivi",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dipendente_id", sa.String(length=10), nullable=False),
        sa.Column("ruolo_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ruolo_id"], ["ruoli.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dipendente_id", "ruolo_id", name="uq_dip_ruolo_agg"),
    )
    n = op.get_bind().execute(
        sa.text("SELECT count(*) FROM dipendenti_ruoli_aggiuntivi")
    ).scalar()
    print(f"✅ dipendenti_ruoli_aggiuntivi creata ({n} righe — il popolamento "
          f"è il passo C)")


def downgrade() -> None:
    """Elimina la tabella.

    Oggi è reversibile senza perdita: la tabella nasce vuota e questa migration
    non scrive nulla. Dopo il passo C conterrà le associazioni delle persone-PM:
    da quel momento il downgrade le perde tutte. Non è perdita di VERITÀ — chi
    dirige un progetto resta in `Progetto.pm_id`, che è la fonte da cui il passo
    C popola, quindi il contenuto è ricostruibile — ma è perdita di dato, e
    ricostruirlo è rieseguire C, non tornare indietro.
    """
    op.drop_table("dipendenti_ruoli_aggiuntivi")
    print("⚠ dipendenti_ruoli_aggiuntivi eliminata — con essa ogni ruolo "
          "aggiuntivo assegnato")
