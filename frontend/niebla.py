# Neblina de la ciudad exterior (Ursina 8.3.0). scene.fog_color / scene.fog_density solo se aplican
# a las entidades que YA existen, así que se llama después de construir la ciudad. El shader
# lit_with_shadows ignora fog_start (t = distancia / (fin - inicio)): por eso el inicio es 0 y la
# fuerza se regula con el ALFA del color (mezcla = t * alfa). Con fin = 260 y alfa = 0.55 a 30 m la
# niebla pesa ~6 %: casi nada; a 260 m o más llega al 55 %.
# Por eso hay que volver a llamarla tras crear entidades nuevas (EscenaMundo lo hace después de
# reconstruir los personajes). Limitación conocida: las entidades con shader=None (ventanas, luces,
# cables, borde de bandera) no reciben niebla y se ven nítidas a cualquier distancia.

from ursina import color as paleta
from ursina import scene

COLOR_NIEBLA = (196, 218, 222)   # RGB 0-255: el horizonte del Sky medido en una captura
FIN_NIEBLA = 260.0               # m a los que la niebla llega a su máximo
INTENSIDAD_NIEBLA = 0.55         # 0-1: fracción de niebla en el máximo (alfa del color)


# Enciende la niebla lineal de 0 a `fin` m con `color` (RGB 0-255) y fuerza `intensidad` (0-1).
def activar_niebla(color=COLOR_NIEBLA, fin=FIN_NIEBLA, intensidad=INTENSIDAD_NIEBLA):
    r, g, b = color
    scene.fog_color = paleta.rgba(r / 255, g / 255, b / 255, intensidad)
    scene.fog_density = (0, fin)


# Apaga la niebla: densidad 0 y color transparente (alfa 0 = los shaders no mezclan nada, así que
# interior y menús quedan sin niebla aunque conserven el rango anterior).
def desactivar_niebla():
    scene.fog_density = 0
    scene.fog_color = paleta.clear
