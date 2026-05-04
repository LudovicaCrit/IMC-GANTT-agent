"""
backend/deps.py
Dependency FastAPI riutilizzabili per autenticazione e autorizzazione.
"""
import os
from fastapi import Depends, HTTPException, Cookie, status
from sqlalchemy.orm import Session
from jose import JWTError

from models import get_session, Utente
from auth import decode_access_token

COOKIE_NAME = os.getenv("COOKIE_NAME", "imc_session")


# ══════════════════════════════════════════════════════════════
# DB session
# ══════════════════════════════════════════════════════════════

def get_db():
    """Apre una sessione db e la chiude a fine richiesta."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# Autenticazione: utente corrente dal cookie httpOnly
# ══════════════════════════════════════════════════════════════

def get_current_user(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> Utente:
    """
    Restituisce l'utente corrente leggendo il cookie httpOnly.
    Solleva 401 se non autenticato o token invalido/scaduto.
    """
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autenticato",
        )
    try:
        payload = decode_access_token(session_cookie)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
        )

    user_id = int(payload.get("sub", 0))
    user = db.query(Utente).filter(Utente.id == user_id).first()
    if not user or not user.attivo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disattivato",
        )

    return user


# ══════════════════════════════════════════════════════════════
# Autorizzazione: solo manager
# ══════════════════════════════════════════════════════════════

def require_manager(current_user: Utente = Depends(get_current_user)) -> Utente:
    """
    Verifica che l'utente corrente abbia ruolo 'manager'.
    Solleva 403 se è un user normale.
    """
    if current_user.ruolo_app != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permessi insufficienti: richiesto ruolo manager",
        )
    return current_user