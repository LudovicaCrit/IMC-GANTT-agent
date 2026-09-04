"""ruolo_app: il terzo ruolo 'pm', e il CHECK che finora non c'era

Tappa 2 (04/09/2026). Il sistema aveva DUE ruoli — `manager` e `user` — mentre
l'organizzazione ne ha tre: chi governa tutto, chi dirige i propri progetti, chi
opera e dichiara. Il PM esisteva solo come `Progetto.pm_id`, cioè un'etichetta
sul progetto e non una proprietà della persona.

IL VALORE NON HA BISOGNO DI UNA MIGRATION — IL VINCOLO SÌ
──────────────────────────────────────────────────────────
`Utente.ruolo_app` è `String(20)` senza CHECK: accetta già qualunque stringa,
quindi scriverci 'pm' funzionerebbe da subito. Il punto di questa migration è
l'opposto: METTERE un vincolo dove non c'era.

Finora i valori ammessi vivevano solo in un commento del modello
(`# "user" | "manager"`). Un refuso — 'Manager', 'pm ', 'admin' — sarebbe
entrato in tabella senza che nulla protestasse, e si sarebbe manifestato come
un utente che *silenziosamente* non è manager: `require_manager` fa
`!= "manager"`, quindi qualunque valore sconosciuto degrada a «non
autorizzato». Un permesso che sparisce per un errore di battitura, senza un
messaggio.

È la lezione della migration f8a9b0c1d2e3, che ha dovuto RICREARE tre CHECK
(`ck_progetti/fasi/task_stato_ammessi`) dichiarati dalle migration ma ASSENTI
dal database. Per questo il vincolo va anche in `__table_args__` del modello e
non solo qui: così sopravvive a un `Base.metadata.create_all()`, che dei CHECK
dichiarati nelle sole migration non sa nulla.

PERCHÉ 'pm' NON ROMPE NIENTE — verificato leggendo tutti i lettori
──────────────────────────────────────────────────────────────────
`ruolo_app` è letto in 14 punti (11 backend, 3 frontend) e TUTTI confrontano
con `"manager"`, mai con `"user"`. Un valore nuovo cade quindi sempre nel ramo
«non manager», cioè viene trattato esattamente come un user:
  deps.require_manager        → 403, come un user
  progetti_attivi_visibili    → ramo PM+membro: vede i suoi progetti
  dipendenti/consuntivi/tasks/attivita_interne/agent → self-only
  frontend RequireManager     → Forbidden
Nessuna guardia va riscritta, ed è il motivo per cui questo passo è sicuro
prima di aver deciso la matrice dei poteri-PM.

Con un'eccezione FAVOREVOLE: `routes/sal.py::_autorizza_progetto` ammette
«manager OPPURE il PM di quel progetto» (`dipendente_id == pm_id`). Un utente
'pm' che è davvero PM di un progetto conserva quindi il potere di consolidarne
SAL e Bollettino — l'unico permesso-PM esistente nel sistema, che sopravvive
alla retrocessione da manager.

VALORI ESISTENTI — verificati prima di vincolare
────────────────────────────────────────────────
    'manager' × 3 · 'user' × 1 · fuori lista: nessuno
Il CHECK non può quindi fallire l'applicazione. La guardia sotto lo ricontrolla
comunque a runtime: su un altro database i valori potrebbero essere diversi, e
fermarsi con un messaggio è meglio che schiantarsi a metà DDL.

NESSUN BACKFILL: questa migration non assegna ruoli a nessuno. Chi è 'manager'
resta 'manager'. L'assegnazione dei profili è un'operazione sui DATI, separata e
reversibile, non una modifica di schema.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copia LOCALE dei valori: una migration è uno snapshot storico e deve produrre
# lo stesso DDL anche se la costante nel modello cambia. Convenzione già seguita
# da a3b4c5d6e7f8, e5f6a7b8c9d0 e f8a9b0c1d2e3.
RUOLI_APP = ("manager", "pm", "user")
CK_RUOLO = "ck_utenti_ruolo_app"


def upgrade() -> None:
    conn = op.get_bind()

    # Guardia: non si vincola una colonna che contiene già valori fuori lista.
    fuori = conn.execute(sa.text(
        "SELECT DISTINCT ruolo_app FROM utenti "
        "WHERE ruolo_app IS NULL OR ruolo_app NOT IN :ammessi"
    ).bindparams(sa.bindparam("ammessi", expanding=True)),
        {"ammessi": list(RUOLI_APP)}).scalars().all()
    if fuori:
        raise RuntimeError(
            f"Migration a9b0c1d2e3f4 abortita: la tabella 'utenti' contiene "
            f"ruoli non ammessi {fuori}. Il CHECK li rifiuterebbe. Correggi i "
            f"dati (o rivedi l'elenco dei ruoli) prima di rilanciare."
        )
    print("✅ Guardia: nessun ruolo_app fuori lista in utenti")

    # DROP IF EXISTS prima di creare: su un database dove il vincolo esistesse
    # già (ricreato dalle migration invece che da create_all) il CREATE
    # fallirebbe per nome duplicato.
    conn.execute(sa.text(f"ALTER TABLE utenti DROP CONSTRAINT IF EXISTS {CK_RUOLO}"))
    op.create_check_constraint(
        CK_RUOLO, "utenti",
        f"ruolo_app IN ({', '.join(repr(r) for r in RUOLI_APP)})",
    )
    print(f"✅ {CK_RUOLO} creato su utenti ({len(RUOLI_APP)} ruoli: {', '.join(RUOLI_APP)})")


def downgrade() -> None:
    """Toglie il vincolo. Nessuna perdita di dati.

    I ruoli 'pm' eventualmente assegnati RESTANO in tabella: senza il CHECK la
    colonna torna a essere una stringa libera, e quei valori continuano a essere
    letti come «non manager» da tutte le guardie. Si perde la garanzia, non
    l'informazione.
    """
    op.drop_constraint(CK_RUOLO, "utenti", type_="check")
    print(f"✅ {CK_RUOLO} rimosso")
