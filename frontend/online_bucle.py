# BucleRed: Entity GLOBAL (cuelga de la raíz, no de EscenaMundo) que cada frame llama al
# núcleo puro (online_bucle_calculos.NucleoRed). No bloquea nunca: solo drena colas.
from ursina import Entity, scene, time

from frontend import online_config
from frontend.online_bucle_calculos import NucleoRed, fuente_pos_local  # noqa: F401 (reexport)

_bucle = None


class BucleRed(Entity):

    def __init__(self, cliente, flujo=None, fuente_pos=None, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self.ignore_paused = True
        self.nucleo = NucleoRed(cliente, flujo, fuente_pos)

    def update(self):
        self.nucleo.paso(min(time.dt, 0.25))

    def suscribir(self, fn):
        self.nucleo.suscribir(fn)

    def desuscribir(self, fn):
        self.nucleo.desuscribir(fn)

    def fijar_flujo(self, flujo):
        self.nucleo.fijar_flujo(flujo)

    def fijar_fuente_pos(self, fuente):
        self.nucleo.fuente_pos = fuente

    def eventos_retenidos(self):
        return self.nucleo.eventos_retenidos()

    def aviso(self):
        return self.nucleo.aviso()


# Crea el bucle global (uno solo). Con ONLINE=False devuelve None salvo forzar=True.
def instalar_bucle(cliente, flujo=None, fuente_pos=None, forzar=False):
    global _bucle
    if not (online_config.ONLINE or forzar):
        return None
    quitar_bucle()
    _bucle = BucleRed(cliente, flujo, fuente_pos)
    return _bucle


def bucle_actual():
    return _bucle


def quitar_bucle():
    global _bucle
    if _bucle is not None:
        from ursina import destroy
        destroy(_bucle)
        _bucle = None
