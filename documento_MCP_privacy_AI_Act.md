# IMC-Group GANTT Agent — MCP, Privacy e AI Act
## Documento preparatorio per la discussione con Vincenzo Carolla

**Autrice:** Ludovica Crit — Stagista IA back-end
**Data:** 1 aprile 2026
**Riferimento normativo:** Reg. (UE) 2024/1689 (AI Act), vademecum Sole 24 Ore di Alberto Bozzo

---

## 1. Dove si colloca il GANTT Agent nell'AI Act

### Classificazione del rischio

L'AI Act classifica i sistemi IA in 4 livelli: inaccettabile, alto, limitato, minimo. Il nostro GANTT Agent rientra nella categoria **rischio limitato**, per tre ragioni:

**Non prende decisioni autonome sulle persone.** Il sistema mostra conseguenze (la cascata, i sovraccarichi), ma il management decide. L'IA non assume, non licenzia, non assegna bonus, non nega servizi. Le decisioni su chi fa cosa restano umane al 100%.

**Non impatta su diritti fondamentali.** Non è un sistema di credit scoring, di selezione personale, di sorveglianza o di accesso a servizi essenziali. Gestisce ore e GANTT — un tool operativo interno.

**La supervisione umana è nativa.** Ogni output dell'IA (interpretazione scenario, suggerimento task, mappatura ore) deve essere confermato da un operatore umano prima di essere applicato. Il sistema è progettato così fin dall'inizio — non è un retrofit.

### Obblighi per il rischio limitato

Per i sistemi a rischio limitato, l'AI Act richiede essenzialmente **trasparenza**: i dipendenti devono sapere che interagiscono con un sistema IA. Nel nostro caso, questo si traduce in:

- Ogni risposta dell'agente è chiaramente etichettata come generata dall'IA (icona 🧠, label "Interpretazione dell'agente")
- Il sistema non finge di essere una persona
- I dipendenti sanno che le ore vengono mappate da un agente IA e possono correggere il risultato

### Perché NON è alto rischio

Potrebbe sorgere il dubbio che, trattando dati sul lavoro (ore, saturazione, assegnazioni), il sistema ricada nella categoria "alto rischio — ambito occupazionale". L'AI Act include nell'Allegato III i sistemi IA per "reclutamento, selezione, valutazione delle prestazioni, promozione, licenziamento". Il nostro sistema non fa nessuna di queste cose: non valuta prestazioni, non suggerisce promozioni o licenziamenti, non fa scoring dei dipendenti. Calcola ore e mostra GANTT — come farebbe un Excel, ma in modo più intelligente.

**Tuttavia**, se in futuro il sistema venisse usato per valutare la produttività dei dipendenti o per prendere decisioni su promozioni/assegnazioni basate su metriche automatiche, la classificazione andrebbe rivista. Questo è un punto da chiarire con Vincenzo: il confine tra "strumento operativo" e "sistema di valutazione" va definito fin d'ora.

---

## 2. I dati che il sistema tratta

### Dati attuali (prototipo)
- Nomi e profili professionali dei dipendenti
- Assegnazione task/progetto
- Ore stimate e ore consuntivate
- Segnalazioni automatiche (ritardi, sovraccarichi)
- Testo libero nella consuntivazione chatbot e nel Tavolo di Lavoro

### Dati sensibili? No, ma...

I dati trattati non sono "dati particolari" ai sensi del GDPR (non ci sono dati sanitari, biometrici, opinioni politiche). Sono dati personali ordinari relativi al rapporto di lavoro. Questo significa che serve una base giuridica GDPR — nel nostro caso il **legittimo interesse del datore di lavoro** alla gestione operativa dei progetti, oppure l'**esecuzione del contratto di lavoro**.

I dipendenti devono essere informati (informativa privacy) che le loro ore vengono elaborate da un sistema con componente IA. Non serve il consenso — ma serve la trasparenza.

