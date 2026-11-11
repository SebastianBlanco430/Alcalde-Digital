# Guardado de la partida local (hot-seat) en disco. Modelo puro: sin ursina; nunca se serializa nada del motor gráfico.
#
# QUÉ SE GUARDA (un solo JSON, ~decenas de KB):
#   sesion      SesionJuego.a_dict(): jugadores (nombre, rol, posición, teléfono, economía), turno e indicadores
#   estado      EstadoPartida.a_dict(): indicadores, noticias ya vistas del mazo y la que está en mesa
#   misiones    SistemaMisiones.a_dict(): la misión activa y su estado, las completadas y sus veredictos
#   game_state  GameState.a_dict() (confianza, relaciones, flags y el ArbolImpactos) o None si la partida no lo tiene
#   mapa        "grande" | "chico" y la semilla del mundo: un guardado de otro mapa o de otra semilla NO se carga
#
# CUÁNDO: solo en un punto seguro, con el jugador en el mundo (`se_puede_guardar`): no durante el minijuego ni con la
# misión recién completada sin terminar. Así al cargar no hay que reconstruir un lote de noticias a medias.
#
# DÓNDE: <directorio de ajustes>/partida.json (backend/logica/ajustes.directorio_ajustes), con escritura atómica
# (temporal + os.replace). La lectura es tolerante: ausente, enorme, corrupto, de otra versión o de otro mapa -> None,
# y el juego ofrece solo «Empezar». Un guardado nunca puede impedir jugar.
#
#   capturar(flujo, mapa, semilla)            -> dict JSON-serializable, o None si no es un punto seguro
#   guardar(datos, ruta=None)                 -> True si se escribió
#   cargar(ruta=None)                         -> dict validado en lo básico, o None
#   borrar(ruta=None) / existe(ruta=None)
#   resumen(datos)                            -> texto corto para el botón «Continuar» («2 jugadores · 5 misiones»)
#   restaurar(datos, estado_partida, fabrica_flujo, escala_mundo, mapa, semilla) -> flujo listo, o ValueError
#
# Bandera: GUARDADO = False (o ALCALDE_SIN_GUARDADO=1) desactiva la escritura y la lectura.

import json
import os
import tempfile
from pathlib import Path

from backend.logica import ajustes
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from backend.logica.sesion import SesionJuego

GUARDADO = True
VERSION = 1
NOMBRE_ARCHIVO = "partida.json"
TAMANO_MAX_ARCHIVO = 4 * 1024 * 1024      # bytes: un archivo mayor no es un guardado nuestro


def activo():
    return GUARDADO and os.environ.get("ALCALDE_SIN_GUARDADO", "").strip().lower() not in ("1", "true", "si", "sí", "on")


def ruta_guardado(directorio=None):
    return (Path(directorio) if directorio is not None else ajustes.directorio_ajustes()) / NOMBRE_ARCHIVO


# -- Capturar ---------------------------------------------------------------------------------------------------------

# ¿Es un punto seguro? Hay jugadores, la partida no terminó y nadie está dentro del minijuego (ni a medio cerrar).
def se_puede_guardar(flujo):
    if flujo is None or not hasattr(flujo, "misiones_a_dict") or flujo.jugador_activo() is None:
        return False
    if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
        return False
    return not flujo.partida_terminada()


def capturar(flujo, mapa, semilla):
    if not se_puede_guardar(flujo):
        return None
    sesion = flujo.sesion
    game_state = getattr(flujo, "game_state", None)
    return {
        "version": VERSION,
        "mapa": mapa,
        "semilla": semilla,
        "sesion": sesion.a_dict(),
        "estado": sesion.estado_partida.a_dict(),
        "misiones": flujo.misiones_a_dict(),
        "game_state": game_state.a_dict() if game_state is not None else None,
    }


# -- Disco ------------------------------------------------------------------------------------------------------------

def guardar(datos, ruta=None):
    if not activo() or datos is None:
        return False
    ruta = Path(ruta) if ruta is not None else ruta_guardado()
    try:
        texto = json.dumps(datos, ensure_ascii=False, allow_nan=False)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.stem, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
                archivo.write(texto)
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)
        return True
    except (OSError, TypeError, ValueError):       # sin permisos, disco lleno, algo no serializable
        return False


def _forma_valida(datos):
    if not isinstance(datos, dict) or datos.get("version") != VERSION:
        return False
    if not all(isinstance(datos.get(clave), dict) for clave in ("sesion", "estado", "misiones")):
        return False
    if datos.get("game_state") is not None and not isinstance(datos["game_state"], dict):
        return False
    jugadores = datos["sesion"].get("jugadores")
    return isinstance(jugadores, list) and len(jugadores) >= 1 and isinstance(datos.get("mapa"), str)


def cargar(ruta=None):
    if not activo():
        return None
    ruta = Path(ruta) if ruta is not None else ruta_guardado()
    try:
        if not ruta.is_file() or ruta.stat().st_size > TAMANO_MAX_ARCHIVO:
            return None
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return None
    return datos if _forma_valida(datos) else None


def existe(ruta=None):
    return cargar(ruta) is not None


def borrar(ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_guardado()
    try:
        ruta.unlink()
        return True
    except OSError:
        return False


# ¿El guardado es de este mundo? (mismo mapa y misma semilla).
def compatible(datos, mapa, semilla):
    return datos is not None and datos.get("mapa") == mapa and datos.get("semilla") == semilla


def resumen(datos):
    try:
        jugadores = len(datos["sesion"]["jugadores"])
        hechas = len(datos["misiones"].get("completadas", ()))
    except (KeyError, TypeError, AttributeError):
        return ""
    return (f"{jugadores} jugador{'es' if jugadores != 1 else ''} · "
            f"{hechas} misi{'ones' if hechas != 1 else 'ón'} hecha{'s' if hechas != 1 else ''}")


# -- Restaurar --------------------------------------------------------------------------------------------------------

# Reconstruye la partida guardada. `estado_partida`: un EstadoPartida NUEVO (con los árboles del seed); `fabrica_flujo`:
# callable(sesion) -> flujo (el mismo que usa una partida nueva: FlujoPartida con sus envoltorios). Devuelve el flujo ya
# restaurado; NO hay que llamar a flujo.iniciar(). ValueError (KeyError/TypeError convertidos) si los datos no cuadran
# con este mundo o este catálogo: quien llama descarta el guardado y empieza una partida nueva.
def restaurar(datos, estado_partida, fabrica_flujo, escala_mundo=1.0, mapa=None, semilla=None):
    if not _forma_valida(datos):
        raise ValueError("Guardado con formato desconocido.")
    if mapa is not None and not compatible(datos, mapa, semilla):
        raise ValueError(f"El guardado es de otro mundo ({datos.get('mapa')!r}, semilla {datos.get('semilla')!r}).")
    try:
        sesion = SesionJuego.desde_dict(datos["sesion"], estado_partida, escala_mundo=escala_mundo)
        estado_partida.restaurar(datos["estado"])
        flujo = fabrica_flujo(sesion)
        flujo.restaurar_misiones(datos["misiones"])
        guardado_gs = datos.get("game_state")
        restaurar_gs = getattr(flujo, "restaurar_game_state", None)
        if guardado_gs is not None and restaurar_gs is not None:
            restaurar_gs(guardado_gs)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"Guardado incompleto o dañado: {type(error).__name__}: {error}") from error
    if flujo.jugador_activo() is None:
        raise ValueError("Guardado sin jugadores.")
    return flujo
