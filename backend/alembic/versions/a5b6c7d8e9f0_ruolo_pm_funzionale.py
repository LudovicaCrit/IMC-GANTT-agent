"""'PM' entra fra i ruoli, come funzionale

Multiruolo, passo A2 (08/09/2026). 'PM' torna nel modello dalla porta giusta.

DA DOVE VIENE, E PERCHÉ NON ERA GIÀ QUI
────────────────────────────────────────
Fino a ieri 'PM' viveva nel CATALOGO DELLE COMPETENZE, accanto ad 'ARIS' e
'python'. Non era una svista isolata: era l'unico modo che il modello offrisse
per dire «questa persona fa anche il PM», dato che `Dipendente.ruolo_id` tiene
UN solo ruolo e quel posto era già occupato dall'inquadramento. Una qualifica
parcheggiata fra le abilità perché non c'era una casella per le qualifiche
aggiuntive.

Quel parcheggio aveva un effetto collaterale che sembrava una funzionalità: il
match dei task confrontava `profilo_richiesto` (un RUOLO) con le competenze
della persona, e 'PM' era l'unico valore presente in entrambi i vocabolari. Il
match sembrava funzionare per le persone-PM e falliva per tutti gli altri
profili — non per un bug, ma perché confrontava due elenchi diversi che si
toccavano in un punto solo. Rimosso il match (08/09/2026) e poi la competenza,
'PM' è rimasto senza casa: 7 task lo chiedono come `profilo_richiesto` e nessun
meccanismo può più dire chi lo ricopra.

Questa migration gli dà la casa giusta: un RUOLO, marcato `funzionale`, cioè
ricopribile IN AGGIUNTA all'inquadramento. Da qui:
  - Cantiere può richiederlo su un task (la tendina «profilo richiesto» legge
    tutti i ruoli attivi, e ora PM è fra questi);
  - il form dipendente NON lo offre come inquadramento, perché il select filtra
    `tipo == 'base'` (passo A1 — è la ragione per cui A1 viene prima);
  - il passo C potrà associarlo alle 7 persone che il PM lo fanno davvero, e il
    passo G potrà farlo matchare.

NON RIPRISTINA LE 5 ASSOCIAZIONI DELLA VECCHIA LABEL, e non deve: erano 5 su 7
PM reali (`Progetto.pm_id` ne conta 7, incluse D016 e D017 che la label non
aveva mai avuto). Le associazioni si popolano al passo C, dai fatti, non dalla
label che stiamo sostituendo.
"""
from alembic import op
import sqlalchemy as sa

revision = "a5b6c7d8e9f0"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

NOME = "PM"
DESCRIZIONE = (
    "Project Manager: dirige uno o più progetti. Ruolo funzionale, si ricopre "
    "IN AGGIUNTA all'inquadramento (un Senior Consultant può essere PM). "
    "Chi lo ricopre su uno specifico progetto resta Progetto.pm_id."
)


def upgrade() -> None:
    conn = op.get_bind()

    # `ruoli.nome` è UNIQUE: un secondo INSERT fallirebbe con IntegrityError
    # invece di dire cosa è successo. La migration è scritta per essere
    # rieseguibile su un database dove 'PM' esista già (per esempio ricreato dal
    # seed, che dal passo A2 lo censisce): in quel caso si limita ad allineare
    # il tipo, che è l'informazione che questa migration esiste per garantire.
    esistente = conn.execute(
        sa.text("SELECT id, tipo FROM ruoli WHERE nome = :n"), {"n": NOME}
    ).first()

    if esistente is None:
        conn.execute(
            sa.text("""INSERT INTO ruoli (nome, descrizione, tipo, attivo)
                       VALUES (:n, :d, 'funzionale', true)"""),
            {"n": NOME, "d": DESCRIZIONE},
        )
        print(f"✅ ruolo '{NOME}' creato con tipo='funzionale'")
    elif esistente[1] != "funzionale":
        conn.execute(
            sa.text("UPDATE ruoli SET tipo = 'funzionale' WHERE nome = :n"),
            {"n": NOME},
        )
        print(f"✅ ruolo '{NOME}' già presente (id={esistente[0]}): tipo "
              f"allineato da '{esistente[1]}' a 'funzionale'")
    else:
        print(f"✅ ruolo '{NOME}' già presente e già funzionale — niente da fare")

    n_base, n_func = conn.execute(sa.text(
        """SELECT count(*) FILTER (WHERE tipo = 'base'),
                  count(*) FILTER (WHERE tipo = 'funzionale') FROM ruoli"""
    )).first()
    print(f"   catalogo ruoli: {n_base} base + {n_func} funzionale/i")


def downgrade() -> None:
    """Toglie il ruolo 'PM'.

    ⚠ Se il passo C ha già associato PM a delle persone, quelle righe spariscono
    con lui: la M2M dei ruoli aggiuntivi ha una FK verso `ruoli` con ON DELETE
    CASCADE. Non è una perdita di verità — chi dirige un progetto resta scritto
    in `Progetto.pm_id`, che è la fonte da cui il passo C popola — ma è una
    perdita di dato, e va saputa prima di eseguirlo, non dopo.

    Non ricrea la vecchia competenza 'PM': quella era il posto sbagliato, e
    tornarci sarebbe un downgrade verso il difetto, non verso lo stato prima.
    """
    conn = op.get_bind()
    n = conn.execute(
        sa.text("DELETE FROM ruoli WHERE nome = :n AND tipo = 'funzionale'"),
        {"n": NOME},
    ).rowcount
    print(f"⚠ ruolo '{NOME}' rimosso ({n} riga/e) — con esso ogni associazione "
          f"che lo referenziava")
