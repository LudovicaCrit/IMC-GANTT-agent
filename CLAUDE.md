# IMC-GANTT-agent — regole per Code

## Dove guardare
- docs/INVENTARIO.md: fotografia del codice al commit indicato in testa. Non si aggiorna: i passi successivi possono averla superata, e lo stato dei lavori sta in docs/PIANO.md. Se il codice la smentisce, dillo.
- docs/DECISIONI.md: scelte fissate. Non si riaprono.
- docs/ARCHITETTURA.md: la mappa del codice, quando esiste. Ogni passo che sposta una responsabilità la aggiorna nello stesso commit.
- docs/PIANO.md: fasi e passi.
- docs/BACKLOG.md: debito e idee.
- Qualunque altro .md non versionato descrive intenzioni, non fatti.

## Come si lavora
- Un passo alla volta, nel perimetro del prompt. Se trovi altro da sistemare, lo segnali, non lo fai.
- Mai commit né push. git restore è ammesso se lo riferisci. Path espliciti, mai git add con il punto.
- Il resoconto contiene sempre: diff, verifica fatta, cosa NON hai verificato.
- Il database di sviluppo è interamente sintetico; solo i nomi dei dipendenti sono reali. Prima e dopo ogni scrittura sul DB calcola l'impronta dei dipendenti con il comando psql -At -c "SELECT md5(string_agg(r::text, '|' ORDER BY r.nome, r::text)) FROM (SELECT d.nome, ru.nome AS inquadramento, round(d.ore_sett::numeric, 2) AS ore_sett, round(d.costo_ora::numeric, 2) AS costo_ora, a.nome AS societa, d.attivo FROM dipendenti d LEFT JOIN ruoli ru ON ru.id = d.ruolo_id JOIN azienda a ON a.id = d.azienda_id) r" sul database di sviluppo: deve restare identica, salvo che il prompt chieda esplicitamente di modificarla, perché gli e2e e gli scenari di prova si appoggiano a quei dipendenti. L'impronta conta solo i campi di significato (nome, inquadramento e società per nome, ore settimanali, costo orario, attivo), senza id né date tecniche, e scrive i numeri sempre con due decimali: così resta uguale quando il database si ricostruisce dal seed e quando una colonna numerica cambia tipo. La stessa formula la usa backend/scripts/ricostruisci_db.py, che ricostruisce il database e stampa l'impronta prima e dopo.
- Tutto il resto del database si può modificare e si rigenera dal seed. Le cancellazioni avvengono comunque per chiave esatta di ciò che hai creato, così ogni passo resta leggibile.
- Prima di lanciare gli e2e, controlla che sulle porte del GANTT (GANTT_PORTA_BACKEND e GANTT_PORTA_FRONTEND in backend/.env) non giri un processo vecchio. Non fermare mai processi di altri progetti.

## Regole di codice
1. Una sola sorgente per ogni dato. Niente copie né colonne derivate salvate. Un calcolo vive in un punto solo.
2. Il codice morto si toglie, non si commenta. Commenti e docstring dicono il vero o spariscono.
3. La logica sta nel livello di servizio. I router traducono HTTP; il frontend mostra e non ricalcola formule.
4. Le etichette dicono il vero: il nome di un numero corrisponde alla sua formula.
5. Nessun valore specifico di IMC nel codice: aziende, persone, id, ore, festività, soglie, modelli IA. Vanno in DB o in configurazione.
6. Nulli e ordine:
   - ogni ORDER BY termina con l'id;
   - ogni JOIN su chiave nullable è una scelta dichiarata, interna o esterna;
   - attenzione a != in SQL, che scarta i NULL;
   - nessun accesso a una relazione nullable senza gestire il caso vuoto.
7. Soldi in Decimal, arrotondati in un punto solo, nel backend.
8. Niente N+1. Le query devono reggere 500 dipendenti, non 18.
9. Test pytest in backend/tests/ per ogni regola di dominio, con il caso nullo nella matrice dei casi.
10. Codice e migration nello stesso commit. Migration scritte a mano o riviste riga per riga, mai autogenerate accettate alla cieca. Ogni drop ha una guardia che conta prima di agire.
11. Portabile su Windows Server: pathlib, encoding utf-8 esplicito, niente comandi solo Linux nel funzionamento.
12. Niente stato modificabile in memoria a livello di modulo (dizionari, cache, contatori): le route girano in più thread e in produzione possono girare più processi. Lo stato condiviso sta nel database.
13. Importare un modulo non ha effetti esterni: niente connessioni, query o scritture all'import. I controlli d'ambiente si fanno all'avvio dell'applicazione.

## Leggibilità
- Il codice deve poterlo prendere in mano chi non ne conosce la storia.
- Un modulo, una responsabilità. Un file che supera qualche centinaio di righe è un segnale da discutere, non da ignorare.
- Nomi che dicono cosa fa la cosa, con le parole del dominio usate in DECISIONI.md.
- I commenti spiegano il perché, mai il cosa. Se serve spiegare il cosa, il codice va riscritto.
- Una funzione non fa due mestieri: chi calcola non scrive sul DB, chi scrive non calcola.
- data_db_impl.py si smonta a strati: quando un passo lavora su un dominio, prima ne sposta le funzioni in un modulo di servizio dedicato a comportamento invariato, con i test che lo provano, poi lo modifica.

## Sicurezza
- Ogni endpoint di scrittura verifica chi scrive e cosa può toccare. Nessun setattr su campi liberi: solo whitelist.
- Mai segreti nel codice, nel frontend o nelle risposte API: password, hash, token, chiavi.
- Sessione solo in cookie httpOnly, Secure e SameSite.
- In produzione /docs e /openapi.json sono chiusi.

## IA
- I numeri li calcola il codice; l'LLM riceve numeri già fatti e si occupa solo di linguaggio e giudizio.
- Ogni proposta dell'IA la decide un umano, e resta registrata.
- L'IA ragiona sul lavoro e sulle competenze per un compito, mai sulla valutazione delle persone (AI Act, Allegato III).
- Streaming e timeout espliciti lungo tutta la catena; modello da variabile d'ambiente.