### Dove vanno i dati

Oggi: SQLite locale, sul server dell'azienda. Nessun dato esce dal perimetro aziendale.

Il modello IA (Gemini 2.5 Flash) riceve come contesto: nomi dipendenti, nomi progetti, task, ore — ma **non riceve dati storici massivi**, solo lo snapshot necessario per la richiesta corrente. Google non usa i dati delle API Gemini per addestrare i propri modelli (policy Google Cloud — verificare i ToS specifici del piano usato).

---

## 3. MCP — Cos'è e cosa potrebbe fare per IMC-Group

### Cos'è MCP in pratica

MCP (Model Context Protocol) è un protocollo che permette a un sistema IA di connettersi a servizi esterni (Teams, Outlook, Google Calendar, Jira, ecc.) tramite "server MCP" — piccoli adattatori standardizzati. Non è una tecnologia proprietaria: è un protocollo aperto creato da Anthropic e adottato da molti vendor.

### Due direzioni possibili

#### Direzione 1 — Notifiche in uscita (BASSO RISCHIO)

Il sistema GANTT invia notifiche su Teams/Outlook quando succede qualcosa di rilevante:
- "Il progetto Adeguamento DORA ha un task in scadenza tra 3 giorni"
- "Stefano Colombo è al 112% di saturazione questa settimana"
- "Nuova segnalazione: il testing del Framework Compliance 262 potrebbe slittare"

**Cosa fa:** il sistema SCRIVE messaggi su un canale Teams o invia email. Non legge nulla.

**Dati coinvolti:** nomi dipendenti, nomi progetti, scadenze, percentuali di saturazione — gli stessi dati già visibili nella piattaforma.

**Rischio privacy:** basso. Il sistema non accede a dati nuovi — invia informazioni che il management ha già nel GANTT. L'unica attenzione è che le notifiche vadano solo ai destinatari autorizzati (il PM del progetto, non tutti i dipendenti).

**Requisiti tecnici:** un server MCP per Microsoft Teams o Outlook, configurabile con le credenziali aziendali (Azure AD). Non richiede permessi di lettura su email o chat.

#### Direzione 2 — Lettura in entrata (ALTO RISCHIO)

Il sistema legge email/chat Teams per intercettare cambiamenti rilevanti:
- Un cliente scrive "anticipiamo la consegna di 2 settimane" → il sistema lo propone nel Tavolo di Lavoro
- Un dipendente scrive in chat "domani non vengo, sono malato" → il sistema segnala l'assenza

**Cosa fa:** il sistema LEGGE messaggi e ne estrae informazioni.

