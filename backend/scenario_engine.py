"""
IMC-Group GANTT Agent — Motore Ricalcolo a Cascata

Questo modulo è il cuore del "tavolo di lavoro": dato un insieme di modifiche
(spostamento date, cambio focus persona, ecc.), calcola l'impatto a cascata
su tutti i GANTT collegati tramite dipendenze e persone condivise.

Principio: NON modifica il database. Lavora su copie in memoria.
Solo /api/scenario/conferma scrive nel db.

Tre funzioni principali:
  1. propaga_cascata()    — ricalcola date dei task dipendenti, ricorsivamente
  2. simula_scenario()    — punto d'ingresso: applica modifiche + cascata + saturazioni
  3. genera_conseguenze() — produce lista leggibile di ciò che cambia
"""

from datetime import datetime, timedelta, date
from copy import deepcopy
import math


# ══════════════════════════════════════════════════════════════════════
# UTILITÀ
# ══════════════════════════════════════════════════════════════════════

def _to_date(d):
    """Converte qualsiasi formato data in date."""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str) and d:
        return datetime.fromisoformat(d).date()
    return None


def _giorni_lavorativi(data_inizio, data_fine):
    """Conta i giorni lavorativi (lun-ven) tra due date, estremi inclusi."""
    if not data_inizio or not data_fine:
        return 0
    d1, d2 = _to_date(data_inizio), _to_date(data_fine)
    if d2 < d1:
        return 0
    giorni = 0
    corrente = d1
    while corrente <= d2:
        if corrente.weekday() < 5:  # lun=0, ven=4
            giorni += 1
        corrente += timedelta(days=1)
    return max(1, giorni)


def _aggiungi_giorni_lavorativi(data_partenza, n_giorni_lav):
    """Aggiunge N giorni lavorativi a una data (salta weekend)."""
    d = _to_date(data_partenza)
    aggiunti = 0
    while aggiunti < n_giorni_lav:
        d += timedelta(days=1)
        if d.weekday() < 5:
            aggiunti += 1
    return d


def _lunedi_settimana(d):
    """Restituisce il lunedì della settimana contenente d."""
    d = _to_date(d)
    return d - timedelta(days=d.weekday())


# ══════════════════════════════════════════════════════════════════════
# 1. PROPAGAZIONE A CASCATA DELLE DIPENDENZE
# ══════════════════════════════════════════════════════════════════════

def propaga_cascata(tasks, task_ids_modificati):
    """
    Dato un dizionario di task (clonati in memoria) e un set di ID
    dei task le cui date sono state modificate, propaga le modifiche
    a tutti i task che dipendono da essi, ricorsivamente.

    I task sono dict con almeno:
      id, predecessore, data_inizio, data_fine, ore_stimate, stato

    Il campo 'predecessore' è un singolo ID task (es. "T045").
    Il tipo di dipendenza è assunto FS (Fine → Inizio) per i task
    esistenti nel db. In futuro si può estendere con un campo tipo_dipendenza.

    Modifica i task IN PLACE e restituisce il set di tutti gli ID modificati
    (inclusi quelli propagati).
    """
    # Costruisci indice: predecessore → lista di task successori
    successori = {}  # { id_predecessore: [task_successore, ...] }
    for t in tasks.values():
        pred = t.get("predecessore", "")
        if pred and pred in tasks:
            if pred not in successori:
                successori[pred] = []
            successori[pred].append(t["id"])

    tutti_modificati = set(task_ids_modificati)
    coda = list(task_ids_modificati)

    while coda:
        pred_id = coda.pop(0)
        pred = tasks[pred_id]
        pred_fine = _to_date(pred["data_fine"])

        if not pred_fine:
            continue

        for succ_id in successori.get(pred_id, []):
            succ = tasks[succ_id]

            # Salta task completati — non li spostiamo
            if succ.get("stato") == "Completato":
                continue

            succ_inizio_old = _to_date(succ["data_inizio"])
            succ_fine_old = _to_date(succ["data_fine"])

            if not succ_inizio_old or not succ_fine_old:
                continue

            # Calcola durata originale in giorni lavorativi
            durata_lav = _giorni_lavorativi(succ_inizio_old, succ_fine_old)

            # FS: il successore inizia il giorno lavorativo dopo la fine del predecessore
            nuovo_inizio = _aggiungi_giorni_lavorativi(pred_fine, 1)

            # Il successore non può iniziare prima di quando iniziava
            # (la cascata sposta solo in avanti, non indietro)
            if nuovo_inizio <= succ_inizio_old:
                continue

            # Nuova fine: mantieni la stessa durata lavorativa
            nuova_fine = _aggiungi_giorni_lavorativi(nuovo_inizio, durata_lav - 1)

            succ["data_inizio"] = nuovo_inizio
            succ["data_fine"] = nuova_fine

            if succ_id not in tutti_modificati:
                tutti_modificati.add(succ_id)
                coda.append(succ_id)  # propaga ulteriormente

    return tutti_modificati


