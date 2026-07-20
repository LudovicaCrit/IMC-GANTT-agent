"""
═══════════════════════════════════════════════════════════════════════
data_legacy.py — Dati grezzi per il seed iniziale del database.
═══════════════════════════════════════════════════════════════════════

NOTA STORICA E SUL NOME (6 mag 2026):
Il nome "_legacy" è fuorviante per il ruolo attuale del file.
In origine era la "modalità memoria di fallback": data.py controllava se
il db era popolato e in caso negativo ricadeva qui per usare DataFrame
in memoria.

Da quando il sistema gira su PostgreSQL + Alembic + seed.py (6 mag 2026),
il fallback memoria non viene più attivato a runtime. Il vero ruolo di
questo file è ora:

    1. Contenere i DataFrame DIPENDENTI, PROGETTI, TASKS, CONSUNTIVI con
       i dati fittizi iniziali (clienti, dipendenti, progetti credibili,
       1282 consuntivi distribuiti su settimane).
    2. Esporre questi DataFrame a seed.py che li legge per popolare il db.

Le 16 funzioni qui dentro (aggiungi_task, modifica_task, ecc.) sono
ancora chiamabili in modalità memoria, ma in pratica non vengono mai
invocate, perché data.py importa sempre data_db_impl quando il db è
popolato.

📌 TODO Blocco 6 (hardening):
    - Rinominare il file a 'seed_data.py' per riflettere il vero ruolo
    - Rimuovere le 16 funzioni di scrittura in memoria (legacy non più
      rilevanti)
    - Conservare SOLO i DataFrame iniziali

Per ora il file resta com'è: rinominarlo richiede di toccare data.py
e i 14 router che importano da data, lavoro che si fa con calma in
fase di hardening, non in mezzo allo sviluppo dei blocchi.

═══════════════════════════════════════════════════════════════════════

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
- "interna"    → attività interna non fatturabile (mansioni continuative,
                 corsi/formazione, progetti di innovazione). Migration #2,
                 03/06/2026. Sostituisce il vecchio contenitore-unico P010.

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
    {"id": "D004", "nome": "Helena Ullah",           "profilo": "IT Consultant",               "ore_sett": 40, "costo_ora": 30.0, "competenze": ["ARIS", "integrazione sistemi", "testing", "processi"]},
    # Senior Consultant (anche PM)
    {"id": "D005", "nome": "Andrea Morstabilini",    "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 50.0, "competenze": ["PM", "GRC", "compliance", "bandi", "gestione progetti"]},
    {"id": "D006", "nome": "Paolo Di Prizio",        "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 50.0, "competenze": ["PM", "risk management", "processi", "gestione progetti"]},
    {"id": "D007", "nome": "Carolina Coccorese",     "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 48.0, "competenze": ["PM", "compliance", "coordinamento", "gestione progetti"]},
    {"id": "D008", "nome": "Fausto Garzillo",        "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 45.0, "competenze": ["GRC", "processi", "ARIS", "relazioni clienti"]},
    # Consultant
    {"id": "D009", "nome": "Tetiana Matveichuk",     "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 35.0, "competenze": ["rendicontazione", "documentazione", "coordinamento", "relazioni clienti"]},
    {"id": "D010", "nome": "Nicola Coccorese",       "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 35.0, "competenze": ["GRC", "analisi", "relazioni clienti"]},
    {"id": "D011", "nome": "Ludovica Di Cianni",     "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 25.0, "competenze": ["IA", "python", "backend", "sviluppo"]},
    # Manager HR
    {"id": "D012", "nome": "Cosimo Pacifico",        "profilo": "Manager HR",                  "ore_sett": 40, "costo_ora": 40.0, "competenze": ["risorse umane", "formazione", "organizzazione", "contratti"]},
    # Responsabile amministrazione
    # Francesco Carolla: qualifica organigramma "Managing Director" (Innovation Plaza),
    # ma fa da PM/commerciale su progetti Improve (Maida/Tecnomat). Il profilo resta
    # una delle 9 categorie chiuse → "Senior Consultant". Le qualifiche-ruolo NON
    # stanno in competenze (che sono funzionali); un eventuale campo "ruolo
    # organizzativo" è lavoro futuro, non esiste ora.
    {"id": "D013", "nome": "Francesco Carolla",      "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 42.0, "competenze": ["bandi", "relazioni clienti", "PM", "gestione progetti", "controllo gestione"]},
    # Addetto amministrazione
    {"id": "D014", "nome": "Carolina Jori",          "profilo": "Addetto amministrazione",     "ore_sett": 20, "costo_ora": 28.0, "competenze": ["amministrazione", "documentazione", "archivio"]},
    {"id": "D015", "nome": "Daniele Tagliabue",      "profilo": "Addetto amministrazione",     "ore_sett": 40, "costo_ora": 30.0, "competenze": ["amministrazione", "rendicontazione", "fatturazione"]},
    # ── Innovation Plaza (nuove persone, DESIGN §2). Profilo tra le 9 categorie;
    #    le qualifiche organigramma (Co-founder, Resp. area, Progettazione Europea)
    #    vivono nelle competenze, non nel profilo.
    {"id": "D016", "nome": "Ida Carolla",            "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 50.0, "competenze": ["PA", "bandi pubblici", "bandi", "progettazione", "gestione progetti", "relazioni clienti"]},
    {"id": "D017", "nome": "Domenica Suma",          "profilo": "Senior Consultant",           "ore_sett": 40, "costo_ora": 50.0, "competenze": ["imprese", "bandi", "progettazione", "gestione progetti", "relazioni clienti"]},
    {"id": "D018", "nome": "Denise Greco",           "profilo": "Consultant",                  "ore_sett": 40, "costo_ora": 35.0, "competenze": ["progettazione europea", "bandi", "progettazione", "documentazione"]},
])

# ── AZIENDA DI APPARTENENZA ─────────────────────────────────────────────
# DESIGN_SEED_Innovation_Plaza §1-§2: ogni persona appartiene a un'azienda.
# Innovation Plaza per Tetiana (D009), Francesco (D013) e le 3 nuove
# (Ida D016 / Domenica D017 / Denise D018); IMC-Improve per tutti gli altri.
# Nota: l'azienda della persona NON vincola su quali progetti può lavorare.
_DIP_INNOVATION = {"D009", "D013", "D016", "D017", "D018"}
DIPENDENTI["azienda"] = DIPENDENTI["id"].map(
    lambda d: "Innovation Plaza" if d in _DIP_INNOVATION else "IMC-Improve"
)

# ── ANAGRAFICA PROGETTI ────────────────────────────────────────────────

PROGETTI = pd.DataFrame([
    # ═══ PROGETTI CLIENTE / BANDI ═══
    {
        "id": "P001", "nome": "Adeguamento DORA", "cliente": "Sparkasse",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 2600, "valore_contratto": 195000.0,
        "descrizione": "Adeguamento al regolamento DORA sulla resilienza operativa digitale.",
        "fase_corrente": "Implementazione",
    },
    {
        "id": "P002", "nome": "Framework Compliance 262", "cliente": "Reale Mutua",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,10,31),
        "budget_ore": 3400, "valore_contratto": 240000.0,
        "descrizione": "Digitalizzazione del framework di compliance L.262.",
        "fase_corrente": "Sviluppo piattaforma",
    },
    {
        "id": "P003", "nome": "Digitalizzazione Corpo Normativo", "cliente": "Duferco Energia",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,9,30),
        "budget_ore": 2000, "valore_contratto": 145000.0,
        "descrizione": "Piattaforma AI per classificazione norme.",
        "fase_corrente": "Design",
    },
    {
        "id": "P004", "nome": "Risk Assessment Operativo", "cliente": "BNP Paribas",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,5,31),
        "budget_ore": 1900, "valore_contratto": 130000.0,
        "descrizione": "Assessment dei rischi operativi e framework di gestione.",
        "fase_corrente": "Assessment",
    },
    {
        "id": "P005", "nome": "ProcessBook Aziendale", "cliente": "Boggi Milano",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2025,12,1), "data_fine": datetime(2026,7,31),
        "budget_ore": 1500, "valore_contratto": 105000.0,
        "descrizione": "ProcessBook aziendale, piattaforma BPM customizzata.",
        "fase_corrente": "Mappatura processi",
    },
    {
        "id": "P006", "nome": "Piattaforma Antiriciclaggio", "cliente": "Banca Popolare di Bari",
        "stato": "Sospeso", "tipologia": "ordinario",
        "data_inizio": datetime(2025,7,1), "data_fine": datetime(2026,3,31),
        "budget_ore": 1800, "valore_contratto": 160000.0,
        "descrizione": "Piattaforma RISKAML antiriciclaggio. Sospeso.",
        "fase_corrente": "Sospeso — era in Sviluppo",
    },
    {
        "id": "P007", "nome": "Framework ESG Reporting", "cliente": "A2A",
        "stato": "Bozza", "tipologia": "ordinario",
        "data_inizio": datetime(2026,5,1), "data_fine": datetime(2026,11,30),
        "budget_ore": 1000, "valore_contratto": 90000.0,
        "descrizione": "Framework per il reporting ESG integrato.",
        "fase_corrente": "Pianificazione",
    },
    {
        "id": "P008", "nome": "Business Continuity Framework", "cliente": "ITAS Assicurazioni",
        "stato": "In esecuzione", "tipologia": "bando",
        "data_inizio": datetime(2026,7,1), "data_fine": datetime(2027,3,31),
        "budget_ore": 1800, "valore_contratto": 155000.0,
        "descrizione": "Framework di Business Continuity Management.",
        "fase_corrente": "Preparazione bando",
    },
    {
        "id": "P009", "nome": "GRC Platform Integration", "cliente": "Banco Desio",
        "stato": "In esecuzione", "tipologia": "bando",
        "data_inizio": datetime(2026,6,1), "data_fine": datetime(2027,1,31),
        "budget_ore": 1500, "valore_contratto": 135000.0,
        "descrizione": "Integrazione piattaforma GRC con sistemi interni.",
        "fase_corrente": "Preparazione bando",
    },

    # ═══ ATTIVITÀ INTERNE (tipologia='interna') — ex contenitore P010 ═══
    # Mansioni continuative (PI), corsi/formazione (PC), progetti innovazione (PN)
    {
        "id": "PC01", "nome": "Corso di inglese", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 360, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (corso/formazione): corso di inglese.",
        "fase_corrente": "Formazione",
    },
    {
        "id": "PC02", "nome": "Aggiornamento strumenti IA", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 64, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (corso/formazione): aggiornamento strumenti ia.",
        "fase_corrente": "Formazione",
    },
    {
        "id": "PC03", "nome": "Corso Excel avanzato", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 60, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (corso/formazione): corso excel avanzato.",
        "fase_corrente": "Formazione",
    },
    {
        "id": "PC04", "nome": "Corso GDPR e privacy dei dati", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 40, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (corso/formazione): corso gdpr e privacy dei dati.",
        "fase_corrente": "Formazione",
    },
    {
        "id": "PC05", "nome": "Primo soccorso e sicurezza sul lavoro", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 72, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (corso/formazione): primo soccorso e sicurezza sul lavoro.",
        "fase_corrente": "Formazione",
    },
    {
        "id": "PI01", "nome": "Direzione e sviluppo commerciale", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 494, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): direzione e sviluppo commerciale.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI02", "nome": "Relazioni istituzionali e clienti", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 494, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): relazioni istituzionali e clienti.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI03", "nome": "Supervisione progetti e qualità", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 494, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): supervisione progetti e qualità.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI04", "nome": "Architettura IT e standard tecnici", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 512, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): architettura it e standard tecnici.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI05", "nome": "Coordinamento tecnico e mentoring", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 512, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): coordinamento tecnico e mentoring.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI05b", "nome": "Sviluppo avanzato e architettura applicativa", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 802, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): sviluppo avanzato e architettura applicativa.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI06", "nome": "Gestione HR e organizzazione", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 797, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): gestione hr e organizzazione.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI07", "nome": "Selezione e onboarding", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 797, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): selezione e onboarding.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI08", "nome": "Controllo di gestione e reporting", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 807, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): controllo di gestione e reporting.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI09", "nome": "Pianificazione economico-finanziaria", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 807, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): pianificazione economico-finanziaria.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI10", "nome": "Amministrazione corrente e fatturazione", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 1352, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): amministrazione corrente e fatturazione.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI11", "nome": "Documentazione e archivio", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 637, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): documentazione e archivio.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI12", "nome": "Scouting bandi e networking", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 1180, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): scouting bandi e networking.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI12b", "nome": "Sviluppo offerte tecniche e prevendita", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 880, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): sviluppo offerte tecniche e prevendita.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI13", "nome": "Coordinamento interno e PMO", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 1210, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): coordinamento interno e pmo.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI13b", "nome": "Supporto coordinamento e relazione cliente", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 986, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): supporto coordinamento e relazione cliente.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI14", "nome": "Supporto analisi e ricerca", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 1208, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): supporto analisi e ricerca.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI15", "nome": "Formazione tecnica individuale", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 708, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): formazione tecnica individuale.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PI15b", "nome": "Formazione e aggiornamento ARIS", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 662, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (mansione continuativa): formazione e aggiornamento aris.",
        "fase_corrente": "Continuativa",
    },
    {
        "id": "PN01", "nome": "Sviluppo GANTT Agent", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 862, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (progetto di innovazione): sviluppo gantt agent.",
        "fase_corrente": "Sviluppo",
    },
    {
        "id": "PN02", "nome": "Sviluppo LOG ARIS Monitor", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 470, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (progetto di innovazione): sviluppo log aris monitor.",
        "fase_corrente": "Sviluppo",
    },
    {
        "id": "PN03", "nome": "Progetto PM e pianificazione IA", "cliente": "IMC-Group",
        "stato": "In esecuzione", "tipologia": "interna",
        "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30),
        "budget_ore": 235, "valore_contratto": 0.0,
        "descrizione": "Attività interna non fatturabile (progetto di innovazione): progetto pm e pianificazione ia.",
        "fase_corrente": "Sviluppo",
    },

    # ═══ NUOVI PROGETTI AIoT — azienda IMC-Improve, PM Francesco (D013) ═══
    # DESIGN §3: materializzano la doppia veste di Francesco (appartiene a
    # Innovation ma fa da PM su progetti Improve). Dataset sintetico plausibile.
    {
        "id": "P010", "nome": "AIoT Smart City Maida", "cliente": "Comune di Maida",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,12,31),
        "budget_ore": 1200, "valore_contratto": 120000.0,
        "descrizione": "Progetto AIoT per il monitoraggio del territorio del Comune di Maida (ente pubblico): sensoristica diffusa e dashboard AI.",
        "fase_corrente": "Design",
    },
    {
        "id": "P011", "nome": "AIoT Industria 4.0 Tecnomat", "cliente": "Tecnomat S.p.A.",
        "stato": "In esecuzione", "tipologia": "ordinario",
        "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,11,30),
        "budget_ore": 1000, "valore_contratto": 95000.0,
        "descrizione": "Progetto AIoT industriale per Tecnomat (impresa): edge computing e manutenzione predittiva sulle linee produttive.",
        "fase_corrente": "Analisi",
    },
])

# ── AZIENDA / AREA / PM PER PROGETTO ────────────────────────────────────
# DESIGN_SEED_Innovation_Plaza §3.
# pm_id: relazione PER-PROGETTO (non ruolo/attributo del dipendente). Solo i
# progetti con responsabile assegnato; bozze (P007) e interni restano senza PM.
_PM = {
    "P001": "D005", "P002": "D007", "P003": "D002", "P004": "D006",
    "P005": "D007", "P006": "D002",          # ordinari Improve
    "P008": "D016", "P009": "D017",          # bandi Innovation (Ida / Domenica)
    "P010": "D013", "P011": "D013",          # AIoT Improve, PM Francesco
}
# area: solo i bandi Innovation — "PA" (Ida) / "Imprese" (Domenica). NULL altrove.
_AREA = {"P008": "PA", "P009": "Imprese"}

def _azienda_progetto(row):
    # interni → NULL (attività trasversale); bandi → Innovation; resto → Improve.
    if row["tipologia"] == "interna":
        return None
    if row["id"] in ("P008", "P009"):
        return "Innovation Plaza"
    return "IMC-Improve"

PROGETTI["pm_id"] = PROGETTI["id"].map(lambda p: _PM.get(p))
PROGETTI["area"] = PROGETTI["id"].map(lambda p: _AREA.get(p))
PROGETTI["azienda"] = PROGETTI.apply(_azienda_progetto, axis=1)

# ── TASK ───────────────────────────────────────────────────────────────

TASKS = pd.DataFrame([
    {"id": "T001", "progetto_id": "P001", "nome": "Gap analysis DORA", "fase": "Analisi", "ore_stimate": 160, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2025,11,15), "stato": "Completato", "profilo_richiesto": "Senior IT Consultant", "dipendente_id": "D003", "predecessore": None},
    {"id": "T002", "progetto_id": "P001", "nome": "Remediation plan ICT risk", "fase": "Design", "ore_stimate": 120, "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,1,15), "stato": "Completato", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T001"},
    {"id": "T003", "progetto_id": "P001", "nome": "Implementazione framework ICT", "fase": "Sviluppo", "ore_stimate": 360, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,5,15), "stato": "In corso", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T002"},
    {"id": "T004", "progetto_id": "P001", "nome": "Testing e validazione DORA", "fase": "Testing", "ore_stimate": 140, "data_inizio": datetime(2026,4,15), "data_fine": datetime(2026,5,15), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T005", "progetto_id": "P001", "nome": "Coordinamento cliente Sparkasse", "fase": "Gestione", "ore_stimate": 140, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D007", "predecessore": None},
    {"id": "T006", "progetto_id": "P001", "nome": "Gestione progetto DORA", "fase": "Gestione", "ore_stimate": 180, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "PM", "dipendente_id": "D005", "predecessore": None},
    {"id": "T007", "progetto_id": "P001", "nome": "Rendicontazione DORA", "fase": "Amministrazione", "ore_stimate": 60, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "Addetto amministrazione", "dipendente_id": "D015", "predecessore": None},
    {"id": "T008", "progetto_id": "P001", "nome": "Configurazione processi DORA", "fase": "Sviluppo", "ore_stimate": 120, "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,4,30), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D008", "predecessore": "T002"},
    {"id": "T009", "progetto_id": "P001", "nome": "Relazione direzionale Sparkasse", "fase": "Gestione", "ore_stimate": 60, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "AD", "dipendente_id": "D001", "predecessore": None},
    {"id": "T010", "progetto_id": "P002", "nome": "Analisi requisiti compliance 262", "fase": "Analisi", "ore_stimate": 160, "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,1,31), "stato": "Completato", "profilo_richiesto": "PM", "dipendente_id": "D006", "predecessore": None},
    {"id": "T011", "progetto_id": "P002", "nome": "Mappatura controlli L.262", "fase": "Analisi", "ore_stimate": 260, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,4,15), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D008", "predecessore": "T010"},
    {"id": "T012", "progetto_id": "P002", "nome": "Sviluppo piattaforma GRC", "fase": "Sviluppo", "ore_stimate": 440, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,7,31), "stato": "In corso", "profilo_richiesto": "Senior IT Consultant", "dipendente_id": "D003", "predecessore": "T010"},
    {"id": "T013", "progetto_id": "P002", "nome": "Modulo certificazione flussi", "fase": "Sviluppo", "ore_stimate": 260, "data_inizio": datetime(2026,5,1), "data_fine": datetime(2026,8,31), "stato": "Da iniziare", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T012"},
    {"id": "T014", "progetto_id": "P002", "nome": "Integrazione sistemi Reale Mutua", "fase": "Sviluppo", "ore_stimate": 200, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,7,31), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T015", "progetto_id": "P002", "nome": "Testing e UAT compliance", "fase": "Testing", "ore_stimate": 150, "data_inizio": datetime(2026,8,1), "data_fine": datetime(2026,10,15), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": "T013"},
    {"id": "T016", "progetto_id": "P002", "nome": "Coordinamento Reale Mutua", "fase": "Gestione", "ore_stimate": 180, "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,10,31), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T017", "progetto_id": "P002", "nome": "Gestione progetto Compliance 262", "fase": "Gestione", "ore_stimate": 220, "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,10,31), "stato": "In corso", "profilo_richiesto": "PM", "dipendente_id": "D006", "predecessore": None},
    {"id": "T018", "progetto_id": "P002", "nome": "Rendicontazione Compliance 262", "fase": "Amministrazione", "ore_stimate": 70, "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,10,31), "stato": "In corso", "profilo_richiesto": "Addetto amministrazione", "dipendente_id": "D015", "predecessore": None},
    {"id": "T019", "progetto_id": "P002", "nome": "Demo intermedia Reale Mutua", "fase": "Vendita", "ore_stimate": 60, "data_inizio": datetime(2026,6,1), "data_fine": datetime(2026,6,15), "stato": "Da iniziare", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D005", "predecessore": "T012"},
    {"id": "T020", "progetto_id": "P002", "nome": "Preparazione ambienti test Compliance", "fase": "Sviluppo", "ore_stimate": 90, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,4,15), "stato": "In corso", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T021", "progetto_id": "P002", "nome": "Relazione direzionale Reale Mutua", "fase": "Gestione", "ore_stimate": 50, "data_inizio": datetime(2025,11,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "AD", "dipendente_id": "D001", "predecessore": None},
    {"id": "T022", "progetto_id": "P003", "nome": "Analisi corpo normativo Duferco", "fase": "Analisi", "ore_stimate": 140, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,3,15), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D010", "predecessore": None},
    {"id": "T023", "progetto_id": "P003", "nome": "Design piattaforma normativa AI", "fase": "Design", "ore_stimate": 150, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,4,30), "stato": "Da iniziare", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T022"},
    {"id": "T024", "progetto_id": "P003", "nome": "Sviluppo classificatore AI norme", "fase": "Sviluppo", "ore_stimate": 150, "data_inizio": datetime(2026,4,15), "data_fine": datetime(2026,7,31), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": "T023"},
    {"id": "T025", "progetto_id": "P003", "nome": "Sviluppo backend piattaforma", "fase": "Sviluppo", "ore_stimate": 300, "data_inizio": datetime(2026,4,15), "data_fine": datetime(2026,7,15), "stato": "Da iniziare", "profilo_richiesto": "Senior IT Consultant", "dipendente_id": "D003", "predecessore": "T023"},
    {"id": "T026", "progetto_id": "P003", "nome": "Testing piattaforma normativa", "fase": "Testing", "ore_stimate": 90, "data_inizio": datetime(2026,7,15), "data_fine": datetime(2026,7,31), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": "T025"},
    {"id": "T027", "progetto_id": "P003", "nome": "Coordinamento Duferco", "fase": "Gestione", "ore_stimate": 120, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,9,30), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T028", "progetto_id": "P003", "nome": "Gestione progetto Duferco", "fase": "Gestione", "ore_stimate": 150, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,9,30), "stato": "In corso", "profilo_richiesto": "PM", "dipendente_id": "D007", "predecessore": None},
    {"id": "T029", "progetto_id": "P003", "nome": "Rendicontazione Duferco", "fase": "Amministrazione", "ore_stimate": 40, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,9,30), "stato": "In corso", "profilo_richiesto": "Addetto amministrazione", "dipendente_id": "D014", "predecessore": None},
    {"id": "T030", "progetto_id": "P003", "nome": "Prototipo classificatore norme", "fase": "Sviluppo", "ore_stimate": 70, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,4,30), "stato": "In corso", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T031", "progetto_id": "P004", "nome": "Mappatura processi operativi BNP", "fase": "Analisi", "ore_stimate": 220, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,1,31), "stato": "Completato", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D008", "predecessore": None},
    {"id": "T032", "progetto_id": "P004", "nome": "Identificazione e scoring rischi", "fase": "Analisi", "ore_stimate": 260, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,3,31), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D006", "predecessore": "T031"},
    {"id": "T033", "progetto_id": "P004", "nome": "Piano mitigazione rischi", "fase": "Design", "ore_stimate": 180, "data_inizio": datetime(2026,3,15), "data_fine": datetime(2026,5,15), "stato": "Da iniziare", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D006", "predecessore": "T032"},
    {"id": "T034", "progetto_id": "P004", "nome": "Configurazione risk framework", "fase": "Sviluppo", "ore_stimate": 160, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,4,30), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D008", "predecessore": None},
    {"id": "T035", "progetto_id": "P004", "nome": "Coordinamento BNP Paribas", "fase": "Gestione", "ore_stimate": 120, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,5,31), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D010", "predecessore": None},
    {"id": "T036", "progetto_id": "P004", "nome": "Gestione progetto BNP", "fase": "Gestione", "ore_stimate": 160, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,5,31), "stato": "In corso", "profilo_richiesto": "PM", "dipendente_id": "D005", "predecessore": None},
    {"id": "T037", "progetto_id": "P004", "nome": "Rendicontazione BNP", "fase": "Amministrazione", "ore_stimate": 50, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,5,31), "stato": "In corso", "profilo_richiesto": "Addetto amministrazione", "dipendente_id": "D015", "predecessore": None},
    {"id": "T038", "progetto_id": "P004", "nome": "Supporto analisi BNP", "fase": "Gestione", "ore_stimate": 90, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,5,31), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T039", "progetto_id": "P004", "nome": "Relazione direzionale BNP", "fase": "Gestione", "ore_stimate": 40, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,5,31), "stato": "In corso", "profilo_richiesto": "AD", "dipendente_id": "D001", "predecessore": None},
    {"id": "T040", "progetto_id": "P005", "nome": "Interviste e raccolta processi", "fase": "Analisi", "ore_stimate": 140, "data_inizio": datetime(2025,12,1), "data_fine": datetime(2026,2,15), "stato": "Completato", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T041", "progetto_id": "P005", "nome": "Mappatura processi", "fase": "Sviluppo", "ore_stimate": 240, "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,5,31), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D008", "predecessore": "T040"},
    {"id": "T042", "progetto_id": "P005", "nome": "Sviluppo piattaforma BPM", "fase": "Sviluppo", "ore_stimate": 260, "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "Senior IT Consultant", "dipendente_id": "D003", "predecessore": None},
    {"id": "T043", "progetto_id": "P005", "nome": "Testing ProcessBook", "fase": "Testing", "ore_stimate": 120, "data_inizio": datetime(2026,6,15), "data_fine": datetime(2026,6,30), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T044", "progetto_id": "P005", "nome": "Coordinamento Boggi", "fase": "Gestione", "ore_stimate": 90, "data_inizio": datetime(2025,12,1), "data_fine": datetime(2026,7,31), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D010", "predecessore": None},
    {"id": "T045", "progetto_id": "P005", "nome": "Gestione progetto Boggi", "fase": "Gestione", "ore_stimate": 140, "data_inizio": datetime(2025,12,1), "data_fine": datetime(2026,7,31), "stato": "In corso", "profilo_richiesto": "PM", "dipendente_id": "D007", "predecessore": None},
    {"id": "T046", "progetto_id": "P005", "nome": "Interviste processi Boggi", "fase": "Analisi", "ore_stimate": 60, "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,4,30), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T047", "progetto_id": "P006", "nome": "Analisi requisiti AML", "fase": "Analisi", "ore_stimate": 100, "data_inizio": datetime(2025,7,1), "data_fine": datetime(2025,9,30), "stato": "Completato", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": None},
    {"id": "T048", "progetto_id": "P006", "nome": "Sviluppo algoritmi AI AML", "fase": "Sviluppo", "ore_stimate": 300, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,2,28), "stato": "Sospeso", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T047"},
    {"id": "T049", "progetto_id": "P006", "nome": "Gestione progetto AML", "fase": "Gestione", "ore_stimate": 60, "data_inizio": datetime(2025,7,1), "data_fine": datetime(2026,3,31), "stato": "Sospeso", "profilo_richiesto": "PM", "dipendente_id": "D005", "predecessore": None},
    # ── P008 BANDO PA (Innovation, PM Ida D016) — analisi bando ministeriale,
    #    predisposizione domanda. Staff Innovation (Ida/Denise/Tetiana).
    {"id": "T050", "progetto_id": "P008", "nome": "Analisi bando ministeriale PA", "fase": "Analisi bando", "ore_stimate": 120, "data_inizio": datetime(2026,2,15), "data_fine": datetime(2026,3,31), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D016", "predecessore": None},
    {"id": "T051", "progetto_id": "P008", "nome": "Predisposizione domanda e istanza PA", "fase": "Predisposizione domanda", "ore_stimate": 90, "data_inizio": datetime(2026,4,1), "data_fine": datetime(2026,5,15), "stato": "Da iniziare", "profilo_richiesto": "Consultant", "dipendente_id": "D018", "predecessore": "T050"},
    {"id": "T052", "progetto_id": "P008", "nome": "Rendicontazione e documentazione ITAS", "fase": "Predisposizione domanda", "ore_stimate": 40, "data_inizio": datetime(2026,4,1), "data_fine": datetime(2026,5,15), "stato": "Da iniziare", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T056", "progetto_id": "P008", "nome": "Coordinamento e PM bando ITAS", "fase": "Gestione", "ore_stimate": 60, "data_inizio": datetime(2026,2,15), "data_fine": datetime(2026,5,15), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D016", "predecessore": None},
    # ── P009 BANDO IMPRESE (Innovation, PM Domenica D017) — scouting agevolazioni,
    #    business plan. Staff Innovation (Domenica/Denise/Tetiana).
    {"id": "T053", "progetto_id": "P009", "nome": "Scouting agevolazioni imprese", "fase": "Scouting agevolazioni", "ore_stimate": 110, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,4,15), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D017", "predecessore": None},
    {"id": "T054", "progetto_id": "P009", "nome": "Business plan e piano economico", "fase": "Business plan", "ore_stimate": 90, "data_inizio": datetime(2026,4,16), "data_fine": datetime(2026,5,31), "stato": "Da iniziare", "profilo_richiesto": "Consultant", "dipendente_id": "D018", "predecessore": "T053"},
    {"id": "T055", "progetto_id": "P009", "nome": "Predisposizione domanda agevolazione", "fase": "Business plan", "ore_stimate": 40, "data_inizio": datetime(2026,4,16), "data_fine": datetime(2026,5,31), "stato": "Da iniziare", "profilo_richiesto": "Consultant", "dipendente_id": "D009", "predecessore": None},
    {"id": "T057", "progetto_id": "PC01", "nome": "Corso inglese — Helena", "fase": "Formazione", "ore_stimate": 72, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D004", "predecessore": None},
    {"id": "T058", "progetto_id": "PC01", "nome": "Corso inglese — Andrea", "fase": "Formazione", "ore_stimate": 72, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D005", "predecessore": None},
    {"id": "T059", "progetto_id": "PC01", "nome": "Corso inglese — Paolo", "fase": "Formazione", "ore_stimate": 72, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D006", "predecessore": None},
    {"id": "T060", "progetto_id": "PC01", "nome": "Corso inglese — Carolina C.", "fase": "Formazione", "ore_stimate": 72, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D007", "predecessore": None},
    {"id": "T061", "progetto_id": "PC01", "nome": "Corso inglese — Cosimo", "fase": "Formazione", "ore_stimate": 72, "data_inizio": datetime(2025,10,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D012", "predecessore": None},
    {"id": "T062", "progetto_id": "PC02", "nome": "Aggiornamento IA — Ludovica", "fase": "Formazione", "ore_stimate": 16, "data_inizio": datetime(2026,2,10), "data_fine": datetime(2026,2,12), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D011", "predecessore": None},
    {"id": "T063", "progetto_id": "PC02", "nome": "Aggiornamento IA — Helena", "fase": "Formazione", "ore_stimate": 16, "data_inizio": datetime(2026,2,10), "data_fine": datetime(2026,2,12), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D004", "predecessore": None},
    {"id": "T064", "progetto_id": "PC02", "nome": "Aggiornamento IA — Davide", "fase": "Formazione", "ore_stimate": 16, "data_inizio": datetime(2026,2,10), "data_fine": datetime(2026,2,12), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D003", "predecessore": None},
    {"id": "T065", "progetto_id": "PC02", "nome": "Aggiornamento IA — Roberto", "fase": "Formazione", "ore_stimate": 16, "data_inizio": datetime(2026,2,10), "data_fine": datetime(2026,2,12), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D002", "predecessore": None},
    {"id": "T066", "progetto_id": "PC03", "nome": "Excel avanzato — Tetiana", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,11,5), "data_fine": datetime(2025,11,20), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D009", "predecessore": None},
    {"id": "T067", "progetto_id": "PC03", "nome": "Excel avanzato — Nicola", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,11,5), "data_fine": datetime(2025,11,20), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D010", "predecessore": None},
    {"id": "T068", "progetto_id": "PC03", "nome": "Excel avanzato — Carolina J.", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,11,5), "data_fine": datetime(2025,11,20), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D014", "predecessore": None},
    {"id": "T069", "progetto_id": "PC03", "nome": "Excel avanzato — Daniele", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,11,5), "data_fine": datetime(2025,11,20), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D015", "predecessore": None},
    {"id": "T070", "progetto_id": "PC03", "nome": "Excel avanzato — Francesco", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,11,5), "data_fine": datetime(2025,11,20), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D013", "predecessore": None},
    {"id": "T071", "progetto_id": "PC04", "nome": "GDPR privacy — Francesco", "fase": "Formazione", "ore_stimate": 8, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,1,22), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D013", "predecessore": None},
    {"id": "T072", "progetto_id": "PC04", "nome": "GDPR privacy — Daniele", "fase": "Formazione", "ore_stimate": 8, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,1,22), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D015", "predecessore": None},
    {"id": "T073", "progetto_id": "PC04", "nome": "GDPR privacy — Cosimo", "fase": "Formazione", "ore_stimate": 8, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,1,22), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D012", "predecessore": None},
    {"id": "T074", "progetto_id": "PC04", "nome": "GDPR privacy — Carolina C.", "fase": "Formazione", "ore_stimate": 8, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,1,22), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D007", "predecessore": None},
    {"id": "T075", "progetto_id": "PC04", "nome": "GDPR privacy — Vincenzo", "fase": "Formazione", "ore_stimate": 8, "data_inizio": datetime(2026,1,15), "data_fine": datetime(2026,1,22), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D001", "predecessore": None},
    {"id": "T076", "progetto_id": "PC05", "nome": "Primo soccorso — Cosimo", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,9,15), "data_fine": datetime(2025,9,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D012", "predecessore": None},
    {"id": "T077", "progetto_id": "PC05", "nome": "Primo soccorso — Tetiana", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,9,15), "data_fine": datetime(2025,9,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D009", "predecessore": None},
    {"id": "T078", "progetto_id": "PC05", "nome": "Primo soccorso — Nicola", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,9,15), "data_fine": datetime(2025,9,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D010", "predecessore": None},
    {"id": "T079", "progetto_id": "PC05", "nome": "Primo soccorso — Helena", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,9,15), "data_fine": datetime(2025,9,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D004", "predecessore": None},
    {"id": "T080", "progetto_id": "PC05", "nome": "Primo soccorso — Garzillo", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,9,15), "data_fine": datetime(2025,9,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D008", "predecessore": None},
    {"id": "T081", "progetto_id": "PC05", "nome": "Primo soccorso — Carolina J.", "fase": "Formazione", "ore_stimate": 12, "data_inizio": datetime(2025,9,15), "data_fine": datetime(2025,9,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D014", "predecessore": None},
    {"id": "T082", "progetto_id": "PN01", "nome": "Sviluppo GANTT Agent", "fase": "Sviluppo", "ore_stimate": 862, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D011", "predecessore": None},
    {"id": "T083", "progetto_id": "PN02", "nome": "Sviluppo LOG ARIS Monitor", "fase": "Sviluppo", "ore_stimate": 470, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D011", "predecessore": None},
    {"id": "T084", "progetto_id": "PN03", "nome": "Progetto PM e pianificazione IA", "fase": "Sviluppo", "ore_stimate": 235, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "Consultant", "dipendente_id": "D011", "predecessore": None},
    {"id": "T085", "progetto_id": "PI01", "nome": "Direzione e sviluppo commerciale", "fase": "Continuativa", "ore_stimate": 494, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D001", "predecessore": None},
    {"id": "T086", "progetto_id": "PI02", "nome": "Relazioni istituzionali e clienti", "fase": "Continuativa", "ore_stimate": 494, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D001", "predecessore": None},
    {"id": "T087", "progetto_id": "PI03", "nome": "Supervisione progetti e qualità", "fase": "Continuativa", "ore_stimate": 494, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D001", "predecessore": None},
    {"id": "T088", "progetto_id": "PI04", "nome": "Architettura IT e standard tecnici", "fase": "Continuativa", "ore_stimate": 512, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D002", "predecessore": None},
    {"id": "T089", "progetto_id": "PI05", "nome": "Coordinamento tecnico e mentoring", "fase": "Continuativa", "ore_stimate": 512, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D002", "predecessore": None},
    {"id": "T090", "progetto_id": "PI05b", "nome": "Sviluppo avanzato e architettura applicativa", "fase": "Continuativa", "ore_stimate": 802, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D003", "predecessore": None},
    {"id": "T091", "progetto_id": "PI15b", "nome": "Formazione e aggiornamento ARIS", "fase": "Continuativa", "ore_stimate": 662, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D004", "predecessore": None},
    {"id": "T092", "progetto_id": "PI12", "nome": "Scouting bandi e networking", "fase": "Continuativa", "ore_stimate": 1180, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D005", "predecessore": None},
    {"id": "T093", "progetto_id": "PI12b", "nome": "Sviluppo offerte tecniche e prevendita", "fase": "Continuativa", "ore_stimate": 880, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D006", "predecessore": None},
    {"id": "T094", "progetto_id": "PI13", "nome": "Coordinamento interno e PMO", "fase": "Continuativa", "ore_stimate": 1210, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D007", "predecessore": None},
    {"id": "T095", "progetto_id": "PI15", "nome": "Formazione tecnica individuale", "fase": "Continuativa", "ore_stimate": 708, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D008", "predecessore": None},
    {"id": "T096", "progetto_id": "PI13b", "nome": "Supporto coordinamento e relazione cliente", "fase": "Continuativa", "ore_stimate": 986, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D009", "predecessore": None},
    {"id": "T097", "progetto_id": "PI14", "nome": "Supporto analisi e ricerca", "fase": "Continuativa", "ore_stimate": 1208, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D010", "predecessore": None},
    {"id": "T098", "progetto_id": "PI06", "nome": "Gestione HR e organizzazione", "fase": "Continuativa", "ore_stimate": 797, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D012", "predecessore": None},
    {"id": "T099", "progetto_id": "PI07", "nome": "Selezione e onboarding", "fase": "Continuativa", "ore_stimate": 797, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D012", "predecessore": None},
    {"id": "T100", "progetto_id": "PI08", "nome": "Controllo di gestione e reporting", "fase": "Continuativa", "ore_stimate": 807, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D013", "predecessore": None},
    {"id": "T101", "progetto_id": "PI09", "nome": "Pianificazione economico-finanziaria", "fase": "Continuativa", "ore_stimate": 807, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D013", "predecessore": None},
    {"id": "T102", "progetto_id": "PI11", "nome": "Documentazione e archivio", "fase": "Continuativa", "ore_stimate": 637, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D014", "predecessore": None},
    {"id": "T103", "progetto_id": "PI10", "nome": "Amministrazione corrente e fatturazione", "fase": "Continuativa", "ore_stimate": 1352, "data_inizio": datetime(2025,9,1), "data_fine": datetime(2026,6,30), "stato": "In corso", "profilo_richiesto": "", "dipendente_id": "D015", "predecessore": None},

    # ── P010 AIoT Smart City Maida (Improve, PM Francesco D013) — ente pubblico
    {"id": "T104", "progetto_id": "P010", "nome": "Analisi requisiti monitoraggio territorio", "fase": "Analisi", "ore_stimate": 120, "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,3,15), "stato": "In corso", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T105", "progetto_id": "P010", "nome": "Design architettura AIoT e sensoristica", "fase": "Design", "ore_stimate": 140, "data_inizio": datetime(2026,3,16), "data_fine": datetime(2026,5,15), "stato": "Da iniziare", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T104"},
    {"id": "T106", "progetto_id": "P010", "nome": "Sviluppo piattaforma raccolta dati sensori", "fase": "Sviluppo", "ore_stimate": 260, "data_inizio": datetime(2026,5,16), "data_fine": datetime(2026,9,30), "stato": "Da iniziare", "profilo_richiesto": "Senior IT Consultant", "dipendente_id": "D003", "predecessore": "T105"},
    {"id": "T107", "progetto_id": "P010", "nome": "Integrazione dashboard AI territoriale", "fase": "Sviluppo", "ore_stimate": 160, "data_inizio": datetime(2026,6,1), "data_fine": datetime(2026,10,31), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": "T105"},
    {"id": "T108", "progetto_id": "P010", "nome": "Gestione progetto Maida", "fase": "Gestione", "ore_stimate": 120, "data_inizio": datetime(2026,2,1), "data_fine": datetime(2026,12,31), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D013", "predecessore": None},

    # ── P011 AIoT Industria 4.0 Tecnomat (Improve, PM Francesco D013) — impresa
    {"id": "T109", "progetto_id": "P011", "nome": "Analisi processi produttivi Tecnomat", "fase": "Analisi", "ore_stimate": 110, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,4,15), "stato": "In corso", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": None},
    {"id": "T110", "progetto_id": "P011", "nome": "Design soluzione AIoT industriale", "fase": "Design", "ore_stimate": 130, "data_inizio": datetime(2026,4,16), "data_fine": datetime(2026,6,15), "stato": "Da iniziare", "profilo_richiesto": "Manager IT", "dipendente_id": "D002", "predecessore": "T109"},
    {"id": "T111", "progetto_id": "P011", "nome": "Sviluppo edge computing e manutenzione predittiva", "fase": "Sviluppo", "ore_stimate": 240, "data_inizio": datetime(2026,6,16), "data_fine": datetime(2026,10,15), "stato": "Da iniziare", "profilo_richiesto": "Senior IT Consultant", "dipendente_id": "D003", "predecessore": "T110"},
    {"id": "T112", "progetto_id": "P011", "nome": "Testing sul campo e collaudo", "fase": "Testing", "ore_stimate": 90, "data_inizio": datetime(2026,10,16), "data_fine": datetime(2026,11,30), "stato": "Da iniziare", "profilo_richiesto": "IT Consultant", "dipendente_id": "D004", "predecessore": "T111"},
    {"id": "T113", "progetto_id": "P011", "nome": "Gestione progetto Tecnomat", "fase": "Gestione", "ore_stimate": 100, "data_inizio": datetime(2026,3,1), "data_fine": datetime(2026,11,30), "stato": "In corso", "profilo_richiesto": "Senior Consultant", "dipendente_id": "D013", "predecessore": None},
])


TASKS = TASKS.fillna({"predecessore": ""})

# ═══════════════════════════════════════════════════════════════════════
# RI-ANCORAGGIO TEMPORALE A date.today() (piano ibrido, 20/07/2026)
# ═══════════════════════════════════════════════════════════════════════
# Prima le date erano assolute (primavera 2026): col passare dei giorni i
# progetti "scadevano" e gli stati (hardcoded) divergevano dalle date. Qui
# rendiamo TUTTE le date relative a OGGI, così il seed resta sempre attuale,
# e DERIVIAMO gli stati dalle date (niente più stati hardcoded incoerenti).
#
# Due trattamenti:
#   • COMMERCIALI/BANDI (P001..P011): shift rolling (l'ancora 2026-07-20 è il
#     giorno per cui le finestre legacy erano già ben distribuite — verificato:
#     nessuno shift le bilancia meglio) + 2 fix mirati per centrare le fasce.
#   • INTERNI (tipologia 'interna'): attività ricorrenti → finestra
#     continuativa che CONTIENE oggi (così i task risultano attivi stasettimana).
#
# Nomenclatura stati (CHECK constraint DB):
#   Progetto: Bozza / Da iniziare / In esecuzione / Sospeso / Completato / Annullato
#   Task:     Da iniziare / In corso / Completato / Bloccato / Sospeso / Annullato
# Le fasce avviati/in corso/chiusura sono POSIZIONI temporali → progetto
# "In esecuzione" (cambia solo il mix di stati dei task); conclusi → "Completato".
from datetime import date as _date

OGGI = _date.today()
_ANCHOR = _date(2026, 7, 20)          # 'oggi' di riferimento delle finestre legacy
_SHIFT = OGGI - _ANCHOR               # timedelta; oggi ≡ 0 → rolling, sempre attuale
_oggi_ts = pd.Timestamp(OGGI)

def _ts(d):
    return pd.Timestamp(d)

_interni = set(PROGETTI[PROGETTI["tipologia"] == "interna"]["id"])

# ── 1) COMMERCIALI: shift rolling su progetti e task ──
_mask_p_comm = ~PROGETTI["id"].isin(_interni)
_mask_t_comm = ~TASKS["progetto_id"].isin(_interni)
for _col in ("data_inizio", "data_fine"):
    PROGETTI.loc[_mask_p_comm, _col] = PROGETTI.loc[_mask_p_comm, _col] + _SHIFT
    TASKS.loc[_mask_t_comm, _col] = TASKS.loc[_mask_t_comm, _col] + _SHIFT

# ── 2) FIX MIRATI (2) per popolare tutte le fasce ──
# P004 → CHIUSURA: fine tra ~3 settimane (i suoi task restano nel passato →
#        quasi tutti Completato, come ci si aspetta da un progetto in chiusura).
# P009 → AVVIATO: inizio ~2 settimane fa; riallineo i suoi 3 task (1 in corso,
#        2 da iniziare) perché "appena avviato" sia coerente.
PROGETTI.loc[PROGETTI["id"] == "P004", "data_fine"] = _ts(OGGI + timedelta(days=21))
PROGETTI.loc[PROGETTI["id"] == "P009", "data_inizio"] = _ts(OGGI - timedelta(days=14))
_p009_task_win = {
    "T053": (OGGI - timedelta(days=10), OGGI + timedelta(days=20)),   # In corso
    "T054": (OGGI + timedelta(days=21), OGGI + timedelta(days=55)),   # Da iniziare
    "T055": (OGGI + timedelta(days=21), OGGI + timedelta(days=55)),   # Da iniziare
}
for _tid, (_di, _df) in _p009_task_win.items():
    TASKS.loc[TASKS["id"] == _tid, "data_inizio"] = _ts(_di)
    TASKS.loc[TASKS["id"] == _tid, "data_fine"] = _ts(_df)

# ── 3) INTERNI: finestra continuativa [OGGI-30 sett, OGGI+12 sett] ──
# Mansioni/formazione/innovazione sono ricorrenti: task = finestra del progetto
# → tutti In corso QUESTA settimana (requisito: i 4 task di D011 attivi ora).
_int_inizio = _ts(OGGI - timedelta(weeks=30))
_int_fine = _ts(OGGI + timedelta(weeks=12))
_mask_t_int = TASKS["progetto_id"].isin(_interni)
for _col, _val in (("data_inizio", _int_inizio), ("data_fine", _int_fine)):
    PROGETTI.loc[PROGETTI["id"].isin(_interni), _col] = _val
    TASKS.loc[_mask_t_int, _col] = _val

# ── 4) D011: un task su progetto COMMERCIALE (badge blu accanto ai grigi) ──
# Oltre ai 4 task interni (T062, T082-84), così la Consuntivazione di Ludovica
# mostra sia interne (grigio) sia progetto (blu) e si testa il raggruppamento.
_t_ludovica = pd.DataFrame([{
    "id": "T114", "progetto_id": "P002",
    "nome": "Supporto testing piattaforma GRC", "fase": "Testing",
    "ore_stimate": 40,
    "data_inizio": _ts(OGGI - timedelta(days=10)),
    "data_fine": _ts(OGGI + timedelta(days=40)),
    "stato": "In corso", "profilo_richiesto": "Consultant",
    "dipendente_id": "D011", "predecessore": "",
}])
TASKS = pd.concat([TASKS, _t_ludovica], ignore_index=True)

# ── 5) EROSIONE: ore_pianificate ≠ ore_stimate su 3 progetti ──
# Prima coincidevano sempre → in Economia le due erosioni erano identiche.
# Simuliamo revisioni di piano del PM: P002 +15%, P004 −15%, P010 +10%.
TASKS["ore_pianificate"] = TASKS["ore_stimate"].astype(float)
for _pid, _factor in (("P002", 1.15), ("P004", 0.85), ("P010", 1.10)):
    _idx = TASKS["progetto_id"] == _pid
    TASKS.loc[_idx, "ore_pianificate"] = (TASKS.loc[_idx, "ore_stimate"] * _factor).round()

# ── 6) STATI DERIVATI dalle date ──
_stati_speciali = {"P006": "Sospeso", "P007": "Bozza"}   # fuori dalle 4 fasce

def _stato_progetto(row):
    if row["id"] in _interni:
        return "In esecuzione"
    if row["id"] in _stati_speciali:
        return _stati_speciali[row["id"]]
    return "Completato" if row["data_fine"] < _oggi_ts else "In esecuzione"

PROGETTI["stato"] = PROGETTI.apply(_stato_progetto, axis=1)
_stato_prog = dict(zip(PROGETTI["id"], PROGETTI["stato"]))

def _stato_task(row):
    sp = _stato_prog.get(row["progetto_id"], "In esecuzione")
    if sp == "Completato":
        return "Completato"                       # progetto concluso → tutti i task chiusi
    if sp == "Bozza":
        return "Da iniziare"
    if sp == "Sospeso":                            # storia preservata: fatti → Completato
        return "Completato" if row["data_fine"] < _oggi_ts else "Sospeso"
    di, df = row["data_inizio"], row["data_fine"]  # progetto In esecuzione → per data
    if df < _oggi_ts:
        return "Completato"
    if di > _oggi_ts:
        return "Da iniziare"
    return "In corso"

TASKS["stato"] = TASKS.apply(_stato_task, axis=1)

# ── 7) ECCEZIONI "in ritardo" (3): finestra passata ma ancora In corso ──
# Fanno scattare gli alert di ritardo. Solo su progetti In esecuzione.
for _tid in ("T011", "T022", "T041"):
    TASKS.loc[TASKS["id"] == _tid, "stato"] = "In corso"

# ── CONSUNTIVI (ore effettivamente lavorate) ───────────────────────────

def genera_consuntivi():
    """Genera consuntivi settimanali realistici con buchi.

    Ancorato a OGGI: si generano consuntivi solo per le settimane FINO a oggi
    (mai future). Le ore settimanali sono proporzionate al budget del task
    spalmato sulla sua durata (ore_pianificate / n_settimane_totali), così il
    consumato accumulato è proporzionale all'avanzamento TEMPORALE: un task
    partito da 3 settimane accumula ~3 settimane di ore, non l'intero budget.
    """
    records = []
    oggi = _oggi_ts  # pd.Timestamp(date.today()) — coerente col ri-ancoraggio

    for _, task in TASKS.iterrows():
        # Solo task avviati: In corso o già Completato. Da iniziare / Sospeso /
        # Bloccato non producono consuntivi (⇒ niente settimane future).
        if task["stato"] not in ("Completato", "In corso"):
            continue

        inizio = task["data_inizio"]
        if inizio > oggi:
            continue
        fine_cap = min(task["data_fine"], oggi)

        # Ritmo settimanale ~ budget / durata totale (min 1 settimana).
        settimane_totali = max(1, ((task["data_fine"] - inizio).days // 7) + 1)
        ritmo = float(task["ore_pianificate"]) / settimane_totali

        settimana = inizio
        while settimana <= fine_cap:
            lun = settimana - timedelta(days=settimana.weekday())
            compilato = random.random() > 0.15

            if compilato:
                # jitter attorno al ritmo; almeno 1h, arrotondato a interi.
                ore = max(1, round(ritmo * random.uniform(0.5, 1.4)))
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


