# Audio del juego sobre Panda3D (AudioManager/OpenAL). Dos canales (música y efectos), cada uno con su propio
# AudioManager: volumen maestro, volumen de música, volumen de efectos y silenciar actúan sobre el volumen
# del manager (afecta al instante a lo que ya suena). Efectos con pool de instancias (varios pasos seguidos
# se solapan sin cortarse), bucles con fundido (motor, ambiente, música con fundido cruzado), pitch variable
# (motor y cadena según la velocidad) y sonidos 3D simples por distancia/balance (para jugadores remotos).
#
# Bandera reversible: AUDIO = False deja un GestorAudio mudo (todas las llamadas son válidas y no hacen nada).
# También se apaga con la variable de entorno ALCALDE_SIN_AUDIO=1.
#
# NUNCA lanza excepción hacia el juego: sin dispositivo de audio (CI, offscreen, sin salida) o con la biblioteca
# `null`, degrada en silencio y avisa UNA sola vez por consola.
#
# Los .wav viven en assets/sonidos/ (scripts/generar_sonidos.py). Si faltan, se sintetizan en memoria con
# frontend/sintesis_calculos.py y se escriben en una carpeta temporal del sistema solo para que Panda3D los cargue.
#
# DISPOSITIVO DE SALIDA (investigado en macOS, Panda3D 1.10.16): el plugin OpenAL abre UN dispositivo compartido
# por todos los AudioManager y lee la variable de config `openal-device` al abrirlo (vacía = predeterminado del
# sistema). Cuando el último manager se cierra, el dispositivo se cierra; el siguiente manager que se cree
# vuelve a leer `openal-device`. Por eso `usar_dispositivo()` cierra los dos managers, fija `openal-device`,
# los recrea y recarga los sonidos: cambio EN CALIENTE sin reiniciar el juego. Limitación real: el OpenAL de
# Apple solo enumera el dispositivo de salida predeterminado del sistema (ALC_ENUMERATE_ALL_EXT no existe), así que
# en macOS `listar_dispositivos()` suele devolver un único elemento; para cambiar de altavoces/auriculares
# se cambia la salida en Ajustes del Sistema (el juego la sigue al reiniciar el audio). Con OpenAL Soft
# (Windows/Linux) sí salen varios dispositivos.

import ctypes
import ctypes.util
import gc
import os
import sys
import tempfile
from pathlib import Path

from frontend import audio_calculos as ac
from frontend import sintesis_calculos as sc

AUDIO = True                 # bandera reversible: False = audio mudo (el juego va como antes)

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_SONIDOS = RAIZ / "assets" / "sonidos"
MUSICA = "musica"
EFECTOS = "efectos"
INSTANCIAS_POR_EFECTO = 3    # pool: cuántos pasos/clics pueden solaparse
VOLUMEN_MAESTRO_DEFECTO = 0.8
VOLUMEN_MUSICA_DEFECTO = 0.6
VOLUMEN_EFECTOS_DEFECTO = 0.8

_AVISOS = set()


# Avisa por consola una sola vez por `clave`.
def _avisar_una_vez(clave, mensaje):
    if clave in _AVISOS:
        return
    _AVISOS.add(clave)
    print(f"[Audio] {mensaje}")


# ------------------------------------------------------------------ dispositivos (OpenAL por ctypes)

_ALC_DEVICE_SPECIFIER = 0x1005
_ALC_DEFAULT_DEVICE_SPECIFIER = 0x1004
_ALC_ALL_DEVICES_SPECIFIER = 0x1013
_cache_dispositivos = None


def _cargar_openal():
    candidatas = [ctypes.util.find_library("openal"), "/System/Library/Frameworks/OpenAL.framework/OpenAL",
                  "libopenal.so.1", "OpenAL32.dll", "soft_oal.dll"]
    for candidata in candidatas:
        if not candidata:
            continue
        try:
            return ctypes.CDLL(candidata)
        except OSError:
            continue
    return None


