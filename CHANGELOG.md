# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.0.0/),
e il progetto adotta il versionamento [Semantic Versioning](https://semver.org/lang/it/).

---

## [0.1.0-beta] - 2026-03-06

### Prima versione pubblica

#### Aggiunto
- Pannello di Amministrazione per la configurazione delle credenziali SiFirma (API Key, API Secret, Partita IVA / Codice Fiscale)
- Test connessione integrato nel pannello admin
- Esportazione automatica del documento aperto in PDF (Writer, Calc, Impress)
- Avvio processo di firma tramite SiFirma WebAPI V2 (`POST /api/v2/processofirma/avvia`)
- Supporto tipi di firma: FES, FEA, FEQ
- Supporto posizionamento firma: MarcatoriV2, coordinate fisse, Acrofield
- Gestione fino a 2 firmatari per processo con ordine sequenziale
- Invio notifica email automatica ai firmatari (opzionale)
- Configurazione URL redirect post-firma e WebHook callback
- Verifica stato processo tramite UID (`GET /api/v2/processofirma/{uid}`)
- Menu SiFirma nella barra dei menu di LibreOffice
- Pulsante di accesso rapido nella toolbar
- Salvataggio configurazione locale in `~/.sifirma_config.json` con permessi 600
- Compatibilita' con LibreOffice 4.0+ su Linux e Windows
- Script di build (`build.sh`) per generare il file `.oxt` installabile
