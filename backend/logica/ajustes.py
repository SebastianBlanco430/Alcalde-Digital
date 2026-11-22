# Almacén de AJUSTES del jugador (Python puro, sin ursina/panda3d): accesibilidad (daltonismo), gráficos
# (pixelado), minimapa, audio y
# espacio para claves de red. Un dataclass con validación/saneado, (de)serialización a dict y JSON, y un
# gestor con suscriptores para que cualquier módulo (filtro de pantalla, motor de audio, online) reaccione
# a los cambios sin conocer la pantalla de Ajustes.
#
# Persistencia: JSON en el directorio de usuario (~/.alcalde_digital/ajustes.json; la variable de entorno
# ALCALDE_AJUSTES_DIR lo cambia, útil en pruebas). Escritura atómica (archivo temporal + os.replace) y
# lectura tolerante: archivo ausente, ilegible, demasiado grande o corrupto -> valores por defecto.
# Todo valor leído se sanea (el archivo es un dato externo): tipos estrictos, rangos, longitudes y
# caracteres permitidos. Las claves desconocidas se conservan en `extras` (solo escalares JSON acotados)
# para que otros módulos añadan las suyas sin editar este archivo.
#
# Bandera reversible: AJUSTES = False hace que `obtener()` devuelva un gestor SIN lectura ni escritura de disco.

import json
import math
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field, fields
from pathlib import Path

AJUSTES = True                      # bandera reversible: False = sin disco, siempre valores por defecto

MODOS_DALTONISMO = ("ninguno", "protanopia", "deuteranopia", "tritanopia", "acromatopsia", "alto_contraste")
NOMBRES_MODO = {
    "ninguno": "Sin filtro",
    "protanopia": "Protanopía (rojo)",
    "deuteranopia": "Deuteranopía (verde)",
    "tritanopia": "Tritanopía (azul)",
    "acromatopsia": "Acromatopsia (grises)",
    "alto_contraste": "Alto contraste",
}
MODO_POR_DEFECTO = "ninguno"

# Gráficos (la matemática del pixelado vive en frontend/pixelado_calculos.py; aquí solo se sanea el dato).
PRESETS_GRAFICOS = ("retro", "nitido", "normal", "personalizado")
PRESET_GRAFICO_POR_DEFECTO = "nitido"
# Minimapa: zoom (campo conservado por compatibilidad con ajustes.json antiguos; ya no tiene fila en Ajustes), modo de giro y
# nivel de detalle (densidad).
MINIMAPA_ZOOMS = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)      # escalones del zoom (el valor guardado siempre cae en uno)
MODOS_ROTACION_MINIMAPA = ("camara", "norte")
MINIMAPA_DENSIDAD_MIN, MINIMAPA_DENSIDAD_MAX = 1, 3
# Suavizado de bordes (MSAA de la ventana, frontend/suavizado.py): muestras por píxel. 0 = sin suavizado. Solo se aplica
# al abrir la ventana (el búfer no cambia de tamaño sin reabrirla), o sea, al reiniciar el juego.
SUAVIZADOS = (0, 2, 4)


def suavizado_por_defecto(plataforma):
    """4× en todas partes salvo macOS («darwin»): allí 0 hasta que se pruebe que Cocoa abre la ventana con MSAA
    (si no consigue formato multimuestra la ventana podría no abrir). ALCALDE_MSAA=4 lo fuerza igual."""
    return 0 if str(plataforma).startswith("darwin") else 4


SUAVIZADO_POR_DEFECTO = suavizado_por_defecto(__import__("sys").platform)

# HUD del mundo (M3.5): «completo» (todo a la vista) o «minimo» (solo la misión y el reloj; el resto aparece cuando hace
# falta). Lo aplica frontend/hud.py si ALCALDE_HUD_MINIMO_AJUSTE no lo apaga.
HUD_MODOS = ("completo", "minimo")
HUD_MODO_POR_DEFECTO = "completo"
# Pulseras en el HUD (M5.3): «siempre» (las mini-pulseras junto al reloj, siempre a la vista) o «al_cambiar» (solo 30 s
# tras un cambio de nivel). Lo aplica frontend/pulseras_visibles_vista.py si ALCALDE_PULSERAS_VISIBLES no lo apaga.
PULSERAS_HUD_MODOS = ("siempre", "al_cambiar")
PULSERAS_HUD_POR_DEFECTO = "siempre"
# Tinta (T3, pase final): «contornos» = solo los contornos de casco de los modelos; «comic» = además la tinta de pantalla
# (líneas sacadas de la profundidad). Lo aplica frontend/pase_final.py si ALCALDE_TINTA_PANTALLA no la apaga.
TINTA_MODOS = ("contornos", "comic")
TINTA_POR_DEFECTO = "comic"