# ══════════════════════════════════════════════════════════════════════
# 2. SIMULAZIONE SCENARIO COMPLETO
# ══════════════════════════════════════════════════════════════════════

def simula_scenario(tasks_df, dipendenti_df, progetti_df, modifiche, data_oggi=None):
    """
    Punto d'ingresso principale.

    Parametri:
      tasks_df:      DataFrame dei task (da TASKS)
      dipendenti_df: DataFrame dei dipendenti (da DIPENDENTI)
      progetti_df:   DataFrame dei progetti (da PROGETTI)
      modifiche:     lista di dict, ciascuno con:
                       tipo: "sposta_task" | "cambia_focus"

                       Per "sposta_task":
                         task_id, nuovo_inizio (opt), nuova_fine (opt),
                         nuove_ore (opt)

                       Per "cambia_focus":
                         dipendente_id, progetto_focus, percentuale (0-100),
                         durata_settimane, data_inizio_focus (opt)

      data_oggi:     data corrente (default: 2026-03-09 per coerenza col sistema)

    Restituisce:
      {
        "tasks_prima":    dict { id: task_originale },
        "tasks_dopo":     dict { id: task_modificato },
        "task_modificati": set di ID task le cui date sono cambiate,
        "conseguenze":    lista di conseguenze leggibili,
        "saturazioni":    { dipendente_id: { settimana: {prima, dopo, dettaglio} } },
        "scadenze_bucate": [{ progetto, scadenza, ultimo_task_fine, giorni_sforo }],
      }
    """
    if data_oggi is None:
        data_oggi = date(2026, 3, 9)
    data_oggi = _to_date(data_oggi)

    # ── Clona i task in memoria ──
    tasks_prima = {}
    tasks_dopo = {}
    for _, row in tasks_df.iterrows():
        t = row.to_dict()
        tasks_prima[t["id"]] = deepcopy(t)
        tasks_dopo[t["id"]] = deepcopy(t)

    # Indici utili
    dipendenti = {}
    for _, row in dipendenti_df.iterrows():
        dipendenti[row["id"]] = row.to_dict()

    progetti = {}
    for _, row in progetti_df.iterrows():
        progetti[row["id"]] = row.to_dict()

    # ── Applica modifiche primarie ──
    task_ids_modificati = set()

    for mod in modifiche:
        tipo = mod.get("tipo", "")

        if tipo == "sposta_task":
            tid = mod["task_id"]
            if tid not in tasks_dopo:
                continue
            task = tasks_dopo[tid]

            if "nuova_fine" in mod and mod["nuova_fine"]:
                task["data_fine"] = _to_date(mod["nuova_fine"])
            if "nuovo_inizio" in mod and mod["nuovo_inizio"]:
                task["data_inizio"] = _to_date(mod["nuovo_inizio"])
            if "nuove_ore" in mod and mod["nuove_ore"]:
                task["ore_stimate"] = mod["nuove_ore"]

            task_ids_modificati.add(tid)

        elif tipo == "cambia_focus":
            # Una persona si concentra su un progetto per N settimane
            # → i suoi task su ALTRI progetti si allungano
            did = mod["dipendente_id"]
            progetto_focus = mod["progetto_focus"]
            percentuale = mod.get("percentuale", 100)  # % dedicata al focus
            durata_sett = mod.get("durata_settimane", 2)
            inizio_focus = _to_date(mod.get("data_inizio_focus")) or data_oggi

            fine_focus = inizio_focus + timedelta(weeks=durata_sett)

            # Disponibilità residua per altri progetti durante il focus
            disponibilita_residua = (100 - percentuale) / 100.0

            # Trova i task di questa persona su ALTRI progetti, attivi nel periodo
            for tid, task in tasks_dopo.items():
                if task["dipendente_id"] != did:
                    continue
                if task["progetto_id"] == progetto_focus:
                    continue
                if task["stato"] in ("Completato", "Sospeso"):
                    continue

                t_inizio = _to_date(task["data_inizio"])
                t_fine = _to_date(task["data_fine"])

                if not t_inizio or not t_fine:
                    continue

                # Il task è attivo durante il periodo di focus?
                if t_fine < inizio_focus or t_inizio > fine_focus:
                    continue  # Non sovrapposto, non impattato

                # Calcola quanto del task cade nel periodo di focus
                sovrapposizione_inizio = max(t_inizio, inizio_focus)
                sovrapposizione_fine = min(t_fine, fine_focus)
                giorni_sovrapposti = _giorni_lavorativi(sovrapposizione_inizio, sovrapposizione_fine)
                giorni_totali = _giorni_lavorativi(t_inizio, t_fine)

                if giorni_totali == 0 or disponibilita_residua >= 1.0:
                    continue

                if disponibilita_residua <= 0:
                    # Blocco totale: il task slitta di tutta la durata del focus
                    giorni_slittamento = giorni_sovrapposti
                else:
                    # Rallentamento: i giorni sovrapposti richiedono più tempo
                    # Se disponibilità = 30%, quei giorni richiedono 1/0.3 = 3.3x il tempo
                    giorni_effettivi_necessari = math.ceil(giorni_sovrapposti / disponibilita_residua)
                    giorni_slittamento = giorni_effettivi_necessari - giorni_sovrapposti

                if giorni_slittamento > 0:
                    nuova_fine = _aggiungi_giorni_lavorativi(t_fine, giorni_slittamento)
                    task["data_fine"] = nuova_fine
                    task_ids_modificati.add(tid)

    # ── Propaga a cascata ──
    tutti_modificati = propaga_cascata(tasks_dopo, task_ids_modificati)

    # ── Calcola saturazioni settimanali prima/dopo ──
    # Identifica tutte le persone coinvolte (direttamente o tramite cascata)
    persone_coinvolte = set()
    for tid in tutti_modificati:
        if tid in tasks_dopo:
            did = tasks_dopo[tid].get("dipendente_id", "")
            if did:
                persone_coinvolte.add(did)
        if tid in tasks_prima:
            did = tasks_prima[tid].get("dipendente_id", "")
            if did:
                persone_coinvolte.add(did)

    saturazioni = _calcola_saturazioni_settimanali(
        tasks_prima, tasks_dopo, persone_coinvolte, dipendenti, data_oggi
    )

    # ── Verifica scadenze progetto ──
    scadenze_bucate = _verifica_scadenze(tasks_dopo, progetti)

    # ── Genera conseguenze leggibili ──
    conseguenze = genera_conseguenze(
        tasks_prima, tasks_dopo, tutti_modificati,
        dipendenti, progetti, saturazioni, scadenze_bucate
    )

    return {
        "tasks_prima": tasks_prima,
        "tasks_dopo": tasks_dopo,
        "task_modificati": tutti_modificati,
        "conseguenze": conseguenze,
        "saturazioni": saturazioni,
        "scadenze_bucate": scadenze_bucate,
    }


