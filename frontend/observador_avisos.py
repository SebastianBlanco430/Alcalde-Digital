# Observador de los avisos de causa-efecto («al día siguiente...») para las misiones visuales. Mira cada frame
# `flujo.ultimo_aviso_retardado` (lo expone FlujoConTiempo) y, cuando cambia, avisa a quien se haya suscrito con el dict
# del aviso ({"clave", "mensaje", "deltas", "confianza", "hora"}). No consume ni cambia nada: el HUD del reloj sigue
# mostrando el aviso como siempre; los suscriptores solo añaden su vista (rectificar: la misma tarjeta del día anterior).
#
# Por qué así: leer el último aviso no toca el flujo ni el reloj (registro_reloj.py sigue vaciando la cola).
# Límite conocido: si llegan dos avisos en el MISMO frame solo se ve el último (raro: la cola los separa en horas).
# GUARDIÁN: un suscriptor que falla avisa una vez por stderr y no impide a los demás.

from frontend import banderas_visuales as bv

_suscriptores = []
_vigia = None


def suscribir(callback):
    if callback not in _suscriptores:
        _suscriptores.append(callback)


def instalar(escena_mundo):
    """Crea (una vez) la entidad que observa los avisos de `escena_mundo.flujo`. Devuelve el vigía."""
    global _vigia
    if _vigia is not None:
        return _vigia
    from ursina import Entity

    class VigiaAvisos(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self._flujo_visto = None
            self._ultimo = None

        def update(self):
            try:
                flujo = escena_mundo.flujo
                if flujo is None:
                    return
                aviso = getattr(flujo, "ultimo_aviso_retardado", None)
                if flujo is not self._flujo_visto:          # partida nueva o «Continuar»: lo que ya estaba no se anuncia
                    self._flujo_visto, self._ultimo = flujo, aviso
                    return
                if aviso is not None and aviso is not self._ultimo:
                    self._ultimo = aviso
                    for callback in list(_suscriptores):
                        try:
                            callback(aviso)
                        except Exception as error:      # noqa: BLE001
                            bv.avisar_una_vez(f"observador_avisos:{getattr(callback, '__name__', callback)}", error)
            except Exception as error:                  # noqa: BLE001
                bv.avisar_una_vez("observador_avisos", error)

    _vigia = VigiaAvisos(parent=escena_mundo.hud)
    return _vigia
