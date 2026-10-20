# Muros de contención visibles (Ursina) en los taludes de la ladera. Cada Muro (backend/datos/muros.py:
# cx, cz, rumbo, largo, y_base, y_tope) se dibuja con un cubo de hormigón y una tapa algo más clara.
# Es estático: todo cuelga de un grupo de Ciudad3D que se funde con combine(), sin update().
#
# Convención: el largo del muro corre a lo largo de su `rumbo` (rotation_y, "adelante" = (sin ψ, cos ψ)),
# como las escaleras; el grosor va a lo ancho.

from frontend.componentes import rgb
from frontend.piezas import pieza

GROSOR_MURO = 0.35                  # m
GROSOR_TAPA = 0.08                  # m
SOBRESALE_TAPA = 0.1                # m más ancha que el muro
COLOR_MURO = (128, 124, 116)
OSCURECER_ALTERNO = 8               # puntos de color menos en los muros pares, para marcar los tramos
ACLARAR_TAPA = 14                   # puntos de color más en la tapa


# Un cubo por muro (colores alternados) y su tapa, colgados de `grupo`.
def construir_muros(grupo, muros):
    for i, muro in enumerate(muros):
        tono = COLOR_MURO if i % 2 == 0 else tuple(c - OSCURECER_ALTERNO for c in COLOR_MURO)
        alto = muro.y_tope - muro.y_base
        pieza(parent=grupo, model="cube", color=rgb(tono), rotation_y=muro.rumbo,
              position=(muro.cx, (muro.y_base + muro.y_tope) / 2, muro.cz),
              scale=(GROSOR_MURO, alto, muro.largo))
        pieza(parent=grupo, model="cube", color=rgb(tuple(min(255, c + ACLARAR_TAPA) for c in tono)),
              rotation_y=muro.rumbo, position=(muro.cx, muro.y_tope + GROSOR_TAPA / 2, muro.cz),
              scale=(GROSOR_MURO + SOBRESALE_TAPA, GROSOR_TAPA, muro.largo))
