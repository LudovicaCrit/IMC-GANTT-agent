"""
Infrastruttura IA — client Gemini (modello scelto dalla variabile d'ambiente GEMINI_MODEL).

Carica un system prompt dalla cartella prompts/ e fa una chiamata one-shot.
Oggi nessun endpoint la usa: le IA che la usavano sono state rimosse e sono
archiviate in docs/EMBRIONI_IA.md. Resta come base per quelle della fase 6,
che vi aggiungeranno streaming, timeout, output strutturato e retry.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

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


def nome_modello_gemini() -> str:
    """Nome del modello Gemini, letto da GEMINI_MODEL (backend/.env).

    Niente default nel codice: i modelli vengono spenti a date fisse e un
    default cablato continuerebbe a puntare a quello vecchio senza che
    nessuno se ne accorga. Se la variabile manca si fallisce qui, con un
    messaggio che dice cosa aggiungere.

    Si legge a OGNI chiamata e non all'import: l'applicazione parte anche
    senza la variabile, e a fallire è solo la richiesta all'IA.
    """
    nome = os.getenv("GEMINI_MODEL", "").strip()
    if not nome:
        raise RuntimeError(
            "Variabile d'ambiente GEMINI_MODEL non impostata: aggiungi "
            "GEMINI_MODEL=<nome del modello Gemini> in backend/.env."
        )
    return nome


def carica_prompt(nome_file: str) -> str:
    """Carica un prompt dalla cartella prompts/."""
    path = PROMPTS_DIR / nome_file
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt non trovato: {path}")


def init_gemini(prompt_file: str):
    """
    Inizializza il client Gemini con il prompt specificato.

    Nel nuovo SDK google-genai il system prompt NON sta dentro il modello:
    va passato a ogni chiamata dentro types.GenerateContentConfig. Quindi
    qui ritorniamo un dict autosufficiente {client, system_prompt}
    che `chiedi_semplice` usa per costruire la config a ogni generate_content. Il nome del modello NON sta nel dict:
    lo risolve `nome_modello_gemini()` al momento della chiamata.

    Ritorna il dict, oppure None se l'SDK non è disponibile o manca la chiave.
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    system_prompt = carica_prompt(prompt_file)

    model = {
        "client": client,
        "system_prompt": system_prompt,
    }
    return model


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
        model=nome_modello_gemini(),
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=model["system_prompt"],
        ),
    )

    return response.text


def is_agent_available():
    """Controlla se l'agente AI è disponibile."""
    return GEMINI_AVAILABLE and bool(GEMINI_API_KEY)
