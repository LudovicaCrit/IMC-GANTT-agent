"""
Le guardie di `scripts/ricostruisci_db.py` fermano la ricostruzione prima di
connettersi: con un nome non ammesso o una conferma sbagliata non si arriva
mai al database. Test puri: l'host degli URL non esiste.
"""

import pytest

from scripts.ricostruisci_db import NOMI_AMMESSI, RicostruzioneRifiutata, ricostruisci

URL = "postgresql://nessuno@host-inesistente.invalid:5432/{}"


def test_un_database_non_ammesso_e_rifiutato():
    assert "gantt_produzione" not in NOMI_AMMESSI
    with pytest.raises(RicostruzioneRifiutata, match="non è fra quelli ricostruibili"):
        ricostruisci(URL.format("gantt_produzione"), conferma="gantt_produzione")


@pytest.mark.parametrize("conferma", ["", "gantt_test", "GANTT_DB"])
def test_senza_la_conferma_esatta_non_si_ricostruisce(conferma):
    with pytest.raises(RicostruzioneRifiutata, match="conferma"):
        ricostruisci(URL.format("gantt_db"), conferma=conferma)
