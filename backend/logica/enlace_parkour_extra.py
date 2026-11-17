# Puertas EXTRA al parkour desde la terminal de un caso (modelo puro, sin motor gráfico). El caso ya declara una puerta
# en su propio JSON (backend/logica/enlace_parkour.py, campo «parkour»); aquí se leen las de más, de un archivo de datos
# aparte (backend/datos/parkour_enlaces.json), para no tocar el JSON del caso. Cada una puede pedir una evidencia para
# abrirse (el segundo sector se desbloquea al cruzar el primero).
# Un dato roto (nivel inexistente, textos vacíos) no tumba nada: esa puerta simplemente no aparece.

import json
from dataclasses import dataclass
from pathlib import Path

from backend.logica import evidencia

RUTA = Path(__file__).resolve().parent.parent / "datos" / "parkour_enlaces.json"
BLOQUEADO, DISPONIBLE, COMPLETADO = "bloqueado", "disponible", "completado"


@dataclass(frozen=True)
class EnlaceExtra:
    nivel: str
    texto: str
    texto_completado: str = ""
    requiere_evidencia: str | None = None
    bloqueado: str = ""


def _texto(valor):
    return isinstance(valor, str) and bool(valor.strip())


def cargar(ruta=RUTA):
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def de_caso(datos, caso_id, niveles_validos=None):
    """Puertas extra del caso `caso_id` (lista de EnlaceExtra válidos, en orden). `niveles_validos`: ids que existen."""
    salida = []
    for bruto in ((datos or {}).get("casos") or {}).get(caso_id) or ():
        if not isinstance(bruto, dict) or not _texto(bruto.get("nivel")) or not _texto(bruto.get("texto")):
            continue
        if niveles_validos is not None and bruto["nivel"] not in set(niveles_validos):
            continue
        requiere = bruto.get("requiere_evidencia")
        salida.append(EnlaceExtra(bruto["nivel"], bruto["texto"].strip(), (bruto.get("texto_completado") or "").strip(),
                                  requiere if _texto(requiere) else None, (bruto.get("bloqueado") or "").strip()))
    return salida


def estado(enlace, game_state, evidencia_del_nivel):
    """bloqueado / disponible / completado para el jugador con `game_state` (None = sin partida: disponible)."""
    if game_state is None:
        return DISPONIBLE
    if evidencia_del_nivel and evidencia.tiene(game_state, evidencia_del_nivel):
        return COMPLETADO
    if enlace.requiere_evidencia and not evidencia.tiene(game_state, enlace.requiere_evidencia):
        return BLOQUEADO
    return DISPONIBLE


def rotulo(enlace, estado_actual, tecla):
    """Texto del botón según su estado."""
    if estado_actual == BLOQUEADO:
        return f"{enlace.texto}  (bloqueado)"
    if estado_actual == COMPLETADO and enlace.texto_completado:
        return f"{enlace.texto_completado}  [{tecla.upper()}]"
    return f"{enlace.texto}  [{tecla.upper()}]"