def _leer_lista(al, codigo):
    # Cadenas separadas por \0 y terminadas en doble \0 (alcGetString con dispositivo NULL).
    puntero = al.alcGetString(None, codigo)
    if not puntero:
        return []
    salida = []
    while True:
        texto = ctypes.string_at(puntero)
        if not texto:
            break
        salida.append(texto.decode("utf-8", "replace"))
        puntero += len(texto) + 1
    return salida


# Nombres de los dispositivos de salida que OpenAL puede abrir. Nunca lanza: lista vacía si no se puede
# (sin OpenAL, headless). `refrescar=True` vuelve a consultar (p. ej. tras enchufar unos auriculares).
def listar_dispositivos(refrescar=False):
    global _cache_dispositivos
    if _cache_dispositivos is not None and not refrescar:
        return list(_cache_dispositivos)
    nombres = []
    try:
        al = _cargar_openal()
        if al is not None:
            al.alcGetString.restype = ctypes.c_void_p
            al.alcGetString.argtypes = [ctypes.c_void_p, ctypes.c_int]
            al.alcIsExtensionPresent.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            if al.alcIsExtensionPresent(None, b"ALC_ENUMERATE_ALL_EXT"):
                nombres = _leer_lista(al, _ALC_ALL_DEVICES_SPECIFIER)
            if not nombres and al.alcIsExtensionPresent(None, b"ALC_ENUMERATION_EXT"):
                nombres = _leer_lista(al, _ALC_DEVICE_SPECIFIER)
            if not nombres:
                nombres = _leer_lista(al, _ALC_DEFAULT_DEVICE_SPECIFIER)
    except Exception as error:
        _avisar_una_vez("lista", f"no se pudo listar los dispositivos de audio ({error}).")
        nombres = []
    _cache_dispositivos = list(dict.fromkeys(n for n in nombres if n))
    return list(_cache_dispositivos)


def _leer(ajustes, nombre, defecto=None):
    # Acepta un objeto con atributos (backend.logica.ajustes.Ajustes) o un dict.
    if isinstance(ajustes, dict):
        return ajustes.get(nombre, defecto)
    return getattr(ajustes, nombre, defecto)


# Un bucle en marcha: su sonido, su volumen (rampa) y su pitch.
class _Bucle:

    def __init__(self, sonido, canal, volumen, pitch):
        self.sonido = sonido
        self.canal = canal
        self.volumen = volumen            # objetivo
        self.pitch = pitch
        self.rampa = ac.Rampa(0.0, 0.5)
        self.parando = False


