# SiFirma Sign - Estensione LibreOffice

**Versione 0.1.0 beta**

Estensione LibreOffice per avviare processi di **firma elettronica** direttamente dal documento aperto, integrata con il servizio **SiFirma** tramite WebAPI V2.

---

## Cos'e' SiFirma

**SiFirma** e' una soluzione cloud italiana per la firma elettronica di documenti, sviluppata e gestita 100% in Italia da [Alias Digital](https://aliasdigital.it/sifirma). E' progettata per professionisti, studi professionali e piccole-medie imprese che vogliono digitalizzare e semplificare i processi di sottoscrizione garantendo piena validita' legale.

### Funzionalita' principali

- **Firma Elettronica Semplice (FES)** - per firme di uso generale
- **Firma Elettronica Avanzata (FEA)** - conforme alla normativa vigente, inclusa in tutti i piani
- **Firma Elettronica Qualificata (FEQ)** - massimo livello di sicurezza e validita' legale
- **Autenticazione OTP** - firma protetta tramite codice One-Time Password
- **Marche temporali** - incluse in tutte le licenze
- **Utenti e firmatari illimitati** (piano Small Business)
- **API integrate** - per l'integrazione nei software esistenti
- **Prova gratuita** di 30 giorni senza carta di credito

### Acquistare SiFirma

Per attivare il servizio SiFirma e ottenere le credenziali API necessarie all'utilizzo di questa estensione, visita:

**[https://www.eldataservizi.it/services/sifirma](https://www.eldataservizi.it/services/sifirma)**

---

## Funzionalita' dell'estensione

- Esportazione automatica del documento aperto in PDF
- Avvio del processo di firma tramite SiFirma WebAPI V2
- Supporto per firma FES, FEA e FEQ
- Posizionamento firma tramite tag nel documento (MarcatoriV2), coordinate fisse o Acrofield
- Gestione di piu' firmatari per ogni processo (fino a 2 nella versione attuale)
- Invio notifiche email automatiche ai firmatari
- Verifica stato processo di firma tramite UID
- Pannello di amministrazione per la configurazione delle credenziali
- Compatibile con LibreOffice Writer, Calc e Impress
- Funziona su Linux e Windows

---

## Requisiti

- LibreOffice 4.0 o superiore (raccomandato 7.x o superiore)
- Python 3.x (incluso in LibreOffice)
- Connessione a internet
- Credenziali API SiFirma attive (API Key, API Secret, Partita IVA o Codice Fiscale)

---

## Installazione

### Metodo 1: da interfaccia grafica (raccomandato)

1. Scarica il file `SiFirmaSign.oxt` dalla pagina [Releases](../../releases) di questo repository
2. Apri LibreOffice
3. Vai su **Strumenti > Gestione estensioni**
4. Clicca su **Aggiungi**
5. Seleziona il file `SiFirmaSign.oxt`
6. Accetta i termini e completa l'installazione
7. Riavvia LibreOffice

### Metodo 2: da riga di comando

```bash
unopkg add SiFirmaSign.oxt
```

Per aggiornare una versione esistente:

```bash
unopkg remove com.sifirma.sign
unopkg add SiFirmaSign.oxt
```

### Build dal sorgente

Per compilare l'estensione dai sorgenti e' necessario avere `zip` installato:

```bash
cd sifirma-sign
chmod +x build.sh
./build.sh
```

Il file `SiFirmaSign.oxt` verra' generato nella directory principale del progetto.

---

## Configurazione

Dopo l'installazione, nella barra dei menu di LibreOffice apparira' la voce **SiFirma**.

1. Vai su **SiFirma > Pannello Amministrazione**
2. Inserisci i dati forniti da SiFirma:
   - **URL API** (default: `https://sifirmawebapi.aliasgrouplab.it`)
   - **API Key**
   - **API Secret**
   - **Partita IVA** o **Codice Fiscale**
3. Configura le impostazioni di default (tipo firma, giorni scadenza, notifiche email)
4. Clicca su **Testa Connessione** per verificare le credenziali
5. Clicca su **Salva**

Le credenziali vengono salvate nel file `~/.sifirma_config.json` con permessi riservati all'utente (600).

---

## Utilizzo

### Avviare un processo di firma

1. Apri il documento da far firmare in LibreOffice (Writer, Calc o Impress)
2. (Opzionale) Inserisci i tag MarcatoriV2 nel documento per il posizionamento della firma
3. Vai su **SiFirma > Avvia Firma Documento...**
4. Compila i dati del processo:
   - Nome processo
   - Data di scadenza
   - Tipo di firma (FES, FEA, FEQ)
   - Dati del firmatario (Nome, Cognome, Codice Fiscale, Email, Telefono)
5. Clicca su **Avvia Firma**
6. L'estensione esportera' automaticamente il documento in PDF e lo inviera' a SiFirma
7. Il firmatario ricevera' una email con il link per firmare

### Verificare lo stato di un processo

1. Vai su **SiFirma > Verifica Stato Processo...**
2. Inserisci l'UID del processo ricevuto al momento dell'avvio
3. Clicca su **Verifica**

---

## Roadmap

Le funzionalita' pianificate per le prossime versioni:

- [ ] **Firme multiple** - supporto per piu' di 2 firmatari per processo, con gestione avanzata dell'ordine sequenziale
- [ ] **Firma con CNS/Smartcard** - integrazione con la Carta Nazionale dei Servizi e altri dispositivi di firma con smartcard per la Firma Elettronica Qualificata (FEQ)

---

## Licenza

Questo software e' distribuito sotto licenza **GNU General Public License v3.0 (GPL-3.0)**.

Vedi il file [LICENSE](LICENSE) per i dettagli completi.

---

## Contribuire

Le segnalazioni di bug e le richieste di funzionalita' sono benvenute tramite le [Issues](../../issues) di GitHub.

---

## Link utili

- [SiFirma - Alias Digital](https://aliasdigital.it/sifirma)
- [Acquista SiFirma - ElData Servizi](https://www.eldataservizi.it/sifirma)
- [Documentazione WebAPI V2](https://sifirmawebapi.aliasgrouplab.it/docs/index.html?urls.primaryName=V2)
