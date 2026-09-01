"""
Test della primitiva-colore del SEMAFORO RITARDABILITÀ (strato 1).

`colore_unita` è pura: nessuna query, nessun modello ORM, nessuna gerarchia.
Questi test lo verificano — girano SENZA database attivo.

Perché l'import è da `data_db_impl` e non da `data`: `data` verifica la
connessione a Postgres all'import (`_verifica_database()`) e solleva se il
server è spento. `data_db_impl` importa `models`, che chiama `create_engine` —
lazy, nessuna connessione aperta finché non si esegue una query. Questi test
non ne eseguono nessuna.

Stile e runner: `test_scenario_engine.py`.
"""

from datetime import date

from data_db_impl import colore_unita, STATI_CHIUSI_SEMAFORO


# Data fissa: nessun test dipende dall'orologio reale, `oggi` è un parametro.
OGGI = date(2026, 9, 1)
IERI = date(2026, 8, 31)
DOMANI = date(2026, 9, 2)


def test_grigio_senza_data_fine():
    """1. data_fine None su unità VIVA → grigio. Ma la chiusura viene prima."""
    assert colore_unita(None, "In corso", OGGI) == "grigio"
    assert colore_unita(None, "Da iniziare", OGGI) == "grigio"

    # Precedenza sul rosso e sul verde: entrambi si leggono da una data che
    # non c'è.
    assert colore_unita(None, "Bloccato", OGGI) == "grigio"

    # LA CHIUSURA BATTE IL GRIGIO (ordine invertito nel sotto-edit 2). Di
    # un'unità chiusa sappiamo già che non è a rischio, senza calendario:
    # chiamarla grigia direbbe «non so» di qualcosa che sappiamo, e in
    # aggregazione (grigio > verde) quel falso dubbio salirebbe al padre.
    assert colore_unita(None, "Completato", OGGI) == "verde"
    assert colore_unita(None, "Completata", OGGI) == "verde"
    for stato in STATI_CHIUSI_SEMAFORO:
        assert colore_unita(None, stato, OGGI) == "verde", stato

    print("✅ 1. grigio su unità viva senza data; chiusura batte grigio OK")


def test_rosso_scaduto_e_vivo():
    """2. data_fine passata + unità viva → rosso."""
    assert colore_unita(IERI, "In corso", OGGI) == "rosso"
    assert colore_unita(IERI, "Da iniziare", OGGI) == "rosso"
    assert colore_unita(IERI, "Bloccato", OGGI) == "rosso"

    # Progetto: "Bozza" e "In esecuzione" sono lavoro vivo, non chiusure.
    assert colore_unita(IERI, "In esecuzione", OGGI) == "rosso"
    assert colore_unita(IERI, "Bozza", OGGI) == "rosso"

    # Molto scaduto resta rosso, non «più rosso»: la scala non ha gradi.
    assert colore_unita(date(2025, 1, 1), "In corso", OGGI) == "rosso"

    print("✅ 2. rosso su scaduto e vivo OK")


def test_completato_non_e_rosso():
    """3. data_fine passata + Completato → verde, mai rosso.

    In tutte e tre le grafie che i livelli usano davvero.
    """
    assert colore_unita(IERI, "Completato", OGGI) == "verde"    # task, progetto
    assert colore_unita(IERI, "Completata", OGGI) == "verde"    # FASE, femminile
    print("✅ 3. completato in ritardo → verde (non rosso) OK")


def test_sospeso_annullato_non_sono_rossi():
    """4. Sospeso/Annullato/Eliminato scaduti → verde, mai rosso.

    Il femminile della fase è il caso che un set al solo maschile sbaglierebbe
    in silenzio: 25 fasi su 71 sono "Completata" e 0 "Completato".
    """
    for stato in ("Sospeso", "Sospesa", "Annullato", "Annullata", "Eliminato"):
        assert colore_unita(IERI, stato, OGGI) == "verde", stato

    # Il set è esattamente quello dichiarato: nessuno stato chiuso produce
    # rosso, qualunque sia la data.
    for stato in STATI_CHIUSI_SEMAFORO:
        assert colore_unita(IERI, stato, OGGI) == "verde", stato
        assert colore_unita(DOMANI, stato, OGGI) == "verde", stato

    print("✅ 4. sospeso/annullato/eliminato → verde (non rosso) OK")


