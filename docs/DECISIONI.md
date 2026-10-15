# Decisioni fissate — IMC-GANTT-agent

*Scelte prese e motivate. Non si riaprono senza una ragione nuova, da scrivere qui. Lo stato del codice sta in INVENTARIO.md, non qui.*

## 1. Visione e principi
- Prodotto: strumento per società che vivono di ore vendute (mercato PSA e resource management). Dice dove atterrerà ogni progetto in data e costo (previsione d'atterraggio), calcolata da ore vere e residuo dichiarato. Propone correzioni di rotta per competenza e disponibilità. Impara dallo storico.
- Controllo, non automazione: il sistema segnala e propone, il PM decide.
- Se si può programmare, si programma. L'IA entra solo dove serve linguaggio o giudizio.
- Il cliente possiede software e dati: niente canoni per utente né dipendenze costose.
- Complessità contro solidità: ogni modalità in più moltiplica i casi. Le regole che riducono le combinazioni valgono doppio. Si arricchiscono le pagine esistenti invece di crearne di nuove.

## 2. Le ore: una scala di quattro numeri
Dal più fisso al più vivo:
1. Vendute (Fase.ore_vendute): il contratto. Le scrive solo il contratto; cambiano solo per rinegoziazione.
2. Stimate (Task.ore_stimate): la stima interna iniziale. Fissata alla creazione, poi in sola lettura.
3. Pianificate (Task.ore_pianificate): il piano corrente. Alla nascita sono uguali alle stimate; poi le muove il PM a livello di fase, e il sistema le distribuisce sui task.
4. Consumate (vista ore_settimanali): le ore vere, dai blocchi della consuntivazione.

Vendute e stimate possono divergere: le vendute guardano il cliente, le stimate guardano noi. Progetto.budget_ore si toglie: non lo chiede nessuno e contraddice la scala.

Due erosioni, entrambe legittime:
- commerciale = costo consumato − costo venduto;
- operativa = costo consumato − costo pianificato.

Divergono solo se il PM ha ripianificato. Il delta in ore (pianificate − consumate) è un terzo numero, distinto dalle erosioni in euro.

Avanzamento: si calcola, non si chiede. Avanzamento onesto = fatte ÷ (fatte + residuo dichiarato), mai fatte ÷ pianificate. Consumo del budget e avanzamento del lavoro sono etichette diverse.

Saturazione: si mostra sia sul piano sia sulle ore vere, affiancate; lo scarto è l'informazione. Saturazione = carico sul piano; copertura = giorni di cui la persona ha reso conto. Non si confondono.

## 3. Consuntivazione
- Ore come blocchi per giorno (blocchi_ore), sorgente unica delle ore fatte. Lo slider con l'avanzamento percentuale è morto e non si riapre.
- Consuntivazione settimanale; si compilano la settimana corrente e quella precedente.
- Uno stato senza ore è legittimo: un task fermo si dichiara con stato e nota.
- Lo storico migrato è intoccabile; ogni salvataggio sostituisce solo i blocchi manuali.
- Un task è scomposto se ha pezzi non annullati. La definizione è unica, ovunque.
- Periodi di assenza: servono solo a far funzionare l'app senza disturbare chi è assente, non a gestire le ferie dell'azienda, la cui comunicazione ufficiale resta fuori dall'app. Il dipendente segna il periodo in Consuntivazione; lo approva il management o un PM di uno dei progetti su cui la persona lavora, e basta la prima approvazione. Solo un periodo approvato ha effetto: nei suoi giorni non si chiede consuntivazione e non partono promemoria, e la copertura li conta come resi conto. Le chiusure aziendali usano lo stesso meccanismo, dichiarate dal management e già approvate. Le ferie non si consuntivano.
- Presenze e rimborsi: costruiti sulla griglia dei giorni; l'amministrazione vede presenze e spese di tutti. Fanno parte del prodotto presentato.

## 4. Dal basso verso il piano: un solo meccanismo propone / ratifica
- Appunto al volo: una casella sempre a portata (Home, griglia, poi avatar vocale). Una riga scritta diventa un pezzo (sottotask) con origine (PM o dipendente), stato di ratifica e, facoltativo, richiesto da. L'IA propone dove collocarlo; senza IA restano due tendine.
- Le ore contano subito; il PM ratifica senza bloccare (conferma, sposta, accorpa).
- Se non esiste un task adatto, il pezzo va nel task Emerso in corsa, creato una volta per progetto: lo scope creep diventa un numero.
- Stima residua: il dipendente dichiara quanto manca; oltre una soglia il PM deve ri-stanziare pianificate e date.
- Top-down e bottom-up producono lo stesso oggetto. Il PM ha una sola coda da ratificare.
- Soccorso (ore su task altrui): si dichiara per persona (ho aiutato X), con conferma dell'aiutato. Il soccorritore mette ore, mai lo stato.
- Chi scompone i task: il PM tiene la struttura alta, il dipendente affina dentro, il PM ratifica.

## 5. Semaforo, urgenza, criticità
- Ritardabilità (semaforo) = piano contro calendario. Strato 1: verde, rosso e grigio da date e stati; scala dal sottotask al progetto col peggio dei figli. Strato 2 (prospettico): ore residue contro capacità residua, condivide il motore con l'IA-scenari.
- Urgenza = priorità decisa dal management, 4 livelli, la fase la eredita. Modula la ritardabilità, non la sostituisce.
- Criticità = il piano contro se stesso (igiene del piano). Non guarda la data di oggi.

## 6. Persone, ruoli, competenze, permessi
- Ruolo: un inquadramento base più eventuali ruoli funzionali aggiuntivi (multiruolo). Il PM è un ruolo funzionale; PM non è una competenza.
- Competenze: catalogo unico, relazione molti-a-molti con i dipendenti. Da aggiungere task_competenze (cosa serve al task). Il match usa i dati strutturati come base e l'IA semantica per coprire i buchi.
- Permessi: il PM agisce sui suoi progetti (pm_id), il management su tutto. Matrice di accesso pagina per pagina da definire nella fase 3.
- Account: ogni dipendente ha un account; si crea da Configurazione; ognuno si cambia la password.
- Attività interne: contano dove conta il tempo delle persone (saturazione, capacità, presenza), non dove conta il progetto-cliente (semaforo, margini, candidati da spostare).

## 7. IA
- I numeri li calcola il codice; l'LLM li riceve già fatti, ragiona e argomenta citandoli. Ogni proposta la decide un umano, e resta registrata.
- L'IA ragiona sul lavoro, mai sulla valutazione delle persone (AI Act, Allegato III). Ogni IA passa la domanda: tocca la valutazione delle persone?
- Le cinque IA:
  1. compila-consuntivazione, con l'avatar vocale come interfaccia;
  2. costruisci-GANTT (bozza da dati accordati);
  3. scenari;
  4. Archivio (lezioni dallo storico);
  5. sintesi per il management (i progetti da guardare e perché, nel cruscotto di Economia).
- Scenari: il cuore è un risolutore a vincoli (OR-Tools). L'LLM traduce la richiesta in vincoli e spiega la proposta.
- Ordine: infrastruttura IA comune (streaming, timeout, modello da env) → registro delle transizioni di stato → sintesi → costruisci-GANTT → scenari → Archivio → avatar.
- Le IA vivono nelle pagine dove servono. Pipeline e Tavolo di Lavoro escono dal menu; i loro embrioni si recuperano nel Cantiere.

## 8. Pagine
- Home a tre raggi: management, PM, dipendente.
- GANTT: dettaglio con le schede Design, Scenari e Storia (il SAL). Le viste portafoglio e per-dipendente sono lenti selezionabili nella stessa pagina, non pagine nuove.
- Cantiere: creazione e gestione del progetto.
- Risorse, Attività interne.
- Economia: margini, avanzamento, cruscotto con le quattro ore affiancate, delta, testata anagrafica, lente sul costo della dispersione delle persone su troppi progetti.
- Consuntivazione.
- Archivio: riusa il componente di dettaglio, con in più la scheda Lezioni.
- Configurazione: fasi e task solo come modelli.

## 9. Sicurezza
- Autorizzazione su ogni scrittura: chi scrive e cosa può toccare. Nessun campo libero.
- Nessun segreto nel codice, nel frontend, nelle risposte API o nei log.
- Sessione in cookie httpOnly, Secure e SameSite. HTTPS obbligatorio in produzione. Limite ai tentativi di login. /docs chiuso in produzione.
- Le stesse regole valgono per PMOGen.

## 10. Tecnica e deploy
- Deploy su Windows Server 2022 (IIS + NSSM), sulla VM di PMOGen e Sapere. In produzione Python 3.12 o 3.13.
- Il DB di produzione nasce da alembic upgrade, confrontato con lo schema attuale.
- Modello IA da variabile d'ambiente; ID stabile esplicito, mai anteprime né alias.
- GANTT e PMOGen restano progetti distinti: si possono collegare, mai travasare codice.

## 11. Futuro, già deciso nel principio
- Notifiche (Teams): il giorno stesso in cui un task finisce.
- Avatar vocale: interfaccia della consuntivazione e dell'appunto al volo.
- Smartphone e PC: l'app è un sito responsive, installabile dal browser come icona, senza store e senza cache offline. Da fuori ufficio si raggiunge tramite la VPN aziendale.
- Transizioni di stato: registrare quando cambia uno stato, non solo lo stato corrente.
- Scheda di valutazione di fine progetto: nutre l'IA-Archivio.
- Tempo di direzione del PM: da modellare con un meccanismo dedicato, non con task-PM legati a pm_id.
