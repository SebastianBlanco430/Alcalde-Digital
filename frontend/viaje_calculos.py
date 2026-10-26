# Cálculos PUROS (sin ursina, con pruebas) del viaje rápido del mapa grande: las filas del menú de destinos y
# ControlViaje (cursor, mensaje y saldo sobre un PerfilEconomia), los textos de rechazo y la cámara del trayecto en
# teleférico. La vista (frontend/mototaxi.py, frontend/teleferico_vista.py) solo dibuja; el orden de los pasos (cobrar,
# fundido, reubicar, trayecto) lo lleva frontend/viaje_rapido.py. Las reglas de dinero y de destino son las de
# backend/logica/viaje_rapido.py.

import math
from dataclasses import dataclass

from backend.logica import viaje_rapido as vr
from frontend.tienda_calculos import DIRECCIONES, TECLAS_COMPRAR, texto_saldo

TEXTOS_MOTIVO = {
    "lejos": "Estás demasiado lejos de la parada.",
    "mismo_lugar": "Ya estás en ese lugar.",
    "no_existe": "Ese destino no existe.",
    "fase": "No se puede viajar ahora.",
    "dentro": "No se puede viajar desde dentro de un edificio.",
    "montado": "Baja del vehículo primero.",
    "espera": "Espera unos segundos antes de otro viaje.",
    "desactivado": "El transporte no está disponible aquí.",
    "desconectado": "Sin conexión con el anfitrión.",
}
TEXTO_SIN_RESPUESTA = "El anfitrión no contestó: no se hizo el viaje."
TEXTO_SIN_DINERO = "Sin dinero."
TEXTO_SIN_BILLETERA = "No llevas billetera para pagar."
TEXTO_OCUPADO = "Ya estás viajando."
MENSAJES_COBRO = {"sin_dinero": TEXTO_SIN_DINERO, "sin_billetera": TEXTO_SIN_BILLETERA}


@dataclass(frozen=True)
class FilaViaje:
    destino: str          # id de viaje_rapido.DESTINOS
    nombre: str
    descripcion: str
    precio: int

    @property
    def texto_precio(self):
        return f"R$ {self.precio}" if self.precio > 0 else "Gratis"


def _descripcion(destino_id, precio):
    destino = vr.DESTINOS[destino_id]
    if destino.tipo == vr.TIPO_TELEFERICO:
        return "Cabina sobre el barrio, unos 40 s de vista (Espacio la salta)"
    return "Mototáxi: viaje con la pantalla negra unos 8-15 s (Espacio lo salta)"


def filas_de_parada(mundo, parada_id):
    """Filas del menú del mototáxi de la parada: los demás destinos con su precio."""
    return [FilaViaje(d, nombre, _descripcion(d, precio), precio) for d, nombre, precio in vr.ofertas_de_parada(mundo, parada_id)]


def filas_de_estacion(mundo, estacion_id):
    """Fila(s) del menú del teleférico en la estación: el trayecto a la otra estación."""
    d, nombre, precio = vr.oferta_de_estacion(mundo, estacion_id)
    return [FilaViaje(d, nombre, _descripcion(d, precio), precio)]


class ControlViaje:
    """Cursor y mensaje del menú de destinos. `al_viajar(fila)` -> (ok, mensaje): decide y arranca el viaje (cobrar, fundido...);
    si ok el menú se cierra, si no se queda abierto con el mensaje en rojo. Misma interfaz de modal que ControlTienda."""

    def __init__(self, perfil, filas, al_viajar):
        self.perfil = perfil
        self.filas = list(filas)
        self.comercio = None
        self.seleccion = 0
        self.mensaje = ""
        self.error = False
        self.version = 0
        self._al_viajar = al_viajar

    def saldo(self):
        return self.perfil.inventario.saldo()

    def fila_seleccionada(self):
        return self.filas[self.seleccion] if self.filas else None

    def _avisar(self, texto, error=False):
        self.mensaje, self.error = texto, error
        self.version += 1

    def mover(self, delta):
        if not self.filas:
            return
        nueva = (self.seleccion + delta) % len(self.filas)
        if nueva != self.seleccion:
            self.seleccion = nueva
            self.version += 1

    # Intenta el viaje de la fila elegida. Devuelve True si arrancó (hay que cerrar el menú).
    def viajar(self):
        fila = self.fila_seleccionada()
        if fila is None:
            self._avisar("No hay destinos.", True)
            return False
        ok, mensaje = self._al_viajar(fila)
        if ok:
            return True
        self._avisar(mensaje, True)
        return False

    def tecla(self, key):
        if key == "escape":
            return "cerrar"
        if key in DIRECCIONES:
            self.mover(DIRECCIONES[key])
        elif key in TECLAS_COMPRAR:
            if self.viajar():
                return "cerrar"
        return None

    def firma(self):
        return (self.version, self.seleccion, self.saldo(), len(self.filas))


# -- Cámara del trayecto en teleférico (órbita lenta alrededor de la cabina, saltable con Espacio) --
DISTANCIA_CAMARA = 15.0       # m de la cabina
PITCH_CAMARA = 21.0           # grados sobre el horizonte (la cámara mira desde arriba y de lado)
AZIMUT_BASE = 118.0           # grados respecto al rumbo del cable: la cámara queda detrás y a un lado
BARRIDO_AZIMUT = 38.0         # grados de ida y vuelta del azimut (la vista recorre el barrio)
PERIODO_BARRIDO = 24.0        # s por ida y vuelta
PITCH_MIN, PITCH_MAX = 4.0, 62.0
VEL_GIRO = 70.0               # grados/s con las flechas / A-D
VEL_INCLINAR = 40.0           # grados/s con arriba / abajo


def camara_trayecto(t, rumbo_cable, giro_extra=0.0, inclinacion_extra=0.0):
    """(yaw, pitch, distancia) de la cámara t segundos después de salir. `rumbo_cable`: rumbo del cable en ese punto
    (grados, convención de Ursina). `giro_extra` / `inclinacion_extra`: lo que el jugador movió con las teclas."""
    barrido = BARRIDO_AZIMUT * math.sin(2.0 * math.pi * t / PERIODO_BARRIDO)
    yaw = rumbo_cable + AZIMUT_BASE + barrido + giro_extra
    yaw = ((yaw + 180.0) % 360.0) - 180.0
    pitch = min(PITCH_MAX, max(PITCH_MIN, PITCH_CAMARA + inclinacion_extra))
    return yaw, pitch, DISTANCIA_CAMARA


def texto_puntos(t):
    """«.», «..», «...» según el tiempo: animación de los puntos suspensivos del texto de espera."""
    return "." * (1 + int(t * 2.0) % 3)