LARGO_MAX_NOMBRE = 24               # nombre en línea
LARGO_MAX_HOST = 64                 # último anfitrión (IP/nombre:puerto)
LARGO_MAX_DISPOSITIVO = 120         # nombre del dispositivo de audio
MAX_EXTRAS = 32
LARGO_MAX_CLAVE_EXTRA = 48
LARGO_MAX_TEXTO_EXTRA = 200
TAMANO_MAX_ARCHIVO = 64 * 1024      # bytes: un archivo mayor se ignora (no es nuestro)
NOMBRE_ARCHIVO = "ajustes.json"
VERSION = 1

_CARACTERES_HOST = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_[]")


# Número finito en [minimo, maximo]; lo que no sea número (bool incluido) o no sea finito -> `defecto`.
def _acotar(valor, minimo, maximo, defecto):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return defecto
    try:
        if not math.isfinite(valor):
            return defecto
    except OverflowError:              # EST-001: un entero enorme (p. ej. 401 cifras) no cabe en un float
        return defecto
    return float(min(maximo, max(minimo, valor)))


# Solo True/False reales cuentan (un "false" en texto no es un booleano).
def _booleano(valor, defecto):
    return valor if isinstance(valor, bool) else defecto


# Texto sin caracteres de control, recortado y con espacios en los extremos fuera.
def _texto_limpio(valor, largo_max):
    if not isinstance(valor, str):
        return ""
    limpio = "".join(c for c in valor if c.isprintable())
    return limpio.strip()[:largo_max]


