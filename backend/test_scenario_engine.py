"""
Test del motore scenario_engine.

Simula una catena di 4 task con dipendenze FS (Fine → Inizio):
  Analisi → Design → Sviluppo → Testing

Se "Analisi" slitta di 10 giorni, tutti i successori devono slittare di 10 giorni.
Poi testa il cambia_focus: se la persona su "Sviluppo" si concentra al 100%
su un altro progetto per 2 settimane, lo sviluppo slitta.
"""

import logging

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
            "dipendenze": [],
        },
        "T002": {
            "id": "T002", "nome": "Design", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 16), "data_fine": date(2026, 3, 27),  # 10 gg lav
            "ore_stimate": 60, "stato": "Da iniziare", "dipendente_id": "D002",
            "dipendenze": [{"pred": "T001", "tipo": "FS"}],
        },
        "T003": {
            "id": "T003", "nome": "Sviluppo", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 30), "data_fine": date(2026, 4, 24),  # 20 gg lav
            "ore_stimate": 160, "stato": "Da iniziare", "dipendente_id": "D001",
            "dipendenze": [{"pred": "T002", "tipo": "FS"}],
        },
        "T004": {
            "id": "T004", "nome": "Testing", "progetto_id": "P001",
            "data_inizio": date(2026, 4, 27), "data_fine": date(2026, 5, 8),  # 10 gg lav
            "ore_stimate": 80, "stato": "Da iniziare", "dipendente_id": "D003",
            "dipendenze": [{"pred": "T003", "tipo": "FS"}],
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
         "dipendente_id": "D001", "dipendenze": []},
        {"id": "T011", "progetto_id": "P002", "nome": "Catalogo prodotti",
         "fase": "Sviluppo", "ore_stimate": 120,
         "data_inizio": datetime(2026, 3, 9), "data_fine": datetime(2026, 4, 3),
         "stato": "In corso", "profilo_richiesto": "Tecnico Senior",
         "dipendente_id": "D001", "dipendenze": []},
        {"id": "T012", "progetto_id": "P002", "nome": "Testing catalogo",
         "fase": "Testing", "ore_stimate": 60,
         "data_inizio": datetime(2026, 4, 6), "data_fine": datetime(2026, 4, 17),
         "stato": "Da iniziare", "profilo_richiesto": "Tecnico Mid",
         "dipendente_id": "D002", "dipendenze": [{"pred": "T011", "tipo": "FS"}]},
    ]

    dip_data = [
        {"id": "D001", "nome": "Marco Bianchi", "profilo": "Tecnico Senior",
         "ore_sett": 40, "costo_ora": 45, "competenze": []},
        {"id": "D002", "nome": "Laura Verdi", "profilo": "Tecnico Mid",
         "ore_sett": 40, "costo_ora": 35, "competenze": []},
    ]

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

    risultato = simula_scenario(tasks_data, dip_data, proj_data, modifiche)

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
         "dipendente_id": "D001", "dipendenze": []},
    ]

    dip_data = [
        {"id": "D001", "nome": "Marco Bianchi", "profilo": "Tecnico Senior",
         "ore_sett": 40, "costo_ora": 45, "competenze": []},
    ]

    proj_data = [
        {"id": "P003", "nome": "Portale Turismo", "cliente": "Regione Puglia",
         "stato": "In esecuzione", "data_inizio": datetime(2026, 1, 1),
         "data_fine": datetime(2026, 4, 20), "budget_ore": 400, "valore_contratto": 60000,
         "descrizione": "", "fase_corrente": ""},
    ]

    # Sposta il task a fine maggio → sfora la scadenza del progetto (20 aprile)
    modifiche = [{
        "tipo": "sposta_task",
        "task_id": "T020",
        "nuova_fine": "2026-05-15",
    }]

    risultato = simula_scenario(tasks_data, dip_data, proj_data, modifiche)

    assert len(risultato["scadenze_bucate"]) > 0, \
        "Dovrebbe segnalare la scadenza bucata del Portale Turismo"

    for sb in risultato["scadenze_bucate"]:
        print(f"  ⚠️ {sb['progetto']}: sfora di {sb['giorni_sforo']} giorni")

    print("✅ Test scadenza bucata OK")


# ══════════════════════════════════════════════════════════════════════
# DIPENDENZE NON-FS — comportamento-ponte (Gruppo B)
# ══════════════════════════════════════════════════════════════════════
# Oggi il motore implementa SOLO la logica temporale FS. I tipi SS/FF/SF
# vengono trattati come FS e loggano un warning informativo. Questi test
# costruiscono task e dipendenze IN MEMORIA (no seed) e asseriscono il
# comportamento-ponte + il CONTENUTO del warning. Sono SEMPRE attivi (mai
# skip): quando arriverà la logica SS/FF/SF (Gruppo C) basterà cambiare
# l'asserzione sulla data attesa, non la struttura del test.