def _calcola_saturazioni_settimanali(tasks_prima, tasks_dopo, persone, dipendenti, data_oggi):
    """
    Per ogni persona coinvolta, calcola il carico settimanale (ore/sett)
    prima e dopo le modifiche, per le prossime 12 settimane.

    Restituisce: {
      dipendente_id: {
        "nome": str,
        "profilo": str,
        "ore_sett": int,
        "settimane": [
          {
            "lunedi": date,
            "carico_prima": float,
            "carico_dopo": float,
            "dettaglio_prima": [{ task, progetto, ore }],
            "dettaglio_dopo": [{ task, progetto, ore }],
          }
        ]
      }
    }
    """
    risultati = {}
    n_settimane = 12

    for did in persone:
        if did not in dipendenti:
            continue
        dip = dipendenti[did]

        settimane = []
        for s in range(n_settimane):
            lun = _lunedi_settimana(data_oggi) + timedelta(weeks=s)
            ven = lun + timedelta(days=4)

            carico_prima, dettaglio_prima = _carico_settimana(
                tasks_prima, did, lun, ven
            )
            carico_dopo, dettaglio_dopo = _carico_settimana(
                tasks_dopo, did, lun, ven
            )

            settimane.append({
                "lunedi": lun.isoformat(),
                "carico_prima": carico_prima,
                "carico_dopo": carico_dopo,
                "dettaglio_prima": dettaglio_prima,
                "dettaglio_dopo": dettaglio_dopo,
            })

        risultati[did] = {
            "nome": dip.get("nome", ""),
            "profilo": dip.get("profilo", ""),
            "ore_sett": dip.get("ore_sett", 40),
            "settimane": settimane,
        }

    return risultati


