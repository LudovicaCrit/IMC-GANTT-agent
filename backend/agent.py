"""
Modulo Agente AI — Gemini 2.5 Flash
Carica i prompt dalla cartella prompts/ e gestisce la conversazione.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Import Gemini SDK ──
try:
    import google.generativeai as genai
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
    """Inizializza il client Gemini con il prompt specificato."""
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    system_prompt = carica_prompt(prompt_file)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
    )
    return model


def costruisci_contesto(dip_data, ore_compilate, stati_compilati, tasks_attivi,
                         ore_assenza=0, tipo_assenza="", nota_assenza="",
                         spese=None, ore_contrattuali=40):
    """Costruisce il contesto JSON da passare all'agente, incluso il carico complessivo."""

    from data import get_progetti_dipendente, carico_settimanale_dipendente
    from datetime import datetime

    task_compilati = []
    task_bloccati = []
    task_zero_ore = []

    for task_id, ore in ore_compilate.items():
        task_row = tasks_attivi[tasks_attivi["id"] == task_id]
        if len(task_row) > 0:
            task_nome = task_row.iloc[0]["nome"]
            stato = stati_compilati.get(task_id, "In corso")
            task_compilati.append({"task": task_nome, "ore": float(ore), "stato": stato})
            if stato == "Bloccato":
                task_bloccati.append(task_nome)
            if ore == 0:
                task_zero_ore.append(task_nome)

    ore_totali = sum(ore_compilate.values())
    ore_non_coperte = ore_contrattuali - ore_totali - ore_assenza

    # Contesto carico complessivo
    oggi = datetime(2026, 3, 9)
    progetti_attivi = get_progetti_dipendente(dip_data["id"])
    carico_assegnato = carico_settimanale_dipendente(dip_data["id"], oggi)
    saturazione_pct = round(carico_assegnato / ore_contrattuali * 100)

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
    """Invia un messaggio all'agente e ottieni la risposta."""

    if model is None:
        return "⚠️ Agente non disponibile. Verifica che GEMINI_API_KEY sia configurata nel .env e che google-generativeai sia installato."

    try:
        contesto_json = json.dumps(contesto_dict, ensure_ascii=False, indent=2)

        prompt_completo = (
            f"CONTESTO COMPILAZIONE CORRENTE:\n```json\n{contesto_json}\n```\n\n"
            f"Messaggio del dipendente: {messaggio_utente}"
        )

        # Chat con storia
        history = []
        if chat_history:
            for msg in chat_history:
                role = "user" if msg["role"] == "user" else "model"
                history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=history)
        response = chat.send_message(prompt_completo)

        return response.text

    except Exception as e:
        return f"⚠️ Errore nella comunicazione con l'agente: {str(e)}"


def is_agent_available():
    """Controlla se l'agente AI è disponibile."""
    return GEMINI_AVAILABLE and bool(GEMINI_API_KEY)
