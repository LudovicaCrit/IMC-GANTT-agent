"""
Test del motore scenario_engine.

Simula una catena di 4 task con dipendenze FS (Fine → Inizio):
  Analisi → Design → Sviluppo → Testing

Se "Analisi" slitta di 10 giorni, tutti i successori devono slittare di 10 giorni.
Poi testa il cambia_focus: se la persona su "Sviluppo" si concentra al 100%
su un altro progetto per 2 settimane, lo sviluppo slitta.
"""

import pandas as pd
from datetime import date, datetime
from scenario_engine import (
    simula_scenario, _giorni_lavorativi, _aggiungi_giorni_lavorativi,
    propaga_cascata, _to_date
)


def test_utilita():
    """Test funzioni di utilità."""
    # Giorni lavorativi: lun 2 mar → ven 6 mar = 5 giorni
    assert _giorni_lavorativi(date(2026, 3, 2), date(2026, 3, 6)) == 5

    # Aggiungi 5 giorni lavorativi a lunedì 2 mar → lunedì 9 mar
    # lun 2 → mar 3 (1) → mer 4 (2) → gio 5 (3) → ven 6 (4) → salta sab/dom → lun 9 (5)
    assert _aggiungi_giorni_lavorativi(date(2026, 3, 2), 5) == date(2026, 3, 9)

    print("✅ Test utilità OK")


def test_cascata_semplice():
    """Test propagazione a cascata lineare: A → B → C → D"""
    tasks = {
        "T001": {
            "id": "T001", "nome": "Analisi", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 2), "data_fine": date(2026, 3, 13),  # 10 gg lav
            "ore_stimate": 80, "stato": "In corso", "dipendente_id": "D001",
            "predecessore": "",
        },
        "T002": {
            "id": "T002", "nome": "Design", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 16), "data_fine": date(2026, 3, 27),  # 10 gg lav
            "ore_stimate": 60, "stato": "Da iniziare", "dipendente_id": "D002",
            "predecessore": "T001",
        },
        "T003": {
            "id": "T003", "nome": "Sviluppo", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 30), "data_fine": date(2026, 4, 24),  # 20 gg lav
            "ore_stimate": 160, "stato": "Da iniziare", "dipendente_id": "D001",
            "predecessore": "T002",
        },
        "T004": {
            "id": "T004", "nome": "Testing", "progetto_id": "P001",
            "data_inizio": date(2026, 4, 27), "data_fine": date(2026, 5, 8),  # 10 gg lav
            "ore_stimate": 80, "stato": "Da iniziare", "dipendente_id": "D003",
            "predecessore": "T003",
        },
    }

    # Sposta Analisi: data_fine da 13 mar → 27 mar (+10 gg lavorativi)
    tasks["T001"]["data_fine"] = date(2026, 3, 27)

    modificati = propaga_cascata(tasks, {"T001"})

    # Verifica che tutti siano slittati
    assert "T002" in modificati, "Design dovrebbe essere slittato"
    assert "T003" in modificati, "Sviluppo dovrebbe essere slittato"
    assert "T004" in modificati, "Testing dovrebbe essere slittato"

    # Design: dovrebbe iniziare il 30 mar (giorno lav dopo 27 mar)
    assert tasks["T002"]["data_inizio"] == date(2026, 3, 30), \
        f"Design inizio: atteso 30/03, ottenuto {tasks['T002']['data_inizio']}"

    print(f"  Analisi:  {tasks['T001']['data_inizio']} → {tasks['T001']['data_fine']}")
    print(f"  Design:   {tasks['T002']['data_inizio']} → {tasks['T002']['data_fine']}")
    print(f"  Sviluppo: {tasks['T003']['data_inizio']} → {tasks['T003']['data_fine']}")
    print(f"  Testing:  {tasks['T004']['data_inizio']} → {tasks['T004']['data_fine']}")
    print("✅ Test cascata semplice OK")


