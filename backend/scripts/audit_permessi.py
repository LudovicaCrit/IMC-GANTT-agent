"""
audit_permessi.py
Analizza main.py + tutti i router in routes/ e produce un report dei
permessi su ogni endpoint REST.

Versione 2 (5 maggio 2026): aggiornato per il refactoring "strangler"
che sposta gli endpoint da main.py a router separati in backend/routes/.

Lo script:
  - Scansiona main.py per @app.<metodo>
  - Scansiona ogni .py in routes/ per @router.<metodo>, ricostruendo il
    path completo concatenando il prefix del router al path del decoratore
  - Riconosce gli stessi pattern di protezione di prima:
      MANAGER     → Depends(require_manager)
      AUTH+FILTRO → Depends(get_current_user) + check ruolo nel corpo
      AUTH-ONLY   → Depends(get_current_user) senza filtro
      PUBLIC+RL   → @limiter.limit (login)
      MISSING     → nessuna protezione (alert!)
  - Esce con codice 1 se trova endpoint MISSING (utile in CI/CD)

Uso (dalla cartella backend/):
    python scripts/audit_permessi.py
"""

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
MAIN_PATH = BACKEND_DIR / "main.py"
ROUTES_DIR = BACKEND_DIR / "routes"

# ── Pattern di parsing ──────────────────────────────────────────────────
# Endpoint da @app.<metodo>("/path") (main.py)
APP_ENDPOINT_RE = re.compile(r'@app\.(get|post|put|patch|delete)\("([^"]+)"')
# Endpoint da @router.<metodo>("/sub_path") (router files)
ROUTER_ENDPOINT_RE = re.compile(r'@router\.(get|post|put|patch|delete)\("([^"]*)"')
# prefix del router: APIRouter(prefix="/api/xxx", ...)
ROUTER_PREFIX_RE = re.compile(r'APIRouter\([^)]*prefix\s*=\s*"([^"]+)"')

# Pattern di protezione (uguali alla v1)
DEPENDS_MANAGER_RE = re.compile(r'Depends\(require_manager\)')
DEPENDS_USER_RE = re.compile(r'Depends\(get_current_user\)')
LIMITER_RE = re.compile(r'@limiter\.limit')
FILTER_CHECK_RE = re.compile(r'current_user\.ruolo_app\s*!=\s*"manager"')


def analizza_blocco(blocco: str) -> str:
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


def estrai_endpoint_da_file(file_path: Path, decoratore_re: re.Pattern, prefix: str = ""):
    """Scansiona un file Python ed estrae endpoint con la loro protezione.

    Args:
        file_path: file da scansionare
        decoratore_re: regex per il decoratore (@app o @router)
        prefix: prefisso da anteporre al path (per i router)

    Returns:
        Lista di dict {metodo, path, tipo, riga, file}.
    """
    if not file_path.exists():
        return []

    contenuto = file_path.read_text()
    righe = contenuto.split("\n")
    endpoints = []

    for i, riga in enumerate(righe):
        match = decoratore_re.search(riga)
        if not match:
            continue
        metodo = match.group(1).upper()
        sub_path = match.group(2)
        # Path completo: prefix del router + sub_path del decoratore
        path = (prefix + sub_path) if prefix else sub_path
        # Path normalizzato: niente doppia slash, niente trailing slash su path lunghi
        if not path:
            path = "/"

        # Estrai il blocco fino al prossimo decoratore o EOF (max 30 righe)
        inizio = i
        fine = min(i + 30, len(righe))
        for j in range(i + 1, fine):
            r = righe[j]
            if r.startswith("@app.") or r.startswith("@router.") or r.startswith("@limiter."):
                # @limiter è un decoratore aggiuntivo dello stesso endpoint, non un nuovo endpoint
                if r.startswith("@limiter."):
                    continue
                fine = j
                break
        blocco = "\n".join(righe[inizio:fine])
        tipo = analizza_blocco(blocco)
        endpoints.append({
            "metodo": metodo,
            "path": path,
            "tipo": tipo,
            "riga": i + 1,
            "file": file_path.name,
        })
    return endpoints


