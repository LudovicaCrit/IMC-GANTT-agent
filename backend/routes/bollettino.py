"""
backend/routes/bollettino.py — Bollettino economico (archivio storico marginalità).

Separato dal SAL per decisione architetturale: il SAL fotografa la struttura
del GANTT, il Bollettino l'economia (margini + grezzi). Stessa forma e stessa
sicurezza del SAL.

Endpoint:
  POST /api/bollettino/{progetto_id}        crea un bollettino (consolida economia)
  GET  /api/bollettino/{progetto_id}        storico SINTETICO (no JSON stato)
  GET  /api/bollettino/snapshot/{id}        singolo bollettino COMPLETO

Autorizzazione self-or-manager: riusa `_autorizza_progetto` del modulo SAL.
Guardia anti-bypass nel dettaglio: si risale PRIMA al progetto_id del bollettino
e si autorizza su QUEL progetto, poi si carica il JSON completo.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user
from models import Utente
from routes.sal import _autorizza_progetto  # riuso DRY dell'helper self-or-manager
from data import (
    crea_bollettino, lista_bollettini_progetto,
    get_bollettino, get_bollettino_progetto_id,
)

router = APIRouter(prefix="/api/bollettino", tags=["bollettino"])


class CreaBollettinoRequest(BaseModel):
    nota: Optional[str] = None


@router.post("/{progetto_id}")
def consolida_bollettino(
    progetto_id: str,
    req: CreaBollettinoRequest = CreaBollettinoRequest(),
    current_user: Utente = Depends(get_current_user),
):
    """Consolida un Bollettino economico: congela l'economia corrente del progetto.
    Solo manager o PM del progetto. 404 se il progetto non esiste."""
    _autorizza_progetto(progetto_id, current_user)
    try:
        return crea_bollettino(
            progetto_id,
            consolidato_da=current_user.dipendente_id,
            nota=req.nota,
        )
    except ValueError as e:
        # progetto esistente ma non in Economia (es. interno): non consolidabile.
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/snapshot/{snapshot_id}")
def leggi_bollettino(
    snapshot_id: int,
    current_user: Utente = Depends(get_current_user),
):
    """Singolo bollettino COMPLETO (con JSON `stato`).

    Anti-bypass: prima si risale al progetto_id del bollettino, poi self-or-manager
    su quel progetto; il JSON si carica solo dopo l'autorizzazione.
    """
    progetto_id = get_bollettino_progetto_id(snapshot_id)
    if progetto_id is None:
        raise HTTPException(status_code=404, detail=f"Bollettino '{snapshot_id}' non trovato")
    _autorizza_progetto(progetto_id, current_user)
    return get_bollettino(snapshot_id)


@router.get("/{progetto_id}")
def storico_bollettino(
    progetto_id: str,
    current_user: Utente = Depends(get_current_user),
):
    """Storico SINTETICO dei bollettini di un progetto (NO JSON stato), data desc.
    Solo manager o PM del progetto."""
    _autorizza_progetto(progetto_id, current_user)
    return lista_bollettini_progetto(progetto_id)
