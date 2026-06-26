"""
backend/routes/sal.py — SAL (snapshot storico del GANTT).

DESIGN_SAL.md. Il SAL è una fotografia immutabile e autocontenuta dello stato
completo di un progetto, consolidata su approvazione del PM ("Consolida SAL").

Endpoint (pezzo 2 — creazione):
  POST /api/sal/{progetto_id}   crea uno snapshot dello stato corrente.

Autorizzazione self-or-manager: manager OPPURE il PM di quel progetto
(current_user.dipendente_id == Progetto.pm_id). Stesso principio di
progetti_attivi_visibili: la conoscenza del DB sta nello strato dati
(get_progetto_meta, crea_snapshot), la route compone e autorizza.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user
from models import Utente
from data import (
    get_progetto_meta, crea_snapshot,
    lista_snapshot_progetto, get_snapshot, get_snapshot_progetto_id,
)

router = APIRouter(prefix="/api/sal", tags=["sal"])


class CreaSnapshotRequest(BaseModel):
    nota: Optional[str] = None


def _autorizza_progetto(progetto_id: str, current_user: Utente):
    """self-or-manager su un progetto: 404 se inesistente, 403 se non
    manager né PM. Ritorna i meta del progetto. Riusato da tutti gli endpoint
    (la conoscenza del DB resta nello strato dati)."""
    meta = get_progetto_meta(progetto_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Progetto '{progetto_id}' non trovato")
    if current_user.ruolo_app != "manager" and current_user.dipendente_id != meta["pm_id"]:
        raise HTTPException(
            status_code=403,
            detail="Permessi insufficienti: solo manager o PM del progetto",
        )
    return meta


@router.post("/{progetto_id}")
def consolida_sal(
    progetto_id: str,
    req: CreaSnapshotRequest = CreaSnapshotRequest(),
    current_user: Utente = Depends(get_current_user),
):
    """Consolida un SAL: serializza lo stato corrente del progetto e lo salva.
    Solo manager o PM del progetto. 404 se il progetto non esiste.
    """
    _autorizza_progetto(progetto_id, current_user)
    return crea_snapshot(
        progetto_id,
        consolidato_da=current_user.dipendente_id,
        nota=req.nota,
    )


@router.get("/snapshot/{snapshot_id}")
def leggi_snapshot(
    snapshot_id: int,
    current_user: Utente = Depends(get_current_user),
):
    """Singolo snapshot COMPLETO (con JSON `stato`).

    Sicurezza: si risale PRIMA al progetto_id dello snapshot e si applica
    self-or-manager su QUEL progetto — un id arbitrario non bypassa il controllo.
    Il JSON completo si carica solo dopo l'autorizzazione.
    """
    progetto_id = get_snapshot_progetto_id(snapshot_id)
    if progetto_id is None:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' non trovato")
    _autorizza_progetto(progetto_id, current_user)
    return get_snapshot(snapshot_id)


@router.get("/{progetto_id}")
def storico_sal(
    progetto_id: str,
    current_user: Utente = Depends(get_current_user),
):
    """Storico SINTETICO degli snapshot di un progetto (NO JSON stato),
    ordinato per data desc. Solo manager o PM del progetto."""
    _autorizza_progetto(progetto_id, current_user)
    return lista_snapshot_progetto(progetto_id)
