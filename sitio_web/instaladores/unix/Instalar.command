#!/usr/bin/env bash
# Doble clic en macOS: abre la terminal y ejecuta el instalador.
cd "$(dirname "$0")"
bash ./instalar.sh
echo
read -r -p "Pulsa Intro para cerrar esta ventana. " _
