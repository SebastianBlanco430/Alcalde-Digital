# Repertorio de piezas que se fabrican en el taller de Beto (datos puros). Cada turno elige una al azar
# (backend/logica/taller_ritmo.py); el dibujo de cada una vive en frontend/taller_vista.py con el mismo `id`.

from dataclasses import dataclass


@dataclass(frozen=True)
class PiezaTaller:
    id: str
    nombre: str
    vehiculo: str            # «moto» o «bicicleta» (solo texto)


PIEZAS_TALLER = (
    PiezaTaller("rueda_bici", "Rueda de bicicleta", "bicicleta"),
    PiezaTaller("plato", "Plato de cadena", "bicicleta"),
    PiezaTaller("cuadro", "Cuadro de bicicleta", "bicicleta"),
    PiezaTaller("manillar", "Manillar", "bicicleta"),
    PiezaTaller("llanta_moto", "Llanta de moto", "moto"),
    PiezaTaller("escape", "Tubo de escape", "moto"),
    PiezaTaller("tanque", "Tanque de gasolina", "moto"),
    PiezaTaller("guardabarros", "Guardabarros", "moto"),
)


# Taller 3D (frontend/taller3d_escena.py, ALCALDE_TALLER3D): otras 8 piezas, cada una con 2-3 variantes de material. El
# turno elige UNA entrada de esta tupla con su semilla (como PIEZAS_TALLER), así la pieza cambia de un turno a otro y es
# determinista. La malla de cada `id` vive en frontend/taller3d_piezas.py; `tono` es el color del material (RGB 0-255).
@dataclass(frozen=True)
class PiezaTaller3D:
    id: str
    nombre: str
    variante: int
    tono: tuple


_VARIANTES_3D = (
    ("engranaje", "Engranaje", (("de latón", (204, 162, 74)), ("de acero", (170, 176, 188)), ("de cobre", (192, 112, 72)))),
    ("llave", "Llave inglesa", (("cromada", (186, 192, 204)), ("de mango azul", (62, 108, 196)),
                                ("de mango rojo", (200, 66, 56)))),
    ("tuerca", "Tuerca y tornillo", (("de acero", (164, 170, 182)), ("de latón", (200, 160, 76)))),
    ("piston", "Pistón", (("de aluminio", (196, 200, 208)), ("de hierro", (120, 124, 136)))),
    ("bisagra", "Bisagra", (("de latón", (206, 166, 80)), ("negra", (64, 66, 74)), ("de acero", (172, 178, 190)))),
    ("rueda", "Rueda de bicicleta", (("de llanta roja", (204, 62, 52)), ("de llanta azul", (58, 110, 200)),
                                     ("de llanta plateada", (190, 196, 206)))),
    ("lampara", "Lámpara de mesa", (("verde", (52, 138, 92)), ("amarilla", (232, 190, 60)), ("roja", (196, 70, 60)))),
    ("radio", "Radio vieja", (("de madera", (150, 100, 60)), ("turquesa", (64, 168, 170)))),
)

PIEZAS_TALLER_3D = tuple(PiezaTaller3D(pid, f"{nombre} {material}", k, tono)
                         for pid, nombre, variantes in _VARIANTES_3D
                         for k, (material, tono) in enumerate(variantes))