class _CatturaWarning(logging.Handler):
    """Handler minimale che accumula i record di log emessi dal motore.

    Indipendente da `caplog`: funziona sia sotto pytest sia col runner __main__.
    """
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _propaga_con_log(tasks, modificati):
    """Esegue propaga_cascata catturando i warning del logger 'scenario_engine'.

    Ritorna (insieme_modificati, lista_messaggi_warning_formattati).
    """
    handler = _CatturaWarning()
    handler.setLevel(logging.WARNING)
    eng_logger = logging.getLogger("scenario_engine")
    livello_orig, propaga_orig = eng_logger.level, eng_logger.propagate
    eng_logger.addHandler(handler)
    eng_logger.setLevel(logging.WARNING)
    eng_logger.propagate = False  # evita rumore su stderr durante i test
    try:
        risultato = propaga_cascata(tasks, modificati)
    finally:
        eng_logger.removeHandler(handler)
        eng_logger.setLevel(livello_orig)
        eng_logger.propagate = propaga_orig
    messaggi = [r.getMessage() for r in handler.records
                if r.levelno == logging.WARNING]
    return risultato, messaggi


def _coppia_pred_succ(tipo):
    """Catena di 2 task (T100→T101) con dipendenza di tipo `tipo`.

    Stesse date di test_cascata_semplice, così la regola FS dà inizio
    successore = 30/03 quando il predecessore finisce il 27/03.
    """
    return {
        "T100": {
            "id": "T100", "nome": "Predecessore", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 2), "data_fine": date(2026, 3, 13),
            "ore_stimate": 80, "stato": "In corso", "dipendente_id": "D001",
            "dipendenze": [],
        },
        "T101": {
            "id": "T101", "nome": "Successore", "progetto_id": "P001",
            "data_inizio": date(2026, 3, 16), "data_fine": date(2026, 3, 27),
            "ore_stimate": 60, "stato": "Da iniziare", "dipendente_id": "D002",
            "dipendenze": [{"pred": "T100", "tipo": tipo}],
        },
    }


def test_dipendenza_non_fs_trattata_come_fs():
    """SS/FF/SF → trattati come FS (ponte) + warning che cita tipo e i due id."""
    for tipo in ("SS", "FF", "SF"):
        tasks = _coppia_pred_succ(tipo)
        # Sposta in avanti la fine del predecessore (come test_cascata_semplice)
        tasks["T100"]["data_fine"] = date(2026, 3, 27)

        modificati, warnings = _propaga_con_log(tasks, {"T100"})

        # Ponte: il successore slitta ESATTAMENTE come farebbe una dip. FS.
        # 👉 Gruppo C: qui cambierà solo la data attesa per ciascun tipo.
        assert "T101" in modificati, \
            f"[{tipo}] il successore dovrebbe slittare (trattato come FS)"
        assert tasks["T101"]["data_inizio"] == date(2026, 3, 30), \
            f"[{tipo}] inizio atteso 30/03 (regola FS), ottenuto {tasks['T101']['data_inizio']}"

        # Il warning deve esistere e citare il tipo e i DUE id corretti.
        rilevanti = [m for m in warnings
                     if tipo in m and "T100" in m and "T101" in m]
        assert rilevanti, \
            f"[{tipo}] atteso un warning che cita {tipo}, T100 e T101; ottenuti: {warnings}"
        print(f"  [{tipo}] ponte FS OK + warning: {rilevanti[0]}")

    print("✅ Test dipendenze non-FS (ponte FS + warning) OK")


def test_dipendenza_fs_non_logga_warning():
    """Controprova: una dipendenza FS slitta ma NON emette alcun warning."""
    tasks = _coppia_pred_succ("FS")
    tasks["T100"]["data_fine"] = date(2026, 3, 27)

    modificati, warnings = _propaga_con_log(tasks, {"T100"})

    assert "T101" in modificati, "FS: il successore dovrebbe slittare"
    assert warnings == [], f"FS non deve loggare warning, ottenuti: {warnings}"

    print("✅ Test dipendenza FS senza warning OK")


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
    test_dipendenza_non_fs_trattata_come_fs()
    print()
    test_dipendenza_fs_non_logga_warning()
    print()
    print("=" * 60)
    print("TUTTI I TEST PASSATI ✅")