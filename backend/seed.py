"""
Seed del database — popola le tabelle con i dati fittizi di data.py.
Eseguire UNA VOLTA per inizializzare il db.
Se il db esiste già e ha dati, non fa nulla (per sicurezza).
"""

from models import (
    create_tables, get_session,
    Dipendente, Progetto, Task, Assegnazione, Consuntivo, Segnalazione,
)
from data import DIPENDENTI, PROGETTI, TASKS, CONSUNTIVI


def seed():
    create_tables()
    session = get_session()

    # Controlla se il db ha già dati
    if session.query(Dipendente).count() > 0:
        print("Il database contiene già dati. Seed saltato.")
        print(f"  Dipendenti: {session.query(Dipendente).count()}")
        print(f"  Progetti: {session.query(Progetto).count()}")
        print(f"  Task: {session.query(Task).count()}")
        print(f"  Consuntivi: {session.query(Consuntivo).count()}")
        session.close()
        return

    # ── Dipendenti ──
    for _, row in DIPENDENTI.iterrows():
        session.add(Dipendente(
            id=row["id"],
            nome=row["nome"],
            profilo=row["profilo"],
            ore_sett=int(row["ore_sett"]),
            costo_ora=float(row["costo_ora"]),
            competenze=row["competenze"],
        ))
    print(f"  ✓ {len(DIPENDENTI)} dipendenti")

    # ── Progetti ──
    for _, row in PROGETTI.iterrows():
        session.add(Progetto(
            id=row["id"],
            nome=row["nome"],
            cliente=row["cliente"],
            stato=row["stato"],
            data_inizio=row["data_inizio"].date() if hasattr(row["data_inizio"], "date") else row["data_inizio"],
            data_fine=row["data_fine"].date() if hasattr(row["data_fine"], "date") else row["data_fine"],
            budget_ore=int(row["budget_ore"]),
            valore_contratto=float(row["valore_contratto"]),
            descrizione=row["descrizione"],
            fase_corrente=row["fase_corrente"],
        ))
    print(f"  ✓ {len(PROGETTI)} progetti")

    # ── Task ──
    for _, row in TASKS.iterrows():
        session.add(Task(
            id=row["id"],
            progetto_id=row["progetto_id"],
            nome=row["nome"],
            fase=row["fase"],
            ore_stimate=int(row["ore_stimate"]),
            data_inizio=row["data_inizio"].date() if hasattr(row["data_inizio"], "date") else row["data_inizio"],
            data_fine=row["data_fine"].date() if hasattr(row["data_fine"], "date") else row["data_fine"],
            stato=row["stato"],
            profilo_richiesto=row["profilo_richiesto"],
            dipendente_id=row["dipendente_id"],
            predecessore=row["predecessore"] if row["predecessore"] else "",
        ))
    print(f"  ✓ {len(TASKS)} task")

    # ── Assegnazioni (1:1 per ora, dalla colonna dipendente_id dei task) ──
    for _, row in TASKS.iterrows():
        if row["dipendente_id"]:
            session.add(Assegnazione(
                task_id=row["id"],
                dipendente_id=row["dipendente_id"],
                ore_assegnate=int(row["ore_stimate"]),
                ruolo="responsabile",
            ))
    print(f"  ✓ {len(TASKS)} assegnazioni")

    # ── Consuntivi ──
    for _, row in CONSUNTIVI.iterrows():
        session.add(Consuntivo(
            task_id=row["task_id"],
            dipendente_id=row["dipendente_id"],
            settimana=row["settimana"].date() if hasattr(row["settimana"], "date") else row["settimana"],
            ore_dichiarate=float(row["ore_dichiarate"]),
            compilato=bool(row["compilato"]),
            data_compilazione=row["data_compilazione"] if row["compilato"] else None,
            nota=row["nota"] if row["nota"] else None,
        ))
    print(f"  ✓ {len(CONSUNTIVI)} consuntivi")

    # ── Segnalazioni default ──
    segnalazioni_default = [
        Segnalazione(
            id="S001", tipo="sovraccarico", priorita="alta",
            dipendente_id="D005", dettaglio="Saturazione al 133%, 5 progetti attivi.",
            fonte="sistema", stato="aperta",
        ),
        Segnalazione(
            id="S002", tipo="richiesta_supporto", priorita="alta",
            dipendente_id="D001", dettaglio="Richiede supporto tecnico junior per Design architettura HL7 FHIR.",
            fonte="sistema", stato="aperta",
        ),
        Segnalazione(
            id="S003", tipo="sovraccarico", priorita="media",
            dipendente_id="D007", dettaglio="Saturazione al 106%, gestisce 3 backend contemporaneamente.",
            fonte="sistema", stato="aperta",
        ),
    ]
    for s in segnalazioni_default:
        session.add(s)
    print(f"  ✓ {len(segnalazioni_default)} segnalazioni default")

    session.commit()
    session.close()
    print("\n✅ Database popolato con successo!")


if __name__ == "__main__":
    print("Popolamento database IMC-Group...")
    seed()
