# Turno del MOSTRADOR 3D (modelo puro, sin ursina): sustituye a TurnoTrabajo en los trabajos ATENDER cuando está la
# bandera ALCALDE_MOSTRADOR3D (frontend/mostrador3d_escena.py). Ciclo de cada cliente:
#   LLEGANDO  - camina hasta el mostrador (LLEGADA_S); no se le puede atender todavía.
#   PEDIDO    - pide 2-4 unidades de los 4 productos del local. entregar(i) da uno: si sobra o no lo pidió, es un error
#               y no cuenta. Al completar el pedido, el cliente paga (mostrador3d_dinero.pago_cliente).
#   CAMBIO    - el jugador pone billetes y monedas de la caja en la bandeja (agregar/quitar) y dar_cambio(): si suma
#               exactamente el cambio, acierto; si no, error y el cliente se ENOJA (cambios_mal; la escena baja la
#               convivencia, como mucho TOPE_CASTIGO por turno).
#   SALIENDO  - se va (SALIDA_S) y llega el siguiente.
# API como TurnoTrabajo (avanzar, tiempo_restante, terminado, resultado) para EscenaTrabajo. resultado() tiene las
# MISMAS claves de siempre {aciertos, errores, rendimiento, pago, fatiga} y añade las opcionales cambios_mal y
# convivencia. pago = round(pago_base + (pago_max - pago_base) * rendimiento), como TurnoTrabajo.

import math
import random

from backend.logica import mostrador3d_dinero as dinero
from backend.logica.trabajos import PENALIZA_ERROR, PEDIDO_UNIDADES

LLEGANDO, PEDIDO, CAMBIO, SALIENDO = "llegando", "pedido", "cambio", "saliendo"
LLEGADA_S = 1.6
SALIDA_S = 1.8
# ritmo de un buen jugador (como RITMO_S[ATENDER] de trabajos.py): define la meta
SEGUNDOS_POR_ACCION = 2.5
# puntos de convivencia que baja cada cambio mal dado...
CASTIGO_CONVIVENCIA = 1
# ...como mucho en un turno
TOPE_CASTIGO = 3
# piezas en la bandeja del cambio
MAX_BANDEJA = 20


