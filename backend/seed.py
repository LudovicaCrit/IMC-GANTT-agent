"""
Seed del database R1 — popola tutte le tabelle incluse le nuove:
Ruoli, Competenze, FasiStandard, Fasi per progetto, Utenti.
Eseguire UNA VOLTA per inizializzare il db.
"""

import pandas as pd

from models import (
    create_tables, get_session,
    Azienda, Dipendente, Progetto, Task, DipendenzaTask, Assegnazione, Consuntivo,
    Segnalazione, Ruolo, Competenza, DipendentiCompetenze, FaseStandard,
    Fase, Utente,
)
from data import DIPENDENTI, PROGETTI, TASKS, CONSUNTIVI
from auth import hash_password


def seed():
    create_tables()
    session = get_session()

    if session.query(Dipendente).count() > 0:
        print("Il database contiene già dati. Seed saltato.")
        session.close()
        return

    # ══════════════════════════════════════════════════════════════
    # 1. RUOLI
    # ══════════════════════════════════════════════════════════════
    ruoli_nomi = [
        "AD", "Manager IT", "Senior IT Consultant", "IT Consultant",
        "Senior Consultant", "Consultant", "Manager HR",
        "Responsabile amministrazione", "Addetto amministrazione",
    ]
    ruoli_obj = {}
    for nome in ruoli_nomi:
        r = Ruolo(nome=nome)
        session.add(r)
        session.flush()
        ruoli_obj[nome] = r
    print(f"  ✓ {len(ruoli_nomi)} ruoli")

    # ══════════════════════════════════════════════════════════════
    # 2. COMPETENZE
    # ══════════════════════════════════════════════════════════════
    competenze_nomi = [
        "GRC", "ARIS", "risk management", "compliance", "processi",
        "sviluppo", "backend", "frontend", "API", "database",
        "python", "AI/ML", "cloud", "architettura",
        "PM", "gestione progetti", "coordinamento",
        "relazioni clienti", "bandi", "strategia",
        "risorse umane", "formazione", "contratti",
        "amministrazione", "rendicontazione", "fatturazione",
        "controllo gestione", "documentazione",
        "ISO 27001", "ISO 9001", "DORA", "CSRD",
        "testing", "integrazione sistemi",
        # Competenze funzionali del redesign Innovation Plaza (26/06/2026).
        # Solo funzionali: le qualifiche-ruolo (Co-founder, Managing Director, ecc.)
        # NON sono competenze. Servono per agganciare la M2M dipendenti_competenze
        # delle persone Innovation (Ida/Domenica/Denise) e il match task↔persona.
        "progettazione", "progettazione europea", "bandi pubblici", "PA", "imprese",
    ]
    competenze_obj = {}
    for nome in competenze_nomi:
        c = Competenza(nome=nome)
        session.add(c)
        session.flush()
        competenze_obj[nome] = c
    print(f"  ✓ {len(competenze_nomi)} competenze")

    # ══════════════════════════════════════════════════════════════
    # 2-bis. AZIENDE (struttura multi-azienda — DESIGN §1)
    # ══════════════════════════════════════════════════════════════
    # Devono esistere PRIMA di dipendenti e progetti (FK azienda_id). Le 2
    # operative vive del Gruppo IMC; struttura estensibile (una riga = un ramo).
    # Derivate dai dati referenziati, più le 2 canoniche, così un eventuale ramo
    # nuovo nei dati non richiede di toccare qui.
    nomi_azienda = {"IMC-Improve", "Innovation Plaza"}
    nomi_azienda |= set(DIPENDENTI["azienda"].dropna().unique())
    nomi_azienda |= set(PROGETTI["azienda"].dropna().unique())
    azienda_obj = {}
    for nome in sorted(nomi_azienda):
        a = Azienda(nome=nome)
        session.add(a)
        session.flush()
        azienda_obj[nome] = a
    print(f"  ✓ {len(azienda_obj)} aziende")

    # ══════════════════════════════════════════════════════════════
    # 3. DIPENDENTI
    # ══════════════════════════════════════════════════════════════
    # Mappa profilo → ruolo per il FK
    for _, row in DIPENDENTI.iterrows():
        ruolo = ruoli_obj.get(row["profilo"])
        session.add(Dipendente(
            id=row["id"],
            nome=row["nome"],
            profilo=row["profilo"],
            azienda_id=azienda_obj[row["azienda"]].id,
            ruolo_id=ruolo.id if ruolo else None,
            ore_sett=int(row["ore_sett"]),
            costo_ora=float(row["costo_ora"]),
            competenze=row["competenze"],
        ))
    print(f"  ✓ {len(DIPENDENTI)} dipendenti")

    # ══════════════════════════════════════════════════════════════
    # 4. DIPENDENTI ↔ COMPETENZE (M2M)
    # ══════════════════════════════════════════════════════════════
    n_assoc = 0
    for _, row in DIPENDENTI.iterrows():
        if isinstance(row["competenze"], list):
            for comp_nome in row["competenze"]:
                comp = competenze_obj.get(comp_nome)
                if comp:
                    session.add(DipendentiCompetenze(
                        dipendente_id=row["id"],
                        competenza_id=comp.id,
                    ))
                    n_assoc += 1
    print(f"  ✓ {n_assoc} associazioni dipendente-competenza")

    # ══════════════════════════════════════════════════════════════
    # 5. FASI STANDARD (template)
    # ══════════════════════════════════════════════════════════════
    templates = [
        # Template generico GRC
        ("Template GRC", "Analisi", 1, 20.0),
        ("Template GRC", "Design", 2, 15.0),
        ("Template GRC", "Implementazione", 3, 30.0),
        ("Template GRC", "Testing", 4, 15.0),
        ("Template GRC", "Go-live", 5, 10.0),
        ("Template GRC", "Gestione progetto", 6, 10.0),
        # Template compliance
        ("Template Compliance", "Analisi requisiti", 1, 15.0),
        ("Template Compliance", "Mappatura controlli", 2, 20.0),
        ("Template Compliance", "Sviluppo piattaforma", 3, 30.0),
        ("Template Compliance", "Testing e UAT", 4, 15.0),
        ("Template Compliance", "Deploy", 5, 10.0),
        ("Template Compliance", "Gestione progetto", 6, 10.0),
        # Template digitalizzazione
        ("Template Digitalizzazione", "Analisi", 1, 15.0),
        ("Template Digitalizzazione", "Design", 2, 15.0),
        ("Template Digitalizzazione", "Sviluppo", 3, 35.0),
        ("Template Digitalizzazione", "Testing", 4, 15.0),
        ("Template Digitalizzazione", "Gestione progetto", 5, 10.0),
        ("Template Digitalizzazione", "Coordinamento cliente", 6, 10.0),
    ]
    for t_nome, f_nome, ordine, pct in templates:
        session.add(FaseStandard(
            template_nome=t_nome,
            fase_nome=f_nome,
            ordine=ordine,
            percentuale_ore=pct,
        ))
    print(f"  ✓ {len(templates)} fasi standard (3 template)")

    # ══════════════════════════════════════════════════════════════
    # 6. PROGETTI
    # ══════════════════════════════════════════════════════════════
    for _, row in PROGETTI.iterrows():
        # azienda/area/pm sono nullable (interni: azienda/pm NULL; area solo bandi).
        az_nome = row.get("azienda")
        area = row.get("area")
        pm_id = row.get("pm_id")
        session.add(Progetto(
            id=row["id"],
            nome=row["nome"],
            cliente=row["cliente"],
            stato=row["stato"],
            tipologia=row.get("tipologia", "ordinario"),
            azienda_id=azienda_obj[az_nome].id if pd.notna(az_nome) else None,
            area=area if pd.notna(area) else None,
            pm_id=pm_id if pd.notna(pm_id) else None,
            data_inizio=row["data_inizio"].date() if hasattr(row["data_inizio"], "date") else row["data_inizio"],
            data_fine=row["data_fine"].date() if hasattr(row["data_fine"], "date") else row["data_fine"],
            budget_ore=int(row["budget_ore"]),
            valore_contratto=float(row["valore_contratto"]),
            descrizione=row["descrizione"],
            fase_corrente=row["fase_corrente"],
        ))
    print(f"  ✓ {len(PROGETTI)} progetti")

    # ══════════════════════════════════════════════════════════════
    # 7. FASI PER PROGETTO (generate dai task esistenti)
    # ══════════════════════════════════════════════════════════════
    # Raggruppa i task per progetto e per fase (stringa)
    fasi_create = {}  # chiave: (progetto_id, fase_nome) → Fase object
    for _, row in TASKS.iterrows():
        pid = row["progetto_id"]
        fase_nome = row["fase"] if row["fase"] else "Generale"
        key = (pid, fase_nome)

        if key not in fasi_create:
            # Trova le date min/max dei task in questa fase
            tasks_fase = TASKS[(TASKS["progetto_id"] == pid) & (TASKS["fase"] == row["fase"])]
            data_inizio = tasks_fase["data_inizio"].min()
            data_fine = tasks_fase["data_fine"].max()
            ore_totali = tasks_fase["ore_stimate"].sum()

            ordine = len([k for k in fasi_create if k[0] == pid]) + 1

            fase = Fase(
                progetto_id=pid,
                nome=fase_nome,
                ordine=ordine,
                data_inizio=data_inizio.date() if hasattr(data_inizio, "date") else data_inizio,
                data_fine=data_fine.date() if hasattr(data_fine, "date") else data_fine,
                ore_vendute=float(ore_totali),
                ore_pianificate=float(ore_totali),
                stato="In corso" if any(tasks_fase["stato"] == "In corso") else
                      "Completata" if all(tasks_fase["stato"] == "Completato") else "Da iniziare",
            )
            session.add(fase)
            session.flush()  # per avere l'id
            fasi_create[key] = fase

    print(f"  ✓ {len(fasi_create)} fasi create dai task esistenti")

    # ══════════════════════════════════════════════════════════════
    # 8. TASK (con fase_id)
    # ══════════════════════════════════════════════════════════════
    for _, row in TASKS.iterrows():
        pid = row["progetto_id"]
        fase_nome = row["fase"] if row["fase"] else "Generale"
        key = (pid, fase_nome)
        fase_obj = fasi_create.get(key)

        session.add(Task(
            id=row["id"],
            progetto_id=pid,
            fase_id=fase_obj.id if fase_obj else None,
            nome=row["nome"],
            ore_stimate=int(row["ore_stimate"]),
            # piano corrente = stima iniziale al seed; poi diverge (prereq. SAL).
            # Allineato alla migration b8c9d0e1f2a3: re-seed da zero → 0 NULL.
            ore_pianificate=float(row["ore_stimate"]),
            ore_rimanenti=float(row["ore_stimate"]),  # all'inizio rimanenti = stimate
            data_inizio=row["data_inizio"].date() if hasattr(row["data_inizio"], "date") else row["data_inizio"],
            data_fine=row["data_fine"].date() if hasattr(row["data_fine"], "date") else row["data_fine"],
            stato=row["stato"],
            profilo_richiesto=row["profilo_richiesto"],
            dipendente_id=row["dipendente_id"],
        ))
    print(f"  ✓ {len(TASKS)} task (con fase_id)")
    session.flush()  # persiste i task: la FK di dipendenza_task li richiede già presenti

    # ══════════════════════════════════════════════════════════════
    # 8-bis. DIPENDENZE TRA TASK (grafo tipizzato — Step 3.1)
    # ══════════════════════════════════════════════════════════════
    # La vecchia colonna Task.predecessore (stringa singola, sempre FS) è ora
    # una riga in dipendenza_task. Iso-comportamento: ogni predecessore non
    # vuoto diventa UNA dipendenza di tipo "FS" pred→succ.
    n_dip = 0
    for _, row in TASKS.iterrows():
        pred = row["predecessore"]
        if pred:
            session.add(DipendenzaTask(
                task_predecessore_id=pred,
                task_successore_id=row["id"],
                tipo_dipendenza="FS",
            ))
            n_dip += 1
    print(f"  ✓ {n_dip} dipendenze task (tutte FS)")

    # 8-bis (cont.) — DIPENDENZE NON-FS (Step 3.1 redesign, 03/06/2026)
    # Set realistico di SS/FF distribuite sui progetti: parallelismi (SS) e
    # co-chiusure (FF) che un PM riconosce. Date allineate nel seed.
    dipendenze_non_fs = [
        # --- SS: task che PARTONO insieme ---
        ("T005", "T006", "SS"),  # P001: coordinamento e gestione partono all'avvio
        ("T012", "T020", "SS"),  # P002: preparazione ambienti test in parallelo allo sviluppo GRC
        ("T024", "T025", "SS"),  # P003: i due sviluppi Duferco partono insieme (15/04)
        ("T032", "T034", "SS"),  # P004: configurazione framework in parallelo a identificazione rischi
        ("T041", "T042", "SS"),  # P005: sviluppo BPM in parallelo a mappatura processi
        # --- FF: task che FINISCONO insieme ---
        ("T003", "T004", "FF"),  # P001: testing chiude con l'implementazione
        ("T012", "T014", "FF"),  # P002: integrazione e piattaforma GRC chiudono insieme (31/07)
        ("T024", "T026", "FF"),  # P003: testing chiude con lo sviluppo del classificatore
        ("T042", "T043", "FF"),  # P005: collaudo ProcessBook chiude con lo sviluppo
    ]
    n_nonfs = 0
    for pred_id, succ_id, tipo in dipendenze_non_fs:
        session.add(DipendenzaTask(
            task_predecessore_id=pred_id,
            task_successore_id=succ_id,
            tipo_dipendenza=tipo,
        ))
        n_nonfs += 1
    print(f"  ✓ {n_nonfs} dipendenze task non-FS (SS/FF)")

    # ══════════════════════════════════════════════════════════════
    # 9. ASSEGNAZIONI
    # ══════════════════════════════════════════════════════════════
    for _, row in TASKS.iterrows():
        if row["dipendente_id"]:
            session.add(Assegnazione(
                task_id=row["id"],
                dipendente_id=row["dipendente_id"],
                ore_assegnate=int(row["ore_stimate"]),
                ruolo="responsabile",
            ))
    print(f"  ✓ assegnazioni create")

    # ══════════════════════════════════════════════════════════════
    # 10. CONSUNTIVI
    # ══════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════
    # 11. SEGNALAZIONI DEFAULT
    # ══════════════════════════════════════════════════════════════
    segnalazioni_default = [
        Segnalazione(
            id="S001", tipo="sovraccarico", priorita="alta",
            dipendente_id="D008", dettaglio="Fausto Garzillo: saturazione al 113%, 4 progetti attivi.",
            fonte="sistema", stato="aperta",
        ),
        Segnalazione(
            id="S002", tipo="sovraccarico", priorita="media",
            dipendente_id="D004", dettaglio="Helena Ullah: saturazione alta, gestisce testing e sviluppo su più progetti.",
            fonte="sistema", stato="aperta",
        ),
        Segnalazione(
            id="S003", tipo="richiesta_supporto", priorita="alta",
            dipendente_id="D003", dettaglio="Davide Guidi: richiede supporto per sviluppo piattaforma GRC parallelo a backend Duferco.",
            fonte="sistema", stato="aperta",
        ),
    ]
    for s in segnalazioni_default:
        session.add(s)
    print(f"  ✓ {len(segnalazioni_default)} segnalazioni default")

    # ══════════════════════════════════════════════════════════════
    # 12. UTENTI DEFAULT
    # ══════════════════════════════════════════════════════════════
    utenti_default = [
        Utente(
            email="vincenzo@imcgroup.it",
            password_hash=hash_password("admin123"),
            ruolo_app="manager",
            dipendente_id="D001",
        ),
        Utente(
            email="roberto@imcgroup.it",
            password_hash=hash_password("admin123"),
            ruolo_app="manager",
            dipendente_id="D002",
        ),
        Utente(
            email="ludovica@imcgroup.it",
            password_hash=hash_password("user123"),
            ruolo_app="manager",  # manager per sviluppo, in produzione sarà user
            dipendente_id="D011",
        ),
        Utente(
            email="helena@imcgroup.it",
            password_hash=hash_password("user123"),
            ruolo_app="user",
            dipendente_id="D004",
        ),
    ]
    for u in utenti_default:
        session.add(u)
    print(f"  ✓ {len(utenti_default)} utenti default")

    # ══════════════════════════════════════════════════════════════
    session.commit()
    session.close()
    print("\n✅ Database R1 popolato con successo!")
    print("   Nuove tabelle: ruoli, competenze, dipendenti_competenze,")
    print("   fasi_standard, fasi, utenti")


if __name__ == "__main__":
    print("Popolamento database IMC-Group R1...")
    seed()