"""
IMC-Group GANTT Agent — Backend API (FastAPI)
Espone endpoint REST per il frontend React.
"""

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
from routes.simulazione import router as simulazione_router
from routes.attivita_interne import router as attivita_interne_router
from routes.configurazione import router as configurazione_router
from routes.agent import router as agent_router
from routes.scenario import router as scenario_router
from routes.fasi import router as fasi_router
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


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
app.include_router(simulazione_router)
app.include_router(attivita_interne_router)
app.include_router(configurazione_router)
app.include_router(agent_router)
app.include_router(scenario_router)
app.include_router(fasi_router)

# CORS per permettere al frontend React di chiamare il backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    uvicorn.run(app, host="0.0.0.0", port=8000)