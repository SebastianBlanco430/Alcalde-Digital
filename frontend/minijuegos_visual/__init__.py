# Selector de vistas visuales de los minijuegos de verificar (plan: misiones más dinámicas, visuales y llamativas).
# frontend/escenas/escena_minijuego.py le pide la clase: clase_visual(id, clase_de_siempre).
#
#   - Con ALCALDE_EFECTOS_UI encendida, devuelve la clase de siempre CON la capa común de efectos (capa.CapaVisual delante
#     en el MRO): rebote, foco, pulso, sello, estrellas, medalla.
#   - Si el minijuego tiene una vista propia (VISTAS) y su bandera está encendida, devuelve esa vista (que hereda de la de
#     siempre y ya trae la capa).
#   - Con la bandera apagada, o si algo falla al importar, devuelve la clase de siempre tal cual: el juego queda idéntico.
#
# Las vistas visuales HEREDAN de las de frontend/minijuegos/ y solo decoran: la partida (*_calculos.py) y el
# ResultadoMinijuego que llega a la escena son exactamente los mismos.
# Este paquete no importa ursina al cargarse (la capa se importa al pedir la clase).

import importlib

from frontend import banderas_visuales as bv

EFECTOS_UI = True
VARIABLE = "ALCALDE_EFECTOS_UI"

# id del minijuego -> (módulo, clase, nombre de la constante de bandera EN ese módulo, variable ALCALDE_*).
VISTAS = {
    "contrarreloj": ("frontend.minijuegos_visual.contrarreloj_visual", "ContrarrelojVisual", "CONTRARRELOJ_VISUAL",
                     "ALCALDE_CONTRARRELOJ_VISUAL"),
    "chat": ("frontend.minijuegos_visual.chat_visual", "ChatVisual", "CHAT_VISUAL", "ALCALDE_CHAT_VISUAL"),
    "rastrear": ("frontend.minijuegos_visual.rastrear_visual", "RastrearVisual", "RASTREAR_VISUAL",
                 "ALCALDE_RASTREAR_VISUAL"),
    "comparar": ("frontend.minijuegos_visual.comparar_visual", "CompararVisual", "COMPARAR_VISUAL",
                 "ALCALDE_COMPARAR_VISUAL"),
    "senales": ("frontend.minijuegos_visual.senales_visual", "SenalesVisual", "SENALES_VISUAL", "ALCALDE_SENALES_VISUAL"),
    "cronologia": ("frontend.minijuegos_visual.cronologia_visual", "CronologiaVisual", "CRONOLOGIA_VISUAL",
                   "ALCALDE_CRONOLOGIA_VISUAL"),
}

_cache = {}


def efectos_activos():
    return bv.activa(EFECTOS_UI, VARIABLE)


def vista_propia(minijuego_id):
    """Clase de la vista propia del minijuego si existe y su bandera está encendida; None si no."""
    entrada = VISTAS.get(minijuego_id)
    if entrada is None:
        return None
    ruta, nombre, constante, variable = entrada
    if not bv.activa(True, variable):           # apagada por variable: ni se importa
        return None
    modulo = importlib.import_module(ruta)
    if not bv.activa(getattr(modulo, constante, True), variable):
        return None
    return getattr(modulo, nombre)


def con_capa(clase_base):
    """La clase de siempre con la capa común delante (una sola subclase por clase base, cacheada)."""
    from frontend.minijuegos_visual.capa import CapaVisual
    if issubclass(clase_base, CapaVisual):
        return clase_base
    if clase_base not in _cache:
        _cache[clase_base] = type(clase_base.__name__ + "ConEfectos", (CapaVisual, clase_base), {})
    return _cache[clase_base]


def clase_visual(minijuego_id, clase_base):
    """Clase a instanciar para `minijuego_id`. Nunca lanza: ante cualquier fallo devuelve `clase_base`."""
    if not efectos_activos():
        return clase_base
    try:
        propia = None
        try:
            propia = vista_propia(minijuego_id)
        except Exception as error:      # noqa: BLE001  la vista propia rota no impide la capa común
            bv.avisar_una_vez(f"vista_{minijuego_id}", error)
        return con_capa(propia or clase_base)
    except Exception as error:          # noqa: BLE001
        bv.avisar_una_vez("minijuegos_visual", error)
        return clase_base
