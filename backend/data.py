"""
Dati fittizi realistici per il prototipo IMC-Group GANTT Agent.
9 progetti con ciclo di vita completo, 8 dipendenti, pressione realistica.

STATI PROGETTO:
- "In bando"         → si lavora per vincerlo (stesura proposta, stima ore/costi)
- "Vinto - Da pianificare" → bando vinto, serve time-sheet e staffing
- "In esecuzione"    → attivo, persone ci lavorano, si consuntiva
- "Sospeso"          → era attivo, messo in pausa, risorse liberate
- "Completato"       → chiuso
"""

import pandas as pd
from datetime import datetime, timedelta
import random

# ── ANAGRAFICA DIPENDENTI ──────────────────────────────────────────────

DIPENDENTI = pd.DataFrame([
    {"id": "D001", "nome": "Marco Bianchi",     "profilo": "Tecnico Senior",       "ore_sett": 40, "costo_ora": 45.0, "competenze": ["sviluppo", "architettura", "cloud"]},
    {"id": "D002", "nome": "Laura Verdi",       "profilo": "Tecnico Junior",       "ore_sett": 40, "costo_ora": 28.0, "competenze": ["sviluppo", "testing", "documentazione"]},
    {"id": "D003", "nome": "Giuseppe Russo",    "profilo": "Project Manager",      "ore_sett": 40, "costo_ora": 50.0, "competenze": ["gestione", "bandi", "rendicontazione"]},
    {"id": "D004", "nome": "Francesca Marino",  "profilo": "Amministrativo",       "ore_sett": 40, "costo_ora": 30.0, "competenze": ["amministrazione", "bandi", "rendicontazione"]},
    {"id": "D005", "nome": "Alessandro Conte",  "profilo": "Tecnico Senior",       "ore_sett": 40, "costo_ora": 45.0, "competenze": ["sviluppo", "AI/ML", "data engineering"]},
    {"id": "D006", "nome": "Sara Lombardi",     "profilo": "UX/UI Designer",       "ore_sett": 32, "costo_ora": 38.0, "competenze": ["design", "frontend", "user research"]},
    {"id": "D007", "nome": "Roberto Esposito",  "profilo": "Tecnico Mid",          "ore_sett": 40, "costo_ora": 35.0, "competenze": ["sviluppo", "backend", "database"]},
    {"id": "D008", "nome": "Chiara Moretti",    "profilo": "Commerciale/Pre-sales","ore_sett": 40, "costo_ora": 40.0, "competenze": ["vendita", "demo", "relazioni clienti"]},
])

# ── PROGETTI ───────────────────────────────────────────────────────────

