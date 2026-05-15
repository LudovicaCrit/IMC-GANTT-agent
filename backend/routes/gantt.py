"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/gantt.py — Router per endpoint /api/gantt
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per la pagina GANTT del frontend:
  - Lettura dati GANTT in JSON (per rendering frappe-gantt nel frontend)
  - Esportazione GANTT in formato PDF, PNG e Excel (download file)
Tutti gli endpoint sono manager-only (vista d'insieme aziendale).

Decisione di design (5 maggio 2026): tutti gli endpoint /api/gantt/*
in un unico file. Coerente con il principio "1 prefix = 1 file" e con la
discoverability per chi cerca dove vivono i GANTT. Se in futuro arriveranno
altri export non-GANTT (es. Excel di marginalità, PDF di consuntivi),
si valuterà di nuovo la scorporazione in un eventuale `routes/export.py`.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/gantt                       │ GET      │ require_manager              │
│ /api/gantt/strutturato           │ GET      │ require_manager              │
│ /api/gantt/export-pdf            │ GET      │ require_manager              │
│ /api/gantt/export-png            │ GET      │ require_manager              │
│ /api/gantt/export-excel          │ GET      │ require_manager              │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/gantt?progetto_id=P00X
   - Manager-only.
   - Parametro opzionale: filtra per progetto.
   - Esclude task con stato "Eliminato" (soft delete).
   - Restituisce JSON formattato per la libreria frappe-gantt:
     id, name, start, end, progress (calcolato da ore_consuntivate/ore_stimate),
     dependencies (predecessore), project, project_id, assignee, profile,
     status, estimated_hours, hours_done, predecessor_name.

2. GET /api/gantt/export-pdf?progetto_id=P00X
   - Manager-only.
   - Genera un PDF tramite `gantt_pdf.genera_gantt_pdf` (modulo dedicato).
   - Filtra automaticamente progetti non sospesi se non c'è filtro esplicito.
   - Response: application/pdf con Content-Disposition: attachment.

3. GET /api/gantt/export-png?progetto_id=P00X
   - Manager-only.
   - Genera prima il PDF, poi lo converte in PNG via `pdftoppm` (poppler-utils).
   - Risoluzione: 200 dpi, single page.
   - 500 con messaggio specifico se `pdftoppm` non è installato.

4. GET /api/gantt/export-excel?progetto_id=P00X
   - Manager-only.
   - Genera un .xlsx con due fogli:
     • "Dati GANTT": tabella con stati colorati per riga
     • "GANTT Visivo": rappresentazione a barre settimanali, raggruppate
       per progetto, con legenda stati
   - Fallback CSV se openpyxl non è installato.

PATTERN AUTH USATI
──────────────────
- `require_manager` su tutti e 4 gli endpoint. Il GANTT aziendale e i suoi
  export sono informazione manageriale (Scenario B); Helena vede solo i
  propri task tramite `/api/tasks` con filtro Scenario B.

DIPENDENZE ESTERNE (oltre al backend)
─────────────────────────────────────
- `gantt_pdf` (modulo locale): `genera_gantt_pdf()` — usato da PDF e PNG
- `reportlab` (via gantt_pdf): rendering PDF
- `pdftoppm` (binario poppler-utils): conversione PDF→PNG. Sistema Linux:
  `sudo apt install poppler-utils`. Se manca, l'endpoint risponde 500 con
  messaggio chiaro.
- `openpyxl`: rendering Excel. Se manca, fallback su CSV.
- `pandas`: manipolazione DataFrame in export.

📌 TODO Blocco 2 roadmap (Macchina delle Fasi):
   Riprogettare `dati_gantt` per restituire dati strutturati a livello di
   fase, non solo task piatti. Il GANTT diventerà "barre raggruppate per
   fase, espandibili al dettaglio task" — coerente con la vista per fasi
   discussa con Vincenzo (post-Francesco).
   Gli export andranno adattati di conseguenza.

DIPENDENZE INTERNE
──────────────────
- `data` (modulo): `get_dipendente`, e DataFrame PROGETTI/TASKS/CONSUNTIVI.
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper locali `_PROGETTI()`, `_TASKS()`, `_CONSUNTIVI()`.
📌 TODO: estrarre in `backend/dataframes.py` quando ≥3 router li replicano
(condizione già soddisfatta — da fare presto).

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
Tutti e 4 gli endpoint /api/gantt/* sono qui (decisione presa con Ludovica
durante il refactoring stesso).
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from deps import require_manager
from models import (
    Utente, Progetto, Fase, Task, Consuntivo, get_session,
    STATI_PROGETTO_ATTIVI,
)
from data import get_dipendente
from dataframes import _PROGETTI, _TASKS, _CONSUNTIVI


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/gantt", tags=["gantt"])


# ═════════════════════════════════════════════════════════════════════════
# 1. GET /api/gantt — dati strutturati per il rendering frontend
# ═════════════════════════════════════════════════════════════════════════

@router.get("")
def dati_gantt(
    progetto_id: Optional[str] = None,
    _: Utente = Depends(require_manager),
):
    """Restituisce i dati formattati per il componente GANTT del frontend."""
    tasks = _TASKS().copy()
    tasks = tasks[tasks["stato"] != "Eliminato"]
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]

    result = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]
        # Ore consuntivate reali per questo task
        cons_task = _CONSUNTIVI()[_CONSUNTIVI()["task_id"] == t["id"]]
        ore_cons = float(cons_task["ore_dichiarate"].sum()) if len(cons_task) > 0 else 0
        ore_stimate = int(t["ore_stimate"]) if t["ore_stimate"] else 0

        # Progress calcolato su ore consuntivate / ore stimate
        if t["stato"] == "Completato":
            progress = 100
        elif ore_stimate > 0 and ore_cons > 0:
            progress = min(99, round(ore_cons / ore_stimate * 100))
        else:
            progress = 0

        result.append({
            "id": t["id"],
            "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "progress": progress,
            "dependencies": t["predecessore"] if t["predecessore"] else "",
            "predecessor_name": "",  # popolato sotto se c'è predecessore
            "project": proj["nome"],
            "project_id": t["progetto_id"],
            "assignee": dip["nome"],
            "profile": dip["profilo"],
            "status": t["stato"],
            "estimated_hours": ore_stimate,
            "hours_done": round(ore_cons, 1),
        })

        # Aggiungi nome predecessore (per il pannello dettaglio del frontend)
        if t["predecessore"]:
            pred_row = _TASKS()[_TASKS()["id"] == t["predecessore"]]
            if len(pred_row) > 0:
                result[-1]["predecessor_name"] = pred_row.iloc[0]["nome"]

    return result


# ═════════════════════════════════════════════════════════════════════════
# 1.b GET /api/gantt/strutturato — gerarchia Progetto → Fase → Task
# ═════════════════════════════════════════════════════════════════════════

@router.get("/strutturato")
def gantt_strutturato(
    stato: Optional[str] = None,
    progetto_id: Optional[str] = None,
    _: Utente = Depends(require_manager),
):
    """Restituisce la gerarchia Progetto → Fase → Task per il drill-down GANTT.

    Step 2.2 del Blocco 2 esteso (handoff v15 §2.2 punto 1, §2.3).

    Filtri query params:
    - `stato`: filtra i progetti per stato. Default: "attivi"
      (In esecuzione + Sospeso, allineato a handoff §3.3).
      Valori: "attivi" | "all" | "bozza" | "in esecuzione" | ...
    - `progetto_id`: drill su un singolo progetto (utile per `/cantiere/{id}`).

    Struttura risposta:
    [
      {
        "id": "P001", "nome": "...", "cliente": "...", "stato": "...",
        "data_inizio": "...", "data_fine": "...",
        "ore_vendute_totali": 240, "ore_consumate_totali": 130,
        "fasi": [
          {
            "id": 1, "nome": "Analisi", "ordine": 1, "stato": "In corso",
            "data_inizio": "...", "data_fine": "...",
            "ore_vendute": 80, "ore_consumate": 50,
            "tasks": [
              {
                "id": "T001", "nome": "...", "stato": "...",
                "ore_stimate": 40, "ore_consumate": 25,
                "data_inizio": "...", "data_fine": "...",
                "dipendente_id": "...", "dipendente_nome": "...",
                "predecessore": ""
              }, ...
            ]
          }, ...
        ]
      }, ...
    ]

    Design:
    - L'endpoint è "stupido": restituisce dati raw. Il frontend calcola
      progress %, colori, default aperture (handoff §2.3 "fasi In corso
      aperte" è scelta UI, non backend).
    - Performance: joinedload per evitare N+1 query su fasi e task.
    - Aggregazioni ore: una query sum() sui consuntivi per evitare
      iterazioni Python.
    """
    session = get_session()
    try:
        # ── 1. Query progetti con filtro stato ────────────────────────
        q = session.query(Progetto).options(
            joinedload(Progetto.fasi).joinedload(Fase.task)
        )
        if progetto_id:
            q = q.filter(Progetto.id == progetto_id)
        elif stato is None or stato.lower() == "attivi":
            q = q.filter(Progetto.stato.in_(STATI_PROGETTO_ATTIVI))
        elif stato.lower() != "all":
            q = q.filter(func.lower(Progetto.stato) == stato.lower())
        progetti = q.order_by(Progetto.id).all()

        # ── 2. Tutti i consuntivi in una query ────────────────────────
        # Aggrego per task_id per non fare N+1 nel loop sotto.
        task_ids_all = [t.id for p in progetti for f in p.fasi for t in f.task]
        ore_per_task = {}
        if task_ids_all:
            righe = session.query(
                Consuntivo.task_id,
                func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0)
            ).filter(Consuntivo.task_id.in_(task_ids_all)).group_by(Consuntivo.task_id).all()
            ore_per_task = {tid: float(ore) for tid, ore in righe}

        # ── 3. Cache nomi dipendenti per evitare lookup ripetuti ──────
        from models import Dipendente
        dip_rows = session.query(Dipendente).all()
        nomi_dip = {d.id: d.nome for d in dip_rows}

        # ── 4. Costruzione struttura nidificata ──────────────────────
        result = []
        for p in progetti:
            # Filtra fasi: nessun filtro qui, mostriamo tutte le fasi del progetto.
            # Il frontend decide quali aprire/chiudere per default.
            fasi_serial = []
            ore_vendute_proj = 0.0
            ore_consumate_proj = 0.0

            for f in sorted(p.fasi, key=lambda x: x.ordine or 0):
                tasks_serial = []
                ore_consumate_fase = 0.0
                for t in f.task:
                    ore_cons_t = ore_per_task.get(t.id, 0.0)
                    ore_consumate_fase += ore_cons_t
                    tasks_serial.append({
                        "id": t.id,
                        "nome": t.nome,
                        "stato": t.stato,
                        "ore_stimate": int(t.ore_stimate) if t.ore_stimate else 0,
                        "ore_consumate": round(ore_cons_t, 1),
                        "data_inizio": t.data_inizio.isoformat() if t.data_inizio else None,
                        "data_fine": t.data_fine.isoformat() if t.data_fine else None,
                        "dipendente_id": t.dipendente_id or "",
                        "dipendente_nome": nomi_dip.get(t.dipendente_id, ""),
                        "profilo_richiesto": t.profilo_richiesto or "",
                        "predecessore": t.predecessore or "",
                    })

                ore_vendute_fase = float(f.ore_vendute or 0)
                ore_vendute_proj += ore_vendute_fase
                ore_consumate_proj += ore_consumate_fase

                fasi_serial.append({
                    "id": f.id,
                    "nome": f.nome,
                    "ordine": f.ordine,
                    "stato": f.stato,
                    "data_inizio": f.data_inizio.isoformat() if f.data_inizio else None,
                    "data_fine": f.data_fine.isoformat() if f.data_fine else None,
                    "ore_vendute": ore_vendute_fase,
                    "ore_pianificate": float(f.ore_pianificate or 0),
                    "ore_consumate": round(ore_consumate_fase, 1),
                    "n_task": len(tasks_serial),
                    "tasks": tasks_serial,
                })

            result.append({
                "id": p.id,
                "nome": p.nome,
                "cliente": p.cliente,
                "stato": p.stato,
                "stato_derivato": p.stato_derivato,  # property calcolata
                "tipologia": p.tipologia or "ordinario",
                "data_inizio": p.data_inizio.isoformat() if p.data_inizio else None,
                "data_fine": p.data_fine.isoformat() if p.data_fine else None,
                "budget_ore": int(p.budget_ore) if p.budget_ore else 0,
                "pm_id": p.pm_id,
                "ore_vendute_totali": ore_vendute_proj,
                "ore_consumate_totali": round(ore_consumate_proj, 1),
                "n_fasi": len(fasi_serial),
                "fasi": fasi_serial,
            })

        return result
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# 2. GET /api/gantt/export-pdf — esportazione PDF
# ═════════════════════════════════════════════════════════════════════════

@router.get("/export-pdf")
def export_gantt_pdf(
    progetto_id: Optional[str] = None,
    _: Utente = Depends(require_manager),
):
    """Genera e scarica un PDF del GANTT."""
    from gantt_pdf import genera_gantt_pdf

    # Riusa la logica di dati_gantt
    tasks = _TASKS().copy()
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]

    # Filtra solo progetti attivi (esclude sospesi)
    progetti_attivi = _PROGETTI()[~_PROGETTI()["stato"].isin(["Sospeso"])]["id"].tolist()
    if not progetto_id:
        tasks = tasks[tasks["progetto_id"].isin(progetti_attivi)]

    gantt_data = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
        proj_nome = proj.iloc[0]["nome"] if len(proj) > 0 else "?"
        gantt_data.append({
            "id": t["id"],
            "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "project": proj_nome,
            "assignee": dip["nome"],
            "status": t["stato"],
            "estimated_hours": int(t["ore_stimate"]),
        })

    # Titolo
    if progetto_id:
        proj = _PROGETTI()[_PROGETTI()["id"] == progetto_id]
        titolo = f"GANTT — {proj.iloc[0]['nome']}" if len(proj) > 0 else "GANTT"
    else:
        titolo = "GANTT IMC-Group — Tutti i progetti"

    pdf_bytes = genera_gantt_pdf(gantt_data, titolo=titolo, progetto_filtro=progetto_id)
    filename = f"gantt_{progetto_id or 'tutti'}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ═════════════════════════════════════════════════════════════════════════
# 3. GET /api/gantt/export-png — esportazione PNG (via PDF + pdftoppm)
# ═════════════════════════════════════════════════════════════════════════

@router.get("/export-png")
def export_gantt_png(
    progetto_id: Optional[str] = None,
    _: Utente = Depends(require_manager),
):
    """Genera e scarica un PNG del GANTT (convertendo il PDF)."""
    from gantt_pdf import genera_gantt_pdf
    import subprocess
    import tempfile
    import os

    # Genera prima il PDF (come export-pdf)
    tasks = _TASKS().copy()
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]
    progetti_attivi = _PROGETTI()[~_PROGETTI()["stato"].isin(["Sospeso"])]["id"].tolist()
    if not progetto_id:
        tasks = tasks[tasks["progetto_id"].isin(progetti_attivi)]

    gantt_data = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
        proj_nome = proj.iloc[0]["nome"] if len(proj) > 0 else "?"
        gantt_data.append({
            "id": t["id"], "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "project": proj_nome, "assignee": dip["nome"],
            "status": t["stato"], "estimated_hours": int(t["ore_stimate"]),
        })

    if progetto_id:
        proj = _PROGETTI()[_PROGETTI()["id"] == progetto_id]
        titolo = f"GANTT — {proj.iloc[0]['nome']}" if len(proj) > 0 else "GANTT"
    else:
        titolo = "GANTT IMC-Group — Tutti i progetti"

    pdf_bytes = genera_gantt_pdf(gantt_data, titolo=titolo)

    # Converti PDF → PNG con pdftoppm (poppler-utils)
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(pdf_bytes)
            tmp_pdf_path = tmp_pdf.name

        png_path = tmp_pdf_path.replace(".pdf", "")
        subprocess.run(
            ["pdftoppm", "-png", "-r", "200", "-singlefile", tmp_pdf_path, png_path],
            check=True, capture_output=True
        )

        png_file = png_path + ".png"
        with open(png_file, "rb") as f:
            png_bytes = f.read()

        os.unlink(tmp_pdf_path)
        os.unlink(png_file)

        filename = f"gantt_{progetto_id or 'tutti'}_{datetime.now().strftime('%Y%m%d')}.png"
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except (subprocess.CalledProcessError, FileNotFoundError):
        raise HTTPException(
            500,
            "Conversione PNG non disponibile. Installa poppler-utils: sudo apt install poppler-utils"
        )


# ═════════════════════════════════════════════════════════════════════════
# 4. GET /api/gantt/export-excel — esportazione Excel (2 fogli)
# ═════════════════════════════════════════════════════════════════════════

@router.get("/export-excel")
def export_gantt_excel(
    progetto_id: Optional[str] = None,
    _: Utente = Depends(require_manager),
):
    """Genera e scarica un file Excel con i dati GANTT + foglio visivo."""
    import io
    import pandas as pd

    tasks = _TASKS().copy()
    tasks = tasks[tasks["stato"] != "Eliminato"]
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]
    progetti_attivi = _PROGETTI()[~_PROGETTI()["stato"].isin(["Sospeso"])]["id"].tolist()
    if not progetto_id:
        tasks = tasks[tasks["progetto_id"].isin(progetti_attivi)]

    # Costruisci DataFrame per l'export
    export_data = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
        proj_nome = proj.iloc[0]["nome"] if len(proj) > 0 else "?"
        export_data.append({
            "Progetto": proj_nome,
            "Task": t["nome"],
            "Fase": t["fase"],
            "Assegnato a": dip["nome"],
            "Profilo": dip["profilo"],
            "Ore stimate": int(t["ore_stimate"]),
            "Data inizio": t["data_inizio"] if hasattr(t["data_inizio"], "strftime") else t["data_inizio"],
            "Data fine": t["data_fine"] if hasattr(t["data_fine"], "strftime") else t["data_fine"],
            "Stato": t["stato"],
        })

    df = pd.DataFrame(export_data)
    df = df.sort_values(["Progetto", "Data inizio"])

    buffer = io.BytesIO()
    try:
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.utils import get_column_letter

        wb = Workbook()

        # ═══ FOGLIO 1: Tabella dati ═══
        ws_data = wb.active
        ws_data.title = "Dati GANTT"

        headers = ["Progetto", "Task", "Fase", "Assegnato a", "Profilo",
                   "Ore stimate", "Data inizio", "Data fine", "Stato"]
        header_fill = PatternFill(start_color="1a365d", end_color="1a365d", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)

        for col, h in enumerate(headers, 1):
            cell = ws_data.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Dati con colore per stato
        for row_idx, (_, row) in enumerate(df.iterrows(), 2):
            for col_idx, h in enumerate(headers, 1):
                val = row[h]
                if h in ("Data inizio", "Data fine") and hasattr(val, "strftime"):
                    val = val.strftime("%d/%m/%Y")
                cell = ws_data.cell(row=row_idx, column=col_idx, value=val)
                cell.alignment = Alignment(horizontal="left")

                if row["Stato"] == "Completato":
                    cell.fill = PatternFill(start_color="d4edda", end_color="d4edda", fill_type="solid")
                elif row["Stato"] == "Da iniziare":
                    cell.fill = PatternFill(start_color="e2e8f0", end_color="e2e8f0", fill_type="solid")

        # Auto-width
        for col in range(1, len(headers) + 1):
            max_len = max(
                len(str(ws_data.cell(row=r, column=col).value or ""))
                for r in range(1, ws_data.max_row + 1)
            )
            ws_data.column_dimensions[get_column_letter(col)].width = min(35, max(10, max_len + 2))

        # ═══ FOGLIO 2: GANTT Visivo ═══
        ws_gantt = wb.create_sheet("GANTT Visivo")

        # Trova range date
        date_inizio = []
        date_fine = []
        for _, t in tasks.iterrows():
            di = t["data_inizio"]
            df_t = t["data_fine"]
            if hasattr(di, "date"):
                date_inizio.append(di)
                date_fine.append(df_t)

        if not date_inizio:
            ws_gantt.cell(row=1, column=1, value="Nessun task da visualizzare")
        else:
            from datetime import timedelta as td
            min_date = min(date_inizio)
            max_date = max(date_fine)

            # Genera settimane (lunedì del primo task → venerdì dell'ultimo + 1 sett)
            settimane = []
            current = min_date - td(days=min_date.weekday())  # lunedì
            while current <= max_date + td(days=7):
                settimane.append(current)
                current += td(days=7)

            n_sett = len(settimane)

            # Colori per progetto (mantenuti per coerenza con vista frontend)
            colori_progetto = {
                "Adeguamento DORA": "4472C4",
                "Framework Compliance 262": "ED7D31",
                "Digitalizzazione Corpo Normativo": "70AD47",
                "Risk Assessment Operativo": "FFC000",
                "ProcessBook Aziendale": "9B59B6",
                "Attività Interne": "95A5A6",
            }
            colore_default = "5B9BD5"

            # Colori per stato
            colori_stato = {
                "Completato": "27ae60",
                "In corso": "3498db",
                "Da iniziare": "95a5a6",
                "Sospeso": "e67e22",
            }

            # Header
            ws_gantt.cell(row=1, column=1, value="Task").font = Font(bold=True, size=9)
            ws_gantt.cell(row=1, column=2, value="Risorsa").font = Font(bold=True, size=9)
            ws_gantt.cell(row=1, column=3, value="Progetto").font = Font(bold=True, size=9)
            ws_gantt.cell(row=1, column=4, value="Stato").font = Font(bold=True, size=9)

            for i, sett in enumerate(settimane):
                cell = ws_gantt.cell(row=1, column=5 + i, value=sett.strftime("%d/%m"))
                cell.font = Font(size=7, bold=True)
                cell.alignment = Alignment(horizontal="center", text_rotation=90)
                ws_gantt.column_dimensions[get_column_letter(5 + i)].width = 4

            ws_gantt.column_dimensions["A"].width = 30
            ws_gantt.column_dimensions["B"].width = 18
            ws_gantt.column_dimensions["C"].width = 22
            ws_gantt.column_dimensions["D"].width = 12

            # Header fill
            for col in range(1, 5 + n_sett):
                ws_gantt.cell(row=1, column=col).fill = PatternFill(
                    start_color="2c3e50", end_color="2c3e50", fill_type="solid"
                )
                ws_gantt.cell(row=1, column=col).font = Font(color="FFFFFF", bold=True, size=8)

            # Righe task
            row = 2
            current_project = ""
            for _, t in tasks.sort_values(["progetto_id", "data_inizio"]).iterrows():
                dip = get_dipendente(t["dipendente_id"])
                proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
                proj_nome = proj.iloc[0]["nome"] if len(proj) > 0 else "?"

                # Riga separatore progetto
                if proj_nome != current_project:
                    current_project = proj_nome
                    sep_cell = ws_gantt.cell(row=row, column=1, value=proj_nome.upper())
                    sep_cell.font = Font(bold=True, size=9, color="FFFFFF")
                    proj_color = colori_progetto.get(proj_nome, colore_default)
                    for col in range(1, 5 + n_sett):
                        ws_gantt.cell(row=row, column=col).fill = PatternFill(
                            start_color=proj_color, end_color=proj_color, fill_type="solid"
                        )
                    row += 1

                # Task info
                ws_gantt.cell(row=row, column=1, value=t["nome"]).font = Font(size=9)
                ws_gantt.cell(row=row, column=2, value=dip["nome"]).font = Font(size=8, color="666666")
                ws_gantt.cell(row=row, column=3, value=proj_nome).font = Font(size=8, color="666666")
                ws_gantt.cell(row=row, column=4, value=t["stato"]).font = Font(size=8)

                # Colore stato nella cella stato
                stato_color = colori_stato.get(t["stato"], "95a5a6")
                ws_gantt.cell(row=row, column=4).fill = PatternFill(
                    start_color=stato_color, end_color=stato_color, fill_type="solid"
                )
                ws_gantt.cell(row=row, column=4).font = Font(size=8, color="FFFFFF")

                # Barre GANTT
                task_start = t["data_inizio"]
                task_end = t["data_fine"]
                bar_color = colori_stato.get(t["stato"], colore_default)

                for i, sett in enumerate(settimane):
                    sett_end = sett + td(days=6)
                    if task_start <= sett_end and task_end >= sett:
                        ws_gantt.cell(row=row, column=5 + i).fill = PatternFill(
                            start_color=bar_color, end_color=bar_color, fill_type="solid"
                        )

                row += 1

            # Legenda in fondo
            row += 2
            ws_gantt.cell(row=row, column=1, value="Legenda:").font = Font(bold=True, size=9)
            row += 1
            for stato, colore in colori_stato.items():
                ws_gantt.cell(row=row, column=1, value=stato).font = Font(size=9)
                ws_gantt.cell(row=row, column=2).fill = PatternFill(
                    start_color=colore, end_color=colore, fill_type="solid"
                )
                row += 1

        wb.save(buffer)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"

    except ImportError:
        # Fallback CSV
        buffer = io.BytesIO()
        df_export = df.copy()
        df_export["Data inizio"] = df_export["Data inizio"].apply(
            lambda x: x.strftime("%d/%m/%Y") if hasattr(x, "strftime") else str(x)
        )
        df_export["Data fine"] = df_export["Data fine"].apply(
            lambda x: x.strftime("%d/%m/%Y") if hasattr(x, "strftime") else str(x)
        )
        df_export.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
        media_type = "text/csv"
        ext = "csv"

    buffer.seek(0)
    filename = f"gantt_{progetto_id or 'tutti'}_{datetime.now().strftime('%Y%m%d')}.{ext}"
    return Response(
        content=buffer.getvalue(),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )