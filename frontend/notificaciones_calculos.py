# Notificaciones de evento por el teléfono (docs/PLAN_CLARIDAD_JUEGO.md §2.6): parte PURA (sin ursina; se prueba sin
# ventana). La vista vive en frontend/notificaciones.py.
#
#   activo()        bandera NOTIF_TELEFONO / ALCALDE_NOTIF_TELEFONO=0 (apagada: los avisos de evento van al centro, como antes)
#   ColaTarjetas    pila de tarjetas con el teléfono ABIERTO: máx. 3 visibles, 4 s cada una, en orden de llegada; en
#                   pausa no avanzan (no se pierden)
#   ColaBanner      banner del teléfono CERRADO: varios mensajes seguidos se muestran uno tras otro, 4 s cada uno
#   entrada(edad) / alfa(edad)   deslizamiento de entrada (0,2 s) y fundido de salida de una tarjeta

import os
from dataclasses import dataclass

NOTIF_TELEFONO = True

REMITENTE = "Ciudad Nova"        # remitente por defecto de los avisos de evento
MAX_VISIBLES = 3
SEGUNDOS_TARJETA = 4.0
SEGUNDOS_ENTRADA = 0.2           # la tarjeta entra deslizándose desde la derecha
SEGUNDOS_SALIDA = 0.4            # y sale con fundido (los últimos 0,4 s de sus 4 s)
TOPE_BANNER = 4                  # mensajes seguidos que el banner repasa como mucho (los más recientes)

# tono -> (símbolo, constante de color en frontend/estilo.py). Nunca solo color: el símbolo va siempre.
TONOS = {
    "exito": ("+", "ESTADO_EXITO"),
    "aviso": ("!", "ESTADO_AVISO"),
    "error": ("x", "ESTADO_ERROR"),
    "info": ("i", "ESTADO_INFO"),
}

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Los avisos de evento llegan por el teléfono? ALCALDE_NOTIF_TELEFONO=1/0 manda sobre la constante."""
    valor = os.environ.get("ALCALDE_NOTIF_TELEFONO", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(NOTIF_TELEFONO)


def tono_valido(tono):
    return tono if tono in TONOS else "info"


@dataclass
class Tarjeta:
    numero: int                  # orden de llegada (identidad: la vista sabe si su ranura cambió de tarjeta)
    texto: str
    remitente: str
    tono: str
    edad: float = 0.0            # s que lleva VISIBLE (en la cola de espera no corre)


class ColaTarjetas:
    """Tarjetas en orden de llegada. Las `maximo` primeras son visibles y envejecen; al cumplir `duracion` salen y entra
    la siguiente. Con `en_pausa` nada envejece ni entra (pausa, cinemática, tutorial, paneles modales)."""

    def __init__(self, maximo=MAX_VISIBLES, duracion=SEGUNDOS_TARJETA):
        self.maximo, self.duracion = maximo, duracion
        self._tarjetas = []
        self._numero = 0

    def agregar(self, texto, remitente=REMITENTE, tono="info"):
        texto = str(texto or "").strip()
        if not texto:
            return None
        self._numero += 1
        tarjeta = Tarjeta(self._numero, texto, str(remitente or REMITENTE), tono_valido(tono))
        self._tarjetas.append(tarjeta)
        return tarjeta

    def pendientes(self):
        return len(self._tarjetas)

    def visibles(self):
        return list(self._tarjetas[:self.maximo])

    def vaciar(self):
        self._tarjetas.clear()

    def avanzar(self, dt, en_pausa=False):
        """Un paso de `dt` s. Devuelve las tarjetas visibles ahora (lista vacía en pausa: la vista las esconde)."""
        if en_pausa:
            return []
        for tarjeta in self._tarjetas[:self.maximo]:
            tarjeta.edad += dt
        self._tarjetas = [t for t in self._tarjetas if t.edad < self.duracion]
        return self.visibles()


def entrada(edad, segundos=SEGUNDOS_ENTRADA):
    """0..1 del deslizamiento de entrada (curva de salida cuadrática)."""
    if segundos <= 0:
        return 1.0
    t = max(0.0, min(1.0, edad / segundos))
    return 1.0 - (1.0 - t) ** 2


def alfa(edad, duracion=SEGUNDOS_TARJETA, salida=SEGUNDOS_SALIDA):
    """1 mientras se lee; baja a 0 en los últimos `salida` s."""
    if salida <= 0:
        return 1.0
    return max(0.0, min(1.0, (duracion - edad) / salida))


class ColaBanner:
    """Qué mensaje enseña el banner del teléfono cerrado. Mientras el teléfono está NOTIFICANDO, repasa de uno en uno
    los mensajes llegados desde la última vez que estuvo en reposo (`duracion` s cada uno, como mucho los `tope` más
    recientes) y solo entonces pide terminar la notificación."""

    def __init__(self, duracion=SEGUNDOS_TARJETA, tope=TOPE_BANNER):
        self.duracion, self.tope = duracion, tope
        self.vistos = 0              # cuántos mensajes había la última vez que el banner no estaba a la vista
        self.indice = None           # mensaje que se enseña ahora (None = ninguno)
        self.tiempo = 0.0

    def reiniciar(self, total, sin_leer=0):
        """Otro teléfono (cambio de turno): los que ya tenía sin leer se repasan, el resto se dan por vistos."""
        self.vistos = max(0, total - max(0, sin_leer))
        self.indice, self.tiempo = None, 0.0

    def avanzar(self, notificando, total, dt):
        """Devuelve True cuando ya se enseñó el último mensaje (toca terminar_notificacion)."""
        if not notificando or total <= 0:
            self.vistos = total
            self.indice, self.tiempo = None, 0.0
            return False
        if self.indice is None:
            self.indice = max(0, total - self.tope, min(self.vistos, total - 1))
            self.tiempo = 0.0
        self.indice = min(self.indice, total - 1)
        self.tiempo += dt
        if self.tiempo < self.duracion:
            return False
        if self.indice < total - 1:
            self.indice += 1
            self.tiempo = 0.0
            return False
        return True
