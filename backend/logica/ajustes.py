# Almacén de AJUSTES del jugador (Python puro, sin ursina/panda3d): accesibilidad (daltonismo), audio y
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
import tempfile
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
    if not math.isfinite(valor):
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


# Lee los ajustes; cualquier problema (falta, permisos, tamaño, JSON roto, tipo raro) -> valores por defecto.
def cargar(ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_ajustes()
    try:
        if not ruta.is_file() or ruta.stat().st_size > TAMANO_MAX_ARCHIVO:
            return Ajustes()
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return Ajustes()
    return Ajustes.desde_dict(datos)


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
