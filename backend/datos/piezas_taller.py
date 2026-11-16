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