PROGETTI = pd.DataFrame([
    # ═══ 5 IN ESECUZIONE ═══
    {
        "id": "P001",
        "nome": "SmartCity Monitoring",
        "cliente": "Comune di Bari",
        "stato": "In esecuzione",
        "data_inizio": datetime(2025, 9, 1),
        "data_fine": datetime(2026, 6, 30),
        "budget_ore": 2400,
        "valore_contratto": 185000.0,
        "descrizione": "Piattaforma di monitoraggio ambientale e infrastrutturale. Sensori IoT, dashboard real-time, modulo predittivo AI.",
        "fase_corrente": "Sviluppo",
    },
    {
        "id": "P002",
        "nome": "Digital Health Records",
        "cliente": "ASL Puglia",
        "stato": "In esecuzione",
        "data_inizio": datetime(2025, 11, 1),
        "data_fine": datetime(2026, 10, 31),
        "budget_ore": 3200,
        "valore_contratto": 260000.0,
        "descrizione": "Digitalizzazione cartelle cliniche. Integrazione HL7 FHIR, portale pazienti, analytics.",
        "fase_corrente": "Design",
    },
    {
        "id": "P003",
        "nome": "Portale Turismo Puglia",
        "cliente": "Regione Puglia",
        "stato": "In esecuzione",
        "data_inizio": datetime(2026, 1, 15),
        "data_fine": datetime(2026, 9, 30),
        "budget_ore": 1800,
        "valore_contratto": 140000.0,
        "descrizione": "Portale turistico regionale con raccomandazioni AI, booking integrato, multilingua.",
        "fase_corrente": "Design",
    },
    {
        "id": "P004",
        "nome": "Piattaforma Open Data",
        "cliente": "Regione Basilicata",
        "stato": "In esecuzione",
        "data_inizio": datetime(2025, 10, 1),
        "data_fine": datetime(2026, 5, 31),
        "budget_ore": 1400,
        "valore_contratto": 110000.0,
        "descrizione": "Catalogo open data regionale con API, dashboard statistiche, modulo CKAN custom.",
        "fase_corrente": "Sviluppo",
    },
    {
        "id": "P005",
        "nome": "Gestionale Scuole Taranto",
        "cliente": "Comune di Taranto",
        "stato": "In esecuzione",
        "data_inizio": datetime(2025, 12, 1),
        "data_fine": datetime(2026, 7, 31),
        "budget_ore": 1600,
        "valore_contratto": 125000.0,
        "descrizione": "Sistema gestionale per le scuole comunali: iscrizioni online, comunicazioni famiglie, registro presenze.",
        "fase_corrente": "Sviluppo",
    },

    # ═══ 1 SOSPESO ═══
    {
        "id": "P006",
        "nome": "Migrazione Cloud PA",
        "cliente": "Provincia BAT",
        "stato": "Sospeso",
        "data_inizio": datetime(2025, 7, 1),
        "data_fine": datetime(2026, 3, 31),
        "budget_ore": 1200,
        "valore_contratto": 95000.0,
        "descrizione": "Migrazione infrastruttura IT su cloud qualificato AgID. Sospeso per problemi di budget del cliente.",
        "fase_corrente": "Sospeso — era in fase Sviluppo",
    },

    # ═══ 1 VINTO DA PIANIFICARE ═══
    {
        "id": "P007",
        "nome": "App Mobilità Sostenibile",
        "cliente": "Comune di Lecce",
        "stato": "Vinto - Da pianificare",
        "data_inizio": datetime(2026, 5, 1),  # previsto
        "data_fine": datetime(2026, 11, 30),   # previsto
        "budget_ore": 900,
        "valore_contratto": 72000.0,
        "descrizione": "App mobile per car sharing e bike sharing comunale. Bando vinto, da fare time-sheet e staffing.",
        "fase_corrente": "Pianificazione",
    },

    # ═══ 2 IN BANDO ═══
    {
        "id": "P008",
        "nome": "Sistema Allerta Meteo IoT",
        "cliente": "Protezione Civile Puglia",
        "stato": "In bando",
        "data_inizio": datetime(2026, 7, 1),   # previsto se vinto
        "data_fine": datetime(2027, 3, 31),     # previsto
        "budget_ore": 2000,
        "valore_contratto": 165000.0,
        "descrizione": "Rete sensori meteo-idrologici con piattaforma allerta. Scadenza bando: 15/04/2026.",
        "fase_corrente": "Preparazione bando",
    },
    {
        "id": "P009",
        "nome": "Portale Servizi Cittadino",
        "cliente": "Comune di Foggia",
        "stato": "In bando",
        "data_inizio": datetime(2026, 6, 1),   # previsto se vinto
        "data_fine": datetime(2027, 1, 31),     # previsto
        "budget_ore": 1500,
        "valore_contratto": 120000.0,
        "descrizione": "Portale unificato servizi al cittadino con SPID/CIE, pagamenti PagoPA. Scadenza bando: 30/04/2026.",
        "fase_corrente": "Preparazione bando",
    },
])

# ── TASK (WBS) ─────────────────────────────────────────────────────────