def estrai_router_endpoints(routes_dir: Path):
    """Scansiona tutti i .py in routes/ e ne estrae endpoint con prefix corretto."""
    if not routes_dir.exists():
        return []

    all_eps = []
    for file_path in sorted(routes_dir.glob("*.py")):
        if file_path.name == "__init__.py":
            continue

        contenuto = file_path.read_text()
        # Trova il prefix dichiarato per APIRouter
        prefix_match = ROUTER_PREFIX_RE.search(contenuto)
        prefix = prefix_match.group(1) if prefix_match else ""

        eps = estrai_endpoint_da_file(file_path, ROUTER_ENDPOINT_RE, prefix=prefix)
        all_eps.extend(eps)
    return all_eps


def main():
    if not MAIN_PATH.exists():
        print(f"❌ File non trovato: {MAIN_PATH}")
        sys.exit(1)

    # Endpoint da main.py (ancora monolitici)
    main_endpoints = estrai_endpoint_da_file(MAIN_PATH, APP_ENDPOINT_RE)
    # Endpoint da routes/*.py (refactoring in corso)
    router_endpoints = estrai_router_endpoints(ROUTES_DIR)

    endpoints = main_endpoints + router_endpoints

    # Anche auth_routes.py vive nel backend ma fuori da routes/. Lo includo a mano.
    auth_routes_path = BACKEND_DIR / "auth_routes.py"
    if auth_routes_path.exists():
        contenuto = auth_routes_path.read_text()
        prefix_match = ROUTER_PREFIX_RE.search(contenuto)
        prefix = prefix_match.group(1) if prefix_match else ""
        auth_eps = estrai_endpoint_da_file(auth_routes_path, ROUTER_ENDPOINT_RE, prefix=prefix)
        endpoints.extend(auth_eps)

    # Endpoint pubblici legittimi (login rate-limited, logout pubblico per design)
    pubblici_attesi = {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
    }

    # ── Tabella ─────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"{'METODO':<8} {'PATH':<55} {'PROTEZIONE':<15} {'FILE':<22} {'RIGA':<5}")
    print("=" * 100)

    counts = {
        "MANAGER": 0,
        "AUTH+FILTRO": 0,
        "AUTH-ONLY": 0,
        "PUBLIC+RL": 0,
        "PUBLIC": 0,
        "MISSING": 0,
    }
    missing_endpoints = []

    for ep in sorted(endpoints, key=lambda x: x["path"]):
        # Endpoint pubblici legittimi: ok anche senza dependency
        if ep["path"] in pubblici_attesi and ep["tipo"] == "MISSING":
            ep["tipo"] = "PUBLIC+RL" if ep["path"] == "/api/auth/login" else "PUBLIC"

        emoji = "✓" if ep["tipo"] != "MISSING" else "⚠️"
        print(f"{ep['metodo']:<8} {ep['path']:<55} {emoji} {ep['tipo']:<13} {ep['file']:<22} {ep['riga']:<5}")

        if ep["tipo"] in counts:
            counts[ep["tipo"]] += 1
        if ep["tipo"] == "MISSING":
            missing_endpoints.append(ep)

    # ── Riepilogo ───────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("RIEPILOGO")
    print("=" * 100)
    totale = len(endpoints)
    print(f"  Totale endpoint:        {totale}")
    print(f"     da main.py:          {len(main_endpoints)}")
    print(f"     da routes/*.py:      {len(router_endpoints)}")
    print(f"     da auth_routes.py:   {len(endpoints) - len(main_endpoints) - len(router_endpoints)}")
    print()
    print(f"  ✓ MANAGER (admin only): {counts['MANAGER']}")
    print(f"  ✓ AUTH+FILTRO:          {counts['AUTH+FILTRO']}")
    print(f"  ✓ AUTH-ONLY:            {counts['AUTH-ONLY']}")
    print(f"  ✓ PUBLIC+RL (login):    {counts['PUBLIC+RL']}")
    print(f"  ✓ PUBLIC (logout/me):   {counts['PUBLIC']}")
    print(f"  ⚠️ MISSING:              {counts['MISSING']}")
    print()

    if missing_endpoints:
        print("⚠️  ENDPOINT NON PROTETTI:")
        for ep in missing_endpoints:
            print(f"     {ep['metodo']:<8} {ep['path']:<50} ({ep['file']}:{ep['riga']})")
        print()
        print("Aggiungi una dependency a questi endpoint!")
        sys.exit(1)
    else:
        print("✅ Tutti gli endpoint sono protetti correttamente!")


if __name__ == "__main__":
    main()