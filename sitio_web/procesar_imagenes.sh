#!/usr/bin/env bash
# Convierte las capturas de img/raw (PNG) a JPG optimizado en img/ con los nombres que usa index.html.
set -euo pipefail
cd "$(dirname "$0")/img"
convertir() {  # origen salida ancho
  [ -f "raw/$1.png" ] || { echo "falta raw/$1.png"; return 0; }
  sips -s format jpeg -s formatOptions 80 -Z "$3" "raw/$1.png" --out "$2.jpg" >/dev/null
}
convertir w_periodista_01_0_limpio hero 2000
convertir w_periodista_01_1_limpio mundo-fuente 1600
convertir w_periodista_03_1_limpio mundo-hospital 1600
convertir w_periodista_04_1_limpio mundo-morro 1600
convertir w_periodista_05_0_limpio mundo-parque 1600
convertir w_periodista_06_0_limpio mundo-rodoviaria 1600
convertir w_periodista_07_0_limpio mundo-padaria 1600
convertir hud_telefono_02 interfaz 1600
convertir mapa_ciudad_01 mapa 1600
convertir menu_01 menu 1600
convertir roles_01 roles 1600
convertir viva2_crisis_01 viva-crisis-fuente 1600
convertir viva2_florece_01 viva-florece-fuente 1600
convertir viva2_crisis_04 viva-crisis-plaza 1600
convertir viva2_florece_04 viva-florece-plaza 1600
for tipo in rastrear comparar cronologia chat senales contrarreloj; do
  convertir "mj_${tipo}_juego" "mj-${tipo}" 1400
done
convertir parkour_05 parkour 1400
convertir parkour_02 parkour-2 1400
convertir interrogatorio_01 interrogatorio 1400
convertir trabajo_taller_02 trabajo-taller 1400
convertir trabajo_super_03 trabajo-super 1400
convertir trabajo_barra_02 trabajo-barra 1400
convertir trabajo_secuencia_02 trabajo-secuencia 1400
convertir dilema_01 dilema 1400
convertir dilema_03 dilema-opciones 1400
convertir civitas_estafa_01 civitas-estafa 1400
convertir civitas_estafa_03 civitas-estafa-revision 1400
convertir civitas_foto_01 civitas-foto 1400
ls -lh *.jpg | awk '{print $5, $9}'
