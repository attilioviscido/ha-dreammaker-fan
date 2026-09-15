# Dream Maker Fan – integrazione per Home Assistant

Integrazione nativa e locale per Home Assistant per i ventilatori smart
**Dream Maker** (es. *Dream Maker Feel Fan Plus*, modello **DM-FAN02-W**), che
di fabbrica funzionano solo tramite il cloud del produttore (`dm-maker.com`)
e non espongono alcuna API locale ufficiale.

Nessun hub esterno, nessun broker MQTT, nessun container Docker separato:
tutto gira dentro il processo di Home Assistant come un normale
`custom_component`.

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-custom__component-41BDF5?logo=home-assistant&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Indice

- [Come funziona](#come-funziona)
- [Dispositivi supportati](#dispositivi-supportati)
- [Entità create](#entità-create)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Configurazione: redirect DNS](#configurazione-redirect-dns)
- [Prima connessione / riconnessione forzata](#prima-connessione--riconnessione-forzata)
- [Risoluzione problemi](#risoluzione-problemi)
- [Limiti noti](#limiti-noti)
- [Come funziona internamente (per sviluppatori)](#come-funziona-internamente-per-sviluppatori)
- [Crediti](#crediti)
- [Licenza](#licenza)

## Come funziona

Il ventilatore non ha un'API locale: tiene aperta una connessione TCP fissa
verso `cloud1.dm-maker.com:31270`, il server cloud del produttore, e scambia
con lui messaggi JSON (stato, comandi). Questa integrazione apre un server
TCP sulla stessa porta **dentro Home Assistant**, e tramite un redirect DNS
locale di quel dominio verso l'IP del tuo Home Assistant, il ventilatore
finisce per collegarsi (convinto) a Home Assistant invece che al cloud reale.
Da lì le entità sono create e aggiornate direttamente, senza intermediari.

```
Ventilatore Dream Maker  --TCP 31270-->  Home Assistant (questa integrazione)
     (in LAN)                             (dopo redirect DNS locale)
```

L'unico requisito esterno a Home Assistant, e resta tale qualunque soluzione
si scelga: il ventilatore è programmato per contattare solo quell'hostname,
quindi un redirect DNS locale è indispensabile (a meno di riflashare il
modulo WiFi del ventilatore, cosa non documentata/rischiosa). È
un'impostazione da fare una tantum sul router o su Pi-hole/AdGuard Home, non
un servizio che deve restare attivo a parte.

Il protocollo (soprannominato "dmiot" dalla community) è stato
riverso-ingegnerizzato nel progetto [dmiot2mqtt](https://github.com/klada/dmiot2mqtt)
(klada, GPLv3) e nella discussione della [community Home Assistant](https://community.home-assistant.io/t/dreammaker-feel-fan-plus-dream-maker-dm-fan02-w/319885).
Questa integrazione ne è un'implementazione nativa indipendente per Home
Assistant (nessun codice riutilizzato direttamente, solo la documentazione
del protocollo).

## Dispositivi supportati

- Dream Maker Feel Fan Plus **DM-FAN02-W** (versione a batteria) — testato
- Dream Maker **DM-FAN01** — non testato, ma stesso protocollo secondo la
  documentazione della community; apri una issue se lo provi

Altri dispositivi Dream Maker che condividono lo stesso protocollo "dmiot"
(riconoscibile da `comm_version` tipo `dmiot_v1.x.x` nelle info del
dispositivo nell'app ufficiale) dovrebbero funzionare allo stesso modo.

## Entità create

Per ogni ventilatore che si collega (identificato per IP LAN), viene creato
un dispositivo con queste entità:

| Entità | Tipo | Descrizione |
|---|---|---|
| Ventilatore Dream Maker | `fan` | Accensione, velocità 1-100%, oscillazione, modalità (direct/natural/smart) |
| Angolo oscillazione | `select` | 30° / 60° / 90° / 120° / 140° |
| Suono tasti | `switch` | Beep ai comandi |
| Luce LED | `switch` | Indicatori LED sul dispositivo |
| Blocco bambini | `switch` | Disabilita i tasti fisici |
| Spegnimento automatico | `number` | Timer 0-480 minuti |
| Ruota a sinistra / a destra | `button` | Step manuale di rotazione |
| Temperatura | `sensor` | °C rilevati dal dispositivo |
| Umidità | `sensor` | % rilevata dal dispositivo |
| Segnale WiFi | `sensor` | % (diagnostico) |
| Sorgente comando | `sensor` | `manual` / `auto` (diagnostico) |
| Anomalia dispositivo / utilizzo | `binary_sensor` | Diagnostica (diagnostico) |

## Requisiti

- Home Assistant (qualsiasi installazione: OS, Supervised, Container, Core)
- Possibilità di reindirizzare il DNS locale per un singolo dominio (router,
  Pi-hole, AdGuard Home, o un resolver dedicato)
- Home Assistant deve poter ricevere connessioni TCP in ingresso sulla porta
  **31270** dalla LAN:
  - **Home Assistant OS / Supervised**: funziona senza altre modifiche, il
    container Core gira già in modalità host network di default.
  - **Home Assistant Container**: assicurati che il container pubblichi la
    porta 31270 verso l'host (`network_mode: host`, oppure
    `-p 31270:31270`), altrimenti il ventilatore non riuscirà mai a
    raggiungere Home Assistant.
- Nessuna dipendenza Python aggiuntiva: usa solo la libreria standard
  (`asyncio`), niente da installare.

## Installazione

### Manuale

1. Scarica questo repository (Code → Download ZIP, oppure `git clone`).
2. Copia la cartella `custom_components/dreammaker_fan/` dentro la cartella
   `config/custom_components/` della tua installazione Home Assistant
   (creala se non esiste). Il percorso finale deve essere:
   ```
   config/custom_components/dreammaker_fan/__init__.py
   config/custom_components/dreammaker_fan/manifest.json
   ... (tutti gli altri file)
   ```
3. Riavvia Home Assistant (Impostazioni → Sistema → Riavvia).
4. Impostazioni → Dispositivi e servizi → **+ Aggiungi integrazione** → cerca
   **"Dream Maker Fan"** → conferma (porta di default 31270).

### Tramite HACS (repository personalizzato)

1. HACS → Integrazioni → menu (⋮) in alto a destra → **Repository
   personalizzati**.
2. Aggiungi l'URL di questo repository, categoria "Integrazione".
3. Cerca "Dream Maker Fan" in HACS e installa.
4. Riavvia Home Assistant e aggiungi l'integrazione come al punto 4 sopra.

## Configurazione: redirect DNS

Reindirizza `cloud1.dm-maker.com` verso l'IP della macchina che esegue Home
Assistant. Alcuni esempi:

**AdGuard Home**: Filtri → Riscritture DNS → Aggiungi riscrittura DNS →
dominio `cloud1.dm-maker.com`, IP quello di Home Assistant.

**Pi-hole**: Impostazioni → DNS locale → Aggiungi record DNS.

**Router**: se supporta un DNS statico/host override per singolo dominio,
usa la stessa configurazione.

Verifica che funzioni con:
```
nslookup cloud1.dm-maker.com
```
deve rispondere con l'IP di Home Assistant. Se risponde con un IP esterno,
il client (PC o router) che hai interrogato non sta usando il DNS che hai
configurato — assicurati che il DHCP della rete distribuisca quel resolver
a tutti i dispositivi (non solo che il resolver stesso abbia il record
giusto).

## Prima connessione / riconnessione forzata

Il ventilatore mantiene aperta la connessione TCP col vecchio DNS finché non
si riconnette da zero: dopo aver impostato il redirect, forzalo a
riconnettersi con una di queste opzioni (dalla meno alla più invasiva):

1. Cerca un interruttore fisico di accensione separato dal telecomando/app
   (i modelli con batteria integrata potrebbero non spegnersi del tutto
   staccando solo la corrente).
2. Disconnetti/blocca temporaneamente il dispositivo dal WiFi tramite la
   lista client del router (per MAC address), poi riabilitalo.
3. Riavvia l'access point/router WiFi (disconnette tutti i dispositivi, ma è
   garantito che funzioni).

Appena il ventilatore si autentica, l'integrazione crea automaticamente il
dispositivo e tutte le sue entità.

## Risoluzione problemi

**Nessun dispositivo compare dopo il redirect DNS**

1. Verifica che l'IP a cui punta il redirect DNS sia davvero quello di Home
   Assistant.
2. Verifica che la porta sia raggiungibile dalla rete:
   ```powershell
   Test-NetConnection -ComputerName <ip-home-assistant> -Port 31270
   ```
   (o `nc -zv <ip> 31270` da Linux/macOS). Se fallisce, il problema è di rete
   (vedi la sezione Requisiti sopra per Container/Docker).
3. Controlla che il ventilatore stia davvero interrogando il tuo DNS locale
   per quel dominio (log query di AdGuard/Pi-hole, filtrando per l'IP del
   ventilatore).
4. Abilita il log di debug dell'integrazione (Impostazioni → Dispositivi e
   servizi → Dream Maker Fan → ⋮ → Abilita registrazione debug) e controlla
   Impostazioni → Sistema → Log dopo aver forzato una riconnessione.

**"icon not available" sull'integrazione**

Puramente estetico: l'icona ufficiale arriva dal repository pubblico delle
"brand" di Home Assistant, a cui questa integrazione (essendo personalizzata)
non è iscritta. Non ha alcun impatto sul funzionamento. Un `icon.png` locale
nella cartella dell'integrazione risolve il dettaglio esteticamente.

## Limiti noti

- Mentre il DNS è reindirizzato, l'app ufficiale Dream Maker smette di
  funzionare per questo dispositivo (l'app parla col vero cloud, il
  ventilatore no). Ripristina temporaneamente il DNS se ti serve l'app, es.
  per un aggiornamento firmware.
- Protocollo non cifrato, nessuna vera autenticazione: da usare solo sulla
  LAN domestica, mai esporre la porta 31270 su Internet.
- Se il ventilatore viene resettato di fabbrica, va ri-provisionato in WiFi
  (richiede l'app ufficiale e/o Bluetooth, non coperto da questa
  integrazione).
- L'identità di ogni entità è legata all'IP LAN del ventilatore al momento
  della connessione: se l'IP cambia, viene creato un nuovo dispositivo
  invece di aggiornare quello esistente. Consigliata una **DHCP reservation**
  per il ventilatore sul router.

## Come funziona internamente (per sviluppatori)

- `server.py` — server TCP asyncio che implementa il protocollo "dmiot"
  (handshake di autenticazione, ack dei messaggi, heartbeat, cambi di stato)
  e lo astrae in un oggetto `DreamMakerDevice` per dispositivo connesso.
- `__init__.py` — avvia/ferma il server all'aggiunta/rimozione
  dell'integrazione e inoltra il setup alle piattaforme.
- `entity.py` — base comune per tutte le entità (device info, disponibilità,
  aggiornamenti push).
- `fan.py`, `switch.py`, `select.py`, `number.py`, `button.py`, `sensor.py`,
  `binary_sensor.py` — le piattaforme di entità, create dinamicamente quando
  un nuovo dispositivo si autentica (via dispatcher signal).

Pull request e segnalazioni di altri modelli Dream Maker compatibili sono
benvenute.

## Crediti

- Protocollo "dmiot" riverso-ingegnerizzato da [klada/dmiot2mqtt](https://github.com/klada/dmiot2mqtt)
  (GPLv3) — questa integrazione ne riusa solo la documentazione del
  protocollo, non il codice.
- Discussione della community che ha portato alla scoperta del protocollo:
  [Home Assistant Community – DreamMaker Feel Fan Plus](https://community.home-assistant.io/t/dreammaker-feel-fan-plus-dream-maker-dm-fan02-w/319885).

## Licenza

[MIT](LICENSE) — vedi il file `LICENSE`.
