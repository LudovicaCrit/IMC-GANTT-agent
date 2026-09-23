# e2e — verifiche in browser

Playwright. Una cartella a sé, con il suo `package.json`: il frontend non deve
portarsi dietro una dipendenza di test per essere costruito.

## Come si lancia

```bash
cd e2e
npm install                 # la prima volta
npx playwright install chromium   # la prima volta
npm test
```

Backend e frontend li accende Playwright (`webServer` nella config) e li spegne
alla fine. Se sono già aperti sulle porte 8000 e 3000 li riusa, così si può
lanciare la verifica mentre si sviluppa.

Serve un Postgres con il seed applicato e `backend/.env` a posto: la verifica
gira sul database di sviluppo, non su uno suo.

## I dati di prova

`dati_prova.py` crea due task assegnati a Helena (D004) fuori dalla settimana
corrente — è il caso che «Ho lavorato su altro» esiste per coprire — e li toglie
insieme a tutto ciò che i test ci hanno scritto sopra. Lo chiamano da soli
`apparecchia.js` (prima) e `sparecchia.js` (dopo).

Prima e dopo si stampa l'impronta md5 di `blocchi_ore` e `consuntivi` al netto
dei task di prova: **devono coincidere**. Se non coincidono, la verifica ha
lasciato in giro qualcosa e va ripulita a mano prima di fidarsi del risultato.

```bash
python e2e/dati_prova.py --impronta    # per controllare in qualunque momento
python e2e/dati_prova.py --pulisci     # se un giro è morto a metà
```

## Cosa copre oggi

`aggiungi-riga.spec.js` — la selezione «Ho lavorato su altro» della griglia a
ore (passo 4, sotto-passo 5): cosa la lista offre e cosa no, il giro completo
aggiungi → ore → salva → riapri, l'avvertenza sulla riga salvata senza ore, la
× che toglie una riga aggiunta per sbaglio, e il fatto che a un manager la lista
resti comunque la sua.

I test sono `serial` e nell'ordine in cui stanno nel file: il primo guarda la
lista, il secondo ci salva dentro e cambia quello che il primo guarderebbe.

Nessun test fa login: `apparecchia.js` accede una volta per utente e salva la
sessione in `e2e/.auth/` (che `sparecchia.js` cancella alla fine — sono JWT
veri). `/api/auth/login` accetta 5 tentativi al minuto per IP: accedere a ogni
test lo sfonderebbe, e i test in coda fallirebbero sulla pagina di login invece
che su quello che stavano provando.
