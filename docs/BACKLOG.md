# Backlog — IMC-GANTT-agent

*Debito e dettagli che non hanno un passo nel piano. Quando un passo tocca un file, si pesca da qui ciò che lo riguarda. Riferimenti in INVENTARIO.md.*

## Dati e schema
- Indici mancanti su task(progetto_id, fase_id, dipendente_id) e consuntivi(dipendente_id, settimana)
- consuntivi.stato_dichiarato senza CHECK
- Colonne morte: dipendenti.data_assunzione e note; progetti.giornate_vendute, sede, scadenza_bando, motivo_sospensione, lezioni_apprese, note; fasi.urgenza; task.motivo_blocco e note; tabelle note_progetto e interventi
- Tabella assegnazioni morta: 0 lettori, 0 scrittori, da droppare con guardia
- UNIQUE su predecessore e successore impedisce SS e FF sulla stessa coppia
- Orari misti: datetime.utcnow nei default dei modelli, datetime.now() altrove
- Calcolo del lunedì e della fine settimana in più copie, con fine settimana diversa (venerdì o domenica)
- Naming convention sul MetaData di SQLAlchemy, per dare nomi prevedibili a tutti i vincoli futuri
- Le migration che inseriscono dati e il seed devono restare compatibili: il seed cerca prima di creare

## Codice
- PATCH di progetti e fasi fanno setattr dal DTO: passare a whitelist esplicita
- Query ordinate solo per id dove serve l'ordine dei task (ordine, id)
- Carico pianificato spalmato uniformemente sulla durata del task
- Criticità calcolata da due funzioni divergenti (Cantiere ed Elenco)
- Festività solo nel frontend: backend e frontend contano i giorni lavorativi in modo diverso; manca il patrono
- Soglie incoerenti tra pagine (85 contro 90), tutte cablate
- Date del frontend da toISOString(), quindi UTC
- Configurazione: fetch senza gestione di 401, 403 e res.ok; Risorse: Promise.all senza catch
- Due istanze di Limiter; segnalazioni scritte solo dal seed
- Commenti e docstring stantii (elenco nel paragrafo 4 dell'inventario)
- add_p010.py obsoleto; README con istruzioni solo Linux e riferimenti a SQLite
- La data di oggi va letta solo da utils.get_oggi(): oggi molti punti chiamano date.today() o datetime.now() per conto loro (elenco nel resoconto del passo 5 bis). Si sistema insieme al fuso orario della fase 8
- In test_solidita.sh resta un test su /task/anteprima-impatto, che non esiste più. Lo script non è chiamato da nessuno: valutare se toglierlo del tutto

## Test
- Nessun e2e su Cantiere, Wizard, GANTT, Risorse, Configurazione, SAL, export
- Test frontend assenti

## IA
- JSON delle risposte ottenuto ripulendo il testo: passare a output strutturato con schema
- Un client Gemini nuovo e una rilettura del prompt da disco a ogni richiesta
- Contesti IA costruiti su carico pianificato e ore stimate, mai sulle ore vere
- is_agent_available controlla solo chiave e SDK, non il modello

## Sicurezza
- /docs e /openapi.json pubblici; COOKIE_SECURE falso di default; CORS cablato a localhost
- Password demo in chiaro nel seed
