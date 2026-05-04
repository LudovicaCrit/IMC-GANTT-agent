"""
backend/auth.py
Utility per autenticazione: hashing password e gestione JWT.
"""
import os
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

# ── Configurazione da .env ──
SECRET_KEY = os.getenv("SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY mancante nel .env — impossibile avviare auth")

# ── Contesto passlib (bcrypt) ──
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ══════════════════════════════════════════════════════════════
# PASSWORD
# ══════════════════════════════════════════════════════════════

def hash_password(plain_password: str) -> str:
    """Hasha una password in chiaro con bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica che una password in chiaro corrisponda all'hash bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


# ══════════════════════════════════════════════════════════════
# JWT
# ══════════════════════════════════════════════════════════════

def create_access_token(payload: dict) -> str:
    """
    Crea un JWT firmato con SECRET_KEY.
    Aggiunge automaticamente 'iat' (issued at) ed 'exp' (expiration).
    """
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=JWT_EXPIRE_HOURS)
    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodifica e verifica un JWT.
    Solleva JWTError se il token è invalido, manomesso o scaduto.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])