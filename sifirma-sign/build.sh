#!/bin/bash
# Script per generare il file .oxt installabile su LibreOffice
# Uso: cd sifirma-sign && ./build.sh

EXTENSION_NAME="SiFirmaSign"
OUTPUT_FILE="../${EXTENSION_NAME}.oxt"

echo "Compilazione estensione ${EXTENSION_NAME}..."

# Elimina eventuale versione precedente
if [ -f "$OUTPUT_FILE" ]; then
    rm "$OUTPUT_FILE"
fi

# Crea il file .oxt (e' un archivio ZIP)
zip -r "$OUTPUT_FILE" \
    META-INF/ \
    sifirma_sign.py \
    Addons.xcu \
    description.xml \
    description-it.txt \
    description-en.txt \
    -x ".*" \
    -x "__pycache__/*" \
    -x "*.pyc" \
    -x "build.sh"

if [ $? -eq 0 ]; then
    echo ""
    echo "Estensione creata: ${OUTPUT_FILE}"
    echo ""
    echo "Installazione:"
    echo "  unopkg add ${OUTPUT_FILE}"
    echo ""
    echo "Oppure da LibreOffice:"
    echo "  Strumenti > Gestione estensioni > Aggiungi"
else
    echo "ERRORE durante la creazione dell'archivio."
    exit 1
fi