def test_simula_cambia_focus():
    """Test: persona si concentra al 100% su un progetto → task su altro progetto slittano."""
    tasks_data = [
        {"id": "T010", "progetto_id": "P001", "nome": "Backend FHIR",
         "fase": "Sviluppo", "ore_stimate": 160,
         "data_inizio": datetime(2026, 3, 2), "data_fine": datetime(2026, 4, 10),
         "stato": "In corso", "profilo_richiesto": "Tecnico Senior",
         "dipendente_id": "D001", "predecessore": ""},
        {"id": "T011", "progetto_id": "P002", "nome": "Catalogo prodotti",
         "fase": "Sviluppo", "ore_stimate": 120,
         "data_inizio": datetime(2026, 3, 9), "data_fine": datetime(2026, 4, 3),
         "stato": "In corso", "profilo_richiesto": "Tecnico Senior",
         "dipendente_id": "D001", "predecessore": ""},
        {"id": "T012", "progetto_id": "P002", "nome": "Testing catalogo",
         "fase": "Testing", "ore_stimate": 60,
         "data_inizio": datetime(2026, 4, 6), "data_fine": datetime(2026, 4, 17),
         "stato": "Da iniziare", "profilo_richiesto": "Tecnico Mid",
         "dipendente_id": "D002", "predecessore": "T011"},
    ]
    tasks_df = pd.DataFrame(tasks_data)

    dip_data = [
        {"id": "D001", "nome": "Marco Bianchi", "profilo": "Tecnico Senior",
         "ore_sett": 40, "costo_ora": 45, "competenze": []},
        {"id": "D002", "nome": "Laura Verdi", "profilo": "Tecnico Mid",
         "ore_sett": 40, "costo_ora": 35, "competenze": []},
    ]
    dip_df = pd.DataFrame(dip_data)

    proj_data = [
        {"id": "P001", "nome": "Digital Health Records", "cliente": "ASL Bari",
         "stato": "In esecuzione", "data_inizio": datetime(2026, 1, 1),
         "data_fine": datetime(2026, 6, 30), "budget_ore": 500, "valore_contratto": 80000,
         "descrizione": "", "fase_corrente": ""},
        {"id": "P002", "nome": "Catalogo Industriale", "cliente": "Duferco",
         "stato": "In esecuzione", "data_inizio": datetime(2026, 2, 1),
         "data_fine": datetime(2026, 4, 30), "budget_ore": 300, "valore_contratto": 50000,
         "descrizione": "", "fase_corrente": ""},
    ]
    proj_df = pd.DataFrame(proj_data)

    # Marco (D001) si concentra al 100% su P001 (Digital Health) per 2 settimane
    # → il suo task su P002 (Catalogo prodotti) dovrebbe slittare
    # → e a cascata, Testing catalogo (D002) dovrebbe slittare
    modifiche = [{
        "tipo": "cambia_focus",
        "dipendente_id": "D001",
        "progetto_focus": "P001",
        "percentuale": 100,
        "durata_settimane": 2,
        "data_inizio_focus": "2026-03-09",
    }]

    risultato = simula_scenario(tasks_df, dip_df, proj_df, modifiche)

    print(f"\n  Task modificati: {len(risultato['task_modificati'])}")
    print(f"  Conseguenze: {len(risultato['conseguenze'])}")
    for c in risultato["conseguenze"]:
        print(f"    [{c['gravita'].upper()}] {c['testo']}")

    # Verifica che il catalogo sia slittato
    assert "T011" in risultato["task_modificati"], \
        "Il task Catalogo prodotti (T011) dovrebbe slittare"

    # Verifica cascata: Testing catalogo dovrebbe slittare perché dipende da T011
    assert "T012" in risultato["task_modificati"], \
        "Il task Testing catalogo (T012) dovrebbe slittare a cascata"

    print("\n✅ Test cambia_focus + cascata OK")


def test_scadenza_bucata():
    """Test: verifica che le scadenze bucate vengano segnalate."""
    tasks_data = [
        {"id": "T020", "progetto_id": "P003", "nome": "Sviluppo portale",
         "fase": "Sviluppo", "ore_stimate": 200,
         "data_inizio": datetime(2026, 3, 1), "data_fine": datetime(2026, 4, 15),
         "stato": "In corso", "profilo_richiesto": "Tecnico Senior",
         "dipendente_id": "D001", "predecessore": ""},
    ]
    tasks_df = pd.DataFrame(tasks_data)

    dip_data = [
        {"id": "D001", "nome": "Marco Bianchi", "profilo": "Tecnico Senior",
         "ore_sett": 40, "costo_ora": 45, "competenze": []},
    ]
    dip_df = pd.DataFrame(dip_data)

    proj_data = [
        {"id": "P003", "nome": "Portale Turismo", "cliente": "Regione Puglia",
         "stato": "In esecuzione", "data_inizio": datetime(2026, 1, 1),
         "data_fine": datetime(2026, 4, 20), "budget_ore": 400, "valore_contratto": 60000,
         "descrizione": "", "fase_corrente": ""},
    ]
    proj_df = pd.DataFrame(proj_data)

    # Sposta il task a fine maggio → sfora la scadenza del progetto (20 aprile)
    modifiche = [{
        "tipo": "sposta_task",
        "task_id": "T020",
        "nuova_fine": "2026-05-15",
    }]

    risultato = simula_scenario(tasks_df, dip_df, proj_df, modifiche)

    assert len(risultato["scadenze_bucate"]) > 0, \
        "Dovrebbe segnalare la scadenza bucata del Portale Turismo"

    for sb in risultato["scadenze_bucate"]:
        print(f"  ⚠️ {sb['progetto']}: sfora di {sb['giorni_sforo']} giorni")

    print("✅ Test scadenza bucata OK")


if __name__ == "__main__":
    print("=" * 60)
    print("TEST SCENARIO ENGINE")
    print("=" * 60)
    test_utilita()
    print()
    test_cascata_semplice()
    print()
    test_simula_cambia_focus()
    print()
    test_scadenza_bucata()
    print()
    print("=" * 60)
    print("TUTTI I TEST PASSATI ✅")