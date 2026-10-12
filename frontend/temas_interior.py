# Temas de la oficina interior (datos puros: NO importa ursina). Hay UNA escena de interior y
# un tema por lugar: color de paredes, piso y acento, 2-3 props distintivos y el letrero. La
# EscenaInterior los traduce a primitivas 3D. Los letreros coinciden con los de los edificios.

from dataclasses import dataclass

PROPS_VALIDOS = frozenset({
    "bandera", "libreria", "cafetera", "pizarra", "camilla", "mapa_rutas", "afiches",
    "planta_grande", "mostrador", "reloj",
})


@dataclass(frozen=True)
class Tema:
    pared: tuple        # RGB 0-255
    piso: tuple
    acento: tuple
    letrero: str
    props: tuple


TEMAS = {
    "Plaza Central": Tema((232, 214, 178), (120, 88, 64), (168, 92, 60),
                          "Café Internet de la Plaza", ("cafetera", "mostrador", "afiches")),
    "Alcaldía": Tema((206, 214, 232), (74, 78, 96), (52, 168, 83),
                     "Alcaldía", ("bandera", "reloj", "planta_grande")),
    "Universidad de Ciudad Nova": Tema((232, 226, 196), (150, 120, 86), (66, 133, 244),
                                       "Universidad de Ciudad Nova", ("pizarra", "libreria", "reloj")),
    "Parque Municipal": Tema((214, 232, 208), (104, 80, 56), (96, 140, 84),
                             "Biblioteca del Parque", ("libreria", "planta_grande", "reloj")),
    "Barrio Las Flores": Tema((244, 206, 214), (140, 110, 100), (234, 67, 53),
                              "Barrio Las Flores", ("afiches", "mostrador", "planta_grande")),
    "Terminal de Buses": Tema((214, 214, 222), (88, 92, 104), (251, 188, 4),
                              "Terminal de Buses", ("mapa_rutas", "reloj", "afiches")),
    "Hospital Las Flores": Tema((238, 244, 246), (170, 190, 196), (214, 62, 62),
                                "Hospital Las Flores", ("camilla", "afiches", "planta_grande")),
}


# ValueError si el lugar no tiene tema.
def tema_de(lugar):
    if lugar not in TEMAS:
        raise ValueError(f"No hay tema de interior para {lugar!r}.")
    return TEMAS[lugar]
