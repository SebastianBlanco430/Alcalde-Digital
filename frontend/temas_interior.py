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
    "Praça da Sé": Tema((232, 214, 178), (120, 88, 64), (168, 92, 60),
                          "Lan House da Praça", ("cafetera", "mostrador", "afiches")),
    "Prefeitura": Tema((206, 214, 232), (74, 78, 96), (52, 168, 83),
                     "Prefeitura", ("bandera", "reloj", "planta_grande")),
    "Universidade de Ciudad Nova": Tema((232, 226, 196), (150, 120, 86), (66, 133, 244),
                                       "Universidade de Ciudad Nova", ("pizarra", "libreria", "reloj")),
    "Parque do Povo": Tema((214, 232, 208), (104, 80, 56), (96, 140, 84),
                             "Biblioteca do Parque", ("libreria", "planta_grande", "reloj")),
    "Morro da Esperança": Tema((244, 206, 214), (140, 110, 100), (234, 67, 53),
                              "Morro da Esperança", ("afiches", "mostrador", "planta_grande")),
    "Rodoviária": Tema((214, 214, 222), (88, 92, 104), (251, 188, 4),
                              "Rodoviária", ("mapa_rutas", "reloj", "afiches")),
    "Hospital Santa Casa": Tema((238, 244, 246), (170, 190, 196), (214, 62, 62),
                                "Hospital Santa Casa", ("camilla", "afiches", "planta_grande")),
    "Mercado Municipal": Tema((246, 222, 184), (128, 92, 62), (200, 96, 58),
                              "Mercado Municipal", ("mostrador", "planta_grande", "afiches")),
    "Escola de Samba": Tema((252, 232, 150), (110, 70, 120), (220, 60, 160),
                            "G.R.E.S. Unidos da Esperança", ("bandera", "afiches", "mostrador")),
    "Rádio Comunitária": Tema((222, 236, 214), (90, 96, 110), (110, 190, 60),
                              "Rádio Comunitária 98,7 FM", ("cafetera", "afiches", "reloj")),
    "Estação do Teleférico": Tema((218, 226, 236), (96, 104, 120), (120, 130, 160),
                                  "Estação do Teleférico", ("mapa_rutas", "reloj", "planta_grande")),
}


# ValueError si el lugar no tiene tema.
def tema_de(lugar):
    if lugar not in TEMAS:
        raise ValueError(f"No hay tema de interior para {lugar!r}.")
    return TEMAS[lugar]
