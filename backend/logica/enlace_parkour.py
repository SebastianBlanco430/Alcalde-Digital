# Enlace «caso -> parkour» (modelo puro, sin motor gráfico). Un caso puede declarar en su JSON, fuera de sus nodos,
# una puerta al parkour que se juega «dentro del mundo virtual»:
#   "parkour": {"nivel": "sector_1", "texto": "Entrar al Sector corrupto", "pista": "...", "texto_completado": "...", "no_disponible": "..."}
# Esto valida esa declaración sin tocar backend/logica/casos.py (el validador de casos ignora las claves de más).
# Un enlace roto (nivel inexistente, textos vacíos) no tumba nada: devuelve None y la escena no muestra el botón.

from dataclasses import dataclass

from backend.logica import evidencia

CLAVE = "parkour"


@dataclass(frozen=True)
class EnlaceParkour:
    nivel: str
    texto: str
    pista: str = ""
    texto_completado: str = ""
    no_disponible: str = ""          # aviso si el parkour no puede abrirse en ese momento


def _texto(valor):
    return isinstance(valor, str) and valor.strip() != ""


# Enlace declarado por el caso (dict del JSON, `Caso.datos`), o None si no lo hay o es inválido. `niveles_validos`:
# ids de nivel que existen (registro_parkour.niveles()); None = no comprobar.
def de_caso(datos_caso, niveles_validos=None):
    bruto = datos_caso.get(CLAVE) if isinstance(datos_caso, dict) else None
    if not isinstance(bruto, dict) or not _texto(bruto.get("nivel")) or not _texto(bruto.get("texto")):
        return None
    if niveles_validos is not None and bruto["nivel"] not in set(niveles_validos):
        return None
    return EnlaceParkour(bruto["nivel"], bruto["texto"], bruto.get("pista") or "", bruto.get("texto_completado") or "",
                         bruto.get("no_disponible") or "")


# True si el jugador ya tiene la evidencia que da ese nivel (el botón pasa a «completado» pero sigue disponible).
def completado(game_state, id_evidencia):
    return bool(id_evidencia) and game_state is not None and evidencia.tiene(game_state, id_evidencia)
