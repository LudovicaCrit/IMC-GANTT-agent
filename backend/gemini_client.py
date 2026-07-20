"""
Modulo Agente AI — Gemini 2.5 Flash
Carica i prompt dalla cartella prompts/ e gestisce la conversazione.

Approccio B: il contesto include task_assegnati (per mappatura ore)
e colleghi_task (per "ho aiutato X").
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

from utils import get_oggi

load_dotenv()

# ── Import Gemini SDK (nuovo google-genai) ──
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PROMPTS_DIR = Path(__file__).parent / "prompts"


def carica_prompt(nome_file: str) -> str:
    """Carica un prompt dalla cartella prompts/."""
    path = PROMPTS_DIR / nome_file
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt non trovato: {path}")


def init_gemini(prompt_file: str = "consuntivazione.md"):
    """
    Inizializza il client Gemini con il prompt specificato.

    Nel nuovo SDK google-genai il system prompt NON sta dentro il modello:
    va passato a ogni chiamata dentro types.GenerateContentConfig. Quindi
    qui ritorniamo un dict autosufficiente {client, system_prompt, model_name}
    che i chiamanti (chiedi_agente / chiedi_semplice) usano per costruire la
    config a ogni generate_content.

    Ritorna il dict, oppure None se l'SDK non è disponibile o manca la chiave.
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    system_prompt = carica_prompt(prompt_file)

    model = {
        "client": client,
        "system_prompt": system_prompt,
        "model_name": "gemini-2.5-flash",
    }
    return model


def costruisci_contesto(dip_data, ore_compilate, stati_compilati, tasks_attivi,
                         colleghi_nomi, tasks_colleghi, progetti_nomi,
                         ore_assenza=0, tipo_assenza="", nota_assenza="",
                         spese=None, ore_contrattuali=40):
    """
    Costruisce il contesto JSON da passare all'agente.
    Include: carico complessivo, task_assegnati (per Approccio B),
    colleghi_task (per "ho aiutato X"), e dati compilazione corrente.

    Strada A: il chiamante (agent.py /chat) prepara via SQLAlchemy le
    list[dict]/dict, questa funzione consuma solo Python puro. Niente
    DataFrame, niente import a runtime di TASKS/DIPENDENTI/PROGETTI.

    Parametri di lettura (forniti dal chiamante):
      tasks_attivi:    list[dict] dei task del dipendente in stato
                       "In corso"/"Da iniziare". Campi attesi:
                       id, nome, progetto_id, fase, ore_stimate, stato.
      colleghi_nomi:   dict {dipendente_id: nome} dei colleghi attivi
                       (il dipendente stesso è già escluso a monte).
      tasks_colleghi:  list[dict] dei task dei colleghi negli stessi stati
                       attivi. Campi: id, nome, progetto_id, dipendente_id.
      progetti_nomi:   dict {progetto_id: nome} per il lookup nome progetto
                       (sostituisce la bool-index ripetuta su PROGETTI).
    """

    from data import get_progetti_dipendente, carico_settimanale_dipendente

    # Indice {task_id: task} per il lookup del nome nel ciclo dei task
    # compilati. Sostituisce la bool-index originale `tasks_attivi[id==tid]`.
    tasks_attivi_idx = {t["id"]: t for t in tasks_attivi}

    task_compilati = []
    task_bloccati = []
    task_zero_ore = []

    for task_id, ore in ore_compilate.items():
        task = tasks_attivi_idx.get(task_id)
        if task is not None:
            task_nome = task["nome"]
            stato = stati_compilati.get(task_id, "In corso")
            task_compilati.append({
                "task": task_nome,
                "task_id": task_id,
                "ore": float(ore),
                "stato": stato,
            })
            if stato == "Bloccato":
                task_bloccati.append(task_nome)
            if ore == 0:
                task_zero_ore.append(task_nome)

    ore_totali = sum(ore_compilate.values())
    ore_non_coperte = ore_contrattuali - ore_totali - ore_assenza

    # Contesto carico complessivo
    oggi = get_oggi()
    progetti_attivi = get_progetti_dipendente(dip_data["id"])
    carico_assegnato = carico_settimanale_dipendente(dip_data["id"], oggi)
    saturazione_pct = round(carico_assegnato / ore_contrattuali * 100)

    # ── task_assegnati: lista completa dei task del dipendente.
    #    L'agente mappa SOLO su questi (Approccio B). ──
    task_assegnati = []
    for t in tasks_attivi:
        task_assegnati.append({
            "id": t["id"],
            "nome": t["nome"],
            "progetto": progetti_nomi.get(t["progetto_id"], "?"),
            "fase": t["fase"],
            # bugfix: ore_stimate da ORM può essere None (era 0 in _load_tasks).
            "ore_stimate": int(t["ore_stimate"] or 0),
            "stato": t["stato"],
        })

    # ── colleghi_task: per ogni collega con task attivi, la lista dei
    #    suoi task arricchita col nome progetto. ──
    # Pre-indicizza i task per dipendente per O(1) lookup; itera poi i
    # colleghi in ordine di `colleghi_nomi` (= ordine query SQLAlchemy =
    # iso-ordine col vecchio loop su DIPENDENTI).
    tasks_per_collega = {}
    for tc in tasks_colleghi:
        tasks_per_collega.setdefault(tc["dipendente_id"], []).append(tc)

    colleghi_task = {}
    for collega_id, collega_nome in colleghi_nomi.items():
        tasks_del_collega = tasks_per_collega.get(collega_id)
        if not tasks_del_collega:
            continue  # collega senza task attivi: salta (come l'originale)
        colleghi_task[collega_nome] = [
            {"id": tc["id"], "nome": tc["nome"],
             "progetto": progetti_nomi.get(tc["progetto_id"], "?")}
            for tc in tasks_del_collega
        ]

    return {
        "nome_dipendente": str(dip_data["nome"]),
        "profilo": str(dip_data["profilo"]),
        "ore_contrattuali": float(ore_contrattuali),
        "carico_complessivo": {
            "ore_assegnate_settimana": float(carico_assegnato),
            "saturazione_percentuale": saturazione_pct,
            "numero_progetti_attivi": len(progetti_attivi),
            "progetti": progetti_attivi,
            "sovraccaricato": saturazione_pct > 100,
        },
        "task_assegnati": task_assegnati,
        "colleghi_task": colleghi_task,
        "task_compilati": task_compilati,
        "task_con_zero_ore": task_zero_ore,
        "ore_totali_lavorate": float(ore_totali),
        "assenze": {
            "tipo": tipo_assenza,
            "ore": float(ore_assenza),
            "nota": nota_assenza,
        } if ore_assenza > 0 else None,
        "spese": spese if spese else [],
        "task_bloccati": task_bloccati,
        "ore_non_coperte": round(float(ore_non_coperte), 1),
    }