@dataclass
class Ajustes:
    # --- Accesibilidad ---
    modo_daltonismo: str = MODO_POR_DEFECTO
    intensidad: float = 1.0                 # 0 = sin efecto, 1 = completo
    simular_daltonismo: bool = False        # True = muestra cómo lo ve alguien con ese tipo (para diseñar), no corrige
    # --- Gráficos ---
    preset_grafico: str = PRESET_GRAFICO_POR_DEFECTO   # retro | nitido | normal | personalizado
    pixel_scale: float = 0.0                # 0 = resolución nativa (sin pase gráfico), 1 = pixelado máximo
    pantalla_completa: bool = False         # ventana sin borde del tamaño del monitor (F11 la alterna también)
    suavizado: int = SUAVIZADO_POR_DEFECTO  # MSAA: uno de SUAVIZADOS (0 = no); se aplica al reiniciar
    # --- Interfaz ---
    hud_modo: str = HUD_MODO_POR_DEFECTO     # uno de HUD_MODOS
    pulseras_hud: str = PULSERAS_HUD_POR_DEFECTO   # uno de PULSERAS_HUD_MODOS
    tinta_pantalla: str = TINTA_POR_DEFECTO         # uno de TINTA_MODOS
    # --- Minimapa ---
    minimapa_zoom: float = 1.0              # uno de MINIMAPA_ZOOMS (1 = lo de siempre)
    minimapa_rotacion: str = "camara"       # camara = gira con la cámara (arriba = adelante) | norte = norte arriba
    minimapa_densidad: int = 2              # nivel de detalle: 1 calles y lugares | 2 + casas y escaleras | 3 + rótulos
    # --- Audio ---
    volumen_maestro: float = 0.8
    volumen_musica: float = 0.6
    volumen_efectos: float = 0.8
    silenciado: bool = False
    dispositivo_audio: object = None        # str | None (None = el del sistema)
    # --- Red (reservado para el modo online) ---
    nombre_en_linea: str = ""
    ultimo_host: str = ""
    # --- Claves futuras que este archivo no conoce (escalares JSON acotados) ---
    extras: dict = field(default_factory=dict)

    def __post_init__(self):
        self.sanear()

    # Deja cada campo en un valor válido (sin lanzar nunca): los inválidos vuelven a su valor por defecto.
    def sanear(self):
        if not isinstance(self.modo_daltonismo, str) or self.modo_daltonismo not in MODOS_DALTONISMO:
            self.modo_daltonismo = MODO_POR_DEFECTO
        self.intensidad = _acotar(self.intensidad, 0.0, 1.0, 1.0)
        self.simular_daltonismo = _booleano(self.simular_daltonismo, False)
        if not isinstance(self.preset_grafico, str) or self.preset_grafico not in PRESETS_GRAFICOS:
            self.preset_grafico = PRESET_GRAFICO_POR_DEFECTO
        self.pixel_scale = _acotar(self.pixel_scale, 0.0, 1.0, 0.0)
        self.pantalla_completa = _booleano(self.pantalla_completa, False)
        muestras = _acotar(self.suavizado, SUAVIZADOS[0], SUAVIZADOS[-1], SUAVIZADO_POR_DEFECTO)
        self.suavizado = min(SUAVIZADOS, key=lambda m: abs(m - muestras))
        if not isinstance(self.hud_modo, str) or self.hud_modo not in HUD_MODOS:
            self.hud_modo = HUD_MODO_POR_DEFECTO
        if not isinstance(self.pulseras_hud, str) or self.pulseras_hud not in PULSERAS_HUD_MODOS:
            self.pulseras_hud = PULSERAS_HUD_POR_DEFECTO
        if not isinstance(self.tinta_pantalla, str) or self.tinta_pantalla not in TINTA_MODOS:
            self.tinta_pantalla = TINTA_POR_DEFECTO
        zoom = _acotar(self.minimapa_zoom, MINIMAPA_ZOOMS[0], MINIMAPA_ZOOMS[-1], 1.0)
        self.minimapa_zoom = min(MINIMAPA_ZOOMS, key=lambda z: abs(z - zoom))
        if not isinstance(self.minimapa_rotacion, str) or self.minimapa_rotacion not in MODOS_ROTACION_MINIMAPA:
            self.minimapa_rotacion = "camara"
        self.minimapa_densidad = int(round(_acotar(self.minimapa_densidad, MINIMAPA_DENSIDAD_MIN,
                                                   MINIMAPA_DENSIDAD_MAX, 2)))
        self.volumen_maestro = _acotar(self.volumen_maestro, 0.0, 1.0, 0.8)
        self.volumen_musica = _acotar(self.volumen_musica, 0.0, 1.0, 0.6)
        self.volumen_efectos = _acotar(self.volumen_efectos, 0.0, 1.0, 0.8)
        self.silenciado = _booleano(self.silenciado, False)
        dispositivo = _texto_limpio(self.dispositivo_audio, LARGO_MAX_DISPOSITIVO) if isinstance(
            self.dispositivo_audio, str) else ""
        self.dispositivo_audio = dispositivo or None
        self.nombre_en_linea = _texto_limpio(self.nombre_en_linea, LARGO_MAX_NOMBRE)
        host = _texto_limpio(self.ultimo_host, LARGO_MAX_HOST) if isinstance(self.ultimo_host, str) else ""
        self.ultimo_host = host if all(c in _CARACTERES_HOST for c in host) else ""
        self.extras = _sanear_extras(self.extras)
        return self

    # Diccionario JSON-seguro (los extras se aplanan al primer nivel, con la versión del formato).
    def a_dict(self):
        datos = {"version": VERSION}
        for campo in fields(self):
            if campo.name != "extras":
                datos[campo.name] = getattr(self, campo.name)
        for clave, valor in self.extras.items():
            datos.setdefault(clave, valor)
        return datos

    # Copia independiente.
    def copia(self):
        return Ajustes.desde_dict(self.a_dict())

    # Construye desde un dict cualquiera (p. ej. JSON leído): lo desconocido pasa a `extras`, lo inválido se sanea.
    @classmethod
    def desde_dict(cls, datos):
        if not isinstance(datos, dict):
            return cls()
        conocidos = {c.name for c in fields(cls) if c.name != "extras"}
        valores = {k: v for k, v in datos.items() if k in conocidos}
        resto = {k: v for k, v in datos.items() if k not in conocidos and k != "version" and k != "extras"}
        previos = datos.get("extras")
        extras = dict(previos) if isinstance(previos, dict) else {}
        extras.update(resto)
        return cls(extras=extras, **valores)

    # Nombres de los campos conocidos (sin `extras`).
    @classmethod
    def claves(cls):
        return tuple(c.name for c in fields(cls) if c.name != "extras")


