"""
audit_permessi.py
Analizza main.py e produce un report dei permessi su ogni endpoint.

Uso (dalla cartella backend/):
    python scripts/audit_permessi.py
"""

import re
import sys
from pathlib import Path

MAIN_PATH = Path(__file__).parent.parent / "main.py"

# Pattern per identificare:
# - decoratori @app.METODO("/path")
# - parametri Depends(get_current_user) o Depends(require_manager)
# - decoratori @limiter.limit per rate limiting
# - check manuali nel corpo (current_user.ruolo_app != "manager")

ENDPOINT_RE = re.compile(r'@app\.(get|post|put|patch|delete)\("([^"]+)"\)')
DEPENDS_MANAGER_RE = re.compile(r'Depends\(require_manager\)')
DEPENDS_USER_RE = re.compile(r'Depends\(get_current_user\)')
LIMITER_RE = re.compile(r'@limiter\.limit')
FILTER_CHECK_RE = re.compile(r'current_user\.ruolo_app\s*!=\s*"manager"')


def analizza_endpoint(blocco: str):
    """Analizza un blocco di codice di un endpoint e ritorna il tipo di protezione."""
    has_manager = bool(DEPENDS_MANAGER_RE.search(blocco))
    has_user = bool(DEPENDS_USER_RE.search(blocco))
    has_limiter = bool(LIMITER_RE.search(blocco))
    has_filter = bool(FILTER_CHECK_RE.search(blocco))
    
    if has_manager:
        return "MANAGER"
    if has_user and has_filter:
        return "AUTH+FILTRO"
    if has_user:
        return "AUTH-ONLY"
    if has_limiter:
        return "PUBLIC+RL"
    return "MISSING"


def main():
    if not MAIN_PATH.exists():
        print(f"❌ File non trovato: {MAIN_PATH}")
        sys.exit(1)
    
    contenuto = MAIN_PATH.read_text()
    righe = contenuto.split("\n")
    
    # Trova tutti gli endpoint con la loro posizione
    endpoints = []
    for i, riga in enumerate(righe):
        match = ENDPOINT_RE.search(riga)
        if match:
            metodo = match.group(1).upper()
            path = match.group(2)
            # Prendi il blocco fino al prossimo @app o EOF (max 30 righe)
            inizio = i
            fine = min(i + 30, len(righe))
            for j in range(i + 1, fine):
                if righe[j].startswith("@app.") or righe[j].startswith("@router."):
                    fine = j
                    break
            blocco = "\n".join(righe[inizio:fine])
            tipo = analizza_endpoint(blocco)
            endpoints.append({
                "metodo": metodo,
                "path": path,
                "tipo": tipo,
                "riga": i + 1,
            })
    
    # Esclude endpoint pubblici legittimi (auth/login, auth/logout, auth/me)
    pubblici_attesi = {
        "/api/auth/login",   # rate-limited
        "/api/auth/logout",  # pubblico per design
        "/api/auth/me",      # gestito in auth_routes.py, non qui
    }
    
    # Stampa tabella
    print("\n" + "=" * 90)
    print(f"{'METODO':<8} {'PATH':<55} {'PROTEZIONE':<15} {'RIGA':<6}")
    print("=" * 90)
    
    counts = {
        "MANAGER": 0,
        "AUTH+FILTRO": 0,
        "AUTH-ONLY": 0,
        "PUBLIC+RL": 0,
        "MISSING": 0,
    }
    
    missing_endpoints = []
    
    for ep in sorted(endpoints, key=lambda x: x["path"]):
        emoji = "✓" if ep["tipo"] != "MISSING" else "⚠️"
        # Endpoint pubblici legittimi: ok anche senza dependency
        if ep["path"] in pubblici_attesi and ep["tipo"] == "MISSING":
            ep["tipo"] = "PUBLIC+RL" if ep["path"] == "/api/auth/login" else "PUBLIC"
            emoji = "✓"
        
        print(f"{ep['metodo']:<8} {ep['path']:<55} {emoji} {ep['tipo']:<13} {ep['riga']:<6}")
        
        if ep["tipo"] in counts:
            counts[ep["tipo"]] += 1
        if ep["tipo"] == "MISSING":
            missing_endpoints.append(ep)
    
    # Riepilogo
    print("\n" + "=" * 90)
    print("RIEPILOGO")
    print("=" * 90)
    totale = len(endpoints)
    print(f"  Totale endpoint:        {totale}")
    print(f"  ✓ MANAGER (admin only): {counts['MANAGER']}")
    print(f"  ✓ AUTH+FILTRO:          {counts['AUTH+FILTRO']}")
    print(f"  ✓ AUTH-ONLY:            {counts['AUTH-ONLY']}")
    print(f"  ✓ PUBLIC+RL (login):    {counts['PUBLIC+RL']}")
    print(f"  ⚠️ MISSING:              {counts['MISSING']}")
    print()
    
    if missing_endpoints:
        print("⚠️  ENDPOINT NON PROTETTI:")
        for ep in missing_endpoints:
            print(f"     {ep['metodo']:<8} {ep['path']:<50} (riga {ep['riga']})")
        print()
        print("Aggiungi una dependency a questi endpoint!")
        sys.exit(1)
    else:
        print("✅ Tutti gli endpoint sono protetti correttamente!")


if __name__ == "__main__":
    main()