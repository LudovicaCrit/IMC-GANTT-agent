"""
Diagnostico pre-migration D1 (Step 2.1, handoff v15 §2.1).

Scopo: prima di toccare la migration, capire lo stato dei dati esistenti.
- Quanti task hanno fase_id valorizzato? Quanti no?
- Quanti task hanno Task.fase (stringa) valorizzato? Quanti no?
- Per i task con `fase` stringa ma senza `fase_id`, esiste una `Fase` nel
  loro progetto che matcha esattamente per nome?
- Quanti task sono "orfani" (hanno fase stringa che non matcha nessuna Fase)?
- Caso speciale: task interni di P010 (`routes/attivita_interne.py` scrive
  `fase=categoria` con valori come "Formazione", "Ferie", ecc.).

NON modifica nulla. Solo SELECT.

Uso:
    cd ~/Azienda/Use_Case_3_GANTT/backend
    source .venvu/bin/activate  # o dove sta il venv
    python diagnostico_d1.py
"""
from collections import Counter, defaultdict
from models import get_session, Task, Fase, Progetto


def main():
    session = get_session()

    # ── Conteggi base ────────────────────────────────────────────────────
    totale_task = session.query(Task).count()
    task_con_fase_id = session.query(Task).filter(Task.fase_id.isnot(None)).count()
    task_con_fase_str = session.query(Task).filter(
        Task.fase.isnot(None), Task.fase != ""
    ).count()
    task_con_entrambi = session.query(Task).filter(
        Task.fase_id.isnot(None),
        Task.fase.isnot(None), Task.fase != ""
    ).count()
    task_senza_nulla = session.query(Task).filter(
        Task.fase_id.is_(None),
        (Task.fase.is_(None)) | (Task.fase == "")
    ).count()

    print("=" * 70)
    print("DIAGNOSTICO D1 — Stato attuale Task.fase / Task.fase_id")
    print("=" * 70)
    print(f"Task totali nel DB:              {totale_task}")
    print(f"  con fase_id valorizzato:       {task_con_fase_id}")
    print(f"  con fase (stringa) valorizzata:{task_con_fase_str}")
    print(f"  con entrambi:                  {task_con_entrambi}")
    print(f"  senza nessuno dei due:         {task_senza_nulla}")
    print()

    # ── Per ogni task con fase stringa ma senza fase_id: matcha o orfano? ─
    candidati = session.query(Task).filter(
        Task.fase_id.is_(None),
        Task.fase.isnot(None), Task.fase != ""
    ).all()

    matchabili = []  # (task_id, fase_stringa, fase.id matched)
    orfani = []      # (task_id, progetto_id, fase_stringa) — nessun match

    # Costruisco un dict {(progetto_id, nome_fase): fase.id}
    fasi_by_key = {
        (f.progetto_id, f.nome.strip().lower()): f.id
        for f in session.query(Fase).all()
    }

    for t in candidati:
        key = (t.progetto_id, (t.fase or "").strip().lower())
        if key in fasi_by_key:
            matchabili.append((t.id, t.fase, fasi_by_key[key]))
        else:
            orfani.append((t.id, t.progetto_id, t.fase))

    print(f"Task da migrare (fase_id NULL, fase stringa valorizzata): {len(candidati)}")
    print(f"  matchabili (esiste Fase con quel nome nel progetto):   {len(matchabili)}")
    print(f"  ORFANI (nessuna Fase matcha):                          {len(orfani)}")
    print()

    # ── Orfani: dettaglio raggruppato per progetto ───────────────────────
    if orfani:
        print("─" * 70)
        print("ORFANI (DETTAGLIO)")
        print("─" * 70)
        per_progetto = defaultdict(list)
        for task_id, prog_id, fase_str in orfani:
            per_progetto[prog_id].append((task_id, fase_str))
        for prog_id, items in sorted(per_progetto.items()):
            prog = session.query(Progetto).filter(Progetto.id == prog_id).first()
            prog_nome = prog.nome if prog else "<???>"
            print(f"\n{prog_id} — {prog_nome} ({len(items)} task orfani)")
            # Mostro fasi reali esistenti di questo progetto
            fasi_reali = session.query(Fase).filter(Fase.progetto_id == prog_id).all()
            print(f"  Fasi esistenti del progetto: {[f.nome for f in fasi_reali] or '(NESSUNA)'}")
            # Mostro i primi 5 task orfani
            categorie_orfane = Counter(item[1] for item in items)
            print(f"  Stringhe fase orfane (con conteggio): {dict(categorie_orfane.most_common())}")

    # ── Caso speciale P010 ───────────────────────────────────────────────
    print()
    print("─" * 70)
    print("FOCUS P010 (attività interne)")
    print("─" * 70)
    task_p010 = session.query(Task).filter(Task.progetto_id == "P010").all()
    if not task_p010:
        print("Nessun task su P010.")
    else:
        print(f"Task totali su P010: {len(task_p010)}")
        fasi_p010 = session.query(Fase).filter(Fase.progetto_id == "P010").all()
        print(f"Fasi reali di P010: {[f.nome for f in fasi_p010] or '(NESSUNA)'}")
        cat_p010 = Counter(t.fase for t in task_p010)
        print(f"Stringhe fase usate sui task P010 (con conteggio): {dict(cat_p010.most_common())}")
        with_fid = sum(1 for t in task_p010 if t.fase_id is not None)
        print(f"Task P010 con fase_id già valorizzato: {with_fid}/{len(task_p010)}")

    session.close()
    print()
    print("=" * 70)
    print("FINE DIAGNOSTICO")
    print("=" * 70)


if __name__ == "__main__":
    main()
