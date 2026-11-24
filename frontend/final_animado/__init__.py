# Final animado en la Ciudad Nova real (sesión C, 2026-11-23): en vez de las viñetas 2D de frontend/cinematica_final.py,
# la cámara recorre el mundo 3D de la partida con planos montados (estilo time-lapse), subtítulos y planos propios del rol.
#
#   __init__.py       bandera ALCALDE_FINAL_ANIMADO y este mapa (no importa ursina)
#   _calculos.py      PURO: guion (finales_historia.json «animacion») -> planos, tiempos, subtítulos, saltar, curvas
#   lugares.py        PURO: anclas del mundo (plaza, podio, prefeitura, morro, radio, azotea...) y su marco local
#   camaras.py        PURO: tomas de cámara por id de plano, relativas a las anclas
#   puesta.py         PURO: qué decorado y qué actores lleva cada plano, relativos a las anclas
#   director.py       Ursina: toma la cámara, esconde el HUD, corre los planos con fundidos, subtítulos y «Mantén para saltar»
#   escenografia.py   Ursina: estado forzado de la ciudad (etapa, hora), decorado de plano y actores; limpia todo al terminar
#
# Contrato interno entre las piezas: frontend/final_animado/contrato.md. Lo lanza frontend/registro_reloj.py; si la
# bandera está en 0, o algo falla al cargar o en un frame, salen las viñetas de siempre y después el panel final.
#
# Bandera (la variable de entorno manda sobre la constante):
#   FINAL_ANIMADO / ALCALDE_FINAL_ANIMADO=0     viñetas 2D de siempre (el juego queda como en 0b7e148)

import os

FINAL_ANIMADO = True


def activo():
    valor = os.environ.get("ALCALDE_FINAL_ANIMADO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(FINAL_ANIMADO)
