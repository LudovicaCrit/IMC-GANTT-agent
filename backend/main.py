"""
IMC-Group GANTT Agent — Backend API (FastAPI)
Espone endpoint REST per il frontend React.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from auth_routes import router as auth_router
from routes.dipendenti import router as dipendenti_router
from routes.progetti import router as progetti_router
from routes.economia import router as economia_router
from routes.risorse import router as risorse_router
from routes.gantt import router as gantt_router
from routes.segnalazioni import router as segnalazioni_router
from routes.pianificazione import router as pianificazione_router
from routes.consuntivi import router as consuntivi_router
from routes.tasks import router as tasks_router
from routes.sottotask import router as sottotask_router
from routes.attivita_interne import router as attivita_interne_router
from routes.configurazione import router as configurazione_router
from routes.agent import router as agent_router
from routes.scenario import router as scenario_router
from routes.fasi import router as fasi_router
from routes.home import router as home_router
from routes.sal import router as sal_router
from routes.bollettino import router as bollettino_router
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# ── Porte e origini ──────────────────────────────────────────────────────
# Si scelgono in backend/.env (GANTT_PORTA_BACKEND, GANTT_PORTA_FRONTEND), che
# leggono anche vite.config.js e gli e2e: un posto solo per tutti e tre. I
# default valgono quando la variabile manca, e sono una coppia che non collide
# con gli altri progetti della macchina di sviluppo.
load_dotenv()
PORTA_BACKEND = int(os.getenv("GANTT_PORTA_BACKEND", "8100"))
PORTA_FRONTEND = int(os.getenv("GANTT_PORTA_FRONTEND", "3100"))


def _origini_cors():
    """Origini ammesse dal CORS: GANTT_ORIGINI_CORS, separate da virgola.

    Senza la variabile vale l'origine del frontend in sviluppo. Con la variabile
    vuota non è ammessa nessuna origine: è il caso di produzione, dove frontend
    e /api stanno sotto lo stesso dominio dietro IIS e il CORS non serve.
    """
    valore = os.getenv("GANTT_ORIGINI_CORS")
    if valore is None:
        return [f"http://localhost:{PORTA_FRONTEND}"]
    return [o.strip() for o in valore.split(",") if o.strip()]


app = FastAPI(title="IMC-Group GANTT Agent", version="0.1.0")

# Rate limiter - strategia: per IP del client
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router)
app.include_router(dipendenti_router)
app.include_router(progetti_router)
app.include_router(economia_router)
app.include_router(risorse_router)
app.include_router(gantt_router)
app.include_router(segnalazioni_router)
app.include_router(pianificazione_router)
app.include_router(consuntivi_router)
app.include_router(tasks_router)
app.include_router(sottotask_router)
app.include_router(attivita_interne_router)
app.include_router(configurazione_router)
app.include_router(agent_router)
app.include_router(scenario_router)
app.include_router(fasi_router)
app.include_router(home_router)
app.include_router(sal_router)
app.include_router(bollettino_router)

# CORS per permettere al frontend React di chiamare il backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origini_cors(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/salute")
def salute():
    """Il processo risponde. Pubblico e senza dati: serve a chi deve sapere se
    il backend è in piedi (healthcheck degli e2e, monitoraggio del servizio).
    Non tocca il database di proposito: dice che il server è vivo, non che
    tutto funziona."""
    return {"stato": "ok"}


# ══════════════════════════════════════════════════════════════════════
# STORE FALLBACK PER MODALITÀ NON-DB (LEGACY)
# 📌 TODO: rimuovere quando PostgreSQL sarà fonte di verità unica
# ══════════════════════════════════════════════════════════════════════

SEGNALAZIONI_STORE = []
_segn_counter = 0


def _next_segn_id():
    global _segn_counter
    _segn_counter += 1
    return f"S{_segn_counter:03d}"


# ══════════════════════════════════════════════════════════════════════
# CLASSE DA ANALIZZARE INSIEME (vedi handoff v13 sezione F.1)
# 📌 SimulaRiassegnaRequest — funzionalità incompleta o futura.
#    Probabilmente per Tavolo di Lavoro: riassegnare un task a un
#    altro dipendente per simulare l'impatto. Da analizzare prima
#    di rimuovere o spostare.
# ══════════════════════════════════════════════════════════════════════

class SimulaRiassegnaRequest(BaseModel):
    task_id: str
    nuovo_dipendente_id: str


# ══════════════════════════════════════════════════════════════════════
# AVVIO
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORTA_BACKEND)