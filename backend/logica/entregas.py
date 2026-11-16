# Trabajo de entregas en moto (modelo puro, sin ursina): sustituye al minijuego de la barra del «Mototaxi y entregas».
# El jugador lleva N_ENTREGAS pedidos, en orden, a puntos de la favela elegidos al azar (catálogo en
# backend/datos/entregas_semilla.py) antes de que se acabe el tiempo. Entregar = pasar a menos de RADIO_ENTREGA m del
# punto; no hay que pulsar nada. La vista (moto, ruta azul, baliza, destinatario y HUD) vive en frontend/entregas_mundo.py.
#
# El mapa (`mundo`) se inyecta: hace falta `lugares()` y `punto_interaccion(lugar)`. La ruta en metros la calcula quien
# llama (con el GPS de siempre) y se pasa a `tiempo_limite`: así este módulo no depende de la navegación.
#
# Pago (resultado() -> {entregas, pago, fatiga, rendimiento}, el formato de pago_trabajo.aplicar_resultado):
#   - las dos entregas: pago_base + (pago_max - pago_base) * bono, con bono = tiempo sobrante / (FRACCION_BONO * límite)
#     (acotado a 1): llegar sobrado de tiempo paga el máximo;
#   - solo una (se acabó el tiempo): PAGO_PARCIAL del pago base; ninguna: 0.

import math
import random
from dataclasses import dataclass

N_ENTREGAS = 2
RADIO_ENTREGA = 3.5              # m: pasar por encima del punto (con holgura para la moto)
DISTANCIA_MINIMA = 35.0          # m entre la salida y la 1.ª entrega y entre las dos entregas
VELOCIDAD_REFERENCIA = 6.0       # m/s medios en moto contando curvas y frenadas (la moto llega a 16 m/s)
MARGEN_S = 25.0                  # s extra para arrancar, orientarse y algún choque
LIMITE_MIN_S, LIMITE_MAX_S = 45.0, 150.0
FRACCION_BONO = 0.4              # con un 40 % del tiempo sobrante (o más) se cobra el máximo
PAGO_PARCIAL = 0.4

EN_CURSO, COMPLETADO, AGOTADO, CANCELADO = "en_curso", "completado", "agotado", "cancelado"


@dataclass(frozen=True)
class PuntoEntrega:
    id: str
    lugar: str               # clave del lugar del mapa: la puerta es el punto de entrega
    destinatario: str        # quien recibe (vecino o puesto de trabajo)
    paquete: str             # lo que se lleva, en minúscula con artículo («una caja de medicinas»)


# Pedido concreto de un turno: el punto y sus coordenadas en el mapa activo.
@dataclass(frozen=True)
class Pedido:
    punto: PuntoEntrega
    x: float
    z: float


# Pedidos posibles en `mundo`: los puntos del catálogo cuyo lugar existe en el mapa. Si quedan menos de N_ENTREGAS
# lugares distintos (otro mapa), se añade un cliente genérico por cada lugar del mapa que falte.
def pedidos_posibles(mundo, catalogo):
    pedidos = []
    for punto in catalogo:
        try:
            x, z = mundo.punto_interaccion(punto.lugar)
        except (ValueError, KeyError):
            continue
        pedidos.append(Pedido(punto, float(x), float(z)))
    con_lugar = {p.punto.lugar for p in pedidos}
    if len(con_lugar) < N_ENTREGAS:
        for lugar in mundo.lugares():
            if lugar in con_lugar:
                continue
            try:
                x, z = mundo.punto_interaccion(lugar)
            except (ValueError, KeyError):
                continue
            pedidos.append(Pedido(PuntoEntrega(f"generico_{len(pedidos)}", lugar, "Cliente", "un paquete"),
                                  float(x), float(z)))
    return pedidos


# Elige N_ENTREGAS pedidos al azar (`rng`: random.Random) en lugares distintos, lejos de la salida (x0, z0) y entre sí
# (DISTANCIA_MINIMA). Si el mapa no da para tanto, relaja la distancia. Lista vacía si no hay pedidos.
def elegir_pedidos(posibles, x0, z0, rng=None, n=N_ENTREGAS, distancia=DISTANCIA_MINIMA):
    rng = rng or random.Random()
    for minimo in (distancia, distancia / 2, 0.0):
        mezclados = list(posibles)
        rng.shuffle(mezclados)
        elegidos, previo = [], (x0, z0)
        for pedido in mezclados:
            if any(p.punto.lugar == pedido.punto.lugar for p in elegidos):
                continue
            if math.hypot(pedido.x - previo[0], pedido.z - previo[1]) < minimo:
                continue
            elegidos.append(pedido)
            previo = (pedido.x, pedido.z)
            if len(elegidos) == n:
                return elegidos
    return []


# Segundos para hacer el recorrido de `metros` (salida -> 1.ª -> 2.ª por la ruta del GPS), acotado.
def tiempo_limite(metros):
    try:
        metros = max(0.0, float(metros))
    except (TypeError, ValueError):
        metros = 0.0
    return max(LIMITE_MIN_S, min(LIMITE_MAX_S, round(MARGEN_S + metros / VELOCIDAD_REFERENCIA)))


class TurnoEntregas:

    def __init__(self, trabajo, pedidos, limite_s):
        if not pedidos:
            raise ValueError("un turno de entregas necesita al menos un pedido")
        self.trabajo = trabajo
        self.pedidos = list(pedidos)
        self.limite_s = float(limite_s)
        self._t = 0.0
        self._hechas = 0
        self.estado = EN_CURSO

    # -- Reloj --

    def avanzar(self, dt):
        if self.estado != EN_CURSO:
            return
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        self._t = min(self._t + dt, self.limite_s)
        if self._t >= self.limite_s:
            self.estado = AGOTADO

    def tiempo_restante(self):
        return max(0.0, self.limite_s - self._t)

    def terminado(self):
        return self.estado != EN_CURSO

    def cancelar(self):
        if self.estado == EN_CURSO:
            self.estado = CANCELADO

    # -- Entregas --

    def entregas_hechas(self):
        return self._hechas

    # Pedido que toca llevar ahora (None si se terminó).
    def pedido_actual(self):
        if self.estado != EN_CURSO or self._hechas >= len(self.pedidos):
            return None
        return self.pedidos[self._hechas]

    # El jugador está en (x, z): si pisa el punto del pedido actual, lo entrega. Devuelve el Pedido entregado o None.
    def llegar(self, x, z):
        pedido = self.pedido_actual()
        if pedido is None or math.hypot(x - pedido.x, z - pedido.z) > RADIO_ENTREGA:
            return None
        self._hechas += 1
        if self._hechas >= len(self.pedidos):
            self.estado = COMPLETADO
        return pedido

    # -- Resultado --

    def rendimiento(self):
        if self._hechas >= len(self.pedidos):
            bono = self.tiempo_restante() / max(1e-6, FRACCION_BONO * self.limite_s)
            return max(0.0, min(1.0, bono))
        return 0.0

    def resultado(self):
        t = self.trabajo
        if self._hechas >= len(self.pedidos):
            pago = round(t.pago_base + (t.pago_max - t.pago_base) * self.rendimiento())
        elif self._hechas > 0:
            pago = round(t.pago_base * PAGO_PARCIAL * self._hechas)
        else:
            pago = 0
        return {"entregas": self._hechas, "aciertos": self._hechas, "errores": 0, "rendimiento": self.rendimiento(),
                "pago": pago, "fatiga": t.fatiga}
