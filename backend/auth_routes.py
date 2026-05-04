"""
backend/auth_routes.py
Endpoint REST per autenticazione: login, me, logout.
"""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import JWTError
from deps import get_current_user
from slowapi import Limiter
from slowapi.util import get_remote_address
from collections import defaultdict
from time import time

from models import get_session, Utente
from auth import verify_password, create_access_token, decode_access_token

limiter = Limiter(key_func=get_remote_address)

# ══════════════════════════════════════════════════════════════
# Rate limiting per email (oltre a quello per IP gestito da slowapi)
# ══════════════════════════════════════════════════════════════

# Storage in-memory: {email_key: [timestamp1, timestamp2, ...]}
_email_attempts: dict[str, list[float]] = defaultdict(list)
_EMAIL_RATE_LIMIT = 5      # tentativi
_EMAIL_RATE_WINDOW = 60    # secondi


def _check_email_rate_limit(key: str) -> bool:
    """
    Ritorna True se la chiamata è permessa, False se ha superato il limite.
    Pulisce timestamp vecchi (più di _EMAIL_RATE_WINDOW secondi).
    """
    now = time()
    cutoff = now - _EMAIL_RATE_WINDOW
    attempts = _email_attempts[key]
    # Rimuove timestamp scaduti
    attempts[:] = [t for t in attempts if t > cutoff]
    if len(attempts) >= _EMAIL_RATE_LIMIT:
        return False
    attempts.append(now)
    return True

# ── Config cookie da .env ──
COOKIE_NAME = os.getenv("COOKIE_NAME", "imc_session")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "False").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))
COOKIE_MAX_AGE = JWT_EXPIRE_HOURS * 3600  # secondi


# ══════════════════════════════════════════════════════════════
# DTO (Data Transfer Object) — input/output
# ══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    ruolo_app: str
    dipendente_id: str | None


# ══════════════════════════════════════════════════════════════
# Helper — sessione db come dependency
# ══════════════════════════════════════════════════════════════

def get_db():
    """Dependency FastAPI: apre una sessione db e la chiude a fine richiesta."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# Router
# ══════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=UserResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Login: verifica credenziali, setta cookie httpOnly con JWT, restituisce utente.
    """
    # Rate limit per email (oltre a quello per IP del decoratore)
    email_key = f"login_email:{payload.email.lower().strip()}"
    if not _check_email_rate_limit(email_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Troppi tentativi su questo account. Riprovare tra qualche minuto.",
        )
    
    user = db.query(Utente).filter(Utente.email == payload.email).first()
    if not user or not user.attivo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    # Aggiorna ultimo_login
    user.ultimo_login = datetime.utcnow()
    db.commit()

    # Crea JWT
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "ruolo": user.ruolo_app,
    })

    # Setta cookie httpOnly
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
        path="/",
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        ruolo_app=user.ruolo_app,
        dipendente_id=user.dipendente_id,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: Utente = Depends(get_current_user)):
    """
    Restituisce l'utente corrente. La dependency get_current_user gestisce
    autenticazione, decodifica JWT, ricerca db e errori 401.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        ruolo_app=current_user.ruolo_app,
        dipendente_id=current_user.dipendente_id,
    )


@router.post("/logout")
def logout(response: Response):
    """
    Logout: cancella il cookie httpOnly.
    """
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    return {"ok": True}