def _carico_settimana(tasks_dict, dipendente_id, lunedi, venerdi):
    """
    Calcola le ore di carico per un dipendente in una settimana specifica.
    Restituisce (ore_totali, dettaglio_per_task).

    Il dettaglio per task mostra COSA sta facendo la persona in quella settimana,
    non solo la percentuale — questo è ciò che rende la saturazione leggibile.
    """
    ore_totale = 0.0
    dettaglio = []

    for tid, t in tasks_dict.items():
        if t.get("dipendente_id") != dipendente_id:
            continue
        if t.get("stato") in ("Completato", "Sospeso"):
            continue

        t_inizio = _to_date(t.get("data_inizio"))
        t_fine = _to_date(t.get("data_fine"))

        if not t_inizio or not t_fine:
            continue

        # Il task è attivo in questa settimana?
        if t_fine < lunedi or t_inizio > venerdi:
            continue

        # Ore settimanali = ore_stimate / durata in settimane
        durata_giorni = max(1, (t_fine - t_inizio).days)
        durata_settimane = max(1, durata_giorni / 7)
        ore_sett = t.get("ore_stimate", 0) / durata_settimane

        ore_totale += ore_sett
        dettaglio.append({
            "task_id": tid,
            "task": t.get("nome", ""),
            "progetto_id": t.get("progetto_id", ""),
            "ore_sett": round(ore_sett, 1),
        })

    return round(ore_totale, 1), dettaglio


# ══════════════════════════════════════════════════════════════════════
# VERIFICA SCADENZE PROGETTO
# ══════════════════════════════════════════════════════════════════════

def _verifica_scadenze(tasks_dopo, progetti):
    """
    Per ogni progetto in esecuzione, verifica se l'ultimo task (dopo cascata)
    sfora la scadenza del progetto.
    """
    scadenze_bucate = []

    # Trova la data_fine dell'ultimo task per ogni progetto
    ultimi_task = {}  # progetto_id → (data_fine_max, nome_task)
    for tid, t in tasks_dopo.items():
        pid = t.get("progetto_id", "")
        if not pid:
            continue
        t_fine = _to_date(t.get("data_fine"))
        if not t_fine:
            continue
        if pid not in ultimi_task or t_fine > ultimi_task[pid][0]:
            ultimi_task[pid] = (t_fine, t.get("nome", ""))

    for pid, (ultimo_fine, ultimo_nome) in ultimi_task.items():
        if pid not in progetti:
            continue
        proj = progetti[pid]
        if proj.get("stato") not in ("In esecuzione", "In bando"):
            continue

        scadenza = _to_date(proj.get("data_fine"))
        if not scadenza:
            continue

        if ultimo_fine > scadenza:
            giorni_sforo = (ultimo_fine - scadenza).days
            scadenze_bucate.append({
                "progetto_id": pid,
                "progetto": proj.get("nome", ""),
                "cliente": proj.get("cliente", ""),
                "scadenza": scadenza.isoformat(),
                "ultimo_task_fine": ultimo_fine.isoformat(),
                "ultimo_task": ultimo_nome,
                "giorni_sforo": giorni_sforo,
            })

    return scadenze_bucate