TASKS = pd.DataFrame([
    # ══════════════════════════════════════════════════════════════════
    # P001: SmartCity Monitoring (in esecuzione — fase Sviluppo)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T001", "progetto_id": "P001", "nome": "Architettura sistema",           "fase": "Design",         "ore_stimate": 120, "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2025, 10, 15), "stato": "Completato",  "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": None},
    {"id": "T002", "progetto_id": "P001", "nome": "Setup infrastruttura cloud",      "fase": "Setup",          "ore_stimate": 80,  "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2025, 11, 15), "stato": "Completato",  "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": "T001"},
    {"id": "T003", "progetto_id": "P001", "nome": "Sviluppo modulo IoT",             "fase": "Sviluppo",       "ore_stimate": 200, "data_inizio": datetime(2025, 11, 15), "data_fine": datetime(2026, 2, 28),  "stato": "In corso",    "profilo_richiesto": "Tecnico Mid",           "dipendente_id": "D007", "predecessore": "T002"},
    {"id": "T004", "progetto_id": "P001", "nome": "Dashboard real-time",             "fase": "Sviluppo",       "ore_stimate": 180, "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 3, 31),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D005", "predecessore": "T002"},
    {"id": "T005", "progetto_id": "P001", "nome": "Modello predittivo AI",           "fase": "Sviluppo",       "ore_stimate": 250, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 5, 15),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D005", "predecessore": "T003"},
    {"id": "T006", "progetto_id": "P001", "nome": "Design UI/UX dashboard",          "fase": "Design",         "ore_stimate": 100, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 1, 15),  "stato": "Completato",  "profilo_richiesto": "UX/UI Designer",        "dipendente_id": "D006", "predecessore": None},
    {"id": "T007", "progetto_id": "P001", "nome": "Gestione progetto SmartCity",     "fase": "Gestione",       "ore_stimate": 160, "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T008", "progetto_id": "P001", "nome": "Demo cliente SmartCity",          "fase": "Vendita",        "ore_stimate": 24,  "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 3, 15),  "stato": "In corso",    "profilo_richiesto": "Commerciale/Pre-sales", "dipendente_id": "D008", "predecessore": "T004"},
    {"id": "T009", "progetto_id": "P001", "nome": "Testing e QA SmartCity",          "fase": "Testing",        "ore_stimate": 150, "data_inizio": datetime(2026, 4, 1),   "data_fine": datetime(2026, 5, 31),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T004"},
    {"id": "T010", "progetto_id": "P001", "nome": "Rendicontazione SmartCity",       "fase": "Amministrazione","ore_stimate": 60,  "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "In corso",    "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P002: Digital Health Records (in esecuzione — fase Design)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T011", "progetto_id": "P002", "nome": "Analisi requisiti sanitari",      "fase": "Analisi",        "ore_stimate": 160, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 1, 31),  "stato": "Completato",  "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T012", "progetto_id": "P002", "nome": "Design architettura HL7 FHIR",   "fase": "Design",         "ore_stimate": 140, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 3, 31),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": "T011"},
    {"id": "T013", "progetto_id": "P002", "nome": "Sviluppo backend FHIR",          "fase": "Sviluppo",       "ore_stimate": 320, "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 7, 31),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Mid",           "dipendente_id": "D007", "predecessore": "T012"},
    {"id": "T014", "progetto_id": "P002", "nome": "Portale pazienti frontend",      "fase": "Sviluppo",       "ore_stimate": 200, "data_inizio": datetime(2026, 4, 1),   "data_fine": datetime(2026, 7, 31),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T012"},
    {"id": "T015", "progetto_id": "P002", "nome": "UX portale pazienti",            "fase": "Design",         "ore_stimate": 80,  "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 3, 31),  "stato": "In corso",    "profilo_richiesto": "UX/UI Designer",        "dipendente_id": "D006", "predecessore": "T011"},
    {"id": "T016", "progetto_id": "P002", "nome": "Modulo analytics clinico",       "fase": "Sviluppo",       "ore_stimate": 180, "data_inizio": datetime(2026, 5, 1),   "data_fine": datetime(2026, 8, 31),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D005", "predecessore": "T013"},
    {"id": "T017", "progetto_id": "P002", "nome": "Testing e certificazione",       "fase": "Testing",        "ore_stimate": 200, "data_inizio": datetime(2026, 8, 1),   "data_fine": datetime(2026, 10, 15), "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T014"},
    {"id": "T018", "progetto_id": "P002", "nome": "Gestione progetto Health",       "fase": "Gestione",       "ore_stimate": 200, "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 10, 31), "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T019", "progetto_id": "P002", "nome": "Rendicontazione Health",         "fase": "Amministrazione","ore_stimate": 80,  "data_inizio": datetime(2025, 11, 1),  "data_fine": datetime(2026, 10, 31), "stato": "In corso",    "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},
    {"id": "T020", "progetto_id": "P002", "nome": "Demo ASL intermedia",            "fase": "Vendita",        "ore_stimate": 32,  "data_inizio": datetime(2026, 6, 1),   "data_fine": datetime(2026, 6, 15),  "stato": "Da iniziare", "profilo_richiesto": "Commerciale/Pre-sales", "dipendente_id": "D008", "predecessore": "T013"},

    # ══════════════════════════════════════════════════════════════════
    # P003: Portale Turismo Puglia (in esecuzione — fase Design)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T021", "progetto_id": "P003", "nome": "Analisi requisiti turismo",      "fase": "Analisi",        "ore_stimate": 80,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 2, 28),  "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T022", "progetto_id": "P003", "nome": "Architettura portale turismo",   "fase": "Design",         "ore_stimate": 100, "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 3, 15),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": None},
    {"id": "T023", "progetto_id": "P003", "nome": "UX/UI portale turistico",        "fase": "Design",         "ore_stimate": 120, "data_inizio": datetime(2026, 2, 15),  "data_fine": datetime(2026, 4, 30),  "stato": "In corso",    "profilo_richiesto": "UX/UI Designer",        "dipendente_id": "D006", "predecessore": None},
    {"id": "T024", "progetto_id": "P003", "nome": "Backend booking e API",          "fase": "Sviluppo",       "ore_stimate": 240, "data_inizio": datetime(2026, 3, 15),  "data_fine": datetime(2026, 7, 15),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Mid",           "dipendente_id": "D007", "predecessore": "T022"},
    {"id": "T025", "progetto_id": "P003", "nome": "Motore raccomandazioni AI",      "fase": "Sviluppo",       "ore_stimate": 160, "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 6, 30),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D005", "predecessore": "T022"},
    {"id": "T026", "progetto_id": "P003", "nome": "Frontend portale multilingua",   "fase": "Sviluppo",       "ore_stimate": 180, "data_inizio": datetime(2026, 4, 1),   "data_fine": datetime(2026, 7, 31),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T023"},
    {"id": "T027", "progetto_id": "P003", "nome": "Testing portale turismo",        "fase": "Testing",        "ore_stimate": 100, "data_inizio": datetime(2026, 7, 15),  "data_fine": datetime(2026, 9, 15),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T026"},
    {"id": "T028", "progetto_id": "P003", "nome": "Demo Regione intermedia",        "fase": "Vendita",        "ore_stimate": 20,  "data_inizio": datetime(2026, 5, 1),   "data_fine": datetime(2026, 5, 15),  "stato": "Da iniziare", "profilo_richiesto": "Commerciale/Pre-sales", "dipendente_id": "D008", "predecessore": "T024"},
    {"id": "T029", "progetto_id": "P003", "nome": "Gestione progetto Turismo",      "fase": "Gestione",       "ore_stimate": 120, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 9, 30),  "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T030", "progetto_id": "P003", "nome": "Rendicontazione Turismo",        "fase": "Amministrazione","ore_stimate": 40,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 9, 30),  "stato": "In corso",    "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P004: Piattaforma Open Data (in esecuzione — fase Sviluppo)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T031", "progetto_id": "P004", "nome": "Analisi e design CKAN",          "fase": "Design",         "ore_stimate": 100, "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2025, 12, 15), "stato": "Completato",  "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": None},
    {"id": "T032", "progetto_id": "P004", "nome": "Sviluppo catalogo open data",    "fase": "Sviluppo",       "ore_stimate": 220, "data_inizio": datetime(2025, 12, 15), "data_fine": datetime(2026, 3, 31),  "stato": "In corso",    "profilo_richiesto": "Tecnico Mid",           "dipendente_id": "D007", "predecessore": "T031"},
    {"id": "T033", "progetto_id": "P004", "nome": "API REST e documentazione",      "fase": "Sviluppo",       "ore_stimate": 120, "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 3, 31),  "stato": "In corso",    "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": None},
    {"id": "T034", "progetto_id": "P004", "nome": "Dashboard statistiche",          "fase": "Sviluppo",       "ore_stimate": 140, "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 4, 30),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D005", "predecessore": None},
    {"id": "T035", "progetto_id": "P004", "nome": "UX dashboard open data",         "fase": "Design",         "ore_stimate": 60,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 2, 28),  "stato": "Completato",  "profilo_richiesto": "UX/UI Designer",        "dipendente_id": "D006", "predecessore": None},
    {"id": "T036", "progetto_id": "P004", "nome": "Testing open data",              "fase": "Testing",        "ore_stimate": 80,  "data_inizio": datetime(2026, 4, 1),   "data_fine": datetime(2026, 5, 15),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T032"},
    {"id": "T037", "progetto_id": "P004", "nome": "Gestione progetto Open Data",    "fase": "Gestione",       "ore_stimate": 100, "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T038", "progetto_id": "P004", "nome": "Rendicontazione Open Data",      "fase": "Amministrazione","ore_stimate": 40,  "data_inizio": datetime(2025, 10, 1),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P005: Gestionale Scuole Taranto (in esecuzione — fase Sviluppo)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T039", "progetto_id": "P005", "nome": "Analisi requisiti scuole",       "fase": "Analisi",        "ore_stimate": 80,  "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 1, 15),  "stato": "Completato",  "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T040", "progetto_id": "P005", "nome": "Design sistema iscrizioni",      "fase": "Design",         "ore_stimate": 80,  "data_inizio": datetime(2026, 1, 15),  "data_fine": datetime(2026, 2, 28),  "stato": "Completato",  "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": "T039"},
    {"id": "T041", "progetto_id": "P005", "nome": "Backend iscrizioni e registro",  "fase": "Sviluppo",       "ore_stimate": 200, "data_inizio": datetime(2026, 2, 15),  "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Tecnico Mid",           "dipendente_id": "D007", "predecessore": "T040"},
    {"id": "T042", "progetto_id": "P005", "nome": "Frontend famiglie",              "fase": "Sviluppo",       "ore_stimate": 160, "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 5, 31),  "stato": "In corso",    "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T040"},
    {"id": "T043", "progetto_id": "P005", "nome": "UX gestionale scuole",           "fase": "Design",         "ore_stimate": 70,  "data_inizio": datetime(2026, 2, 1),   "data_fine": datetime(2026, 3, 15),  "stato": "In corso",    "profilo_richiesto": "UX/UI Designer",        "dipendente_id": "D006", "predecessore": None},
    {"id": "T044", "progetto_id": "P005", "nome": "Demo Comune di Taranto",         "fase": "Vendita",        "ore_stimate": 16,  "data_inizio": datetime(2026, 4, 15),  "data_fine": datetime(2026, 4, 30),  "stato": "Da iniziare", "profilo_richiesto": "Commerciale/Pre-sales", "dipendente_id": "D008", "predecessore": "T041"},
    {"id": "T045", "progetto_id": "P005", "nome": "Testing gestionale scuole",      "fase": "Testing",        "ore_stimate": 100, "data_inizio": datetime(2026, 5, 15),  "data_fine": datetime(2026, 7, 15),  "stato": "Da iniziare", "profilo_richiesto": "Tecnico Junior",        "dipendente_id": "D002", "predecessore": "T042"},
    {"id": "T046", "progetto_id": "P005", "nome": "Gestione progetto Scuole",       "fase": "Gestione",       "ore_stimate": 120, "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 7, 31),  "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T047", "progetto_id": "P005", "nome": "Rendicontazione Scuole",         "fase": "Amministrazione","ore_stimate": 40,  "data_inizio": datetime(2025, 12, 1),  "data_fine": datetime(2026, 7, 31),  "stato": "In corso",    "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P006: Migrazione Cloud PA (SOSPESO — task congelati)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T048", "progetto_id": "P006", "nome": "Assessment infrastruttura",      "fase": "Analisi",        "ore_stimate": 80,  "data_inizio": datetime(2025, 7, 1),   "data_fine": datetime(2025, 8, 31),  "stato": "Completato",  "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": None},
    {"id": "T049", "progetto_id": "P006", "nome": "Piano migrazione",               "fase": "Design",         "ore_stimate": 60,  "data_inizio": datetime(2025, 9, 1),   "data_fine": datetime(2025, 10, 15), "stato": "Completato",  "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": "T048"},
    {"id": "T050", "progetto_id": "P006", "nome": "Migrazione servizi core",        "fase": "Sviluppo",       "ore_stimate": 300, "data_inizio": datetime(2025, 10, 15), "data_fine": datetime(2026, 2, 28),  "stato": "Sospeso",     "profilo_richiesto": "Tecnico Mid",           "dipendente_id": "D007", "predecessore": "T049"},
    {"id": "T051", "progetto_id": "P006", "nome": "Gestione progetto Cloud",        "fase": "Gestione",       "ore_stimate": 80,  "data_inizio": datetime(2025, 7, 1),   "data_fine": datetime(2026, 3, 31),  "stato": "Sospeso",     "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},

    # ══════════════════════════════════════════════════════════════════
    # P008 e P009: BANDI (task di preparazione bando — lavoro reale!)
    # ══════════════════════════════════════════════════════════════════
    {"id": "T052", "progetto_id": "P008", "nome": "Stesura proposta tecnica Allerta","fase": "Bando",         "ore_stimate": 60,  "data_inizio": datetime(2026, 2, 15),  "data_fine": datetime(2026, 4, 10),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D005", "predecessore": None},
    {"id": "T053", "progetto_id": "P008", "nome": "Stima costi e budget Allerta",   "fase": "Bando",          "ore_stimate": 30,  "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 4, 10),  "stato": "In corso",    "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T054", "progetto_id": "P008", "nome": "Documentazione admin Allerta",   "fase": "Bando",          "ore_stimate": 20,  "data_inizio": datetime(2026, 3, 15),  "data_fine": datetime(2026, 4, 10),  "stato": "Da iniziare", "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},
    {"id": "T055", "progetto_id": "P008", "nome": "Presentazione commerciale Allerta","fase": "Bando",        "ore_stimate": 16,  "data_inizio": datetime(2026, 3, 20),  "data_fine": datetime(2026, 4, 10),  "stato": "Da iniziare", "profilo_richiesto": "Commerciale/Pre-sales", "dipendente_id": "D008", "predecessore": None},

    {"id": "T056", "progetto_id": "P009", "nome": "Stesura proposta Servizi Cittadino","fase": "Bando",       "ore_stimate": 50,  "data_inizio": datetime(2026, 3, 1),   "data_fine": datetime(2026, 4, 25),  "stato": "In corso",    "profilo_richiesto": "Tecnico Senior",        "dipendente_id": "D001", "predecessore": None},
    {"id": "T057", "progetto_id": "P009", "nome": "Stima costi Servizi Cittadino",  "fase": "Bando",          "ore_stimate": 25,  "data_inizio": datetime(2026, 3, 15),  "data_fine": datetime(2026, 4, 25),  "stato": "Da iniziare", "profilo_richiesto": "Project Manager",       "dipendente_id": "D003", "predecessore": None},
    {"id": "T058", "progetto_id": "P009", "nome": "Documentazione admin Cittadino", "fase": "Bando",          "ore_stimate": 20,  "data_inizio": datetime(2026, 3, 20),  "data_fine": datetime(2026, 4, 25),  "stato": "Da iniziare", "profilo_richiesto": "Amministrativo",        "dipendente_id": "D004", "predecessore": None},
    {"id": "T059", "progetto_id": "P009", "nome": "Presentazione commerciale Cittadino","fase": "Bando",      "ore_stimate": 16,  "data_inizio": datetime(2026, 3, 25),  "data_fine": datetime(2026, 4, 25),  "stato": "Da iniziare", "profilo_richiesto": "Commerciale/Pre-sales", "dipendente_id": "D008", "predecessore": None},
])

TASKS = TASKS.fillna({"predecessore": ""})

# ── CONSUNTIVI (ore effettivamente lavorate) ───────────────────────────

def genera_consuntivi():
    """Genera consuntivi settimanali realistici con buchi."""
    records = []
    oggi = datetime(2026, 3, 9)

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
                            "Ritardo per attesa feedback cliente",
                            "Bloccato da dipendenze",
                            "Lavoro extra per bug critico",
                            "Riunione di allineamento non prevista",
                            "Supporto a collega su altro progetto",
                            "Attesa approvazione da parte del cliente",
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
    return DIPENDENTI[DIPENDENTI["id"] == did].iloc[0]

def get_progetto(pid):
    return PROGETTI[PROGETTI["id"] == pid].iloc[0]

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
