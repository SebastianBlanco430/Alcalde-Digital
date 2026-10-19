# Catálogo de los modelos 3D de edificios (datos puros: NO importa ursina). Lo usan los datos
# del mundo (backend/datos/ciudad_3d.py, para dimensionar la caja de colisión de cada edificio)
# y la ciudad 3D (frontend/ciudad_3d.py, para cargar y escalar el modelo).
#
# Los valores los imprime buildings/exportar_edificios.py al exportar cada .blend: si se vuelve
# a exportar una casa, hay que pegar aquí la línea nueva.
#
# Medidas en unidades del modelo exportado: origen en el centro de la huella de planta baja y a
# la altura del umbral de la puerta; el frente (la fachada con la puerta) mira a +z de Ursina.
#   frente: ancho de la huella (eje x del modelo); fondo: profundidad (eje z); alto: hasta el techo.
#   puerta_x: centro de la puerta respecto del centro de la fachada, sobre el eje x del modelo.

from dataclasses import dataclass

CARPETA_MODELOS = "modelos/edificios"      # dentro de assets/


@dataclass(frozen=True)
class ModeloEdificio:
    archivo: str            # nombre del .glb en assets/modelos/edificios (sin extensión)
    frente: float
    fondo: float
    alto: float
    puerta_x: float
    puerta_ancho: float
    puerta_alto: float
    textura_puerta: str     # imagen de la hoja de la puerta, junto al .glb


MODELOS = {
    "casa1": ModeloEdificio("casa1", frente=2.366, fondo=2.594, alto=3.108, puerta_x=-0.082, puerta_ancho=0.604, puerta_alto=1.043, textura_puerta="casa1_puerta.jpg"),
    "casa2": ModeloEdificio("casa2", frente=2.721, fondo=3.707, alto=3.369, puerta_x=-0.860, puerta_ancho=0.591, puerta_alto=0.943, textura_puerta="casa2_puerta.jpg"),
    "casa3": ModeloEdificio("casa3", frente=2.774, fondo=4.394, alto=2.531, puerta_x=-0.822, puerta_ancho=0.450, puerta_alto=0.922, textura_puerta="casa3_puerta.jpg"),
    "casa4": ModeloEdificio("casa4", frente=2.352, fondo=1.749, alto=3.593, puerta_x=-0.738, puerta_ancho=0.576, puerta_alto=1.029, textura_puerta="casa4_puerta.jpg"),
}


# ValueError si el modelo no está en el catálogo.
def modelo_de(nombre):
    if nombre not in MODELOS:
        raise ValueError(f"Modelo de edificio desconocido: {nombre!r}.")
    return MODELOS[nombre]


# Escala uniforme con la que se dibuja el modelo de un Edificio (su alto ya es el del modelo escalado).
def escala_de(edificio):
    return edificio.alto / modelo_de(edificio.modelo).alto
