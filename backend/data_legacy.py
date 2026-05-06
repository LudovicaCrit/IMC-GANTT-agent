"""
Dati fittizi realistici per il prototipo IMC-Group GANTT Agent.
Clienti reali, progetti GRC/compliance credibili, 15 dipendenti.

STATI PROGETTO:
- "In esecuzione"    → attivo, persone ci lavorano
- "Vinto - Da pianificare" → bando vinto, serve pianificazione
- "Sospeso"          → messo in pausa
- "Completato"       → chiuso

TIPOLOGIE PROGETTO (decisione Francesco 4 mag 2026):
- "ordinario"  → progetto commerciale standard
- "bando"      → bando con 3 fasi standard fisse (Monitoraggio + Proposal + PM)

NB: lo stato "In bando" è stato rimosso il 6 mag 2026.
Bando è una TIPOLOGIA, non uno stato. I bandi non ancora vinti hanno
stato "In esecuzione" + tipologia "bando".
"""

import pandas as pd
from datetime import datetime, timedelta
import random

# ── ANAGRAFICA DIPENDENTI ──────────────────────────────────────────────

DIPENDENTI = pd.DataFrame([
    # AD
    {"id": "D001", "nome": "Vincenzo Carolla",       "profilo": "AD",                          "ore_sett": 40, "costo_ora": 75.0, "competenze": ["strategia", "GRC", "relazioni clienti", "bandi"]},
    # Manager IT (anche PM e sviluppo)
    {"id": "D002", "nome": "Roberto Pezzuto",        "profilo": "Manager IT",                  "ore_sett": 40, "costo_ora": 55.0, "competenze": ["PM", "sviluppo", "architettura", "cloud", "gestione progetti"]},
    # Senior IT Consultant
    {"id": "D003", "nome": "Davide Guidi",           "profilo": "Senior IT Consultant",        "ore_sett": 40, "costo_ora": 48.0, "competenze": ["sviluppo", "backend", "API", "integrazione sistemi", "database"]},
    # IT Consultant
    {"id": "D004", "nome": "Helena Ullah",           "profilo": "IT Consultant",               "ore_sett": 40, "costo_ora": 30.0, "competenze": ["sviluppo", "python", "AI/ML", "testing"]},
    # Senior Consultant (anche PM)
    {"id": "D005", "nome": "Andrea Morstabilini",    "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 50.0, "competenze": ["PM", "GRC", "compliance", "bandi", "gestione progetti"]},
    {"id": "D006", "nome": "Paolo Di Prizio",        "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 50.0, "competenze": ["PM", "risk management", "processi", "gestione progetti"]},
    {"id": "D007", "nome": "Carolina Coccorese",     "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 48.0, "competenze": ["PM", "compliance", "coordinamento", "gestione progetti"]},
    {"id": "D008", "nome": "Fausto Garzillo",        "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 45.0, "competenze": ["GRC", "processi", "ARIS", "relazioni clienti"]},
    # Consultant
    {"id": "D009", "nome": "Tetiana Matveichuk",     "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 35.0, "competenze": ["coordinamento", "relazioni clienti", "documentazione"]},
    {"id": "D010", "nome": "Nicola Coccorese",       "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 35.0, "competenze": ["GRC", "analisi", "relazioni clienti"]},
    {"id": "D011", "nome": "Ludovica Di Cianni",     "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 25.0, "competenze": ["IA", "python", "backend", "sviluppo"]},
    # Manager HR
    {"id": "D012", "nome": "Cosimo Pacifico",        "profilo": "Manager HR",                  "ore_sett": 40, "costo_ora": 40.0, "competenze": ["risorse umane", "formazione", "organizzazione", "contratti"]},
    # Responsabile amministrazione
    {"id": "D013", "nome": "Francesco Carolla",      "profilo": "Responsabile amministrazione","ore_sett": 40, "costo_ora": 42.0, "competenze": ["amministrazione", "rendicontazione", "fatturazione", "controllo gestione"]},
    # Addetto amministrazione
    {"id": "D014", "nome": "Carolina Jori",          "profilo": "Addetto amministrazione",     "ore_sett": 20, "costo_ora": 28.0, "competenze": ["amministrazione", "documentazione", "archivio"]},
    {"id": "D015", "nome": "Daniele Tagliabue",      "profilo": "Addetto amministrazione",     "ore_sett": 40, "costo_ora": 30.0, "competenze": ["amministrazione", "rendicontazione", "fatturazione"]},
])

# ── PROGETTI ───────────────────────────────────────────────────────────

PROGETTI = pd.DataFrame([
    # ═══ 5 IN ESECUZIONE ═══
    {
        "id": "P001",
        "nome": "Adeguamento DORA",
        "cliente": "Sparkasse",
        "stato": "In esecuzione",
        "tipologia": "ordinario",
        "data_inizio": datetime(2025, 9, 1),
        "data_fine": datetime(2026, 6, 30),
        "budget_ore": 2200,
        "valore_contratto": 195000.0,
        "descrizione": "Adeguamento al regolamento DORA sulla resilienza operativa digitale. Gap analysis, remediation plan, implementazione framework ICT risk.",
        "fase_corrente": "Implementazione",
    },
    {
        "id": "P002",
        "nome": "Framework Compliance 262",
        "cliente": "Reale Mutua",
        "stato": "In esecuzione",
        "tipologia": "ordinario",
        "data_inizio": datetime(2025, 11, 1),
        "data_fine": datetime(2026, 10, 31),
        "budget_ore": 2800,
        "valore_contratto": 240000.0,
        "descrizione": "Digitalizzazione del framework di compliance L.262. Mappatura controlli, flussi certificativi, piattaforma GRC integrata.",
        "fase_corrente": "Sviluppo piattaforma",
    },
    {
        "id": "P003",
        "nome": "Digitalizzazione Corpo Normativo",
        "cliente": "Duferco Energia",
        "stato": "In esecuzione",
        "tipologia": "ordinario",
        "data_inizio": datetime(2026, 1, 15),
        "data_fine": datetime(2026, 9, 30),
        "budget_ore": 1600,
        "valore_contratto": 145000.0,
        "descrizione": "Digitalizzazione e gestione del corpo normativo aziendale. Piattaforma AI per classificazione norme, impatto su processi e funzioni di controllo.",
        "fase_corrente": "Design",
    },
    {
        "id": "P004",
        "nome": "Risk Assessment Operativo",
        "cliente": "BNP Paribas",
        "stato": "In esecuzione",
        "tipologia": "ordinario",
        "data_inizio": datetime(2025, 10, 1),
        "data_fine": datetime(2026, 5, 31),
        "budget_ore": 1400,
        "valore_contratto": 130000.0,
        "descrizione": "Assessment dei rischi operativi e definizione del framework di gestione. Mappatura processi, identificazione rischi, piano di mitigazione.",
        "fase_corrente": "Assessment",
    },
    {
        "id": "P005",
        "nome": "ProcessBook Aziendale",
        "cliente": "Boggi Milano",
        "stato": "In esecuzione",
        "tipologia": "ordinario",
        "data_inizio": datetime(2025, 12, 1),
        "data_fine": datetime(2026, 7, 31),
        "budget_ore": 1200,
        "valore_contratto": 105000.0,
        "descrizione": "Realizzazione del ProcessBook aziendale: mappatura processi, ownership, KPI, procedure operative. Piattaforma BPM customizzata.",
        "fase_corrente": "Mappatura processi",
    },

    # ═══ 1 SOSPESO ═══
    {
        "id": "P006",
        "nome": "Piattaforma Antiriciclaggio",
        "cliente": "Banca Popolare di Bari",
        "stato": "Sospeso",
        "tipologia": "ordinario",
        "data_inizio": datetime(2025, 7, 1),
        "data_fine": datetime(2026, 3, 31),
        "budget_ore": 1800,
        "valore_contratto": 160000.0,
        "descrizione": "Piattaforma RISKAML per gestione antiriciclaggio con algoritmi AI. Sospeso per riorganizzazione interna del cliente.",
        "fase_corrente": "Sospeso — era in fase Sviluppo",
    },

    # ═══ 1 VINTO DA PIANIFICARE ═══
    {
        "id": "P007",
        "nome": "Framework ESG Reporting",
        "cliente": "A2A",
        "stato": "Vinto - Da pianificare",
        "tipologia": "ordinario",
        "data_inizio": datetime(2026, 5, 1),
        "data_fine": datetime(2026, 11, 30),
        "budget_ore": 1000,
        "valore_contratto": 90000.0,
        "descrizione": "Framework per il reporting ESG integrato. Raccolta dati, calcolo KPI sostenibilità, dashboard direzionale, report normativo.",
        "fase_corrente": "Pianificazione",
    },

    # ═══ 2 IN BANDO ═══
    {
        "id": "P008",
        "nome": "Business Continuity Framework",
        "cliente": "ITAS Assicurazioni",
        "stato": "In esecuzione",
        "tipologia": "bando",
        "data_inizio": datetime(2026, 7, 1),
        "data_fine": datetime(2027, 3, 31),
        "budget_ore": 1800,
        "valore_contratto": 155000.0,
        "descrizione": "Framework di Business Continuity Management. BIA, piani di continuità, testing, piattaforma di gestione. Scadenza bando: 15/04/2026.",
        "fase_corrente": "Preparazione bando",
    },
    {
        "id": "P009",
        "nome": "GRC Platform Integration",
        "cliente": "Banco Desio",
        "stato": "In esecuzione",
        "tipologia": "bando",
        "data_inizio": datetime(2026, 6, 1),
        "data_fine": datetime(2027, 1, 31),
        "budget_ore": 1500,
        "valore_contratto": 135000.0,
        "descrizione": "Integrazione piattaforma GRC con sistemi interni della banca. Compliance, risk management, audit trail. Scadenza bando: 30/04/2026.",
        "fase_corrente": "Preparazione bando",
    },

    # ═══ ATTIVITÀ INTERNE (non fatturabile) ═══
    {
        "id": "P010",
        "nome": "Attività Interne",
        "cliente": "IMC-Group",
        "stato": "In esecuzione",
        "tipologia": "ordinario",
        "data_inizio": datetime(2025, 1, 1),
        "data_fine": datetime(2026, 12, 31),
        "budget_ore": 8000,
        "valore_contratto": 0,
        "descrizione": "Attività non a progetto: strategia, formazione, amministrazione, riunioni interne, HR, coordinamento.",
        "fase_corrente": "Continuativa",
    },
])

# ── TASK (WBS) ─────────────────────────────────────────────────────────

TASKS = pd.DataFrame([
    # ══════════════════════════════════════════════════════════════════
    # P001: Adeguamento DORA — Sparkasse (in esecuzione — fase Implementazione)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T001", "progetto_id": "P001", "nome": "Gap analysis DORA",                  "fase": "Analisi",        "ore_stimate": 160, "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2025, 11, 15), "stato": "Completato",  "profilo_richiesto": "Senior IT Consultant",  "dipendente_id": "D003", "predecessore": None},
    {"id": "T002", "progetto_id": "P001", "nome": "Remediation plan ICT risk",          "fase": "Design",         "ore_stimate": 120, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 1, 15),  "stato": "Completato",  "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": "T001"},
    {"id": "T003", "progetto_id": "P001", "nome": "Implementazione framework ICT",      "fase": "Sviluppo",       "ore_stimate": 280, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 5, 15),  "stato": "In corso",    "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": "T002"},
    {"id": "T004", "progetto_id": "P001", "nome": "Testing e validazione DORA",         "fase": "Testing",        "ore_stimate": 120, "data_inizio": datetime(2026, 4, 15),  "data_fine": datetime(2026, 6, 15),  "stato": "Da iniziare", "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": "T003"},
    {"id": "T005", "progetto_id": "P001", "nome": "Coordinamento cliente Sparkasse",    "fase": "Gestione",       "ore_stimate": 100, "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D007", "predecessore": None},
    {"id": "T006", "progetto_id": "P001", "nome": "Gestione progetto DORA",             "fase": "Gestione",       "ore_stimate": 140, "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "PM",                    "dipendente_id": "D005", "predecessore": None},
    {"id": "T007", "progetto_id": "P001", "nome": "Rendicontazione DORA",               "fase": "Amministrazione","ore_stimate": 50,  "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D015", "predecessore": None},
    {"id": "T008", "progetto_id": "P001", "nome": "Configurazione processi DORA",       "fase": "Sviluppo",       "ore_stimate": 80,  "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 4, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D008", "predecessore": "T002"},

    # ══════════════════════════════════════════════════════════════════
    # P002: Framework Compliance 262 — Reale Mutua (in esecuzione)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T009", "progetto_id": "P002", "nome": "Analisi requisiti compliance 262",   "fase": "Analisi",        "ore_stimate": 140, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 1, 31),  "stato": "Completato",  "profilo_richiesto": "PM",                    "dipendente_id": "D006", "predecessore": None},
    {"id": "T010", "progetto_id": "P002", "nome": "Mappatura controlli L.262",          "fase": "Analisi",        "ore_stimate": 200, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 4, 15),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D008", "predecessore": "T009"},
    {"id": "T011", "progetto_id": "P002", "nome": "Sviluppo piattaforma GRC",          "fase": "Sviluppo",       "ore_stimate": 350, "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 7, 31),  "stato": "In corso",    "profilo_richiesto": "Senior IT Consultant",  "dipendente_id": "D003", "predecessore": "T009"},
    {"id": "T012", "progetto_id": "P002", "nome": "Modulo certificazione flussi",       "fase": "Sviluppo",       "ore_stimate": 180, "data_inizio": datetime(2026, 5, 1),   "data_fine": datetime(2026, 8, 31),  "stato": "Da iniziare", "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": "T011"},
    {"id": "T013", "progetto_id": "P002", "nome": "Integrazione sistemi Reale Mutua",   "fase": "Sviluppo",       "ore_stimate": 160, "data_inizio": datetime(2026, 4, 1),   "data_fine": datetime(2026, 7, 31),  "stato": "Da iniziare", "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": "T011"},
    {"id": "T014", "progetto_id": "P002", "nome": "Testing e UAT compliance",           "fase": "Testing",        "ore_stimate": 150, "data_inizio": datetime(2026, 8, 1),   "data_fine": datetime(2026, 10, 15), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": "T012"},
    {"id": "T015", "progetto_id": "P002", "nome": "Coordinamento Reale Mutua",          "fase": "Gestione",       "ore_stimate": 120, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 10, 31), "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D009", "predecessore": None},
    {"id": "T016", "progetto_id": "P002", "nome": "Gestione progetto Compliance 262",   "fase": "Gestione",       "ore_stimate": 180, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 10, 31), "stato": "In corso",    "profilo_richiesto": "PM",                    "dipendente_id": "D006", "predecessore": None},
    {"id": "T017", "progetto_id": "P002", "nome": "Rendicontazione Compliance 262",     "fase": "Amministrazione","ore_stimate": 60,  "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 10, 31), "stato": "In corso",    "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D015", "predecessore": None},
    {"id": "T018", "progetto_id": "P002", "nome": "Demo intermedia Reale Mutua",        "fase": "Vendita",        "ore_stimate": 24,  "data_inizio": datetime(2026, 6, 1),   "data_fine": datetime(2026, 6, 15),  "stato": "Da iniziare", "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D005", "predecessore": "T011"},

    # ══════════════════════════════════════════════════════════════════
    # P003: Digitalizzazione Corpo Normativo — Duferco Energia (in esecuzione)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T019", "progetto_id": "P003", "nome": "Analisi corpo normativo Duferco",    "fase": "Analisi",        "ore_stimate": 100, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 3, 15),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D010", "predecessore": None},
    {"id": "T020", "progetto_id": "P003", "nome": "Design piattaforma normativa AI",    "fase": "Design",         "ore_stimate": 120, "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 4, 30),  "stato": "Da iniziare", "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": "T019"},
    {"id": "T021", "progetto_id": "P003", "nome": "Sviluppo classificatore AI norme",   "fase": "Sviluppo",       "ore_stimate": 250, "data_inizio": datetime(2026, 4, 15),  "data_fine": datetime(2026, 7, 31),  "stato": "Da iniziare", "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": "T020"},
    {"id": "T022", "progetto_id": "P003", "nome": "Sviluppo backend piattaforma",       "fase": "Sviluppo",       "ore_stimate": 200, "data_inizio": datetime(2026, 4, 15),  "data_fine": datetime(2026, 7, 15),  "stato": "Da iniziare", "profilo_richiesto": "Senior IT Consultant",  "dipendente_id": "D003", "predecessore": "T020"},
    {"id": "T023", "progetto_id": "P003", "nome": "Testing piattaforma normativa",      "fase": "Testing",        "ore_stimate": 80,  "data_inizio": datetime(2026, 7, 15),  "data_fine": datetime(2026, 9, 15),  "stato": "Da iniziare", "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": "T022"},
    {"id": "T024", "progetto_id": "P003", "nome": "Coordinamento Duferco",              "fase": "Gestione",       "ore_stimate": 80,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 9, 30),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D009", "predecessore": None},
    {"id": "T025", "progetto_id": "P003", "nome": "Gestione progetto Duferco",          "fase": "Gestione",       "ore_stimate": 100, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 9, 30),  "stato": "In corso",    "profilo_richiesto": "PM",                    "dipendente_id": "D007", "predecessore": None},
    {"id": "T026", "progetto_id": "P003", "nome": "Rendicontazione Duferco",            "fase": "Amministrazione","ore_stimate": 40,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 9, 30),  "stato": "In corso",    "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D014", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P004: Risk Assessment Operativo — BNP Paribas (in esecuzione)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T027", "progetto_id": "P004", "nome": "Mappatura processi operativi BNP",   "fase": "Analisi",        "ore_stimate": 180, "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 1, 31),  "stato": "Completato",  "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D008", "predecessore": None},
    {"id": "T028", "progetto_id": "P004", "nome": "Identificazione e scoring rischi",   "fase": "Analisi",        "ore_stimate": 160, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 3, 31),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D006", "predecessore": "T027"},
    {"id": "T029", "progetto_id": "P004", "nome": "Piano mitigazione rischi",           "fase": "Design",         "ore_stimate": 120, "data_inizio": datetime(2026, 3, 15),  "data_fine": datetime(2026, 5, 15),  "stato": "Da iniziare", "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D006", "predecessore": "T028"},
    {"id": "T030", "progetto_id": "P004", "nome": "Configurazione risk framework",      "fase": "Sviluppo",       "ore_stimate": 100, "data_inizio": datetime(2026, 2, 15),  "data_fine": datetime(2026, 4, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D008", "predecessore": "T027"},
    {"id": "T031", "progetto_id": "P004", "nome": "Coordinamento BNP Paribas",          "fase": "Gestione",       "ore_stimate": 80,  "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D010", "predecessore": None},
    {"id": "T032", "progetto_id": "P004", "nome": "Gestione progetto BNP",              "fase": "Gestione",       "ore_stimate": 100, "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "PM",                    "dipendente_id": "D005", "predecessore": None},
    {"id": "T033", "progetto_id": "P004", "nome": "Rendicontazione BNP",                "fase": "Amministrazione","ore_stimate": 40,  "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D015", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P005: ProcessBook Aziendale — Boggi Milano (in esecuzione)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T034", "progetto_id": "P005", "nome": "Interviste e raccolta processi",     "fase": "Analisi",        "ore_stimate": 120, "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 2, 15),  "stato": "Completato",  "profilo_richiesto": "Consultant",            "dipendente_id": "D009", "predecessore": None},
    {"id": "T035", "progetto_id": "P005", "nome": "Mappatura processi",                 "fase": "Sviluppo",       "ore_stimate": 200, "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D008", "predecessore": "T034"},
    {"id": "T036", "progetto_id": "P005", "nome": "Sviluppo piattaforma BPM",           "fase": "Sviluppo",       "ore_stimate": 180, "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior IT Consultant",  "dipendente_id": "D003", "predecessore": "T034"},
    {"id": "T037", "progetto_id": "P005", "nome": "Testing ProcessBook",                "fase": "Testing",        "ore_stimate": 80,  "data_inizio": datetime(2026, 6, 15),  "data_fine": datetime(2026, 7, 31),  "stato": "Da iniziare", "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": "T036"},
    {"id": "T038", "progetto_id": "P005", "nome": "Coordinamento Boggi",                "fase": "Gestione",       "ore_stimate": 60,  "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 7, 31),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D010", "predecessore": None},
    {"id": "T039", "progetto_id": "P005", "nome": "Gestione progetto Boggi",            "fase": "Gestione",       "ore_stimate": 80,  "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 7, 31),  "stato": "In corso",    "profilo_richiesto": "PM",                    "dipendente_id": "D007", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P006: Piattaforma Antiriciclaggio — Banca Pop. Bari (SOSPESO)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T040", "progetto_id": "P006", "nome": "Analisi requisiti AML",              "fase": "Analisi",        "ore_stimate": 100, "data_inizio": datetime(2025, 7, 1),   "data_fine": datetime(2025, 9, 30),  "stato": "Completato",  "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": None},
    {"id": "T041", "progetto_id": "P006", "nome": "Sviluppo algoritmi AI AML",          "fase": "Sviluppo",       "ore_stimate": 300, "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 2, 28),  "stato": "Sospeso",     "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": "T040"},
    {"id": "T042", "progetto_id": "P006", "nome": "Gestione progetto AML",              "fase": "Gestione",       "ore_stimate": 60,  "data_inizio": datetime(2025, 7, 1),   "data_fine": datetime(2026, 3, 31),  "stato": "Sospeso",     "profilo_richiesto": "PM",                    "dipendente_id": "D005", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P008 e P009: BANDI
    # ══════════════════════════════════════════════════════════════════
    {"id": "T043", "progetto_id": "P008", "nome": "Proposta tecnica Business Continuity","fase": "Bando",         "ore_stimate": 60,  "data_inizio": datetime(2026, 2, 15),  "data_fine": datetime(2026, 4, 10),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D005", "predecessore": None},
    {"id": "T044", "progetto_id": "P008", "nome": "Stima costi ITAS",                   "fase": "Bando",          "ore_stimate": 30,  "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 4, 10),  "stato": "In corso",    "profilo_richiesto": "PM",                    "dipendente_id": "D006", "predecessore": None},
    {"id": "T045", "progetto_id": "P008", "nome": "Documentazione bando ITAS",          "fase": "Bando",          "ore_stimate": 20,  "data_inizio": datetime(2026, 3, 15),  "data_fine": datetime(2026, 4, 10),  "stato": "Da iniziare", "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D015", "predecessore": None},

    {"id": "T046", "progetto_id": "P009", "nome": "Proposta GRC Platform Banco Desio",  "fase": "Bando",          "ore_stimate": 50,  "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 4, 25),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D005", "predecessore": None},
    {"id": "T047", "progetto_id": "P009", "nome": "Stima costi Banco Desio",            "fase": "Bando",          "ore_stimate": 25,  "data_inizio": datetime(2026, 3, 15),  "data_fine": datetime(2026, 4, 25),  "stato": "Da iniziare", "profilo_richiesto": "PM",                    "dipendente_id": "D006", "predecessore": None},
    {"id": "T048", "progetto_id": "P009", "nome": "Documentazione bando Banco Desio",   "fase": "Bando",          "ore_stimate": 20,  "data_inizio": datetime(2026, 3, 20),  "data_fine": datetime(2026, 4, 25),  "stato": "Da iniziare", "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D014", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # TASK TRASVERSALI
    # ══════════════════════════════════════════════════════════════════
    {"id": "T049", "progetto_id": "P004", "nome": "Supporto analisi BNP",                 "fase": "Gestione",       "ore_stimate": 60,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D009", "predecessore": None},
    {"id": "T050", "progetto_id": "P005", "nome": "Interviste processi Boggi",            "fase": "Analisi",        "ore_stimate": 40,  "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 4, 30),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D009", "predecessore": None},

    {"id": "T051", "progetto_id": "P002", "nome": "Preparazione ambienti test Compliance","fase": "Sviluppo",       "ore_stimate": 80,  "data_inizio": datetime(2026, 2, 15),  "data_fine": datetime(2026, 4, 15),  "stato": "In corso",    "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": None},
    {"id": "T052", "progetto_id": "P003", "nome": "Prototipo classificatore norme",       "fase": "Sviluppo",       "ore_stimate": 60,  "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 4, 30),  "stato": "In corso",    "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P010: ATTIVITÀ INTERNE
    # ══════════════════════════════════════════════════════════════════
    # Vincenzo Carolla (AD)
    {"id": "T053", "progetto_id": "P010", "nome": "Strategia e relazioni clienti",        "fase": "Gestione",       "ore_stimate": 1400, "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "AD",                    "dipendente_id": "D001", "predecessore": None},
    {"id": "T054", "progetto_id": "P010", "nome": "Review bandi e proposte",              "fase": "Vendita",        "ore_stimate": 200,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "AD",                    "dipendente_id": "D001", "predecessore": None},

    # Cosimo Pacifico (Manager HR)
    {"id": "T055", "progetto_id": "P010", "nome": "Gestione presenze e contratti",        "fase": "Gestione",       "ore_stimate": 860,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Manager HR",            "dipendente_id": "D012", "predecessore": None},
    {"id": "T056", "progetto_id": "P010", "nome": "Formazione e onboarding",              "fase": "Gestione",       "ore_stimate": 430,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Manager HR",            "dipendente_id": "D012", "predecessore": None},
    {"id": "T057", "progetto_id": "P010", "nome": "Selezione e recruiting",               "fase": "Gestione",       "ore_stimate": 430,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Manager HR",            "dipendente_id": "D012", "predecessore": None},

    # Responsabile amministrazione
    {"id": "T058", "progetto_id": "P010", "nome": "Controllo gestione e reporting",       "fase": "Amministrazione","ore_stimate": 1200, "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Responsabile amministrazione","dipendente_id": "D013", "predecessore": None},

    # Daniele Tagliabue (Addetto amministrazione)
    {"id": "T059", "progetto_id": "P010", "nome": "Amministrazione corrente e fatturazione","fase": "Amministrazione","ore_stimate": 1000, "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D015", "predecessore": None},

    # Carolina Jori (Addetto amministrazione part-time 20h)
    {"id": "T060", "progetto_id": "P010", "nome": "Documentazione e archivio",            "fase": "Amministrazione","ore_stimate": 400,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Addetto amministrazione","dipendente_id": "D014", "predecessore": None},

    # Andrea Morstabilini (Senior Consultant/PM)
    {"id": "T061", "progetto_id": "P010", "nome": "Scouting bandi e networking",          "fase": "Vendita",        "ore_stimate": 500,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D005", "predecessore": None},

    # Tetiana Matveichuk (Consultant)
    {"id": "T062", "progetto_id": "P010", "nome": "Coordinamento e supporto interno",     "fase": "Gestione",       "ore_stimate": 500,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D009", "predecessore": None},

    # Helena Ullah (IT Consultant)
    {"id": "T063", "progetto_id": "P010", "nome": "Formazione tecnica e autoapprendimento","fase": "Gestione",      "ore_stimate": 500,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "IT Consultant",         "dipendente_id": "D004", "predecessore": None},

    # Nicola Coccorese (Consultant)
    {"id": "T064", "progetto_id": "P010", "nome": "Supporto analisi e documentazione",    "fase": "Gestione",       "ore_stimate": 600,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D010", "predecessore": None},

    # Ludovica Di Cianni (Consultant - stage IA)
    {"id": "T065", "progetto_id": "P010", "nome": "Sviluppo GANTT Agent e progetti IA",   "fase": "Sviluppo",       "ore_stimate": 700,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Consultant",            "dipendente_id": "D011", "predecessore": None},

    # Roberto Pezzuto (Manager IT)
    {"id": "T066", "progetto_id": "P010", "nome": "Architettura e aggiornamento tecnico",  "fase": "Gestione",       "ore_stimate": 200,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Manager IT",            "dipendente_id": "D002", "predecessore": None},

    # Davide Guidi (Senior IT Consultant)
    {"id": "T067", "progetto_id": "P010", "nome": "Formazione interna e knowledge sharing","fase": "Gestione",      "ore_stimate": 86,   "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior IT Consultant",  "dipendente_id": "D003", "predecessore": None},

    # Fausto Garzillo (Senior Consultant)
    {"id": "T068", "progetto_id": "P010", "nome": "Aggiornamento metodologie e formazione","fase": "Gestione",       "ore_stimate": 86,   "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D008", "predecessore": None},

    # Carolina Coccorese (Senior Consultant/PM)
    {"id": "T069", "progetto_id": "P010", "nome": "Coordinamento interno e riunioni",      "fase": "Gestione",       "ore_stimate": 400,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D007", "predecessore": None},

    # Paolo Di Prizio (Senior Consultant/PM)
    {"id": "T070", "progetto_id": "P010", "nome": "Analisi rischi e compliance interna",   "fase": "Gestione",       "ore_stimate": 300,  "data_inizio": datetime(2025, 9, 1),  "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Senior Consultant",     "dipendente_id": "D006", "predecessore": None},
])

TASKS = TASKS.fillna({"predecessore": ""})

# ── CONSUNTIVI (ore effettivamente lavorate) ───────────────────────────

def genera_consuntivi():
    """Genera consuntivi settimanali realistici con buchi."""
    records = []
    oggi = datetime.now()

    for _, task in TASKS.iterrows():
        if task["stato"] in ["Completato", "In corso"]:
            inizio = task["data_inizio"]
            fine = min(task["data_fine"], oggi)

            settimana = inizio
            while settimana <= fine:
                lun = settimana - timedelta(days=settimana.weekday())

                compilato = random.random() > 0.15

                if compilato:
                    ore = random.choice([4, 4, 6, 8, 8, 8, 12, 16, 16, 20, 24])
                    records.append({
                        "task_id": task["id"],
                        "dipendente_id": task["dipendente_id"],
                        "settimana": lun,
                        "ore_dichiarate": ore,
                        "compilato": True,
                        "data_compilazione": lun + timedelta(days=random.choice([4, 5, 6, 7, 8, 9, 12])),
                        "nota": random.choice([
                            "", "", "", "", "",
                            "Attesa feedback dal cliente",
                            "Ritardo per approvazione interna",
                            "Lavoro extra per change request",
                            "Call di allineamento non prevista",
                            "Supporto a collega su altro progetto",
                            "Attesa documentazione dal cliente",
                        ]),
                    })
                else:
                    records.append({
                        "task_id": task["id"],
                        "dipendente_id": task["dipendente_id"],
                        "settimana": lun,
                        "ore_dichiarate": 0,
                        "compilato": False,
                        "data_compilazione": None,
                        "nota": "",
                    })

                settimana += timedelta(weeks=1)

    return pd.DataFrame(records)

random.seed(42)
CONSUNTIVI = genera_consuntivi()

# ── HELPER FUNCTIONS ───────────────────────────────────────────────────

def get_dipendente(did):
    if not did or did == "":
        return pd.Series({"id": "", "nome": "Non assegnato", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []})
    matches = DIPENDENTI[DIPENDENTI["id"] == did]
    if len(matches) == 0:
        return pd.Series({"id": did, "nome": f"Sconosciuto ({did})", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []})
    return matches.iloc[0]

def get_progetto(pid):
    if not pid or pid == "":
        return pd.Series({"id": "", "nome": "Sconosciuto", "cliente": "", "stato": ""})
    matches = PROGETTI[PROGETTI["id"] == pid]
    if len(matches) == 0:
        return pd.Series({"id": pid, "nome": f"Sconosciuto ({pid})", "cliente": "", "stato": ""})
    return matches.iloc[0]

def get_tasks_progetto(pid):
    return TASKS[TASKS["progetto_id"] == pid].copy()

def get_consuntivi_task(tid):
    return CONSUNTIVI[CONSUNTIVI["task_id"] == tid].copy()

def get_consuntivi_dipendente(did):
    return CONSUNTIVI[CONSUNTIVI["dipendente_id"] == did].copy()

def ore_consuntivate_progetto(pid):
    task_ids = TASKS[TASKS["progetto_id"] == pid]["id"].tolist()
    cons = CONSUNTIVI[CONSUNTIVI["task_id"].isin(task_ids)]
    return cons["ore_dichiarate"].sum()

def tasso_compilazione_progetto(pid):
    task_ids = TASKS[TASKS["progetto_id"] == pid]["id"].tolist()
    cons = CONSUNTIVI[CONSUNTIVI["task_id"].isin(task_ids)]
    if len(cons) == 0:
        return 0
    return cons["compilato"].sum() / len(cons) * 100

def carico_settimanale_dipendente(did, settimana):
    """Calcola le ore totali assegnate a un dipendente in una data settimana."""
    lun = settimana - timedelta(days=settimana.weekday())
    tasks_dip = TASKS[
        (TASKS["dipendente_id"] == did) &
        (~TASKS["stato"].isin(["Completato", "Sospeso"]))
    ]
    ore = 0
    for _, t in tasks_dip.iterrows():
        if t["data_inizio"] <= lun + timedelta(days=4) and t["data_fine"] >= lun:
            weeks = max(1, (t["data_fine"] - t["data_inizio"]).days / 7)
            ore += t["ore_stimate"] / weeks
    return round(ore, 1)

def get_progetti_dipendente(did):
    """Restituisce i nomi dei progetti su cui un dipendente è attivo."""
    task_dip = TASKS[
        (TASKS["dipendente_id"] == did) &
        (TASKS["stato"].isin(["In corso", "Da iniziare"]))
    ]
    proj_ids = task_dip["progetto_id"].unique()
    return [PROGETTI[PROGETTI["id"] == pid].iloc[0]["nome"] for pid in proj_ids]


# ── FUNZIONI DI MODIFICA DATI ─────────────────────────────────────────

def _next_task_id():
    existing = TASKS["id"].tolist()
    nums = [int(tid[1:]) for tid in existing if tid.startswith("T") and tid[1:].isdigit()]
    return f"T{max(nums) + 1:03d}" if nums else "T001"


def _next_progetto_id():
    existing = PROGETTI["id"].tolist()
    nums = [int(pid[1:]) for pid in existing if pid.startswith("P") and pid[1:].isdigit()]
    return f"P{max(nums) + 1:03d}" if nums else "P001"


def aggiungi_task(progetto_id, nome, fase, ore_stimate, data_inizio, data_fine,
                  stato="Da iniziare", profilo_richiesto="", dipendente_id="",
                  predecessore=""):
    global TASKS
    new_id = _next_task_id()
    new_row = pd.DataFrame([{
        "id": new_id, "progetto_id": progetto_id, "nome": nome, "fase": fase,
        "ore_stimate": ore_stimate, "data_inizio": data_inizio, "data_fine": data_fine,
        "stato": stato, "profilo_richiesto": profilo_richiesto,
        "dipendente_id": dipendente_id, "predecessore": predecessore,
    }])
    TASKS = pd.concat([TASKS, new_row], ignore_index=True)
    return new_id


def modifica_task(task_id, **kwargs):
    global TASKS
    idx = TASKS.index[TASKS["id"] == task_id]
    if len(idx) == 0:
        return False
    for campo, valore in kwargs.items():
        if campo in TASKS.columns:
            TASKS.loc[idx, campo] = valore
    return True


def cambia_stato_progetto(progetto_id, nuovo_stato):
    global PROGETTI
    idx = PROGETTI.index[PROGETTI["id"] == progetto_id]
    if len(idx) == 0:
        return False
    PROGETTI.loc[idx, "stato"] = nuovo_stato
    return True


def calcola_impatto_saturazione(task_modifiche, task_nuovi=None):
    tasks_sim = TASKS.copy()
    for mod in (task_modifiche or []):
        idx = tasks_sim.index[tasks_sim["id"] == mod["task_id"]]
        if len(idx) > 0 and mod["campo"] in tasks_sim.columns:
            tasks_sim.loc[idx, mod["campo"]] = mod["nuovo_valore"]
    if task_nuovi:
        for nt in task_nuovi:
            tasks_sim = pd.concat([tasks_sim, pd.DataFrame([nt])], ignore_index=True)

    dipendenti_coinvolti = set()
    for mod in (task_modifiche or []):
        tr = TASKS[TASKS["id"] == mod["task_id"]]
        if len(tr) > 0:
            dipendenti_coinvolti.add(tr.iloc[0]["dipendente_id"])
            if mod["campo"] == "dipendente_id":
                dipendenti_coinvolti.add(mod["nuovo_valore"])
    for nt in (task_nuovi or []):
        if nt.get("dipendente_id"):
            dipendenti_coinvolti.add(nt["dipendente_id"])

    oggi = datetime.now()
    risultati_dip = []
    for did in dipendenti_coinvolti:
        if not did:
            continue
        try:
            dip = get_dipendente(did)
        except (IndexError, KeyError):
            continue
        carico_prima = carico_settimanale_dipendente(did, oggi)
        sat_prima = round(carico_prima / dip["ore_sett"] * 100)
        tasks_dip_sim = tasks_sim[
            (tasks_sim["dipendente_id"] == did) &
            (~tasks_sim["stato"].isin(["Completato", "Sospeso"]))
        ]
        lun = oggi - timedelta(days=oggi.weekday())
        carico_dopo = 0
        for _, t in tasks_dip_sim.iterrows():
            if t["data_inizio"] <= lun + timedelta(days=4) and t["data_fine"] >= lun:
                weeks = max(1, (t["data_fine"] - t["data_inizio"]).days / 7)
                carico_dopo += t["ore_stimate"] / weeks
        carico_dopo = round(carico_dopo, 1)
        sat_dopo = round(carico_dopo / dip["ore_sett"] * 100)
        risultati_dip.append({
            "id": did, "nome": dip["nome"], "profilo": dip["profilo"],
            "saturazione_prima": sat_prima, "saturazione_dopo": sat_dopo,
            "delta": sat_dopo - sat_prima, "ore_sett": int(dip["ore_sett"]),
        })

    progetti_ids = set()
    for mod in (task_modifiche or []):
        tr = TASKS[TASKS["id"] == mod["task_id"]]
        if len(tr) > 0:
            progetti_ids.add(tr.iloc[0]["progetto_id"])
    for nt in (task_nuovi or []):
        if nt.get("progetto_id"):
            progetti_ids.add(nt["progetto_id"])

    progetti_impattati = []
    for pid in progetti_ids:
        try:
            proj = get_progetto(pid)
            progetti_impattati.append({"id": pid, "nome": proj["nome"]})
        except (IndexError, KeyError):
            pass

    alert = []
    for r in risultati_dip:
        if r["saturazione_dopo"] > 100 and r["saturazione_prima"] <= 100:
            alert.append(f"{r['nome']} passerebbe dal {r['saturazione_prima']}% al {r['saturazione_dopo']}% — sovraccarico!")
        elif r["saturazione_dopo"] > 100 and r["delta"] > 0:
            alert.append(f"{r['nome']} è già al {r['saturazione_prima']}% e salirebbe al {r['saturazione_dopo']}%")

    return {"dipendenti_impattati": risultati_dip, "progetti_impattati": progetti_impattati, "alert": alert}