# ══════════════════════════════════════════════════════════════════════
# 3. GENERAZIONE CONSEGUENZE LEGGIBILI
# ══════════════════════════════════════════════════════════════════════

def genera_conseguenze(tasks_prima, tasks_dopo, task_modificati,
                       dipendenti, progetti, saturazioni, scadenze_bucate):
    """
    Confronta prima/dopo e produce una lista strutturata di conseguenze.

    Ogni conseguenza è un dict con:
      tipo:     "task_slittato" | "scadenza_bucata" | "sovraccarico_persona"
      gravita:  "alta" | "media" | "bassa"
      testo:    descrizione leggibile (senza sigle, con nomi completi)
      dettagli: dati strutturati per il frontend
    """
    conseguenze = []

    # ── Task slittati ──
    for tid in task_modificati:
        if tid not in tasks_prima or tid not in tasks_dopo:
            continue

        prima = tasks_prima[tid]
        dopo = tasks_dopo[tid]

        inizio_prima = _to_date(prima.get("data_inizio"))
        fine_prima = _to_date(prima.get("data_fine"))
        inizio_dopo = _to_date(dopo.get("data_inizio"))
        fine_dopo = _to_date(dopo.get("data_fine"))

        if not fine_prima or not fine_dopo:
            continue

        delta_giorni = (fine_dopo - fine_prima).days
        if delta_giorni <= 0:
            continue  # Non è slittato (o è andato indietro, ignoriamo)

        # Chi è assegnato
        did = dopo.get("dipendente_id", "")
        nome_persona = dipendenti.get(did, {}).get("nome", "Non assegnato") if did else "Non assegnato"

        # Progetto
        pid = dopo.get("progetto_id", "")
        nome_progetto = progetti.get(pid, {}).get("nome", "Progetto sconosciuto") if pid else ""

        # Gravità basata sui giorni di slittamento
        if delta_giorni >= 15:
            gravita = "alta"
        elif delta_giorni >= 7:
            gravita = "media"
        else:
            gravita = "bassa"

        # È uno slittamento diretto o a cascata?
        # Se il task era nelle modifiche primarie, è diretto
        # (ma non possiamo saperlo qui — il chiamante potrebbe passarlo)
        # Per ora distinguiamo: se ha un predecessore che è stato modificato, è cascata
        pred_id = dopo.get("predecessore", "")
        e_cascata = pred_id and pred_id in task_modificati

        testo = (
            f"{dopo['nome']} ({nome_progetto}, assegnato a {nome_persona}): "
            f"slitta di {delta_giorni} giorni "
            f"(fine: {fine_prima.strftime('%d/%m')} → {fine_dopo.strftime('%d/%m')})"
        )
        if e_cascata:
            pred_nome = tasks_dopo.get(pred_id, {}).get("nome", "")
            testo += f" — a cascata da '{pred_nome}'"

        conseguenze.append({
            "tipo": "task_slittato",
            "gravita": gravita,
            "testo": testo,
            "dettagli": {
                "task_id": tid,
                "task_nome": dopo["nome"],
                "progetto_id": pid,
                "progetto_nome": nome_progetto,
                "persona": nome_persona,
                "data_fine_prima": fine_prima.isoformat(),
                "data_fine_dopo": fine_dopo.isoformat(),
                "delta_giorni": delta_giorni,
                "a_cascata": e_cascata,
            },
        })

    # ── Scadenze progetto bucate ──
    for sb in scadenze_bucate:
        conseguenze.append({
            "tipo": "scadenza_bucata",
            "gravita": "alta",
            "testo": (
                f"Progetto {sb['progetto']} ({sb['cliente']}): "
                f"l'ultimo task finisce il {_to_date(sb['ultimo_task_fine']).strftime('%d/%m/%Y')}, "
                f"sfora la scadenza del {_to_date(sb['scadenza']).strftime('%d/%m/%Y')} "
                f"di {sb['giorni_sforo']} giorni"
            ),
            "dettagli": sb,
        })

    # ── Sovraccarichi persona ──
    for did, sat_data in saturazioni.items():
        ore_sett = sat_data.get("ore_sett", 40)
        nome = sat_data.get("nome", "")

        for sett in sat_data.get("settimane", []):
            carico_dopo = sett.get("carico_dopo", 0)
            carico_prima = sett.get("carico_prima", 0)

            # Segnala se dopo la modifica la persona supera le ore contrattuali
            # e prima non le superava (o le supera di più)
            if carico_dopo > ore_sett and carico_dopo > carico_prima:
                delta = carico_dopo - ore_sett
                lunedi = sett["lunedi"]

                # Costruisci dettaglio di cosa fa quella settimana
                attivita = []
                for det in sett.get("dettaglio_dopo", []):
                    pid = det.get("progetto_id", "")
                    nome_prog = progetti.get(pid, {}).get("nome", "") if pid else ""
                    attivita.append(f"{det['task']} ({nome_prog}, ~{det['ore_sett']}h)")

                testo = (
                    f"{nome}: settimana del {_to_date(lunedi).strftime('%d/%m')} — "
                    f"{carico_dopo}h su {ore_sett}h contrattuali (+{delta:.0f}h). "
                    f"Attività: {', '.join(attivita)}"
                )

                # Gravità: leggero sovraccarico vs pesante
                if delta > 16:
                    gravita = "alta"
                elif delta > 8:
                    gravita = "media"
                else:
                    gravita = "bassa"

                conseguenze.append({
                    "tipo": "sovraccarico_persona",
                    "gravita": gravita,
                    "testo": testo,
                    "dettagli": {
                        "dipendente_id": did,
                        "nome": nome,
                        "settimana": lunedi,
                        "carico_prima": carico_prima,
                        "carico_dopo": carico_dopo,
                        "ore_contrattuali": ore_sett,
                        "attivita": sett.get("dettaglio_dopo", []),
                    },
                })

    # Ordina: scadenze bucate prima, poi task slittati per gravità, poi sovraccarichi
    ordine_tipo = {"scadenza_bucata": 0, "task_slittato": 1, "sovraccarico_persona": 2}
    ordine_gravita = {"alta": 0, "media": 1, "bassa": 2}
    conseguenze.sort(key=lambda c: (
        ordine_tipo.get(c["tipo"], 9),
        ordine_gravita.get(c["gravita"], 9),
    ))

    return conseguenze