def test_verde_futuro_il_giallo_e_spento():
    """5. data_fine futura + In corso → verde: in strato 1 il giallo non esiste."""
    assert colore_unita(DOMANI, "In corso", OGGI) == "verde"

    # Scadenza vicinissima, lavoro fermo a zero: sarebbe il candidato naturale
    # al giallo, e in strato 1 è VERDE per scelta. Il giallo su base tempo
    # ingiallirebbe ogni lavoro in corso — rumore, non segnale.
    assert colore_unita(DOMANI, "In corso", OGGI, percentuale=0) == "verde"

    # Contratto di strato 1: il giallo non è MAI emesso, su nessuna
    # combinazione di input. Questo test cadrà — di proposito — quando lo
    # strato 2 lo accenderà.
    combinazioni = [
        (d, s, p, oc, op)
        for d in (IERI, OGGI, DOMANI, None)
        for s in ("In corso", "Da iniziare", "Completato", "Completata",
                  "Sospeso", "Annullato", "Bozza", None, "stato-ignoto")
        for p in (None, 0, 50, 100)
        for oc in (None, 0.0, 120.0)
        for op in (None, 0.0, 40.0)
    ]
    for d, s, p, oc, op in combinazioni:
        colore = colore_unita(d, s, OGGI, percentuale=p,
                              ore_consumate=oc, ore_pianificate=op)
        assert colore != "giallo", (d, s, p, oc, op)
        assert colore in ("verde", "rosso", "grigio"), (colore, d, s)

    print(f"✅ 5. verde su futuro, giallo spento su {len(combinazioni)} combinazioni OK")


def test_scadenza_oggi_non_e_ritardo():
    """6. data_fine == oggi → verde. Il confronto è `<` STRETTO.

    La giornata non è finita: chi consegna oggi non è in ritardo. È anche la
    soglia di `_in_ritardo` (`data_fine < oggi`) in task_settimana_dipendente —
    divergere di un `=` farebbe dissentire il badge di /me e il semaforo sullo
    stesso task per l'esattezza di un giorno.
    """
    assert colore_unita(OGGI, "In corso", OGGI) == "verde"
    assert colore_unita(OGGI, "Da iniziare", OGGI) == "verde"

    # Il giorno dopo, lo stesso task è rosso: la soglia è dove diciamo che sia.
    assert colore_unita(OGGI, "In corso", DOMANI) == "rosso"

    print("✅ 6. scadenza = oggi → verde (`<` stretto) OK")


def test_purezza():
    """7. Pura: stesso input → stesso output, nessun effetto collaterale."""
    # Determinismo.
    for _ in range(3):
        assert colore_unita(IERI, "In corso", OGGI) == "rosso"
        assert colore_unita(DOMANI, "In corso", OGGI) == "verde"
        assert colore_unita(None, "In corso", OGGI) == "grigio"

    # `oggi` è l'UNICA sorgente di tempo: stessa unità, `oggi` diverso,
    # risultato diverso. Se la funzione leggesse il clock, il colore non
    # cambierebbe al variare del parametro.
    scadenza = date(2026, 6, 15)
    assert colore_unita(scadenza, "In corso", date(2026, 6, 14)) == "verde"
    assert colore_unita(scadenza, "In corso", date(2026, 6, 16)) == "rosso"

    # Gli argomenti non vengono mutati.
    d, s, o = date(2026, 6, 15), "In corso", date(2026, 6, 16)
    colore_unita(d, s, o)
    assert (d, s, o) == (date(2026, 6, 15), "In corso", date(2026, 6, 16))

    # I tre parametri dello strato 2 NON influenzano il colore in strato 1.
    atteso = colore_unita(IERI, "In corso", OGGI)
    for p in (None, 0, 1, 50, 99, 100):
        for oc in (None, 0.0, 10.0, 999.0):
            for op in (None, 0.0, 1.0, 40.0):
                assert colore_unita(IERI, "In corso", OGGI, percentuale=p,
                                    ore_consumate=oc,
                                    ore_pianificate=op) == atteso

    print("✅ 7. purezza (determinismo, nessuna mutazione, gancio inerte) OK")


def test_stato_sconosciuto_non_disarma_la_scadenza():
    """Extra: uno stato non riconosciuto NON è chiuso → vale il calendario.

    Comportamento prudente e deliberato: davanti a uno stato che non sappiamo
    leggere, una data scaduta resta un allarme. L'alternativa (trattarlo come
    chiuso) spegnerebbe il semaforo proprio sui dati anomali.
    """
    assert colore_unita(IERI, "stato-mai-visto", OGGI) == "rosso"
    assert colore_unita(IERI, None, OGGI) == "rosso"
    assert colore_unita(IERI, "", OGGI) == "rosso"
    assert colore_unita(IERI, "completato", OGGI) == "rosso"  # case-sensitive

    print("✅ 8. stato sconosciuto → vale la scadenza OK")


if __name__ == "__main__":
    test_grigio_senza_data_fine()
    test_rosso_scaduto_e_vivo()
    test_completato_non_e_rosso()
    test_sospeso_annullato_non_sono_rossi()
    test_verde_futuro_il_giallo_e_spento()
    test_scadenza_oggi_non_e_ritardo()
    test_purezza()
    test_stato_sconosciuto_non_disarma_la_scadenza()
    print()
    print("=" * 60)
    print("TUTTI I TEST PASSATI ✅")