def chiedi_agente(model, contesto_dict, messaggio_utente, chat_history=None):
    """Invia un messaggio all'agente (con storia) e ottieni la risposta.

    Contratto verso /chat: in caso di errore ritorna una STRINGA di errore
    (non solleva). Usa il nuovo SDK google-genai: la storia è costruita come
    list[types.Content] e il system prompt va nella config.
    """

    if model is None:
        return "⚠️ Agente non disponibile. Verifica che GEMINI_API_KEY sia configurata nel .env e che google-genai sia installato."

    try:
        contesto_json = json.dumps(contesto_dict, ensure_ascii=False, indent=2)

        prompt_completo = (
            f"CONTESTO COMPILAZIONE CORRENTE:\n```json\n{contesto_json}\n```\n\n"
            f"Messaggio del dipendente: {messaggio_utente}"
        )

        # Costruisci i contents: storia + messaggio corrente
        contents = []
        if chat_history:
            for msg in chat_history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])],
                ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_completo)],
        ))

        response = model["client"].models.generate_content(
            model=model["model_name"],
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=model["system_prompt"],
            ),
        )

        return response.text

    except Exception as e:
        return f"⚠️ Errore nella comunicazione con l'agente: {str(e)}"


def chiedi_semplice(model, prompt):
    """Invio one-shot senza storia (nuovo SDK google-genai).

    Nessun try/except: l'eccezione sale al chiamante, che ha già la sua
    gestione (raise HTTPException(500, ...)). Ritorna response.text grezzo.
    """
    contents = [types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )]

    response = model["client"].models.generate_content(
        model=model["model_name"],
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=model["system_prompt"],
        ),
    )

    return response.text


def is_agent_available():
    """Controlla se l'agente AI è disponibile."""
    return GEMINI_AVAILABLE and bool(GEMINI_API_KEY)
