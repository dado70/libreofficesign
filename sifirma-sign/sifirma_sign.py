"""
SiFirma Sign - Estensione LibreOffice
Integrazione con SiFirma WebAPI V2 per l'avvio di processi di firma elettronica.

Flusso principale:
  1. L'utente configura le credenziali nel Pannello Amministrazione
  2. Il documento aperto (con eventuali tag per il posizionamento firma) viene
     esportato in PDF e inviato all'API SiFirma tramite POST /api/v2/processofirma/avvia
  3. SiFirma avvia il processo e notifica i firmatari via email (opzionale)
"""

import uno
import unohelper
import os
import json
import base64
import datetime

from com.sun.star.task import XJobExecutor
from com.sun.star.awt import XActionListener
from com.sun.star.beans import PropertyValue

try:
    import urllib.request as urlrequest
    import urllib.error as urlerror
except ImportError:
    import urllib2 as urlrequest
    import urllib2 as urlerror

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

SIFIRMA_API_BASE_DEFAULT = "https://sifirmawebapi.aliasgrouplab.it"
CONFIG_FILENAME = ".sifirma_config.json"
TEMP_DIR_NAME = ".sifirma_temp"

TIPO_FIRMA_LABELS = [
    "FES - Firma Elettronica Semplice",
    "FEA - Firma Elettronica Avanzata",
    "FEQ - Firma Elettronica Qualificata",
]
TIPO_FIRMA_VALUES = [1, 2, 3]

TIPO_IDENTIFICATORE_LABELS = [
    "Coordinate (posizione fissa)",
    "Acrofield (campi PDF)",
    "MarcatoriV2 (tag nel documento)",
]
TIPO_IDENTIFICATORE_VALUES = [2, 3, 4]

STATO_PROCESSO = {
    1: "Bozza",
    2: "Invio in Elaborazione",
    3: "In Attesa di Firma",
    4: "Completato",
    5: "Bloccato",
    6: "Scaduto",
    7: "Annullato",
    8: "Reinviato",
    9: "Rifiutato",
    101: "Terminato",
    255: "Non Definito",
}

PDF_FILTERS = {
    "com.sun.star.text.TextDocument": "writer_pdf_Export",
    "com.sun.star.sheet.SpreadsheetDocument": "calc_pdf_Export",
    "com.sun.star.presentation.PresentationDocument": "impress_pdf_Export",
    "com.sun.star.drawing.DrawingDocument": "draw_pdf_Export",
}


# ---------------------------------------------------------------------------
# Listener ausiliario per il test connessione
# ---------------------------------------------------------------------------

class TestConnectionListener(unohelper.Base, XActionListener):
    """Listener per il pulsante 'Testa Connessione' nel pannello admin."""

    def __init__(self, job, dialog):
        self.job = job
        self.dialog = dialog

    def actionPerformed(self, event):
        config = {
            "api_url": self.dialog.getControl("txtApiUrl").getText().strip().rstrip("/"),
            "api_key": self.dialog.getControl("txtApiKey").getText().strip(),
            "api_secret": self.dialog.getControl("txtApiSecret").getText().strip(),
            "partita_iva": self.dialog.getControl("txtPiva").getText().strip(),
            "codice_fiscale": self.dialog.getControl("txtCf").getText().strip(),
        }
        success, msg = self.job.test_api_connection(config)
        title = "Test Connessione - OK" if success else "Test Connessione - Errore"
        self.job.show_message(msg, title)

    def disposing(self, event):
        pass


# ---------------------------------------------------------------------------
# Classe principale dell'estensione
# ---------------------------------------------------------------------------