# ══════════════════════════════════════════════════════════════════════
# FORMATTAZIONE PER API — converte il risultato in JSON-serializable
# ══════════════════════════════════════════════════════════════════════

def risultato_per_api(risultato):
    """
    Converte il risultato di simula_scenario() in un formato
    JSON-serializzabile per l'endpoint API.
    """
    # Converti task in formato GANTT per il frontend
    def task_to_gantt(tasks_dict, progetti):
        gantt = {}  # progetto_id → [task_gantt]
        for tid, t in tasks_dict.items():
            pid = t.get("progetto_id", "")
            if pid not in gantt:
                gantt[pid] = {
                    "progetto_id": pid,
                    "progetto_nome": progetti.get(pid, {}).get("nome", ""),
                    "cliente": progetti.get(pid, {}).get("cliente", ""),
                    "task": [],
                }
            t_inizio = _to_date(t.get("data_inizio"))
            t_fine = _to_date(t.get("data_fine"))
            gantt[pid]["task"].append({
                "id": tid,
                "nome": t.get("nome", ""),
                "inizio": t_inizio.isoformat() if t_inizio else "",
                "fine": t_fine.isoformat() if t_fine else "",
                "stato": t.get("stato", ""),
                "dipendente_id": t.get("dipendente_id", ""),
                "ore_stimate": t.get("ore_stimate", 0),
                "predecessore": t.get("predecessore", ""),
            })
        return gantt

    # Identifica solo i progetti impattati
    progetti_impattati_ids = set()
    for tid in risultato["task_modificati"]:
        if tid in risultato["tasks_dopo"]:
            pid = risultato["tasks_dopo"][tid].get("progetto_id", "")
            if pid:
                progetti_impattati_ids.add(pid)

    # Costruisci risposta
    # (il chiamante passerà i progetti come dizionario)
    return {
        "progetti_impattati": list(progetti_impattati_ids),
        "n_task_modificati": len(risultato["task_modificati"]),
        "conseguenze": risultato["conseguenze"],
        "scadenze_bucate": risultato["scadenze_bucate"],
        "saturazioni": risultato["saturazioni"],
    }