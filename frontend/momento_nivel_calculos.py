# Cálculos puros (sin ursina) del «momento de cambio de nivel» (M1 del plan ambiente y pulseras, ALCALDE_MOMENTO_NIVEL).
# Cuando el Ambiente cruza de nivel (backend/logica/momento_nivel.py, leído en frontend/ambiente_vivo.py):
#   M1.2 titular corto de 2,5 s arriba al centro, BAJO la franja «Confianza de Ciudad Nova» (fundidos M3.6);
#   M1.3 la atmósfera acelera hacia el nuevo nivel (lo hace ambiente_vivo con AmbienteSuave.acelerar);
#   M1.4 stinger de audio sintetizado (sintesis_calculos.nivel_sube / nivel_baja), por debajo de la música.
# La vista está en frontend/registro_momento_nivel.py.

from backend.logica import manillas
from frontend import hud_contextual_calculos as hcc
from frontend import hud_esquinas_calculos as hec

DURACION_TITULAR = 2.5          # s a la vista (contando entrada y salida)
ANCHO_TITULAR = 0.58            # unidades de camera.ui
ALTO_TITULAR = 0.062
PX_TITULAR = 19                 # px de la letra a 600 px de referencia
VOLUMEN_STINGER = 0.55          # el pico del sonido ya es bajo (PICO_STINGER); esto lo deja bajo la música
STINGER = {"sube": "nivel_sube", "baja": "nivel_baja"}


def color_nivel(nivel):
    """RGB del nivel: la paleta de las pulseras (amarillo florece, azul sano, bermellón tenso, violeta apagado)."""
    return manillas.ESTILO_NIVEL[nivel][0]


def rect_titular(ancho_px, alto_px, con_desinfo=True):
    """Rect del titular: centrado, dos PASOS bajo la franja de arriba al centro (no la tapa nunca)."""
    franja = hec.layout_esquinas(ancho_px, alto_px, con_desinfo)["franja"]
    y1 = franja.y0 - 2 * hec.PASO
    return hec.Rect(-ANCHO_TITULAR / 2, y1 - ALTO_TITULAR, ANCHO_TITULAR / 2, y1)


def alfa_titular(t, duracion=DURACION_TITULAR):
    """Alfa del titular a los `t` s de aparecer: entra con ease-out (M3.6), se queda y sale en la regla de la UI."""
    if t < 0 or t >= duracion:
        return 0.0
    entrada, salida = hcc.tiempo("ENTRADA"), hcc.tiempo("SALIDA")
    if t < entrada:
        return hcc.ease_out(t / entrada)
    if t > duracion - salida:
        return 1.0 - hcc.ease_out((t - (duracion - salida)) / salida)
    return 1.0


def stinger_de(direccion):
    return STINGER.get(direccion)
