"""
Generazione PDF del GANTT — IMC-Group
Disegna un diagramma GANTT professionale con reportlab.
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timedelta
import io


# ── Colori per stato ──
COLORI_STATO = {
    "Completato": HexColor("#22c55e"),
    "In corso":   HexColor("#3b82f6"),
    "Da iniziare": HexColor("#9ca3af"),
    "Sospeso":    HexColor("#d97706"),
}

COLORI_PROGETTO = [
    HexColor("#3b82f6"), HexColor("#8b5cf6"), HexColor("#ec4899"),
    HexColor("#f59e0b"), HexColor("#10b981"), HexColor("#06b6d4"),
    HexColor("#ef4444"), HexColor("#84cc16"), HexColor("#f97316"),
    HexColor("#6366f1"),
]


def genera_gantt_pdf(tasks, titolo="GANTT IMC-Group", progetto_filtro=None):
    """
    Genera un PDF con il diagramma GANTT.
    
    tasks: lista di dict con id, name, start, end, project, assignee, status, estimated_hours
    titolo: titolo del documento
    progetto_filtro: nome del progetto (se filtrato) o None per tutti
    
    Restituisce: bytes del PDF
    """
    buffer = io.BytesIO()
    
    # Orientamento landscape per il GANTT
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    if not tasks:
        c.setFont("Helvetica", 16)
        c.drawString(50, page_h - 80, "Nessun task da visualizzare.")
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    # ── Calcola range date ──
    all_starts = [datetime.strptime(t["start"], "%Y-%m-%d") for t in tasks]
    all_ends = [datetime.strptime(t["end"], "%Y-%m-%d") for t in tasks]
    date_min = min(all_starts)
    date_max = max(all_ends)
    total_days = max(1, (date_max - date_min).days)
    
    # ── Layout ──
    margin_left = 55 * mm
    margin_right = 10 * mm
    margin_top = 25 * mm
    margin_bottom = 15 * mm
    header_height = 12 * mm
    row_height = 6 * mm
    bar_height = 4 * mm
    
    chart_width = page_w - margin_left - margin_right
    chart_top = page_h - margin_top - header_height
    
    # Raggruppa per progetto
    progetti_unici = []
    for t in tasks:
        if t["project"] not in progetti_unici:
            progetti_unici.append(t["project"])
    
    colori_proj = {}
    for i, p in enumerate(progetti_unici):
        colori_proj[p] = COLORI_PROGETTO[i % len(COLORI_PROGETTO)]
    
    # ── Quante righe per pagina ──
    max_rows_per_page = int((chart_top - margin_bottom) / row_height)
    
    # ── Funzione per disegnare una pagina ──
    def draw_page(c, page_tasks, page_num, total_pages):
        # Titolo
        c.setFont("Helvetica-Bold", 14)
        c.drawString(15 * mm, page_h - 15 * mm, titolo)
        c.setFont("Helvetica", 8)
        c.drawString(15 * mm, page_h - 20 * mm,
            f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')} — "
            f"{len(tasks)} task — "
            f"dal {date_min.strftime('%d/%m/%Y')} al {date_max.strftime('%d/%m/%Y')}"
            f"  —  Pagina {page_num}/{total_pages}")
        
        # ── Header timeline (mesi) ──
        c.setFont("Helvetica-Bold", 7)
        current = date_min.replace(day=1)
        while current <= date_max:
            next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
            x_start = margin_left + ((current - date_min).days / total_days) * chart_width
            x_end = margin_left + (min((next_month - date_min).days, total_days) / total_days) * chart_width
            x_start = max(x_start, margin_left)
            x_end = min(x_end, margin_left + chart_width)
            
            if x_end > x_start + 5:
                # Sfondo mese alternato
                month_idx = current.month
                if month_idx % 2 == 0:
                    c.setFillColor(HexColor("#f0f0f0"))
                else:
                    c.setFillColor(HexColor("#e8e8e8"))
                c.rect(x_start, chart_top, x_end - x_start, header_height, fill=1, stroke=0)
                
                # Nome mese
                c.setFillColor(black)
                mesi_it = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"]
                label = f"{mesi_it[current.month-1]} {current.year}"
                mid_x = (x_start + x_end) / 2
                c.drawCentredString(mid_x, chart_top + 4 * mm, label)
            
            current = next_month
        
        # Bordo header
        c.setStrokeColor(HexColor("#cccccc"))
        c.line(margin_left, chart_top, margin_left + chart_width, chart_top)
        c.line(margin_left, chart_top + header_height, margin_left + chart_width, chart_top + header_height)
        
        # ── Linea "Oggi" ──
        oggi = datetime(2026, 3, 9)
        if date_min <= oggi <= date_max:
            x_oggi = margin_left + ((oggi - date_min).days / total_days) * chart_width
            c.setStrokeColor(HexColor("#ef4444"))
            c.setDash(3, 2)
            c.line(x_oggi, chart_top + header_height, x_oggi, chart_top - len(page_tasks) * row_height)
            c.setDash()
            c.setFont("Helvetica", 5)
            c.setFillColor(HexColor("#ef4444"))
            c.drawCentredString(x_oggi, chart_top + header_height + 2, "Oggi")
            c.setFillColor(black)
        
        # ── Righe task ──
        current_project = None
        for i, t in enumerate(page_tasks):
            y = chart_top - (i + 1) * row_height
            
            # Banda progetto (sfondo alternato per progetto)
            proj_idx = progetti_unici.index(t["project"]) if t["project"] in progetti_unici else 0
            if proj_idx % 2 == 0:
                c.setFillColor(HexColor("#fafafa"))
            else:
                c.setFillColor(HexColor("#f5f5f5"))
            c.rect(0, y, page_w, row_height, fill=1, stroke=0)
            
            # Separatore progetto
            if t["project"] != current_project:
                current_project = t["project"]
                c.setStrokeColor(HexColor("#dddddd"))
                c.line(0, y + row_height, page_w, y + row_height)
            
            # Nome task (colonna sinistra)
            c.setFont("Helvetica", 6)
            c.setFillColor(black)
            task_label = t["name"]
            if len(task_label) > 35:
                task_label = task_label[:33] + "..."
            c.drawString(3 * mm, y + 2 * mm, task_label)
            
            # Assegnato (sotto il nome)
            c.setFont("Helvetica", 4.5)
            c.setFillColor(HexColor("#888888"))
            c.drawString(3 * mm, y + 0.3 * mm, f"{t['assignee']} · {t['project']}")
            
            # ── Barra GANTT ──
            t_start = datetime.strptime(t["start"], "%Y-%m-%d")
            t_end = datetime.strptime(t["end"], "%Y-%m-%d")
            
            x1 = margin_left + ((t_start - date_min).days / total_days) * chart_width
            x2 = margin_left + ((t_end - date_min).days / total_days) * chart_width
            bar_w = max(x2 - x1, 2)  # minimo 2pt visibile
            
            # Colore barra per stato
            color = COLORI_STATO.get(t.get("status", "Da iniziare"), HexColor("#9ca3af"))
            c.setFillColor(color)
            bar_y = y + (row_height - bar_height) / 2
            c.roundRect(x1, bar_y, bar_w, bar_height, 1.5, fill=1, stroke=0)
            
            # Ore stimate sulla barra
            if bar_w > 20:
                c.setFont("Helvetica-Bold", 4.5)
                c.setFillColor(white)
                c.drawCentredString(x1 + bar_w / 2, bar_y + 1.2 * mm,
                    f"{t.get('estimated_hours', '')}h")
        
        # ── Legenda ──
        legend_y = margin_bottom - 2 * mm
        c.setFont("Helvetica", 6)
        x_leg = margin_left
        for stato, colore in COLORI_STATO.items():
            c.setFillColor(colore)
            c.rect(x_leg, legend_y, 8, 5, fill=1, stroke=0)
            c.setFillColor(black)
            c.drawString(x_leg + 10, legend_y + 0.5, stato)
            x_leg += 55
    
    # ── Genera pagine ──
    # Ordina task per progetto
    tasks_sorted = sorted(tasks, key=lambda t: (
        progetti_unici.index(t["project"]) if t["project"] in progetti_unici else 99,
        t["start"]
    ))
    
    total_pages = max(1, -(-len(tasks_sorted) // max_rows_per_page))  # ceil division
    
    for page in range(total_pages):
        start_idx = page * max_rows_per_page
        end_idx = min(start_idx + max_rows_per_page, len(tasks_sorted))
        page_tasks = tasks_sorted[start_idx:end_idx]
        
        draw_page(c, page_tasks, page + 1, total_pages)
        if page < total_pages - 1:
            c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