class SiFirmaSignJob(unohelper.Base, XJobExecutor):
    """Job LibreOffice che gestisce l'integrazione con SiFirma."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.smgr = ctx.ServiceManager
        self.desktop = self.smgr.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx
        )

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------

    def trigger(self, args):
        """Dispatch delle azioni invocate dal menu."""
        if args == "ConfigureAdmin":
            self.show_admin_panel()
        elif args == "StartSigning":
            self.start_signing_process()
        elif args == "CheckStatus":
            self.check_process_status()

    # -----------------------------------------------------------------------
    # PANNELLO AMMINISTRAZIONE
    # -----------------------------------------------------------------------

    def show_admin_panel(self):
        """Mostra il pannello di amministrazione/configurazione."""
        config = self.load_config()
        dialog = self._build_admin_dialog(config)
        result = self._execute_dialog(dialog)
        if result == 1:  # OK / Salva
            new_config = self._read_admin_dialog(dialog, config)
            errors = self._validate_config_values(new_config)
            if errors:
                dialog.dispose()
                self.show_message(
                    "Configurazione non valida:\n" + "\n".join(errors),
                    "SiFirma Sign - Errore"
                )
                return
            self.save_config(new_config)
            self.show_message(
                "Configurazione salvata con successo!", "SiFirma Sign"
            )
        dialog.dispose()

    def _build_admin_dialog(self, config):
        """Costruisce il dialog del pannello admin."""
        dm = self._new_dialog_model(280, 285, "SiFirma Sign - Pannello Amministrazione")
        y = 8

        # URL API
        self._lbl(dm, "lblApiUrl", "URL API SiFirma:", 8, y, 100, 12)
        self._txt(dm, "txtApiUrl", 112, y, 160, 12)
        y += 18

        # Separatore visivo
        self._lbl(dm, "lblSep1", "Credenziali account SiFirma:", 8, y, 270, 12)
        y += 14

        # API Key
        self._lbl(dm, "lblApiKey", "API Key:", 8, y, 100, 12)
        self._txt(dm, "txtApiKey", 112, y, 160, 12)
        y += 16

        # API Secret
        self._lbl(dm, "lblApiSecret", "API Secret:", 8, y, 100, 12)
        self._txt(dm, "txtApiSecret", 112, y, 160, 12, password=True)
        y += 16

        # Partita IVA
        self._lbl(dm, "lblPiva", "Partita IVA:", 8, y, 100, 12)
        self._txt(dm, "txtPiva", 112, y, 160, 12)
        y += 16

        # Codice Fiscale
        self._lbl(dm, "lblCf", "Codice Fiscale:", 8, y, 100, 12)
        self._txt(dm, "txtCf", 112, y, 160, 12)
        y += 18

        # Separatore visivo
        self._lbl(dm, "lblSep2", "Impostazioni default processo:", 8, y, 270, 12)
        y += 14

        # Tipo Firma
        self._lbl(dm, "lblTipoFirma", "Tipo firma:", 8, y, 100, 12)
        self._dropdown(dm, "lstTipoFirma", 112, y, 160, 12, TIPO_FIRMA_LABELS)
        y += 16

        # Tipo Identificatore firma (posizionamento)
        self._lbl(dm, "lblTipoId", "Posizionamento firma:", 8, y, 100, 12)
        self._dropdown(dm, "lstTipoId", 112, y, 160, 12, TIPO_IDENTIFICATORE_LABELS)
        y += 16

        # Giorni scadenza
        self._lbl(dm, "lblGiorni", "Giorni scadenza default:", 8, y, 100, 12)
        self._txt(dm, "txtGiorni", 112, y, 40, 12)
        y += 16

        # Invia mail
        self._chk(dm, "chkInviaMail", "Invia email automatica ai firmatari", 8, y, 270, 12)
        y += 16

        # URL Redirect (opzionale)
        self._lbl(dm, "lblRedirect", "URL redirect post-firma:", 8, y, 100, 12)
        self._txt(dm, "txtRedirect", 112, y, 160, 12)
        y += 16

        # WebHook (opzionale)
        self._lbl(dm, "lblWebhook", "URL WebHook callback:", 8, y, 100, 12)
        self._txt(dm, "txtWebhook", 112, y, 160, 12)
        y += 22

        # Pulsanti
        self._btn(dm, "btnTest", "Testa Connessione", 8, y, 80, 14, 0)
        self._btn(dm, "btnOK", "Salva", 178, y, 42, 14, 1)
        self._btn(dm, "btnCancel", "Annulla", 230, y, 42, 14, 2)

        dialog = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", self.ctx
        )
        dialog.setModel(dm)

        # Popola valori correnti
        dialog.getControl("txtApiUrl").setText(
            config.get("api_url", SIFIRMA_API_BASE_DEFAULT)
        )
        dialog.getControl("txtApiKey").setText(config.get("api_key", ""))
        dialog.getControl("txtApiSecret").setText(config.get("api_secret", ""))
        dialog.getControl("txtPiva").setText(config.get("partita_iva", ""))
        dialog.getControl("txtCf").setText(config.get("codice_fiscale", ""))
        dialog.getControl("txtGiorni").setText(str(config.get("giorni_scadenza", 30)))
        dialog.getControl("chkInviaMail").setState(
            1 if config.get("invia_mail", True) else 0
        )
        dialog.getControl("txtRedirect").setText(config.get("url_redirect", ""))
        dialog.getControl("txtWebhook").setText(config.get("webhook_callback", ""))

        # Selezione tipo firma
        tf_val = config.get("tipo_firma", 2)
        idx_tf = TIPO_FIRMA_VALUES.index(tf_val) if tf_val in TIPO_FIRMA_VALUES else 1
        dialog.getControl("lstTipoFirma").selectItemPos(idx_tf, True)

        # Selezione tipo identificatore
        ti_val = config.get("tipo_identificatore_firma", 4)
        idx_ti = (
            TIPO_IDENTIFICATORE_VALUES.index(ti_val)
            if ti_val in TIPO_IDENTIFICATORE_VALUES
            else 2
        )
        dialog.getControl("lstTipoId").selectItemPos(idx_ti, True)

        # Listener pulsante test
        dialog.getControl("btnTest").addActionListener(
            TestConnectionListener(self, dialog)
        )

        return dialog

    def _read_admin_dialog(self, dialog, old_config):
        """Legge i valori dal dialog admin e restituisce un dict config."""
        sel_tf = dialog.getControl("lstTipoFirma").getSelectedItemPos()
        tipo_firma = TIPO_FIRMA_VALUES[sel_tf] if 0 <= sel_tf < len(TIPO_FIRMA_VALUES) else 2

        sel_ti = dialog.getControl("lstTipoId").getSelectedItemPos()
        tipo_id = (
            TIPO_IDENTIFICATORE_VALUES[sel_ti]
            if 0 <= sel_ti < len(TIPO_IDENTIFICATORE_VALUES)
            else 4
        )

        giorni_str = dialog.getControl("txtGiorni").getText().strip()
        try:
            giorni = max(1, int(giorni_str))
        except ValueError:
            giorni = 30

        return {
            "api_url": dialog.getControl("txtApiUrl").getText().strip().rstrip("/")
                or SIFIRMA_API_BASE_DEFAULT,
            "api_key": dialog.getControl("txtApiKey").getText().strip(),
            "api_secret": dialog.getControl("txtApiSecret").getText().strip(),
            "partita_iva": dialog.getControl("txtPiva").getText().strip(),
            "codice_fiscale": dialog.getControl("txtCf").getText().strip(),
            "tipo_firma": tipo_firma,
            "tipo_identificatore_firma": tipo_id,
            "giorni_scadenza": giorni,
            "invia_mail": dialog.getControl("chkInviaMail").getState() == 1,
            "url_redirect": dialog.getControl("txtRedirect").getText().strip(),
            "webhook_callback": dialog.getControl("txtWebhook").getText().strip(),
        }

    # -----------------------------------------------------------------------
    # TEST CONNESSIONE
    # -----------------------------------------------------------------------

    def test_api_connection(self, config=None):
        """
        Testa la raggiungibilita' dell'API SiFirma via GET /api/v2/info/versioni.
        Restituisce (bool successo, str messaggio).
        """
        if config is None:
            config = self.load_config()
        api_url = config.get("api_url", SIFIRMA_API_BASE_DEFAULT).rstrip("/")
        url = "{}/api/v2/info/versioni".format(api_url)
        try:
            req = urlrequest.Request(url)
            req.add_header("Accept", "application/json")
            response = urlrequest.urlopen(req, timeout=10)
            result = json.loads(response.read().decode("utf-8"))
            ver_api = result.get("versioneAPI", "N/A")
            ver_core = result.get("versioneCore", "N/A")
            return True, (
                "Connessione riuscita!\n\n"
                "Versione API: {}\n"
                "Versione Core: {}".format(ver_api, ver_core)
            )
        except Exception as e:
            return False, "Errore connessione:\n{}".format(str(e))

    # -----------------------------------------------------------------------
    # AVVIA PROCESSO DI FIRMA
    # -----------------------------------------------------------------------

    def start_signing_process(self):
        """Punto di ingresso per l'avvio della firma dal menu."""
        config = self.load_config()

        # Verifica configurazione
        cfg_errors = self._validate_config_required(config)
        if cfg_errors:
            self.show_message(
                "Configurazione incompleta:\n{}\n\n"
                "Vai su SiFirma > Pannello Amministrazione.".format(
                    "\n".join(cfg_errors)
                ),
                "SiFirma Sign - Errore"
            )
            return

        # Verifica documento aperto
        doc = self.desktop.getCurrentComponent()
        if not doc:
            self.show_message("Nessun documento aperto!", "SiFirma Sign - Errore")
            return

        if not self._is_signable_document(doc):
            self.show_message(
                "Il documento corrente non supporta l'esportazione PDF.\n"
                "Aprire un documento Writer, Calc o Impress.",
                "SiFirma Sign - Errore"
            )
            return

        # Dialog per i dati del processo
        process_data = self.show_signing_dialog(doc, config)
        if not process_data:
            return  # l'utente ha annullato

        # Validazione dati processo
        proc_errors = self._validate_process_data(process_data)
        if proc_errors:
            self.show_message(
                "Dati non validi:\n{}".format("\n".join(proc_errors)),
                "SiFirma Sign - Errore"
            )
            return

        # Esporta PDF
        pdf_path = self.export_to_pdf(doc)
        if not pdf_path:
            return

        try:
            # Invia a SiFirma
            success, result = self._call_avvia_processo(pdf_path, config, process_data)
        finally:
            # Elimina file temporaneo
            try:
                os.remove(pdf_path)
            except Exception:
                pass

        if success:
            self._show_success_result(result)
        else:
            self.show_message(
                "Errore durante l'invio a SiFirma:\n{}".format(result),
                "SiFirma Sign - Errore"
            )

    # -----------------------------------------------------------------------
    # DIALOG FIRMA
    # -----------------------------------------------------------------------

    def show_signing_dialog(self, doc, config):
        """Mostra il dialog per la configurazione del processo di firma."""
        # Nome file documento
        doc_name = ""
        try:
            url = doc.getURL()
            if url:
                doc_name = url.split("/")[-1].rsplit(".", 1)[0]
        except Exception:
            pass

        giorni = config.get("giorni_scadenza", 30)
        scadenza_default = (
            datetime.date.today() + datetime.timedelta(days=giorni)
        ).strftime("%Y-%m-%d")

        dialog = self._build_signing_dialog(config, doc_name, scadenza_default)
        result = self._execute_dialog(dialog)

        if result != 1:
            dialog.dispose()
            return None

        data = self._read_signing_dialog(dialog, config)
        dialog.dispose()
        return data

    def _build_signing_dialog(self, config, doc_name, scadenza_default):
        """Costruisce il dialog di avvio firma."""
        dm = self._new_dialog_model(300, 310, "SiFirma Sign - Avvia Processo di Firma")
        y = 8

        # --- Sezione processo ---
        self._lbl(dm, "lblSezProc", "IMPOSTAZIONI PROCESSO", 8, y, 280, 12)
        y += 14

        self._lbl(dm, "lblNomeProc", "Nome processo:", 8, y, 100, 12)
        self._txt(dm, "txtNomeProc", 112, y, 180, 12)
        y += 16

        self._lbl(dm, "lblNomeDoc", "Nome file PDF:", 8, y, 100, 12)
        self._txt(dm, "txtNomeDoc", 112, y, 180, 12)
        y += 16

        self._lbl(dm, "lblScadenza", "Scadenza (YYYY-MM-DD):", 8, y, 100, 12)
        self._txt(dm, "txtScadenza", 112, y, 80, 12)
        y += 16

        self._lbl(dm, "lblTipoFirma", "Tipo firma:", 8, y, 100, 12)
        self._dropdown(dm, "lstTipoFirma", 112, y, 180, 12, TIPO_FIRMA_LABELS)
        y += 16

        self._chk(dm, "chkInviaMail", "Invia email ai firmatari", 8, y, 270, 12)
        y += 20

        # --- Firmatario 1 (obbligatorio) ---
        self._lbl(dm, "lblSezF1", "FIRMATARIO 1 (obbligatorio)", 8, y, 280, 12)
        y += 14

        self._lbl(dm, "lblF1Nome", "Nome:", 8, y, 45, 12)
        self._txt(dm, "txtF1Nome", 56, y, 95, 12)
        self._lbl(dm, "lblF1Cognome", "Cognome:", 156, y, 55, 12)
        self._txt(dm, "txtF1Cognome", 214, y, 78, 12)
        y += 14

        self._lbl(dm, "lblF1CF", "Codice Fiscale:", 8, y, 80, 12)
        self._txt(dm, "txtF1CF", 90, y, 130, 12)
        y += 14

        self._lbl(dm, "lblF1Email", "Email:", 8, y, 45, 12)
        self._txt(dm, "txtF1Email", 56, y, 236, 12)
        y += 14

        self._lbl(dm, "lblF1Tel", "Telefono:", 8, y, 45, 12)
        self._txt(dm, "txtF1Tel", 56, y, 120, 12)
        y += 20

        # --- Firmatario 2 (opzionale) ---
        self._lbl(dm, "lblSezF2", "FIRMATARIO 2 (opzionale)", 8, y, 280, 12)
        y += 14

        self._lbl(dm, "lblF2Nome", "Nome:", 8, y, 45, 12)
        self._txt(dm, "txtF2Nome", 56, y, 95, 12)
        self._lbl(dm, "lblF2Cognome", "Cognome:", 156, y, 55, 12)
        self._txt(dm, "txtF2Cognome", 214, y, 78, 12)
        y += 14

        self._lbl(dm, "lblF2CF", "Codice Fiscale:", 8, y, 80, 12)
        self._txt(dm, "txtF2CF", 90, y, 130, 12)
        y += 14

        self._lbl(dm, "lblF2Email", "Email:", 8, y, 45, 12)
        self._txt(dm, "txtF2Email", 56, y, 236, 12)
        y += 14

        self._lbl(dm, "lblF2Tel", "Telefono:", 8, y, 45, 12)
        self._txt(dm, "txtF2Tel", 56, y, 120, 12)
        y += 22

        # Pulsanti
        self._btn(dm, "btnOK", "Avvia Firma", 158, y, 64, 14, 1)
        self._btn(dm, "btnCancel", "Annulla", 230, y, 62, 14, 2)

        dialog = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", self.ctx
        )
        dialog.setModel(dm)

        # Pre-popola valori
        dialog.getControl("txtNomeProc").setText(doc_name or "Processo di Firma")
        dialog.getControl("txtNomeDoc").setText(
            "{}.pdf".format(doc_name) if doc_name else "documento.pdf"
        )
        dialog.getControl("txtScadenza").setText(scadenza_default)
        dialog.getControl("chkInviaMail").setState(
            1 if config.get("invia_mail", True) else 0
        )

        tf_val = config.get("tipo_firma", 2)
        idx_tf = TIPO_FIRMA_VALUES.index(tf_val) if tf_val in TIPO_FIRMA_VALUES else 1
        dialog.getControl("lstTipoFirma").selectItemPos(idx_tf, True)

        return dialog

    def _read_signing_dialog(self, dialog, config):
        """Legge i dati dal dialog di firma e restituisce un dict."""
        sel_tf = dialog.getControl("lstTipoFirma").getSelectedItemPos()
        tipo_firma = TIPO_FIRMA_VALUES[sel_tf] if 0 <= sel_tf < len(TIPO_FIRMA_VALUES) else 2

        firmatari = []

        # Firmatario 1
        f1 = self._read_firmatario(dialog, "1")
        if f1:
            firmatari.append(f1)

        # Firmatario 2
        f2 = self._read_firmatario(dialog, "2")
        if f2:
            firmatari.append(f2)

        nome_doc = dialog.getControl("txtNomeDoc").getText().strip()
        if nome_doc and not nome_doc.lower().endswith(".pdf"):
            nome_doc += ".pdf"

        return {
            "nome_processo": dialog.getControl("txtNomeProc").getText().strip(),
            "nome_documento": nome_doc or "documento.pdf",
            "data_scadenza": dialog.getControl("txtScadenza").getText().strip(),
            "tipo_firma": tipo_firma,
            "invia_mail": dialog.getControl("chkInviaMail").getState() == 1,
            "firmatari": firmatari,
        }

    def _read_firmatario(self, dialog, n):
        """Legge i campi del firmatario N dal dialog. Restituisce dict o None."""
        nome = dialog.getControl("txtF{}Nome".format(n)).getText().strip()
        cognome = dialog.getControl("txtF{}Cognome".format(n)).getText().strip()
        cf = dialog.getControl("txtF{}CF".format(n)).getText().strip()
        email = dialog.getControl("txtF{}Email".format(n)).getText().strip()
        tel = dialog.getControl("txtF{}Tel".format(n)).getText().strip()

        # Un firmatario e' valido solo se ha almeno nome+cognome e CF o email
        if not (nome or cognome or cf or email):
            return None

        return {
            "nome": nome,
            "cognome": cognome,
            "codiceFiscale": cf,
            "email": email,
            "telefono": tel,
            "tipoIdentificativoFiscale": 1,  # 1 = CodiceFiscale
        }

    # -----------------------------------------------------------------------
    # ESPORTAZIONE PDF
    # -----------------------------------------------------------------------

    def export_to_pdf(self, doc):
        """Esporta il documento corrente in PDF. Restituisce il path o None."""
        try:
            temp_dir = os.path.join(os.path.expanduser("~"), TEMP_DIR_NAME)
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            pdf_path = os.path.join(temp_dir, "sifirma_export.pdf")
            pdf_url = uno.systemPathToFileUrl(pdf_path)

            filter_name = self._get_pdf_filter(doc)
            properties = (
                PropertyValue("FilterName", 0, filter_name, 0),
                PropertyValue("Overwrite", 0, True, 0),
            )
            doc.storeToURL(pdf_url, properties)
            return pdf_path

        except Exception as e:
            self.show_message(
                "Errore durante l'esportazione PDF:\n{}".format(str(e)),
                "SiFirma Sign - Errore"
            )
            return None

    def _get_pdf_filter(self, doc):
        """Determina il filtro PDF corretto in base al tipo di documento."""
        for service, filter_name in PDF_FILTERS.items():
            try:
                if doc.supportsService(service):
                    return filter_name
            except Exception:
                pass
        return "writer_pdf_Export"  # fallback

    def _is_signable_document(self, doc):
        """Verifica che il documento supporti l'esportazione PDF."""
        for service in PDF_FILTERS:
            try:
                if doc.supportsService(service):
                    return True
            except Exception:
                pass
        return False

    # -----------------------------------------------------------------------
    # CHIAMATA API SIFIRMA - AVVIA PROCESSO
    # -----------------------------------------------------------------------

    def _call_avvia_processo(self, pdf_path, config, process_data):
        """
        Chiama POST /api/v2/processofirma/avvia.
        Restituisce (bool successo, dict|str result).
        """
        try:
            with open(pdf_path, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

            firmatari_api = []
            for idx, f in enumerate(process_data.get("firmatari", [])):
                firmatario = {
                    "nome": f.get("nome", ""),
                    "cognome": f.get("cognome", ""),
                    "tipoIdentificativoFiscale": f.get("tipoIdentificativoFiscale", 1),
                    "codiceFiscale": f.get("codiceFiscale", ""),
                    "email": f.get("email", ""),
                    "telefono": f.get("telefono", ""),
                    "ordineSequenziale": idx + 1,
                }
                firmatari_api.append(firmatario)

            payload = {
                "nomeProcesso": process_data.get("nome_processo", ""),
                "tipoFirma": process_data.get("tipo_firma", 2),
                "nomeDocumentoDaFirmare": process_data.get("nome_documento", "documento.pdf"),
                "documentoDaFirmare": pdf_b64,
                "firmatari": firmatari_api,
                "dataScadenza": process_data.get("data_scadenza", ""),
                "inviaMail": process_data.get("invia_mail", True),
            }

            # Tipo identificatore firma (posizionamento nel PDF)
            tipo_id = config.get("tipo_identificatore_firma")
            if tipo_id:
                payload["tipoIdentificatoreFirma"] = tipo_id

            # Campi opzionali
            url_redirect = config.get("url_redirect", "").strip()
            if url_redirect:
                payload["urlRedirect"] = url_redirect

            webhook = config.get("webhook_callback", "").strip()
            if webhook:
                payload["webHookCallback"] = webhook

            headers = self._build_auth_headers(config)
            headers["Content-Type"] = "application/json"

            api_url = config.get("api_url", SIFIRMA_API_BASE_DEFAULT).rstrip("/")
            url = "{}/api/v2/processofirma/avvia".format(api_url)

            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urlrequest.Request(url, data=body, headers=headers)
            response = urlrequest.urlopen(req, timeout=60)
            result = json.loads(response.read().decode("utf-8"))
            return True, result

        except Exception as e:
            return False, self._extract_error(e)

    def _show_success_result(self, result):
        """Mostra il messaggio di successo dopo l'avvio del processo."""
        uid = result.get("uidProcesso", "N/A")
        richieste = result.get("richiesteFirma", [])

        lines = [
            "Processo di firma avviato con successo!",
            "",
            "UID Processo: {}".format(uid),
        ]

        for i, r in enumerate(richieste, 1):
            firmatario = r.get("firmatario", {})
            nome = "{} {}".format(
                firmatario.get("nome", ""), firmatario.get("cognome", "")
            ).strip()
            url_firma = r.get("portaleFirmaURL", "")
            uid_r = r.get("uidRichiesta", "")

            lines.append("")
            lines.append("Richiesta {}: {}".format(i, nome or uid_r))
            if url_firma:
                lines.append("URL firma: {}".format(url_firma))

        self.show_message("\n".join(lines), "SiFirma Sign - Processo Avviato")

    # -----------------------------------------------------------------------
    # VERIFICA STATO PROCESSO
    # -----------------------------------------------------------------------

    def check_process_status(self):
        """Verifica lo stato di un processo di firma tramite il suo UID."""
        config = self.load_config()
        cfg_errors = self._validate_config_required(config)
        if cfg_errors:
            self.show_message(
                "Configurazione incompleta. Vai su SiFirma > Pannello Amministrazione.",
                "SiFirma Sign - Errore"
            )
            return

        dialog = self._build_status_dialog()
        result = self._execute_dialog(dialog)
        if result != 1:
            dialog.dispose()
            return

        uid = dialog.getControl("txtUID").getText().strip()
        dialog.dispose()

        if not uid:
            self.show_message(
                "Inserire un UID processo valido.", "SiFirma Sign - Errore"
            )
            return

        self._fetch_and_show_status(uid, config)

    def _build_status_dialog(self):
        """Costruisce il dialog per inserire l'UID del processo."""
        dm = self._new_dialog_model(260, 66, "SiFirma Sign - Verifica Stato Processo")
        self._lbl(dm, "lblUID", "UID Processo:", 8, 12, 80, 12)
        self._txt(dm, "txtUID", 92, 12, 160, 12)
        self._btn(dm, "btnOK", "Verifica", 148, 40, 52, 14, 1)
        self._btn(dm, "btnCancel", "Annulla", 210, 40, 42, 14, 2)

        dialog = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", self.ctx
        )
        dialog.setModel(dm)
        return dialog

    def _fetch_and_show_status(self, uid, config):
        """Recupera e visualizza lo stato del processo."""
        try:
            api_url = config.get("api_url", SIFIRMA_API_BASE_DEFAULT).rstrip("/")
            url = "{}/api/v2/processofirma/{}".format(api_url, uid)

            headers = self._build_auth_headers(config)
            req = urlrequest.Request(url, headers=headers)
            response = urlrequest.urlopen(req, timeout=30)
            result = json.loads(response.read().decode("utf-8"))

            stato = STATO_PROCESSO.get(result.get("statoProcesso", 255), "Sconosciuto")
            nome = result.get("nomeProcesso", "N/A")
            scadenza = result.get("dataScadenza", "N/A")
            creazione = result.get("dataCreazione", "N/A")
            richieste = result.get("richiesteFirma", [])

            msg = (
                "Processo: {}\n"
                "Stato: {}\n"
                "Creato il: {}\n"
                "Scadenza: {}\n"
                "Richieste di firma: {}"
            ).format(nome, stato, creazione, scadenza, len(richieste))

            self.show_message(msg, "SiFirma Sign - Stato Processo")

        except Exception as e:
            self.show_message(
                "Errore nel recupero stato:\n{}".format(self._extract_error(e)),
                "SiFirma Sign - Errore"
            )

    # -----------------------------------------------------------------------
    # CONFIG: CARICA / SALVA / VALIDA
    # -----------------------------------------------------------------------

    def load_config(self):
        """Carica la configurazione dal file JSON nell'home dell'utente."""
        try:
            path = os.path.join(os.path.expanduser("~"), CONFIG_FILENAME)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_config(self, config):
        """Salva la configurazione su disco."""
        try:
            path = os.path.join(os.path.expanduser("~"), CONFIG_FILENAME)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            # Permessi restrittivi (solo utente proprietario)
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        except Exception as e:
            self.show_message(
                "Errore salvataggio configurazione:\n{}".format(str(e)),
                "SiFirma Sign - Errore"
            )

    def _validate_config_required(self, config):
        """Controlla che la configurazione minima necessaria sia presente."""
        errors = []
        if not config:
            errors.append("- Nessuna configurazione trovata")
            return errors
        if not config.get("api_key"):
            errors.append("- API Key mancante")
        if not config.get("api_secret"):
            errors.append("- API Secret mancante")
        if not config.get("partita_iva") and not config.get("codice_fiscale"):
            errors.append("- Partita IVA o Codice Fiscale obbligatorio")
        return errors

    def _validate_config_values(self, config):
        """Valida i valori del form admin prima del salvataggio."""
        errors = []
        if not config.get("api_key"):
            errors.append("- API Key obbligatoria")
        if not config.get("api_secret"):
            errors.append("- API Secret obbligatorio")
        if not config.get("partita_iva") and not config.get("codice_fiscale"):
            errors.append("- Inserire Partita IVA o Codice Fiscale")
        return errors

    def _validate_process_data(self, data):
        """Valida i dati del processo prima di inviare la richiesta API."""
        errors = []

        if not data.get("nome_processo"):
            errors.append("- Nome processo obbligatorio")

        scadenza = data.get("data_scadenza", "").strip()
        if not scadenza:
            errors.append("- Data scadenza obbligatoria")
        else:
            try:
                dt = datetime.datetime.strptime(scadenza, "%Y-%m-%d").date()
                if dt <= datetime.date.today():
                    errors.append("- La data di scadenza deve essere nel futuro")
            except ValueError:
                errors.append("- Formato data non valido (usare YYYY-MM-DD)")

        firmatari = data.get("firmatari", [])
        if not firmatari:
            errors.append("- Almeno un firmatario e' obbligatorio")
        else:
            for i, f in enumerate(firmatari, 1):
                if not f.get("nome") or not f.get("cognome"):
                    errors.append(
                        "- Firmatario {}: Nome e Cognome obbligatori".format(i)
                    )
                if not f.get("codiceFiscale") and not f.get("email"):
                    errors.append(
                        "- Firmatario {}: Codice Fiscale o Email obbligatorio".format(i)
                    )

        return errors

    # -----------------------------------------------------------------------
    # UTILITY
    # -----------------------------------------------------------------------

    def _build_auth_headers(self, config):
        """Costruisce gli header di autenticazione per le chiamate API."""
        headers = {
            "Accept": "application/json",
            "APIKey": config.get("api_key", ""),
            "APISecret": config.get("api_secret", ""),
        }
        piva = config.get("partita_iva", "").strip()
        cf = config.get("codice_fiscale", "").strip()
        if piva:
            headers["PartitaIva"] = piva
        if cf:
            headers["CodiceFiscale"] = cf
        return headers

    def _extract_error(self, exc):
        """Estrae il messaggio di errore da un'eccezione HTTP o generica."""
        if hasattr(exc, "read"):
            try:
                return exc.read().decode("utf-8")
            except Exception:
                pass
        return str(exc)

    def show_message(self, message, title):
        """Mostra una message box all'utente."""
        try:
            toolkit = self.smgr.createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx
            )
            frame = self.desktop.getCurrentFrame()
            parent = frame.getContainerWindow() if frame else None
            if parent:
                box_type = uno.Enum(
                    "com.sun.star.awt.MessageBoxType", "MESSAGEBOX"
                )
                msgbox = toolkit.createMessageBox(parent, box_type, 1, title, message)
                msgbox.execute()
            else:
                print("[SiFirma Sign] {}: {}".format(title, message))
        except Exception:
            print("[SiFirma Sign] {}: {}".format(title, message))

    # -----------------------------------------------------------------------
    # HELPER COSTRUZIONE DIALOG MODEL
    # -----------------------------------------------------------------------

    def _execute_dialog(self, dialog):
        """
        Crea il peer della finestra e mostra il dialog in modo modale.
        Il createPeer e' OBBLIGATORIO per i dialog creati programmaticamente
        in LibreOffice: senza di esso il dialog non viene visualizzato.
        """
        toolkit = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.Toolkit", self.ctx
        )
        dialog.createPeer(toolkit, None)
        return dialog.execute()

    def _new_dialog_model(self, width, height, title):
        dm = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", self.ctx
        )
        dm.PositionX = 80
        dm.PositionY = 60
        dm.Width = width
        dm.Height = height
        dm.Title = title
        return dm

    def _lbl(self, dm, name, label, x, y, w, h):
        m = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        m.Label = label
        dm.insertByName(name, m)

    def _txt(self, dm, name, x, y, w, h, password=False):
        m = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        if password:
            m.EchoChar = ord("*")
        dm.insertByName(name, m)

    def _btn(self, dm, name, label, x, y, w, h, btn_type=0):
        m = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        m.Label = label
        m.PushButtonType = btn_type
        dm.insertByName(name, m)

    def _chk(self, dm, name, label, x, y, w, h):
        m = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        m.Label = label
        dm.insertByName(name, m)

    def _dropdown(self, dm, name, x, y, w, h, items):
        m = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        m.Dropdown = True
        m.StringItemList = tuple(items)
        dm.insertByName(name, m)


# ---------------------------------------------------------------------------
# Registrazione componente LibreOffice
# ---------------------------------------------------------------------------

def createInstance(ctx):
    return SiFirmaSignJob(ctx)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    createInstance,
    "com.sifirma.sign.Job",
    ("com.sun.star.task.Job",),
)
