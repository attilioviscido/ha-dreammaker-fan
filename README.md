# Dream Maker Fan – Home Assistant Integration

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-custom__component-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Read this in [Italiano](#italiano) / Leggi in [Italiano](#italiano)*

---

## English

A native, 100% local Home Assistant integration for **Dream Maker** smart fans (e.g. *Dream Maker Feel Fan Plus*, model **DM-FAN02-W** and **DM-FAN01**). By default, these fans only work via the manufacturer's cloud (`dm-maker.com`) and do not provide any official local API.

No external hubs, no MQTT brokers, no separate Docker containers required: everything runs directly inside Home Assistant as a native `custom_component`.

### Table of Contents

- [How It Works](#how-it-works)
- [Supported Devices](#supported-devices)
- [Created Entities](#created-entities)
- [Requirements](#requirements)
- [Installation](#installation)
  - [HACS (Recommended)](#hacs-custom-repository)
  - [Manual](#manual-installation)
- [DNS Redirection Setup](#dns-redirection-setup)
- [First Connection / Forcing Reconnection](#first-connection--forcing-reconnection)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Under the Hood (For Developers)](#under-the-hood-for-developers)
- [Credits](#credits)
- [License](#license)

---

### How It Works

The fan does not have a local HTTP/REST API: it maintains an active outbound TCP connection to `cloud1.dm-maker.com:31270`, the vendor's cloud server, exchanging JSON messages (state telemetry, heartbeats, and control commands).

This integration runs an internal TCP server on port **31270 inside Home Assistant**. By setting up a local DNS rewrite on your router or DNS resolver redirecting `cloud1.dm-maker.com` to your Home Assistant IP, the fan connects directly to Home Assistant instead of the real cloud. Entities are created and updated directly via push events without any intermediaries.

```
Dream Maker Fan  --- TCP 31270 --->  Home Assistant (this integration)
   (on LAN)                              (via local DNS rewrite)
```

The only external requirement is the local DNS rewrite. Because the fan's firmware is hardcoded to connect to that hostname, DNS redirection is mandatory (unless reverse-engineering and flashing the ESP/WiFi module, which is undocumented and risky). This is a one-time network configuration on your router, Pi-hole, or AdGuard Home.

The protocol ("dmiot") was reverse-engineered by the community in [dmiot2mqtt](https://github.com/klada/dmiot2mqtt) (klada, GPLv3) and discussed on the [Home Assistant Community Forum](https://community.home-assistant.io/t/dreammaker-feel-fan-plus-dream-maker-dm-fan02-w/319885). This integration is an independent, clean-room native Home Assistant implementation based on protocol documentation.

---

### Supported Devices

- **Dream Maker Feel Fan Plus (DM-FAN02-W)** (battery version) — *Tested & verified*
- **Dream Maker DM-FAN01** — *Untested, but uses the identical protocol according to community reports; please open an issue if you test it*
- Other Dream Maker devices using the "dmiot" protocol (identifiable by `comm_version` like `dmiot_v1.x.x` in device info inside the official app) should work similarly.

---

### Created Entities

For each connected fan (keyed by its LAN IP address), a device is registered with the following entities:

| Entity | Platform | Description |
|---|---|---|
| Dream Maker Fan | `fan` | Power, speed (1–100%), oscillation toggle, modes (direct / natural / smart) |
| Oscillation Angle | `select` | 30° / 60° / 90° / 120° / 140° |
| Button Beep | `switch` | Feedback buzzer on button presses / commands |
| LED Light | `switch` | Device status LED indicators |
| Child Lock | `switch` | Disables physical buttons on the device |
| Auto-off Timer | `number` | Timer 0–480 minutes |
| Rotate Left / Right | `button` | Manual single-step rotation control |
| Temperature | `sensor` | Ambient temperature in °C |
| Humidity | `sensor` | Ambient relative humidity in % |
| Wi-Fi Signal | `sensor` | Signal quality in % (diagnostic) |
| Command Source | `sensor` | `manual` / `auto` (diagnostic) |
| Device / Usage Exception | `binary_sensor` | Hardware or operational anomaly alerts (diagnostic) |

---

### Requirements

- Home Assistant (any install method: OS, Supervised, Container, Core).
- A local DNS resolver capable of rewriting a single domain (Router, Pi-hole, AdGuard Home, dnsmasq, etc.).
- Home Assistant must be reachable on inbound TCP port **31270** from your LAN:
  - **HA OS / Supervised**: Works out of the box (Core runs in host network mode).
  - **HA Container (Docker)**: Ensure port 31270 is published to the host (`network_mode: host` or `-p 31270:31270`), otherwise incoming connections cannot reach Home Assistant.
- Zero external Python dependencies (uses standard library `asyncio` and `json`).

---

### Installation

#### HACS (Custom Repository)

1. Go to **HACS** → **Integrations** → click the three dots (⋮) in the top-right → **Custom repositories**.
2. Paste the URL of this repository and choose category **Integration**.
3. Search for **"Dream Maker Fan"** in HACS and click **Download**.
4. Restart Home Assistant (**Settings** → **System** → **Restart**).
5. Go to **Settings** → **Devices & Services** → **Add Integration** → search for **"Dream Maker Fan"** → confirm (default port 31270).

#### Manual Installation

1. Download or clone this repository.
2. Copy `custom_components/dreammaker_fan/` into your Home Assistant directory `config/custom_components/`:
   ```text
   config/custom_components/dreammaker_fan/__init__.py
   config/custom_components/dreammaker_fan/manifest.json
   ... (all other files)
   ```
3. Restart Home Assistant.
4. Go to **Settings** → **Devices & Services** → **Add Integration** → search for **"Dream Maker Fan"**.

---

### DNS Redirection Setup

Redirect `cloud1.dm-maker.com` to the local LAN IP of your Home Assistant server:

- **AdGuard Home**: Filters → DNS rewrites → Add DNS rewrite:
  - Domain: `cloud1.dm-maker.com`
  - Answer: `<YOUR_HOME_ASSISTANT_IP>`
- **Pi-hole**: Settings → Local DNS → DNS Records:
  - Domain: `cloud1.dm-maker.com`
  - IP: `<YOUR_HOME_ASSISTANT_IP>`
- **Router**: Use Static DNS Host Override or custom dnsmasq rule (`address=/cloud1.dm-maker.com/<YOUR_HA_IP>`).

Test the resolution from a computer or terminal:
```bash
nslookup cloud1.dm-maker.com
```
It must reply with your Home Assistant IP. If it returns an external public IP, check that your device's DHCP is distributing the local DNS resolver to all network clients.

---

### First Connection / Forcing Reconnection

The fan holds its existing TCP socket to the old IP until disconnected. After setting up the DNS rewrite, force the fan to reconnect using one of these steps (from easiest to most decisive):

1. Toggle the physical power switch on the base of the fan (note: battery models might remain awake if only AC is unplugged).
2. Temporarily kick or block the fan's MAC address in your Wi-Fi router / Access Point client list, then re-enable it.
3. Reboot your Wi-Fi Access Point or router (forces all clients to reconnect).

As soon as the fan connects and authenticates, the integration will automatically discover the device and create all its entities.

---

### Troubleshooting

- **No device appears after DNS redirection:**
  1. Verify the DNS rewrite points to the correct Home Assistant IP.
  2. Test port reachability from your PC:
     - Windows (PowerShell): `Test-NetConnection -ComputerName <HA_IP> -Port 31270`
     - Linux/macOS: `nc -zv <HA_IP> 31270`
  3. Inspect your DNS query logs (Pi-hole / AdGuard) filtered by the fan's IP to verify queries for `cloud1.dm-maker.com`.
  4. Enable debug logging in Home Assistant (**Settings** → **Devices & Services** → **Dream Maker Fan** → **Enable debug logging**).
- **Static DHCP IP Recommended:**
  Entities are currently mapped to the fan's IP address. Assign a DHCP reservation in your router so the IP stays constant.

---

### Known Limitations

- While the DNS redirect is active, the official vendor mobile app will not work for this device (the mobile app expects the cloud server). Temporarily disable the DNS rule if you need to perform firmware updates.
- Communication is unencrypted plain-text JSON on the local network. Do not expose port 31270 to the public Internet.
- Initial Wi-Fi provisioning requires the official app or Bluetooth before local redirection can take place.

---

### Under the Hood (For Developers)

- `server.py`: Asyncio TCP server implementing the "dmiot" handshake, telemetry parsing, heartbeat ack, and entity command dispatching (`DreamMakerDevice`).
- `__init__.py`: Lifecycle management, config entry setup, platform forwarding.
- `entity.py`: Base entity class handling push updates, availability, and device registry info.
- Platforms: `fan.py`, `select.py`, `switch.py`, `number.py`, `button.py`, `sensor.py`, `binary_sensor.py`.

---

### Author & Credits

- **Author / Developer:** [Attilio Viscido](https://www.attilioviscido.it) ([www.attilioviscido.it](https://www.attilioviscido.it))
- Protocol reverse-engineered by [klada/dmiot2mqtt](https://github.com/klada/dmiot2mqtt) (GPLv3).
- Community research: [Home Assistant Community – DreamMaker Feel Fan Plus](https://community.home-assistant.io/t/dreammaker-feel-fan-plus-dream-maker-dm-fan02-w/319885).

---

### License

[MIT](LICENSE) — see the `LICENSE` file for details.

---
---

<a name="italiano"></a>
## Italiano

*Torna a [English](#english)*

Integrazione nativa e 100% locale per Home Assistant per i ventilatori smart **Dream Maker** (es. *Dream Maker Feel Fan Plus*, modello **DM-FAN02-W** e **DM-FAN01**), che di fabbrica funzionano solo tramite il cloud del produttore (`dm-maker.com`) e non espongono alcuna API locale ufficiale.

Nessun hub esterno, nessun broker MQTT, nessun container Docker separato: tutto gira direttamente dentro il processo di Home Assistant come un normale `custom_component`.

### Indice

- [Come funziona](#come-funziona-it)
- [Dispositivi supportati](#dispositivi-supportati-it)
- [Entità create](#entità-create-it)
- [Requisiti](#requisiti-it)
- [Installazione](#installazione-it)
  - [HACS (Consigliato)](#hacs-repository-personalizzato-it)
  - [Manuale](#installazione-manuale-it)
- [Configurazione: redirect DNS](#configurazione-redirect-dns-it)
- [Prima connessione / riconnessione forzata](#prima-connessione--riconnessione-forzata-it)
- [Risoluzione problemi](#risoluzione-problemi-it)
- [Limiti noti](#limiti-noti-it)
- [Come funziona internamente (per sviluppatori)](#come-funziona-internamente-per-sviluppatori-it)
- [Crediti](#crediti-it)
- [Licenza](#licenza-it)

---

### <a name="come-funziona-it"></a>Come funziona

Il ventilatore non ha un'API locale HTTP: tiene aperta una connessione TCP fissa verso `cloud1.dm-maker.com:31270`, il server cloud del produttore, e scambia con lui messaggi JSON (stato, battito cardiaco/heartbeat, comandi).

Questa integrazione apre un server TCP sulla stessa porta **31270 dentro Home Assistant**. Tramite un redirect DNS locale di quel dominio verso l'IP del tuo Home Assistant, il ventilatore si collega direttamente a Home Assistant invece che al cloud reale. Da lì le entità sono create e aggiornate in push, senza intermediari.

```
Ventilatore Dream Maker  --TCP 31270-->  Home Assistant (questa integrazione)
      (in LAN)                                (dopo redirect DNS locale)
```

L'unico requisito esterno a Home Assistant è il redirect DNS locale: il ventilatore è programmato per contattare solo quell'hostname, quindi il reindirizzamento è indispensabile (a meno di riflashare il modulo WiFi del ventilatore, operazione non documentata e rischiosa). È una configurazione da fare una tantum sul router o su Pi-hole/AdGuard Home.

Il protocollo (soprannominato "dmiot" dalla community) è stato riverso-ingegnerizzato nel progetto [dmiot2mqtt](https://github.com/klada/dmiot2mqtt) (klada, GPLv3) e nella discussione della [community Home Assistant](https://community.home-assistant.io/t/dreammaker-feel-fan-plus-dream-maker-dm-fan02-w/319885). Questa integrazione ne è un'implementazione nativa indipendente per Home Assistant (nessun codice riutilizzato direttamente, solo la documentazione del protocollo).

---

### <a name="dispositivi-supportati-it"></a>Dispositivi supportati

- **Dream Maker Feel Fan Plus DM-FAN02-W** (versione a batteria) — *Testato*
- **Dream Maker DM-FAN01** — *Non testato direttamente, ma usa lo stesso protocollo secondo la community; apri una issue se lo provi*
- Altri dispositivi Dream Maker che condividono il protocollo "dmiot" (riconoscibile da `comm_version` tipo `dmiot_v1.x.x` nelle info del dispositivo nell'app ufficiale) dovrebbero funzionare allo stesso modo.

---

### <a name="entità-create-it"></a>Entità create

Per ogni ventilatore che si collega (identificato per IP LAN), viene creato un dispositivo con queste entità:

| Entità | Tipo | Descrizione |
|---|---|---|
| Ventilatore Dream Maker | `fan` | Accensione, velocità 1–100%, oscillazione, modalità (direct / natural / smart) |
| Angolo oscillazione | `select` | 30° / 60° / 90° / 120° / 140° |
| Suono tasti | `switch` | Beep di feedback alla pressione tasti / comandi |
| Luce LED | `switch` | Indicatori LED sul dispositivo |
| Blocco bambini | `switch` | Disabilita i tasti fisici del ventilatore |
| Spegnimento automatico | `number` | Timer 0–480 minuti |
| Ruota a sinistra / a destra | `button` | Step manuale di rotazione |
| Temperatura | `sensor` | °C rilevati dal dispositivo |
| Umidità | `sensor` | % rilevata dal dispositivo |
| Segnale WiFi | `sensor` | % (diagnostico) |
| Sorgente comando | `sensor` | `manual` / `auto` (diagnostico) |
| Anomalia dispositivo / utilizzo | `binary_sensor` | Diagnostica problemi hardware/uso (diagnostico) |

---

### <a name="requisiti-it"></a>Requisiti

- Home Assistant (qualsiasi installazione: OS, Supervised, Container, Core).
- Possibilità di reindirizzare il DNS locale per un singolo dominio (router, Pi-hole, AdGuard Home, dnsmasq).
- Home Assistant deve poter ricevere connessioni TCP in ingresso sulla porta **31270** dalla LAN:
  - **Home Assistant OS / Supervised**: funziona nativamente senza modifiche (il container Core usa già la modalità host network).
  - **Home Assistant Container (Docker)**: assicurati che il container pubblichi la porta 31270 verso l'host (`network_mode: host`, oppure `-p 31270:31270`), altrimenti il ventilatore non potrà raggiungere Home Assistant.
- Nessuna dipendenza Python esterna: usa solo la libreria standard (`asyncio`, `json`).

---

### <a name="installazione-it"></a>Installazione

#### <a name="hacs-repository-personalizzato-it"></a>Tramite HACS (repository personalizzato)

1. HACS → **Integrazioni** → menu (⋮) in alto a destra → **Repository personalizzati**.
2. Aggiungi l'URL di questo repository, selezionando la categoria **Integrazione**.
3. Cerca **"Dream Maker Fan"** in HACS e clicca **Scarica**.
4. Riavvia Home Assistant (**Impostazioni** → **Sistema** → **Riavvia**).
5. **Impostazioni** → **Dispositivi e servizi** → **Aggiungi integrazione** → cerca **"Dream Maker Fan"** → conferma (porta default 31270).

#### <a name="installazione-manuale-it"></a>Installazione manuale

1. Scarica questo repository (Code → Download ZIP, oppure `git clone`).
2. Copia la cartella `custom_components/dreammaker_fan/` dentro `config/custom_components/` della tua installazione Home Assistant:
   ```text
   config/custom_components/dreammaker_fan/__init__.py
   config/custom_components/dreammaker_fan/manifest.json
   ... (tutti gli altri file)
   ```
3. Riavvia Home Assistant.
4. Vai su **Impostazioni** → **Dispositivi e servizi** → **Aggiungi integrazione** → cerca **"Dream Maker Fan"**.

---

### <a name="configurazione-redirect-dns-it"></a>Configurazione: redirect DNS

Reindirizza `cloud1.dm-maker.com` verso l'IP LAN della macchina su cui gira Home Assistant:

- **AdGuard Home**: Filtri → Riscritture DNS → Aggiungi riscrittura DNS:
  - Dominio: `cloud1.dm-maker.com`
  - Risposta IP: `<IP_DI_HOME_ASSISTANT>`
- **Pi-hole**: Impostazioni → DNS locale → Record DNS:
  - Dominio: `cloud1.dm-maker.com`
  - IP: `<IP_DI_HOME_ASSISTANT>`
- **Router**: se supporta DNS statici / host override, crea la regola per quel dominio.

Verifica che risponda correttamente:
```bash
nslookup cloud1.dm-maker.com
```
Deve rispondere con l'IP locale del tuo Home Assistant. Se risponde con un IP pubblico esterno, assicurati che il server DHCP distribuisca quel resolver locale a tutti i client della rete.

---

### <a name="prima-connessione--riconnessione-forzata-it"></a>Prima connessione / riconnessione forzata

Il ventilatore mantiene aperta la connessione TCP col vecchio indirizzo finché non si disconnette. Dopo aver impostato il redirect DNS, forzalo a riconnettersi:

1. Spegni e riaccendi l'interruttore fisico sulla base (i modelli a batteria rimangono accesi se si stacca solo il cavo).
2. Disconnetti o blocca momentaneamente il MAC address del ventilatore dall'access point / router Wi-Fi, quindi riabilitalo.
3. Riavvia l'access point o il router Wi-Fi.

Non appena il ventilatore si autentica, l'integrazione scopre automaticamente il dispositivo e genera tutte le relative entità.

---

### <a name="risoluzione-problemi-it"></a>Risoluzione problemi

- **Nessun dispositivo compare dopo il redirect DNS:**
  1. Verifica che l'IP del redirect sia esattamente quello di Home Assistant.
  2. Verifica la raggiungibilità della porta 31270:
     - PowerShell (Windows): `Test-NetConnection -ComputerName <IP_HA> -Port 31270`
     - Linux/macOS: `nc -zv <IP_HA> 31270`
  3. Controlla nei log del DNS locale (Pi-hole / AdGuard) che arrivino effettivamente le query per `cloud1.dm-maker.com` dall'IP del ventilatore.
  4. Abilita il log di debug (**Impostazioni** → **Dispositivi e servizi** → **Dream Maker Fan** → **Abilita registrazione debug**).
- **IP statico / DHCP reservation consigliata:**
  Le entità sono associate all'IP LAN del ventilatore: è vivamente consigliato impostare una reservation DHCP sul router per evitare cambi di IP.

---

### <a name="limiti-noti-it"></a>Limiti noti

- Con il redirect DNS attivo, l'app ufficiale Dream Maker smette di funzionare per questo dispositivo (l'app parla con il cloud reale, il ventilatore no). Ripristina temporaneamente il DNS se occorre aggiornare il firmware dall'app.
- Protocollo non cifrato in chiaro: usare solo nella LAN domestica protetta, non esporre mai la porta 31270 all'esterno su Internet.
- Se resettato di fabbrica, il ventilatore necessita della configurazione iniziale Wi-Fi tramite app o Bluetooth.

---

### <a name="come-funziona-internamente-per-sviluppatori-it"></a>Come funziona internamente (per sviluppatori)

- `server.py`: server TCP asyncio che implementa il protocollo "dmiot" (handshake, ack heartbeat, telemetria di stato) e astrae il dispositivo nell'oggetto `DreamMakerDevice`.
- `__init__.py`: ciclo di vita del componente, setup entry e forward alle piattaforme.
- `entity.py`: classe base per tutte le entità (device info, disponibilità, aggiornamenti push).
- Piattaforme: `fan.py`, `select.py`, `switch.py`, `number.py`, `button.py`, `sensor.py`, `binary_sensor.py`.

---

### <a name="crediti-it"></a>Autore e Crediti

- **Autore / Sviluppatore:** [Attilio Viscido](https://www.attilioviscido.it) ([www.attilioviscido.it](https://www.attilioviscido.it))
- Protocollo "dmiot" riverso-ingegnerizzato da [klada/dmiot2mqtt](https://github.com/klada/dmiot2mqtt) (GPLv3).
- Discussione della community Home Assistant: [DreamMaker Feel Fan Plus Thread](https://community.home-assistant.io/t/dreammaker-feel-fan-plus-dream-maker-dm-fan02-w/319885).

---

### <a name="licenza-it"></a>Licenza

Distribuito sotto licenza [MIT](LICENSE) — consulta il file `LICENSE` per maggiori dettagli.
