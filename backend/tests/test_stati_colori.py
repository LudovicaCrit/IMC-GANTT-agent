"""
Il file degli stati condiviso (condiviso/stati.json), letto dal backend.

Test puri: nessun database. Il file è la fonte unica dei colori per il
frontend (statiColori.js) e per l'export Excel (stati_colori.py): qui si
controlla che il backend lo trovi e lo legga, e che gli stati siano quelli
che il database ammette (models.py).
"""

import re

from models import STATI_FASE, STATI_PROGETTO, STATI_TASK
from stati_colori import FILE_STATI, carica_stati, colore_stato


def test_il_backend_legge_il_file_dalla_radice_del_repo():
    assert FILE_STATI.is_file(), FILE_STATI
    assert FILE_STATI.parent.name == "condiviso"
    stati = carica_stati()
    assert set(stati) == {"progetto", "fase", "task", "ignoto"}


def test_gli_stati_sono_quelli_di_models_nello_stesso_ordine():
    stati = carica_stati()
    assert tuple(stati["progetto"]) == STATI_PROGETTO
    assert tuple(stati["fase"]) == STATI_FASE
    assert tuple(stati["task"]) == STATI_TASK


def test_ogni_voce_ha_colore_esadecimale_ed_etichetta():
    stati = carica_stati()
    esadecimale = re.compile(r"^#[0-9a-fA-F]{6}$")
    assert esadecimale.match(stati["ignoto"]["colore"])
    for livello in ("progetto", "fase", "task"):
        for stato, voce in stati[livello].items():
            assert esadecimale.match(voce["colore"]), (livello, stato)
            assert voce["etichetta"], (livello, stato)


def test_colore_stato_e_il_neutro_per_gli_ignoti():
    stati = carica_stati()
    assert colore_stato(stati, "task", "Bloccato") == stati["task"]["Bloccato"]["colore"]
    assert colore_stato(stati, "task", "Eliminato") == stati["ignoto"]["colore"]
    assert colore_stato(stati, "livello inesistente", "In corso") == stati["ignoto"]["colore"]