class GestorAudio:

    # directorio: carpeta de .wav (por defecto assets/sonidos). biblioteca: nombre de `audio-library-name` a
    # forzar (p. ej. "null" en pruebas). habilitado: None = la bandera AUDIO y el entorno.
    def __init__(self, directorio=None, biblioteca=None, habilitado=None):
        self.directorio = Path(directorio) if directorio is not None else DIRECTORIO_SONIDOS
        if habilitado is None:
            habilitado = AUDIO and os.environ.get("ALCALDE_SIN_AUDIO", "") not in ("1", "true", "si")
        self.habilitado = bool(habilitado)
        self.disponible = False            # ¿hay AudioManager (aunque sea nulo)?
        self.sin_salida = False            # True si el manager es nulo o no hay dispositivo real
        self.maestro = VOLUMEN_MAESTRO_DEFECTO
        self.volumen_musica = VOLUMEN_MUSICA_DEFECTO
        self.volumen_efectos = VOLUMEN_EFECTOS_DEFECTO
        self.silenciado = False
        self.dispositivo = None            # None = predeterminado del sistema
        self.biblioteca = biblioteca
        self._gestores = {}                # canal -> AudioManager
        self._pool = {}                    # (canal, nombre) -> [AudioSound]
        self._siguiente = {}               # (canal, nombre) -> índice a robar si todo suena
        self._bucles = {}                  # nombre -> _Bucle
        self._musica_actual = None
        self._rutas = {}
        self._reserva = []                 # un AudioSound por bucle, retenido para que Panda3D conserve su buffer decodificado
        self._carpeta_respaldo = None
        self.reproducciones = 0            # cuántos efectos se pidieron (diagnóstico/pruebas)
        if self.habilitado:
            self._iniciar()

    # -- Arranque --

    def _iniciar(self):
        try:
            if self.biblioteca:
                from panda3d.core import loadPrcFileData
                loadPrcFileData("", f"audio-library-name {self.biblioteca}")
            self._crear_gestores()
            self.disponible = bool(self._gestores)
            if not self.disponible:
                _avisar_una_vez("sin_gestor", "sin dispositivo de audio: el juego seguirá sin sonido.")
                return
            self._aplicar_volumenes()
        except Exception as error:
            self.disponible = False
            self._gestores = {}
            _avisar_una_vez("iniciar", f"no se pudo iniciar el audio ({error}); el juego seguirá sin sonido.")

    def _crear_gestores(self):
        from panda3d.core import AudioManager
        self._gestores = {}
        for canal in (MUSICA, EFECTOS):
            gestor = AudioManager.create_AudioManager()
            if gestor is None:
                self._gestores = {}
                return
            if not gestor.is_valid():
                # Biblioteca `null` (pruebas/CI) o sin dispositivo: el manager existe y acepta todas las llamadas
                # (sonidos nulos) pero no suena. Se avisa una vez y el resto del código funciona igual.
                self.sin_salida = True
                _avisar_una_vez("sin_salida", "sin salida de audio real (biblioteca nula o sin dispositivo): "
                                              "el juego seguirá sin sonido.")
            self._gestores[canal] = gestor

    @property
    def activo(self):
        return self.habilitado and self.disponible

    # Nombre de la biblioteca real (p. ej. "OpenALAudioManager" o "NullAudioManager"); "" si no hay.
    def tipo_gestor(self):
        gestor = self._gestores.get(EFECTOS)
        return type(gestor).__name__ if gestor is not None else ""

    # -- Volúmenes --

    def _aplicar_volumenes(self):
        for canal, gestor in self._gestores.items():
            propio = self.volumen_musica if canal == MUSICA else self.volumen_efectos
            try:
                gestor.set_volume(ac.volumen_canal(self.maestro, propio, self.silenciado))
            except Exception as error:
                _avisar_una_vez("volumen", f"no se pudo fijar el volumen ({error}).")

    def fijar_volumenes(self, maestro=None, musica=None, efectos=None, silenciado=None):
        if maestro is not None:
            self.maestro = ac.acotar01(maestro, self.maestro)
        if musica is not None:
            self.volumen_musica = ac.acotar01(musica, self.volumen_musica)
        if efectos is not None:
            self.volumen_efectos = ac.acotar01(efectos, self.volumen_efectos)
        if silenciado is not None:
            self.silenciado = bool(silenciado)
        self._aplicar_volumenes()

    def silenciar(self, valor=True):
        self.fijar_volumenes(silenciado=valor)

    def volumen_efectivo(self, canal):
        propio = self.volumen_musica if canal == MUSICA else self.volumen_efectos
        return ac.volumen_canal(self.maestro, propio, self.silenciado)

    # Aplica un objeto/dict de ajustes (volumen_maestro, volumen_musica, volumen_efectos, silenciado,
    # dispositivo_audio). Valores en 0-1 (>1 se toma como porcentaje). Devuelve True si no falló nada.
    # El dispositivo solo se reabre si cambió.
    def aplicar_ajustes(self, ajustes):
        try:
            self.fijar_volumenes(
                maestro=_leer(ajustes, "volumen_maestro"), musica=_leer(ajustes, "volumen_musica"),
                efectos=_leer(ajustes, "volumen_efectos"), silenciado=_leer(ajustes, "silenciado"))
            dispositivo = _leer(ajustes, "dispositivo_audio")
            dispositivo = dispositivo if isinstance(dispositivo, str) and dispositivo.strip() else None
            if dispositivo != self.dispositivo:
                self.usar_dispositivo(dispositivo)
            return True
        except Exception as error:
            _avisar_una_vez("ajustes", f"no se pudieron aplicar los ajustes de audio ({error}).")
            return False

    # -- Dispositivo de salida --

    def listar_dispositivos(self, refrescar=False):
        return listar_dispositivos(refrescar)

    # Cambia la salida EN CALIENTE (ver la nota de arriba): cierra los managers, fija `openal-device`, los
    # recrea y vuelve a cargar los sonidos y los bucles en marcha. Devuelve (ok, mensaje). `None` o "" = el
    # predeterminado del sistema. Un nombre que OpenAL no lista (cuando la lista no está vacía) cae al predeterminado.
    def usar_dispositivo(self, nombre):
        nombre = nombre.strip() if isinstance(nombre, str) else None
        nombre = nombre or None
        if nombre is not None and any(c in nombre for c in "\r\n\0"):
            nombre = None
        elegido = nombre
        mensaje = "salida: predeterminada del sistema"
        listados = listar_dispositivos()
        if nombre is not None and listados and nombre not in listados:
            _avisar_una_vez("dispositivo:" + nombre, f"el dispositivo de audio {nombre!r} no está disponible; uso el predeterminado.")
            elegido = None
            mensaje = f"{nombre!r} no disponible: salida predeterminada"
        elif elegido is not None:
            mensaje = f"salida: {elegido}"
        if not self.activo:
            self.dispositivo = elegido        # se recuerda para cuando haya audio
            return (False, "sin audio: " + mensaje)
        try:
            from panda3d.core import ConfigVariableString
            estado = self._guardar_estado()
            self._musica_actual = None            # se vuelve a pedir al restaurar (si no, `musica` creería que ya suena)
            self._cerrar_gestores()
            ConfigVariableString("openal-device", "").set_value(elegido or "")
            self._crear_gestores()
            self.disponible = bool(self._gestores)
            self.dispositivo = elegido
            if self.disponible:
                self._aplicar_volumenes()
                self.precargar()
                self._restaurar_estado(estado)
            else:
                _avisar_una_vez("redispositivo", "no se pudo reabrir el audio en ese dispositivo.")
            return (self.disponible, mensaje + " (aplicado en caliente)")
        except Exception as error:
            self.disponible = False
            _avisar_una_vez("usar_dispositivo", f"error al cambiar de dispositivo ({error}).")
            return (False, f"error: {error}")

    def _guardar_estado(self):
        return {"musica": self._musica_actual,
                "bucles": {n: (b.volumen, b.pitch, b.canal) for n, b in self._bucles.items() if not b.parando}}

    def _restaurar_estado(self, estado):
        for nombre, (volumen, pitch, canal) in estado["bucles"].items():
            if nombre != estado["musica"]:
                self.bucle(nombre, volumen, pitch, fundido=0.2, canal=canal)
        if estado["musica"]:
            volumen, pitch, canal = estado["bucles"].get(estado["musica"], (1.0, 1.0, MUSICA))
            self.musica(estado["musica"], volumen=volumen, fundido=0.2)

    def _cerrar_gestores(self):
        for bucle in list(self._bucles.values()):
            self._parar_sonido(bucle.sonido)
        self._bucles = {}
        self._pool = {}
        self._siguiente = {}
        self._reserva = []
        for gestor in self._gestores.values():
            try:
                gestor.stop_all_sounds()
                gestor.shutdown()
            except Exception:
                pass
        self._gestores = {}
        gc.collect()          # suelta los AudioSound que retenían el dispositivo

    # -- Carga de sonidos --

    # Ruta del .wav de `nombre`; si no existe en disco se sintetiza y se escribe en una carpeta temporal.
    def _ruta(self, nombre):
        if nombre in self._rutas:
            return self._rutas[nombre]
        ruta = self.directorio / f"{nombre}.wav"
        if not ruta.exists():
            if nombre not in sc.CATALOGO:
                return None
            _avisar_una_vez("respaldo:" + nombre, f"falta {ruta.name}; lo sintetizo en memoria.")
            if self._carpeta_respaldo is None:
                self._carpeta_respaldo = Path(tempfile.gettempdir()) / "alcalde_digital_sonidos"
                self._carpeta_respaldo.mkdir(parents=True, exist_ok=True)
            ruta = self._carpeta_respaldo / f"{nombre}.wav"
            if not ruta.exists():
                sc.escribir_wav(ruta, sc.generar(nombre))
        self._rutas[nombre] = ruta
        return ruta

    def _cargar(self, canal, nombre):
        gestor = self._gestores.get(canal)
        ruta = self._ruta(nombre)
        if gestor is None or ruta is None:
            return None
        from panda3d.core import AudioManager, Filename
        # SM_sample: se decodifica entera en memoria (nada de streaming, que dejaría un hueco al repetir el bucle).
        sonido = gestor.get_sound(Filename.from_os_specific(str(ruta)), False, AudioManager.SM_sample)
        return sonido

    # Precarga (al inicio) los efectos y los bucles: así no hay carga en mitad de una partida.
    def precargar(self, nombres=None):
        if not self.activo:
            return 0
        cargados = 0
        for nombre in (nombres or list(sc.CATALOGO)):
            try:
                if sc.es_bucle(nombre):
                    # Bucles: se carga una instancia y se retiene; al arrancar el bucle Panda3D reutiliza el
                    # buffer ya decodificado (sin tirón de carga en mitad del juego).
                    sonido = self._cargar(MUSICA if nombre.startswith("musica") else EFECTOS, nombre)
                    if sonido is not None:
                        self._reserva.append(sonido)
                else:
                    self._instancias(EFECTOS, nombre)
                cargados += 1
            except Exception as error:
                _avisar_una_vez("precarga:" + nombre, f"no se pudo cargar {nombre} ({error}).")
        return cargados

    def _instancias(self, canal, nombre):
        clave = (canal, nombre)
        if clave not in self._pool:
            lista = []
            for _ in range(INSTANCIAS_POR_EFECTO):
                sonido = self._cargar(canal, nombre)
                if sonido is not None:
                    lista.append(sonido)
            self._pool[clave] = lista
        return self._pool[clave]

    @staticmethod
    def _parar_sonido(sonido):
        try:
            sonido.stop()
        except Exception:
            pass

    # -- Efectos --

    # Reproduce un efecto una vez. volumen 0-1, pitch (velocidad de reproducción, 1 = normal), balance -1..1.
    # Devuelve True si se lanzó. Nunca lanza.
    def efecto(self, nombre, volumen=1.0, pitch=1.0, balance=0.0):
        self.reproducciones += 1
        if not self.activo:
            return False
        try:
            instancias = self._instancias(EFECTOS, nombre)
            if not instancias:
                return False
            clave = (EFECTOS, nombre)
            sonido = next((s for s in instancias if s.status() != 2), None)    # 2 = PLAYING
            if sonido is None:                                                  # todos suenan: se roba el más viejo
                i = self._siguiente.get(clave, 0) % len(instancias)
                self._siguiente[clave] = i + 1
                sonido = instancias[i]
                sonido.stop()
            sonido.set_volume(max(0.0, min(1.0, volumen)))
            sonido.set_play_rate(max(0.25, min(3.0, pitch)))
            sonido.set_balance(max(-1.0, min(1.0, balance)))
            sonido.set_loop(False)
            sonido.play()
            return True
        except Exception as error:
            _avisar_una_vez("efecto:" + nombre, f"no se pudo reproducir {nombre} ({error}).")
            return False

    # Efecto 3D simple: más lejos, más bajo (y se omite si no se oiría); balance según el lado donde está.
    def efecto_3d(self, nombre, distancia, volumen=1.0, pitch=1.0, dx=0.0, dz=0.0, yaw_grados=0.0):
        atenuado = volumen * ac.atenuacion_distancia(distancia)
        if atenuado < 0.01:
            return False
        return self.efecto(nombre, atenuado, pitch, ac.balance_estereo(dx, dz, yaw_grados))

    # -- Bucles y música --

    # Inicia (o ajusta si ya suena) un bucle: volumen y pitch objetivo, con fundido de entrada.
    def bucle(self, nombre, volumen=1.0, pitch=1.0, fundido=0.5, canal=EFECTOS):
        if not self.activo:
            return False
        try:
            actual = self._bucles.get(nombre)
            if actual is not None:
                # Ya existe (sonando o apagándose): se reactiva con el mismo sonido, sin duplicarlo.
                actual.volumen = max(0.0, min(1.0, volumen))
                actual.pitch = pitch
                if actual.parando:
                    actual.parando = False
                    actual.rampa.duracion = max(1e-3, fundido)
                return True
            sonido = self._cargar(canal, nombre)
            if sonido is None:
                return False
            bucle = _Bucle(sonido, canal, max(0.0, min(1.0, volumen)), pitch)
            bucle.rampa = ac.Rampa(0.0, fundido)
            sonido.set_loop(True)
            sonido.set_volume(0.0)
            sonido.set_play_rate(max(0.25, min(3.0, pitch)))
            sonido.play()
            self._bucles[nombre] = bucle
            return True
        except Exception as error:
            _avisar_una_vez("bucle:" + nombre, f"no se pudo iniciar el bucle {nombre} ({error}).")
            return False

    # Ajusta un bucle que ya suena (motor: pitch y volumen por velocidad). No hace nada si no está.
    def ajustar_bucle(self, nombre, volumen=None, pitch=None):
        bucle = self._bucles.get(nombre)
        if bucle is None or bucle.parando:
            return
        if volumen is not None:
            bucle.volumen = max(0.0, min(1.0, volumen))
        if pitch is not None:
            bucle.pitch = pitch

    def parar_bucle(self, nombre, fundido=0.5):
        bucle = self._bucles.get(nombre)
        if bucle is None:
            return
        bucle.parando = True
        bucle.rampa.duracion = max(1e-3, fundido)
        bucle.rampa.ir_a(0.0)

    def bucle_sonando(self, nombre):
        bucle = self._bucles.get(nombre)
        return bucle is not None and not bucle.parando

    # Cambia la música con fundido cruzado. nombre=None apaga la música. Si ya suena esa, solo ajusta el volumen.
    def musica(self, nombre, volumen=1.0, fundido=1.5):
        if not self.activo:
            self._musica_actual = nombre
            return False
        if nombre == self._musica_actual and nombre is not None:
            self.ajustar_bucle(nombre, volumen=volumen)
            return True
        anterior = self._musica_actual
        self._musica_actual = nombre
        if anterior is not None:
            self.parar_bucle(anterior, fundido)
        if nombre is None:
            return True
        return self.bucle(nombre, volumen, 1.0, fundido, canal=MUSICA)

    @property
    def musica_actual(self):
        return self._musica_actual

    # Un paso de tiempo (cada frame): rampas de los bucles y refresco de los managers de Panda3D.
    def actualizar(self, dt):
        if not self.activo:
            return
        try:
            for nombre in list(self._bucles):
                bucle = self._bucles[nombre]
                if not bucle.parando:
                    bucle.rampa.ir_a(bucle.volumen)
                v = bucle.rampa.avanzar(dt)
                bucle.sonido.set_volume(v)
                if bucle.pitch != getattr(bucle, "_pitch_puesto", None):
                    bucle.sonido.set_play_rate(max(0.25, min(3.0, bucle.pitch)))
                    bucle._pitch_puesto = bucle.pitch
                if bucle.parando and bucle.rampa.llegado:
                    self._parar_sonido(bucle.sonido)
                    del self._bucles[nombre]
            for gestor in self._gestores.values():
                gestor.update()
        except Exception as error:
            _avisar_una_vez("actualizar", f"error al actualizar el audio ({error}).")

    # Para todo y libera (al cerrar el juego o en pruebas).
    def cerrar(self):
        if self._gestores:
            self._cerrar_gestores()
        self.disponible = False


_gestor_global = None


# Gestor único del juego (se crea al pedirlo la primera vez).
def obtener():
    global _gestor_global
    if _gestor_global is None:
        _gestor_global = GestorAudio()
    return _gestor_global


# Descarta el gestor global (pruebas).
def reiniciar_global():
    global _gestor_global
    if _gestor_global is not None:
        _gestor_global.cerrar()
    _gestor_global = None