# Solo claves str cortas con valores escalares JSON (bool/int/float finito/str corto): máximo MAX_EXTRAS.
def _sanear_extras(extras):
    limpio = {}
    if not isinstance(extras, dict):
        return limpio
    for clave, valor in extras.items():
        if len(limpio) >= MAX_EXTRAS:
            break
        if not isinstance(clave, str) or not clave or len(clave) > LARGO_MAX_CLAVE_EXTRA:
            continue
        if not clave.isidentifier():
            continue
        if isinstance(valor, bool) or valor is None:
            limpio[clave] = valor
        elif isinstance(valor, int):
            limpio[clave] = valor if abs(valor) < 2 ** 53 else 0
        elif isinstance(valor, float):
            if math.isfinite(valor):
                limpio[clave] = valor
        elif isinstance(valor, str):
            limpio[clave] = _texto_limpio(valor, LARGO_MAX_TEXTO_EXTRA)
    return limpio


# Directorio de ajustes del usuario: $ALCALDE_AJUSTES_DIR o ~/.alcalde_digital.
def directorio_ajustes():
    elegido = os.environ.get("ALCALDE_AJUSTES_DIR")
    return Path(elegido) if elegido else Path.home() / ".alcalde_digital"


def ruta_ajustes(directorio=None):
    return (Path(directorio) if directorio is not None else directorio_ajustes()) / NOMBRE_ARCHIVO


SUFIJO_DANADO = ".dañado"


# Aparta un archivo propio que no se puede usar (corrupto, enorme, de otra versión): lo RENOMBRA a «<nombre>.dañado»
# (sustituye a uno anterior con ese nombre; nunca se borra) y avisa por stderr. Devuelve la ruta nueva o None.
def apartar_danado(ruta, motivo):
    ruta = Path(ruta)
    destino = ruta.with_name(ruta.name + SUFIJO_DANADO)
    try:
        os.replace(ruta, destino)
    except OSError as error:
        print(f"[archivos] {ruta.name} no se puede usar ({motivo}) ni apartar ({error}); se ignora", file=sys.stderr)
        return None
    print(f"[archivos] {ruta.name} no se puede usar ({motivo}): se apartó como {destino.name} y se sigue con los "
          f"valores por defecto", file=sys.stderr)
    return destino


# EST-006: borra los temporales («*.tmp») que dejó una escritura atómica interrumpida (cierre a mitad de un guardado).
# Solo los de más de `edad_min_s` segundos: otra instancia del juego (en línea en el mismo equipo) puede estar
# escribiendo ahora mismo. Con `recursivo` recorre las subcarpetas (la caché de animación tiene una por huella).
# Devuelve cuántos borró.
def limpiar_temporales(carpetas, edad_min_s=120.0, recursivo=False):
    borrados, ahora = 0, time.time()
    for carpeta in carpetas:
        try:
            carpeta = Path(carpeta)
            candidatos = list(carpeta.rglob("*.tmp") if recursivo else carpeta.glob("*.tmp"))
        except OSError:
            continue
        for tmp in candidatos:
            try:
                if tmp.is_file() and ahora - tmp.stat().st_mtime > edad_min_s:
                    tmp.unlink()
                    borrados += 1
            except OSError:
                pass
    return borrados


