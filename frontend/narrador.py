# Reproductor de la narradora y de la Rádio Comunitária (ver frontend/narrador_calculos.py, la parte pura).
#
#   narrador.decir(texto, radio=False) -> bool   suena la voz de ese texto (corta la anterior); False si no hay audio
#   narrador.callar()                            corta la voz (al saltar, cerrar o cambiar de escena)
#   narrador.hablando() -> bool
#
# Canal propio (un AudioManager aparte de música y efectos), con el volumen maestro de frontend/audio.py (y mudo si
# está silenciado). Mientras habla, la música baja a narrador_calculos.ATENUACION_MUSICA con una rampa y vuelve al
# terminar. Un pequeño Entity invisible hace el tic por frame (update del manager y rampa). NUNCA lanza.

import sys

from frontend import narrador_calculos as nc

VOLUMEN_VOZ = 1.0
RAMPA_S = 0.3

_estado = {"manager": None, "sonido": None, "tic": None, "factor": 1.0, "fallo": False}


def _aviso(texto):
    print(f"[narrador] {texto}", file=sys.stderr)


def _audio():
    try:
        from frontend import audio
        return audio.obtener()
    except Exception:
        return None


def _volumen():
    gestor = _audio()
    if gestor is None:
        return VOLUMEN_VOZ
    if getattr(gestor, "silenciado", False):
        return 0.0
    return max(0.0, min(1.0, float(getattr(gestor, "maestro", 1.0)) * VOLUMEN_VOZ))


def _manager():
    if _estado["manager"] is None and not _estado["fallo"]:
        try:
            from panda3d.core import AudioManager
            _estado["manager"] = AudioManager.create_AudioManager()
        except Exception as error:
            _estado["fallo"] = True
            _aviso(f"sin canal de voz ({type(error).__name__}: {error})")
    return _estado["manager"]


def _asegurar_tic():
    if _estado["tic"] is not None:
        return
    try:
        from ursina import Entity

        class _Tic(Entity):
            def update(self):
                _tic()

        _estado["tic"] = _Tic(eternal=True, ignore_paused=True, name="narrador_tic")
    except Exception as error:
        _aviso(f"sin tic ({type(error).__name__}: {error})")


def _musica(factor):
    gestor = _audio()
    if gestor is None:
        return
    try:
        from frontend import audio
        manager = gestor._gestores.get(audio.MUSICA)
        if manager is not None:
            manager.set_volume(gestor.volumen_efectivo(audio.MUSICA) * factor)
    except Exception:
        pass


def _tic():
    try:
        from ursina import time
        dt = min(float(time.dt), 0.1)
    except Exception:
        dt = 1 / 60
    try:
        manager = _estado["manager"]
        if manager is not None:
            manager.update()
        objetivo = nc.ATENUACION_MUSICA if (hablando() and nc.atenuar_activo()) else 1.0
        actual = _estado["factor"]
        if actual != objetivo:
            paso = dt / RAMPA_S * (1.0 - nc.ATENUACION_MUSICA)
            actual = min(objetivo, actual + paso) if actual < objetivo else max(objetivo, actual - paso)
            _estado["factor"] = actual
            _musica(actual)
        elif actual < 1.0:
            _musica(actual)                  # la música pudo cambiar (fundido cruzado) mientras habla
    except Exception as error:
        _aviso(f"tic: {type(error).__name__}: {error}")


def decir(texto, radio=False):
    """Suena la voz de `texto`. Devuelve True si arrancó. Sin bandera, sin audio o con cualquier error: False."""
    try:
        if not (nc.radio_activa() if radio else nc.activo()):
            return False
        ruta = nc.ruta_audio(texto)
        if ruta is None:
            return False
        manager = _manager()
        if manager is None:
            return False
        callar()
        from panda3d.core import Filename
        sonido = manager.get_sound(Filename.from_os_specific(str(ruta)))
        if sonido is None:
            return False
        sonido.set_volume(_volumen())
        sonido.play()
        _estado["sonido"] = sonido
        _asegurar_tic()
        return True
    except Exception as error:
        _aviso(f"decir: {type(error).__name__}: {error}")
        return False


def callar():
    sonido, _estado["sonido"] = _estado["sonido"], None
    if sonido is not None:
        try:
            sonido.stop()
        except Exception:
            pass


def hablando():
    sonido = _estado["sonido"]
    if sonido is None:
        return False
    try:
        return sonido.status() == 2          # AudioSound.PLAYING
    except Exception:
        return False
