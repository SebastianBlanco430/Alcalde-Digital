# Castigo de convivencia del MOSTRADOR 3D: cada cambio mal dado baja la convivencia de la ciudad
# (backend/logica/mostrador3d_turno.py decide cuándo: CASTIGO_CONVIVENCIA por error, como mucho TOPE_CASTIGO por turno).
# Usa la API que ya existe, sin reescribirla: EstadoPartida.aplicar_deltas({"convivencia": -n}) de la sesión del mundo
# (la misma que leen el HUD y frontend/ambiente_vivo.py). La escena de trabajo no conoce el mundo: frontend/trabajo_mundo.py
# llama a enganchar(escena_mundo) al conectar los puestos. Solo en partida LOCAL: en la cooperativa los indicadores
# viajan por otro camino (online_flujo) y no se tocan. Sin mundo enganchado (pruebas, escena suelta) no hace nada.

import sys

_mundo = {"escena": None}


def enganchar(escena_mundo):
    _mundo["escena"] = escena_mundo


def soltar():
    _mundo["escena"] = None


def castigar(puntos=1):
    """Baja `puntos` de convivencia en la partida local. True si se aplicó. Nunca lanza."""
    escena = _mundo["escena"]
    if escena is None or puntos <= 0:
        return False
    if getattr(escena, "online", None) is not None:
        return False
    sesion = getattr(escena, "_sesion", None)
    estado = getattr(sesion, "estado_partida", None)
    if estado is None:
        return False
    try:
        estado.aplicar_deltas({"convivencia": -puntos})
        return True
    except Exception as error:                   # noqa: BLE001
        print(f"[mostrador3d] no se pudo bajar la convivencia ({error})", file=sys.stderr)
        return False
