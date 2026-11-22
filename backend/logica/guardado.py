# Guardado de la partida local (hot-seat) en disco. Modelo puro: sin ursina; nunca se serializa nada del motor gráfico.
#
# QUÉ SE GUARDA (un solo JSON, ~decenas de KB):
#   sesion      SesionJuego.a_dict(): jugadores (nombre, rol, posición, teléfono, economía), turno e indicadores
#   estado      EstadoPartida.a_dict(): indicadores, noticias ya vistas del mazo y la que está en mesa
#   misiones    SistemaMisiones.a_dict(): la misión activa y su estado, las completadas y sus veredictos
#   game_state  GameState.a_dict() (confianza, relaciones, flags y el ArbolImpactos) o None si la partida no lo tiene
#   mapa        "chico" y la semilla del mundo: un guardado de otro mapa o de otra semilla NO se carga
#   reloj, efectos_retardados, aislamiento, ambiente   OPCIONALES (plan final): las pone FlujoConTiempo.tiempo_a_dict()
#               si el flujo tiene reloj. Un guardado sin ellas (anterior al reloj) carga igual, en el día 1 a las 08:00;
#               VERSION sigue en 1 porque el formato solo creció con claves que el código viejo ignora.
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
import math
import os
import tempfile
import threading
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
    datos = {
        "version": VERSION,
        "mapa": mapa,
        "semilla": semilla,
        "sesion": sesion.a_dict(),
        "estado": sesion.estado_partida.a_dict(),
        "misiones": flujo.misiones_a_dict(),
        "game_state": game_state.a_dict() if game_state is not None else None,
    }
    # Claves OPCIONALES del tiempo (reloj, efectos_retardados, aislamiento, ambiente): solo si el flujo las tiene.
    tiempo = getattr(flujo, "tiempo_a_dict", None)
    if callable(tiempo):
        datos.update(tiempo())
    # Clave OPCIONAL de la recta final (backend/logica/recta_final.py): solo si el flujo la tiene.
    recta = getattr(flujo, "recta_final_a_dict", None)
    if callable(recta):
        datos["recta_final"] = recta()
    return datos


# -- Disco ------------------------------------------------------------------------------------------------------------

_cerrojo = threading.Lock()


def guardar(datos, ruta=None, segundo_plano=False):
    """Escribe el guardado (atómico, con fsync). `segundo_plano`: la escritura va en un hilo (el autoguardado del juego:
    sin tirones en el frame); devuelve True si se lanzó."""
    if not activo() or datos is None:
        return False
    ruta = Path(ruta) if ruta is not None else ruta_guardado()
    try:
        texto = json.dumps(datos, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return False
    if segundo_plano:
        threading.Thread(target=_escribir, args=(texto, ruta), name="alcalde-guardado", daemon=True).start()
        return True
    return _escribir(texto, ruta)


def _escribir(texto, ruta):
    with _cerrojo:
        return _escribir_ya(texto, ruta)


def _escribir_ya(texto, ruta):
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.stem, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
                archivo.write(texto)
                archivo.flush()
                os.fsync(archivo.fileno())          # EST-007: los datos en disco ANTES del rename (como los ajustes)
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
        if not ruta.is_file():
            return None
        if ruta.stat().st_size > TAMANO_MAX_ARCHIVO:
            apartar(ruta, "demasiado grande")
            return None
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except OSError:
        return None
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        apartar(ruta, type(error).__name__)                 # BUG-006: se aparta como partida.json.dañado
        return None
    if not _forma_valida(datos):
        apartar(ruta, "formato desconocido u otra versión")
        return None
    return datos


# Aparta el guardado que no se puede usar (partida.json -> partida.json.dañado; nunca se borra) y avisa por stderr.
def apartar(ruta=None, motivo="dañado"):
    return ajustes.apartar_danado(Path(ruta) if ruta is not None else ruta_guardado(), motivo)


def existe(ruta=None):
    return cargar(ruta) is not None


def borrar(ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_guardado()
    with _cerrojo:                     # espera a un autoguardado en vuelo: no puede reaparecer después de borrar
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
    _validar_numeros(datos)
    try:
        sesion = SesionJuego.desde_dict(datos["sesion"], estado_partida, escala_mundo=escala_mundo)
        estado_partida.restaurar(datos["estado"])
        flujo = fabrica_flujo(sesion)
        flujo.restaurar_misiones(datos["misiones"])
        guardado_gs = datos.get("game_state")
        restaurar_gs = getattr(flujo, "restaurar_game_state", None)
        if guardado_gs is not None and restaurar_gs is not None:
            restaurar_gs(guardado_gs)
        # Tiempo (claves opcionales): un guardado anterior al reloj no las trae y la partida sigue desde el día 1.
        restaurar_tiempo = getattr(flujo, "restaurar_tiempo", None)
        if callable(restaurar_tiempo):
            restaurar_tiempo(datos)
        restaurar_recta = getattr(flujo, "restaurar_recta_final", None)
        if callable(restaurar_recta) and datos.get("recta_final") is not None:
            restaurar_recta(datos["recta_final"])
        sin_jugadores = flujo.jugador_activo() is None
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError(f"Guardado incompleto o dañado: {type(error).__name__}: {error}") from error
    if sin_jugadores:
        raise ValueError("Guardado sin jugadores.")
    return flujo


def _numero_finito(valor):
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return False
    try:
        return math.isfinite(valor)
    except OverflowError:
        return False


# BUG-006: valores que se restauraban «bien» y tumbaban el juego después (al avanzar el tiempo o completar una misión):
# turno no entero, indicadores booleanos o no finitos. ValueError si aparece alguno.
def _validar_numeros(datos):
    sesion = datos["sesion"]
    for clave in ("indice_turno", "numero_turno"):
        valor = sesion.get(clave)
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
            raise ValueError(f"Guardado dañado: {clave}={valor!r}.")
    for origen in (sesion.get("indicadores"), datos["estado"].get("indicadores")):
        if origen is None:
            continue
        if not isinstance(origen, dict):
            raise ValueError("Guardado dañado: indicadores.")
        for nombre, valor in origen.items():
            if not _numero_finito(valor):
                raise ValueError(f"Guardado dañado: indicador {nombre}={valor!r}.")
