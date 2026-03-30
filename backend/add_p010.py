"""
Aggiunge un progetto "Vinto - Da pianificare" per testare la verifica IA.
Eseguire UNA VOLTA.
"""
from models import get_session, Progetto
from datetime import date

session = get_session()

# Verifica che non esista già
existing = session.query(Progetto).filter(Progetto.id == 'P010').first()
if existing:
    print("P010 esiste già, skip.")
else:
    session.add(Progetto(
        id='P010',
        nome='Piattaforma HR Interna',
        cliente='IMC-Group (interno)',
        stato='Vinto - Da pianificare',
        tipo='progetto',
        priorita='media',
        data_inizio=date(2026, 6, 1),
        data_fine=date(2026, 12, 31),
        budget_ore=800,
        valore_contratto=0,
        descrizione='Sistema interno per gestione ferie, presenze, note spese e anagrafica dipendenti. Progetto interno IMC-Group.',
        fase_corrente='Pianificazione',
    ))
    session.commit()
    print("✅ P010 'Piattaforma HR Interna' creato — stato: Vinto - Da pianificare")

session.close()
