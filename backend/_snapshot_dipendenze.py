#!/usr/bin/env python3
"""_snapshot_dipendenze.py — snapshot READ-ONLY di dipendenza_task.

Stampa: totale, conteggio per tipo, ed elenco ordinato delle coppie
(predecessore, successore, tipo). Salva l'elenco in JSON per il confronto
post-reseed. NON scrive nulla sul DB.

Uso:
  python _snapshot_dipendenze.py            # cattura + salva in /tmp
  python _snapshot_dipendenze.py --confronta # confronta DB attuale col JSON salvato
"""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from models import get_session, DipendenzaTask

OUT = "/tmp/_snapshot_dipendenze.json"


def leggi_coppie():
    s = get_session()
    try:
        return sorted(
            (d.task_predecessore_id, d.task_successore_id, d.tipo_dipendenza)
            for d in s.query(DipendenzaTask).all()
        )
    finally:
        s.close()


def stampa(coppie):
    per_tipo = {}
    for _, _, tipo in coppie:
        per_tipo[tipo] = per_tipo.get(tipo, 0) + 1
    print(f"Totale dipendenze: {len(coppie)}")
    print("Per tipo:")
    for tipo, n in sorted(per_tipo.items()):
        print(f"  {tipo} | {n}")
    print("\nCoppie (pred -> succ [tipo]):")
    for pred, succ, tipo in coppie:
        print(f"  {pred} -> {succ}  [{tipo}]")


def main():
    coppie = leggi_coppie()

    if "--confronta" in sys.argv:
        with open(OUT) as f:
            atteso = sorted(tuple(c) for c in json.load(f))
        print("=== CONFRONTO col DB fresco ===")
        stampa(coppie)
        if coppie == atteso:
            print(f"\nOK — identico allo snapshot ({len(coppie)} coppie).")
        else:
            mancanti = sorted(set(atteso) - set(coppie))
            extra = sorted(set(coppie) - set(atteso))
            print(f"\nDIVERSO dallo snapshot! mancanti={mancanti} extra={extra}")
            sys.exit(1)
        return

    stampa(coppie)
    with open(OUT, "w") as f:
        json.dump([list(c) for c in coppie], f, indent=2)
    print(f"\nSnapshot salvato in {OUT}")


if __name__ == "__main__":
    main()