class TurnoMostrador:

    # trabajo: Trabajo ATENDER. local: dict de mostrador3d_locales.json (4 productos con precio en centavos).
    def __init__(self, trabajo, local, semilla=0):
        self.trabajo = trabajo
        self.local = local
        self.productos = [p["nombre"] for p in local["productos"]]
        self.precios = {p["nombre"]: p["precio"] for p in local["productos"]}
        self.instrucciones = ("Clic (o 1-4) en los productos que pide el cliente. Cuando pague, clic en los billetes y "
                              "monedas de la caja y Enter para dar el cambio.")
        self._rng = random.Random(semilla)
        self._t = 0.0
        self._aciertos = 0
        self._errores = 0
        self.cambios_mal = 0
        self.cambios_bien = 0
        self.cliente = 0
        self._eventos = []
        self._nuevo_cliente()

    # -- Reloj --

    def avanzar(self, dt):
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        self._t = min(self._t + dt, self.trabajo.duracion_s)
        self._t_estado += dt
        if self.estado == LLEGANDO and self._t_estado >= LLEGADA_S:
            self._pasar(PEDIDO)
        elif self.estado == SALIENDO and self._t_estado >= SALIDA_S:
            self.cliente += 1
            self._nuevo_cliente()

    def tiempo(self):
        return self._t

    def tiempo_restante(self):
        return max(0.0, self.trabajo.duracion_s - self._t)

    def terminado(self):
        return self._t >= self.trabajo.duracion_s

    def tiempo_en_estado(self):
        return self._t_estado

    # -- Cliente --

    def _pasar(self, estado):
        self.estado, self._t_estado = estado, 0.0
        self._eventos.append((estado, self.cliente))

    def _nuevo_cliente(self):
        total = self._rng.randint(*PEDIDO_UNIDADES)
        self._pedido = {}
        for _ in range(total):
            producto = self._rng.choice(self.productos)
            self._pedido[producto] = self._pedido.get(producto, 0) + 1
        self._entregado = {}
        self._pagado = []
        self._bandeja = []
        # None, "contento" o "enojado" (al dar el cambio)
        self.reaccion = None
        self._pasar(LLEGANDO)

    def pedido(self):
        return dict(self._pedido)

    def entregado(self):
        return dict(self._entregado)

    def pedido_texto(self):
        return " + ".join(f"{n} {p}" for p, n in self._pedido.items())

    def total(self):
        return dinero.total_pedido(self._pedido, self.precios)

    def pagado(self):
        return list(self._pagado)

    def cambio_esperado(self):
        return dinero.cambio(self.total(), self._pagado)

    def bandeja(self):
        return list(self._bandeja)

    def suma_bandeja(self):
        return sum(self._bandeja)

    # Eventos desde la última llamada: [(estado nuevo | "acierto" | "error" | "castigo", cliente)]. Para la vista.
    def sacar_eventos(self):
        eventos, self._eventos = self._eventos, []
        return eventos

    # -- Acciones del jugador (False sin penalizar si no tocan: fuera de su fase o con el turno terminado) --

    def entregar(self, indice):
        if self.terminado() or self.estado != PEDIDO:
            return False
        if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(self.productos):
            return False
        producto = self.productos[indice]
        if self._entregado.get(producto, 0) >= self._pedido.get(producto, 0):
            self._errores += 1
            self._eventos.append(("error", self.cliente))
            return False
        self._entregado[producto] = self._entregado.get(producto, 0) + 1
        self._aciertos += 1
        if self._entregado == self._pedido:
            self._pagado = dinero.pago_cliente(self.total(), self._rng)
            self._pasar(CAMBIO)
        return True

    def agregar(self, valor):
        if self.terminado() or self.estado != CAMBIO or valor not in dinero.DENOMINACIONES:
            return False
        if len(self._bandeja) >= MAX_BANDEJA:
            return False
        self._bandeja.append(valor)
        return True

    def quitar(self, indice=-1):
        if self.estado != CAMBIO or not self._bandeja:
            return False
        try:
            self._bandeja.pop(indice)
        except (IndexError, TypeError):
            return False
        return True

    def dar_cambio(self):
        if self.terminado() or self.estado != CAMBIO:
            return False
        if dinero.cambio_correcto(self._bandeja, self.total(), self._pagado):
            self._aciertos += 1
            self.cambios_bien += 1
            self.reaccion = "contento"
            self._eventos.append(("acierto", self.cliente))
            correcto = True
        else:
            self._errores += 1
            self.cambios_mal += 1
            self.reaccion = "enojado"
            self._eventos.append(("error", self.cliente))
            if self.cambios_mal <= TOPE_CASTIGO:
                self._eventos.append(("castigo", self.cliente))
            correcto = False
        self._pasar(SALIENDO)
        return correcto

    # -- Resultado --

    def meta_aciertos(self):
        return max(1, round(self.trabajo.duracion_s / SEGUNDOS_POR_ACCION))

    def rendimiento(self):
        puntos = self._aciertos - PENALIZA_ERROR * self._errores
        return max(0.0, min(1.0, puntos / self.meta_aciertos()))

    def convivencia(self):
        """Puntos de convivencia que ha costado el turno (0 o negativo, como mucho -TOPE_CASTIGO)."""
        return -CASTIGO_CONVIVENCIA * min(self.cambios_mal, TOPE_CASTIGO)

    def resultado(self):
        t = self.trabajo
        rendimiento = self.rendimiento()
        return {
            "aciertos": self._aciertos,
            "errores": self._errores,
            "rendimiento": rendimiento,
            "pago": round(t.pago_base + (t.pago_max - t.pago_base) * rendimiento),
            "fatiga": t.fatiga,
            "cambios_mal": self.cambios_mal,
            "convivencia": self.convivencia(),
        }