**Rischio privacy:** alto. L'IA legge comunicazioni private o semi-private. Questo solleva questioni di:
- Privacy delle comunicazioni (il dipendente sa che le sue chat vengono lette da un'IA?)
- GDPR Art. 22 (decisioni automatizzate basate su comunicazioni personali)
- Rischio di classificazione "alto rischio" AI Act se le informazioni estratte influenzano decisioni sul lavoro

**Raccomandazione:** NON implementare la Direzione 2 nel MVP. Presentarla come possibilità futura, solo dopo aver definito un protocollo di trasparenza e consenso con i dipendenti.

---

## 4. Diagramma "Chi vede cosa"

```
┌─────────────────────────────────────────────────────────────┐
│                    GANTT Agent — Flusso dati                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Dipendente]  ──consuntivazione ore──→  [Database locale]  │
│       │                                        │            │
│       │ (linguaggio naturale)                   │            │
│       ▼                                        │            │
│  [Gemini API]  ←─contesto snapshot──────────────┘            │
│       │                                                     │
│       │ (interpretazione, NON decisione)                    │
│       ▼                                                     │
│  [GANTT Agent]  ──mostra conseguenze──→  [Management]       │
│       │                                        │            │
│       │                               (decide, conferma)    │
│       │                                        │            │
│       │         ┌──────────────────────────────┘            │
│       │         │                                           │
│       │         ▼                                           │
│       │    [Database locale]  ──aggiorna GANTT               │
│       │                                                     │
│  ─ ─ ─│─ ─ ─ ─ ─ ─ ─ FUTURO (Direzione 1) ─ ─ ─ ─ ─ ─   │
│       │                                                     │
│       └──notifica──→  [Teams/Outlook]  ──→  [PM/Management] │
│                       (solo scrittura,                      │
│                        nessuna lettura)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Cosa NON esce dal perimetro aziendale:**
- Le decisioni (restano umane)
- I dati storici (restano nel database locale)
- Le email/chat dei dipendenti (non vengono lette)

**Cosa va a Gemini (Google Cloud):**
- Snapshot del contesto corrente (nomi, task, ore) per interpretazione
- Nessun dato storico massivo
- Nessun dato sensibile (sanitario, finanziario personale)

---

## 5. Cosa fare prima della fase pilota

### Checklist privacy/AI Act per IMC-Group

1. **Informativa dipendenti** — Aggiornare l'informativa privacy aziendale per includere il trattamento dati tramite il GANTT Agent. Specificare: quali dati, per quale finalità, con quale base giuridica, chi vi accede, dove vengono elaborati.

2. **Verifica ToS Gemini** — Confermare con Google che i dati inviati via API non vengono usati per addestrare i modelli. Verificare il piano di pricing e le garanzie contrattuali (DPA, Standard Contractual Clauses per trasferimento dati extra-UE se applicabile).

3. **Registro dei trattamenti** — Aggiungere il GANTT Agent al registro dei trattamenti GDPR di IMC-Group (art. 30).

4. **Policy interna di utilizzo** — Definire chi può accedere al Tavolo di Lavoro (solo management? PM? tutti?), chi vede le saturazioni individuali, chi può confermare le modifiche.

5. **Trasparenza IA** — Assicurarsi che ogni output dell'agente sia chiaramente etichettato come generato da IA (già fatto nel prototipo con le icone 🧠 e le label).

6. **Definire il confine** — Chiarire per iscritto che il sistema NON viene usato per: valutare prestazioni individuali, decidere promozioni/licenziamenti, monitorare la produttività. Questo mantiene la classificazione "rischio limitato".

---

## 6. Raccomandazione per Vincenzo

**Fase 1 (ora):** Il GANTT Agent funziona come strumento interno senza integrazioni esterne. I dipendenti compilano le ore nel sistema, il management usa il Tavolo di Lavoro. Nessun dato esce. Nessun rischio normativo significativo oltre la trasparenza.

**Fase 2 (dopo 2-3 mesi di uso):** Attivare le notifiche Teams/Outlook (Direzione 1 — solo scrittura). Richiede configurazione Azure AD e un server MCP. Rischio basso, valore alto (il PM riceve alert senza dover aprire la piattaforma).

**Fase 3 (da valutare con calma):** Valutare la Direzione 2 (lettura email/chat) solo se il valore operativo lo giustifica e solo dopo aver definito il protocollo di consenso e trasparenza con i dipendenti. Questa fase richiede una valutazione d'impatto GDPR (DPIA) e potrebbe richiedere una riclassificazione AI Act.

**Il principio guida:** partire leggero, dimostrare valore, espandere con trasparenza. Come dice il vademecum AI Act: la compliance non è un costo, è un vantaggio competitivo — specialmente per un'azienda di consulenza GRC che dovrebbe essere la prima a dare l'esempio.

---

## Riferimenti

- Reg. (UE) 2024/1689 — AI Act (testo completo)
- "AI Act: la sfida della conformità" — Alberto Bozzo, Il Sole 24 Ore, 2025
- Allegato III AI Act — Elenco sistemi ad alto rischio
- MCP Protocol: https://modelcontextprotocol.io
- Google Gemini API Terms of Service