# Lee los ajustes; cualquier problema (falta, permisos, tamaño, JSON roto, tipo raro) -> valores por defecto. Un archivo
# corrupto (JSON roto, raíz que no es un objeto, demasiado grande) se aparta como «ajustes.json.dañado» (EST-001).
def cargar(ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_ajustes()
    try:
        if not ruta.is_file():
            return Ajustes()
        if ruta.stat().st_size > TAMANO_MAX_ARCHIVO:
            apartar_danado(ruta, "demasiado grande")
            return Ajustes()
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except OSError:
        return Ajustes()
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        apartar_danado(ruta, type(error).__name__)
        return Ajustes()
    if not isinstance(datos, dict):
        apartar_danado(ruta, "no es un objeto JSON")
        return Ajustes()
    try:
        return Ajustes.desde_dict(datos)
    except Exception as error:         # noqa: BLE001 — un valor imposible nunca impide arrancar
        apartar_danado(ruta, f"{type(error).__name__}: {error}")
        return Ajustes()


# Guarda de forma atómica (temporal en el mismo directorio + os.replace). Devuelve True si se guardó.
# Nunca lanza: si no se puede escribir (disco lleno, permisos) devuelve False y el juego sigue.
def guardar(ajustes, ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_ajustes()
    temporal = None
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(prefix=".ajustes-", suffix=".tmp", dir=str(ruta.parent))
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(ajustes.a_dict(), archivo, ensure_ascii=False, indent=2, allow_nan=False)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
        temporal = None
        return True
    except (OSError, ValueError, TypeError):
        return False
    finally:
        if temporal is not None:
            try:
                os.unlink(temporal)
            except OSError:
                pass


# Gestor en memoria: valor actual + suscriptores. Quien cambia un ajuste llama a `cambiar(...)`; los
# suscriptores reciben `callback(ajustes, claves_cambiadas)` ya y en cada cambio posterior.
class GestorAjustes:

    def __init__(self, ruta=None, usar_disco=True):
        self._ruta = Path(ruta) if ruta is not None else None
        self._usar_disco = usar_disco
        self.actual = cargar(self._ruta) if usar_disco else Ajustes()
        self._guardado = self.actual.copia()      # lo último persistido: base de «descartar»
        self._suscritos = []

    def ruta(self):
        return self._ruta if self._ruta is not None else ruta_ajustes()

    # Registra un callback; se le llama de inmediato con TODAS las claves (para sincronizar el estado inicial).
    def suscribir(self, callback, llamar_ya=True):
        self._suscritos.append(callback)
        if llamar_ya:
            callback(self.actual, set(Ajustes.claves()))

    def desuscribir(self, callback):
        if callback in self._suscritos:
            self._suscritos.remove(callback)

    # Cambia campos por nombre (ignora nombres desconocidos), sanea y avisa solo de lo que cambió de verdad.
    # Devuelve el conjunto de claves que cambiaron.
    def cambiar(self, **cambios):
        antes = self.actual.a_dict()
        for clave, valor in cambios.items():
            if clave in Ajustes.claves():
                setattr(self.actual, clave, valor)
            elif isinstance(clave, str):
                self.actual.extras[clave] = valor
        self.actual.sanear()
        despues = self.actual.a_dict()
        cambiadas = {k for k in set(antes) | set(despues) if antes.get(k) != despues.get(k) and k != "version"}
        if cambiadas:
            self._avisar(cambiadas)
        return cambiadas

    # Persiste lo actual (si hay disco). Devuelve True si se guardó.
    def guardar(self):
        if not self._usar_disco:
            self._guardado = self.actual.copia()
            return True
        correcto = guardar(self.actual, self._ruta)
        if correcto:
            self._guardado = self.actual.copia()
        return correcto

    # Vuelve a lo último guardado (descarta cambios de vista previa). Devuelve las claves que cambiaron.
    def descartar(self):
        return self._sustituir(self._guardado.copia())

    # Valores por defecto de todo (sin guardar todavía). Devuelve las claves que cambiaron.
    def restablecer(self):
        nuevo = Ajustes()
        nuevo.extras = dict(self.actual.extras)      # lo ajeno a esta pantalla no se borra
        return self._sustituir(nuevo)

    def hay_cambios_sin_guardar(self):
        return self.actual.a_dict() != self._guardado.a_dict()

    def _sustituir(self, nuevo):
        antes = self.actual.a_dict()
        self.actual.__dict__.update(nuevo.__dict__)
        cambiadas = {k for k, v in self.actual.a_dict().items() if antes.get(k) != v and k != "version"}
        if cambiadas:
            self._avisar(cambiadas)
        return cambiadas

    def _avisar(self, cambiadas):
        for callback in list(self._suscritos):
            try:
                callback(self.actual, cambiadas)
            except Exception as error:     # un suscriptor roto no debe impedir a los demás
                print(f"[ajustes] suscriptor falló: {error}")


_gestor = None


# Gestor global (se crea y carga la primera vez). Con AJUSTES = False no toca el disco.
def obtener():
    global _gestor
    if _gestor is None:
        _gestor = GestorAjustes(usar_disco=AJUSTES)
    return _gestor


# Descarta el gestor global (pruebas).
def reiniciar_global():
    global _gestor
    _gestor = None
