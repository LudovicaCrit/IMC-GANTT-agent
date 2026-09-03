"""urgenza (ex ritardabilita) su progetti+fasi, e i CHECK sugli stati che mancavano

Due lavori nella stessa migration perché toccano le stesse tre tabelle e la
stessa domanda — «quali valori sono ammessi in questa colonna, e chi lo
garantisce».

═══════════════════════════════════════════════════════════════════════════
A1 — L'URGENZA
═══════════════════════════════════════════════════════════════════════════

RINOMINA, NON UN CAMPO NUOVO. `Progetto.ritardabilita` era già l'urgenza, con
il nome sbagliato: dichiarata dal PM, mai letta da nessuna logica, solo
trasportata e serializzata. Non si affianca un campo `urgenza` lasciando l'altro
lì — sarebbero due colonne per lo stesso fatto, ed è la trappola che la
migration d6e7f8a9b0c1 ha già dovuto disinnescare droppando `sottotask_nota`:
«due colonne quasi omonime nella stessa area del modello, una viva e una morta,
sono una trappola per chi scriverà la prossima query». Qui sarebbe peggio, perché
i due nomi sono semanticamente INVERSI — alta ritardabilità = bassa urgenza — e
chi le trovasse entrambe rischierebbe di leggerle al contrario.

IL MOMENTO È QUESTO, e non per comodità: `sal_snapshot` ha 0 righe e
`bollettino_economico` 0. La chiave compare nel JSONB del SAL
(`_serializza_stato_progetto`), quindi rinominare cambia la forma dello
snapshot — ma non esiste un solo snapshot da migrare o da leggere in due
formati. Fra un mese non sarebbe più vero. Il frontend non la usa affatto (zero
occorrenze in src/), quindi non c'è nemmeno una UI da riallineare.

I QUATTRO LIVELLI
-----------------
    Bassa · Medio-Bassa · Medio-Alta · Alta

Senza un centro: quattro livelli pari costringono a scegliere da che parte
stare, che è il punto di una scala di urgenza. La costante vive in
`models.LIVELLI_URGENZA`, accanto agli altri enum applicativi.

LA COLONNA SI ALLARGA — String(10) → String(16). Non è un ritocco: "Medio-Bassa"
è 11 caratteri e non ci starebbe. Con 16 c'è margine se un giorno i livelli
cambiassero nome.

LA MAPPATURA DEI 38 PROGETTI — "media" → "Medio-Bassa", ed è una DECISIONE
--------------------------------------------------------------------------
Tutti e 38 hanno `ritardabilita = 'media'`, e vale la pena sapere perché: non
è una scelta di nessuno. Il campo non compare nel wizard, non è mai stato
mostrato in nessuna schermata; "media" è il default del DTO
(`routes/progetti.py`), scritto a ogni creazione senza che nessuno lo vedesse.

Fra due livelli senza centro si arrotonda VERSO IL BASSO. Promuovere 38 progetti
a "Medio-Alta" attribuirebbe al PM una dichiarazione di urgenza che non ha mai
fatto, e su un dato che servirà a modulare le soglie del semaforo: inventare
urgenza dove non c'era significherebbe far gridare il semaforo per una scelta
del sistema, non della persona. Il default innocuo è quello che chiede meno
attenzione, non quello di mezzo.

PROGETTO: NOT NULL. FASE: NULLABLE, ED È LA DIFFERENZA CHE CONTA
----------------------------------------------------------------
`Progetto.urgenza` diventa NOT NULL (oggi è nullable): il progetto è la RADICE
dell'eredità, e una radice NULL renderebbe irrisolvibile l'urgenza di tutte le
sue fasi. `server_default 'Medio-Bassa'` perché la colonna NOT NULL deve poter
nascere su una tabella popolata, e perché tre punti creano Progetto fuori dal
DTO (`seed.py`, `add_p010.py`, e le due route): senza default lato DB uno di
quelli si romperebbe.

`Fase.urgenza` nasce NULLABLE e SENZA default, e il NULL è l'informazione:
«eredita dal progetto». È il pattern di `Sottotask.dipendente_id`, con la stessa
motivazione scritta in models.py: «nullable=True NON è una lacuna da riempire:
il NULL È l'informazione, e un default inventato la cancellerebbe». Un valore
copiato dal progetto alla creazione della fase sembrerebbe identico oggi e
DIVERGEREBBE domani, appena il PM cambia l'urgenza del progetto: la fase
resterebbe ferma al valore di ieri senza che nessuno l'abbia deciso.

═══════════════════════════════════════════════════════════════════════════
A2 — I TRE CHECK SUGLI STATI, CHE ERANO DICHIARATI MA NON ESISTEVANO
═══════════════════════════════════════════════════════════════════════════

`ck_progetti_stato_ammessi`, `ck_fasi_stato_ammessi` e `ck_task_stato_ammessi`
sono creati dalle migration c3d4e5f6a7b8 e d4e5f6a7b8c9, e `alembic current` è
a head — ma nel database NON CI SONO. Verificato interrogando pg_constraint: gli
unici CHECK presenti sono i sei di consuntivi/sottotask/dipendenze.

`alembic check` non se ne accorge perché confronta i MODELLI con il database, e
quei CHECK vivevano solo dentro le migration: nessun `__table_args__` li
dichiarava. L'ipotesi più probabile — non verificabile a posteriori — è che il
database sia stato ricreato con `create_tables()` (`Base.metadata.create_all`,
cioè `python models.py`), che di quei vincoli non sa nulla, e poi stampato ad
alembic.

Non è un dettaglio formale: più commenti nel codice li citano come garanzie
ATTIVE. models.py su STATI_DICHIARABILI dice «il CHECK ck_task_stato_ammessi non
viene mai raggiunto con un valore fuori lista (l'IntegrityError sarebbe un 500
opaco invece di un 400 parlante)». Oggi quella frase è falsa.

Per questo i CHECK di questa migration vanno ANCHE in `__table_args__` dei
modelli, non solo qui: così sopravvivono a un `create_all` e la prossima
ricreazione del database non li perde di nuovo.

DATI VERIFICATI PRIMA DI VINCOLARE — nessuna riga fuori lista:
    progetti : In esecuzione 35 · Sospeso 1 · Completato 1 · Bozza 1   → tutti ✓
    fasi     : In corso 44 · Completata 25 · Da iniziare 2             → tutti ✓
    task     : In corso 68 · Completato 41 · Da iniziare 4 · Bloccato 1 → tutti ✓
    stato NULL: 0 righe su tutte e tre le tabelle.

⚠ «ELIMINATO» — il CHECK sui task È PIÙ LARGO della costante, di proposito
---------------------------------------------------------------------------
Il soft-delete dei task scrive `stato = "Eliminato"` (routes/tasks.py:722, via
`modifica_task`), ed è raggiungibile dalla UI: il cestino nella riga-task del
Cantiere. Ma "Eliminato" NON è in `STATI_TASK`, e la migration d4e5f6a7b8c9
costruiva il CHECK esattamente su quella costante.

Ripristinare il CHECK come dichiarato ROMPEREBBE il soft-delete: il cestino
comincerebbe a restituire 500 (IntegrityError). Oggi non succede solo perché il
CHECK non esiste — il difetto è latente da quando la migration è stata scritta,
e nessuno l'ha incontrato perché in DB non c'è un solo task "Eliminato".

Quindi il CHECK ammette STATI_TASK **+ "Eliminato"**, e la costante resta com'è.
Non si aggiunge "Eliminato" a `STATI_TASK` perché quella costante alimenta la
tendina dello stato nel Cantiere (`_costanti.js` → `SezioneFasiTask`): il PM si
ritroverebbe "Eliminato" fra le opzioni selezionabili a mano, che è peggio del
problema che stiamo risolvendo. Il vincolo protegge il database da valori
inventati; la costante governa cosa si può SCEGLIERE. Sono due domande diverse e
la seconda è più stretta.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Copie LOCALI dei valori ammessi ──────────────────────────────────────
# Una migration è uno snapshot storico: deve produrre lo stesso DDL fra un anno
# anche se le costanti di models.py nel frattempo cambiano. È la convenzione già
# seguita da a3b4c5d6e7f8 ed e5f6a7b8c9d0, che ricopiano i valori invece di
# importarli.
LIVELLI_URGENZA = ("Bassa", "Medio-Bassa", "Medio-Alta", "Alta")
URGENZA_DEFAULT = "Medio-Bassa"

STATI_PROGETTO_AMMESSI = (
    "Bozza", "Da iniziare", "In esecuzione", "Sospeso", "Completato", "Annullato",
)
STATI_FASE_AMMESSI = (
    "Da iniziare", "In corso", "Completata", "Sospesa", "Annullata",
)
# STATI_TASK + "Eliminato" (soft delete). Vedi il blocco ⚠ nel docstring.
STATI_TASK_AMMESSI = (
    "Da iniziare", "In corso", "Completato", "Bloccato", "Sospeso", "Annullato",
    "Eliminato",
)

CK_URGENZA_PROGETTI = "ck_progetti_urgenza"
CK_URGENZA_FASI = "ck_fasi_urgenza"
CK_STATO_PROGETTI = "ck_progetti_stato_ammessi"
CK_STATO_FASI = "ck_fasi_stato_ammessi"
CK_STATO_TASK = "ck_task_stato_ammessi"


def _in_clause(colonna, valori):
    """`colonna IN ('a','b',...)` — i valori sono costanti locali, non input."""
    return f"{colonna} IN ({', '.join(repr(v) for v in valori)})"


def upgrade() -> None:
    conn = op.get_bind()

    # ═══ GUARDIA — non vincolare dati che violerebbero il vincolo ═══════
    # Se un altro database avesse stati fuori lista, il CHECK fallirebbe a metà
    # migration lasciando lo schema a metà. Meglio fermarsi PRIMA, dicendo quali
    # valori sono il problema, che schiantarsi su un IntegrityError generico.
    for tabella, ammessi in (("progetti", STATI_PROGETTO_AMMESSI),
                             ("fasi", STATI_FASE_AMMESSI),
                             ("task", STATI_TASK_AMMESSI)):
        fuori = conn.execute(sa.text(
            f"SELECT DISTINCT stato FROM {tabella} "
            f"WHERE stato IS NULL OR NOT ({_in_clause('stato', ammessi)})"
        )).scalars().all()
        if fuori:
            raise RuntimeError(
                f"Migration f8a9b0c1d2e3 abortita: la tabella '{tabella}' contiene "
                f"stati non ammessi {fuori}. Il CHECK li rifiuterebbe. Correggi i "
                f"dati (o rivedi l'elenco degli stati) prima di rilanciare."
            )
    print("✅ Guardia: nessuno stato fuori lista in progetti/fasi/task")

    # ═══ A1 — URGENZA ═══════════════════════════════════════════════════
    # 1. Rinomina + allarga. ALTER TYPE con USING implicito: String→String più
    #    lungo non perde dati.
    op.alter_column('progetti', 'ritardabilita', new_column_name='urgenza')
    op.alter_column('progetti', 'urgenza',
                    type_=sa.String(length=16), existing_nullable=True)
    print("✅ progetti.ritardabilita → urgenza, String(10) → String(16)")

    # 2. Mappatura dei valori esistenti. `IS NULL` incluso: la colonna era
    #    nullable e sta per diventare NOT NULL — una riga NULL bloccherebbe il
    #    passo 3. Oggi non ce ne sono, ma la migration non lo dà per scontato.
    n = conn.execute(sa.text(
        "UPDATE progetti SET urgenza = :nuovo "
        "WHERE urgenza IS NULL OR urgenza NOT IN :ammessi"
    ).bindparams(sa.bindparam('ammessi', expanding=True)),
        {"nuovo": URGENZA_DEFAULT, "ammessi": list(LIVELLI_URGENZA)}
    ).rowcount
    print(f"✅ {n} progetti mappati a '{URGENZA_DEFAULT}' (erano 'media', default mai scelto)")

    # 3. NOT NULL + default lato DB: il progetto è la radice dell'eredità.
    op.alter_column('progetti', 'urgenza',
                    existing_type=sa.String(length=16),
                    nullable=False,
                    server_default=URGENZA_DEFAULT)
    op.create_check_constraint(
        CK_URGENZA_PROGETTI, 'progetti', _in_clause('urgenza', LIVELLI_URGENZA))
    print(f"✅ progetti.urgenza NOT NULL default '{URGENZA_DEFAULT}' + CHECK {CK_URGENZA_PROGETTI}")

    # 4. Fase.urgenza — NULLABLE e SENZA default: il NULL è «eredita».
    op.add_column('fasi', sa.Column('urgenza', sa.String(length=16), nullable=True))
    op.create_check_constraint(
        CK_URGENZA_FASI, 'fasi',
        f"urgenza IS NULL OR {_in_clause('urgenza', LIVELLI_URGENZA)}")
    print(f"✅ fasi.urgenza aggiunta (nullable = eredita) + CHECK {CK_URGENZA_FASI}")

    # ═══ A2 — I TRE CHECK SUGLI STATI ═══════════════════════════════════
    # `DROP ... IF EXISTS` prima di creare: su un database dove esistessero
    # davvero (uno ricreato dalle migration invece che da create_all) il CREATE
    # fallirebbe per nome duplicato. Così la migration è applicabile a entrambe
    # le storie.
    for nome, tabella, ammessi in (
        (CK_STATO_PROGETTI, 'progetti', STATI_PROGETTO_AMMESSI),
        (CK_STATO_FASI, 'fasi', STATI_FASE_AMMESSI),
        (CK_STATO_TASK, 'task', STATI_TASK_AMMESSI),
    ):
        conn.execute(sa.text(f"ALTER TABLE {tabella} DROP CONSTRAINT IF EXISTS {nome}"))
        op.create_check_constraint(nome, tabella, _in_clause('stato', ammessi))
        print(f"✅ {nome} creato su {tabella} ({len(ammessi)} stati ammessi)")


def downgrade() -> None:
    """Torna a `ritardabilita` e toglie i vincoli.

    REVERSIBILE CON UNA PERDITA DICHIARATA: `fasi.urgenza` sparisce, e con essa
    gli override che il PM avesse impostato sulle singole fasi — quel dato non ha
    dove tornare, perché prima non esisteva una colonna che lo contenesse.
    L'urgenza di PROGETTO invece sopravvive: torna in `ritardabilita` coi
    quattro livelli scritti dentro. Non si rimappa a 'media' — sarebbe
    distruggere una scelta del PM per ricostruire un default che nessuno aveva
    scelto. La colonna torna String(10), che tronca "Medio-Bassa" a 10 caratteri:
    per questo la si riporta prima a 'media' SOLO dove il valore non ci sta.
    """
    for nome, tabella in ((CK_STATO_PROGETTI, 'progetti'),
                          (CK_STATO_FASI, 'fasi'),
                          (CK_STATO_TASK, 'task')):
        op.drop_constraint(nome, tabella, type_='check')
    print("✅ CHECK sugli stati rimossi")

    op.drop_constraint(CK_URGENZA_FASI, 'fasi', type_='check')
    op.drop_column('fasi', 'urgenza')
    print("✅ fasi.urgenza rimossa (gli override di fase sono persi)")

    op.drop_constraint(CK_URGENZA_PROGETTI, 'progetti', type_='check')
    op.alter_column('progetti', 'urgenza',
                    existing_type=sa.String(length=16),
                    nullable=True,
                    server_default=None)
    # I valori più lunghi di 10 caratteri non entrano nella colonna vecchia.
    op.get_bind().execute(sa.text(
        "UPDATE progetti SET urgenza = 'media' WHERE length(urgenza) > 10"))
    op.alter_column('progetti', 'urgenza',
                    type_=sa.String(length=10), existing_nullable=True)
    op.alter_column('progetti', 'urgenza', new_column_name='ritardabilita')
    print("✅ progetti.urgenza → ritardabilita, String(16) → String(10)")
