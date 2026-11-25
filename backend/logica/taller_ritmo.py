# Turno de taller con ritmo (modelo puro, sin ursina): sustituye a la SECUENCIA estática en el taller de Beto.
# Las flechas llegan una tras otra por un carril hasta un recuadro; hay que pulsar la flecha (o W A S D) mientras está
# dentro del recuadro. Acierto = un martillazo sobre la pieza. Pulsar otra flecha con la nota en el recuadro, o dejarla
# pasar, es un fallo: la pieza queda con un defecto y baja la calidad.
#
# Ritmo: la primera nota llega a los PRIMERA_LLEGADA_S; las siguientes, cada INTERVALO_INICIAL_S al principio y cada
# INTERVALO_FINAL_S al final del turno (acelera poco a poco). Cada nota tarda VIAJE_S en cruzar el carril, así que se
# ven 2-3 por delante: da tiempo a leer la siguiente.
#
# Calidad = aciertos / notas. Pago = pago_max * calidad (el pago_base del puesto no se usa: sin aciertos no hay paga).
# API como TurnoTrabajo (avanzar, tiempo_restante, terminado, accion, resultado) más notas_en_carril() y
# sacar_eventos() para la vista (frontend/taller_vista.py).

import math
import random
from dataclasses import dataclass, field

VIAJE_S = 3.0                 # s que tarda una nota desde que aparece hasta el recuadro
VENTANA_S = 0.32              # s antes o después de la llegada en que la nota está «dentro» del recuadro
PRIMERA_LLEGADA_S = 3.5
INTERVALO_INICIAL_S = 1.5
INTERVALO_FINAL_S = 1.05
MARGEN_FINAL_S = 1.2          # la última nota llega como muy tarde a falta de esto
SALIDA_VISIBLE = 0.12         # fracción del carril que se sigue viendo una nota que ya pasó el recuadro

ACIERTO, FALLO, PASADA = "acierto", "fallo", "pasada"

# Calidad -> etiqueta visible (de mayor a menor umbral).
NIVELES_CALIDAD = ((0.9, "Perfecta"), (0.7, "Buena"), (0.45, "Con defectos"), (0.0, "Chatarra"))


@dataclass
class Nota:
    indice: int
    direccion: str
    llegada: float
    estado: str = None            # None = pendiente; ACIERTO, FALLO (otra tecla) o PASADA (no se pulsó)
    resuelta_en: float = field(default=None)


def etiqueta_calidad(calidad):
    for umbral, nombre in NIVELES_CALIDAD:
        if calidad >= umbral:
            return nombre
    return NIVELES_CALIDAD[-1][1]


# Momentos de llegada de las notas en un turno de `duracion` s.
def llegadas(duracion):
    tiempos, t = [], PRIMERA_LLEGADA_S
    fin = duracion - MARGEN_FINAL_S
    while t <= fin:
        tiempos.append(t)
        avance = min(1.0, t / max(duracion, 1e-6))
        t += INTERVALO_INICIAL_S + (INTERVALO_FINAL_S - INTERVALO_INICIAL_S) * avance
    return tiempos


class TurnoRitmo:

    # trabajo: Trabajo (opciones = direcciones). piezas: repertorio (backend/datos/piezas_taller.py).
    # velocidad: multiplica la rapidez con que las notas cruzan el carril (1 = VIAJE_S de siempre; el taller 3D pasa
    # 1,2 con ALCALDE_TALLER3D_VELOCIDAD). Solo cambia el viaje: el ritmo de llegadas y la ventana son los mismos.
    def __init__(self, trabajo, semilla=0, piezas=None, velocidad=1.0):
        if piezas is None:
            from backend.datos.piezas_taller import PIEZAS_TALLER
            piezas = PIEZAS_TALLER
        valida = isinstance(velocidad, (int, float)) and not isinstance(velocidad, bool) and math.isfinite(velocidad)
        self.viaje_s = VIAJE_S / velocidad if valida and velocidad > 0 else VIAJE_S
        self.trabajo = trabajo
        self._rng = random.Random(semilla)
        self.pieza = self._rng.choice(tuple(piezas))
        self._t = 0.0
        self.notas = []
        anterior = None
        for i, llegada in enumerate(llegadas(trabajo.duracion_s)):
            # Nunca tres iguales seguidas: se lee mejor el cambio.
            opciones = [d for d in trabajo.opciones if d != anterior] if self._rng.random() < 0.75 else list(
                trabajo.opciones)
            direccion = self._rng.choice(opciones)
            anterior = direccion
            self.notas.append(Nota(i, direccion, llegada))
        self._eventos = []

    # -- Reloj --

    def avanzar(self, dt):
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        self._t = min(self._t + dt, self.trabajo.duracion_s)
        for nota in self.notas:
            if nota.estado is None and self._t > nota.llegada + VENTANA_S:
                self._resolver(nota, PASADA)

    def tiempo(self):
        return self._t

    def tiempo_restante(self):
        return max(0.0, self.trabajo.duracion_s - self._t)

    def terminado(self):
        return self._t >= self.trabajo.duracion_s

    # -- Notas --

    def _resolver(self, nota, estado):
        nota.estado, nota.resuelta_en = estado, self._t
        self._eventos.append((estado, nota))

    # Primera nota sin resolver (o None).
    def siguiente(self):
        return next((n for n in self.notas if n.estado is None), None)

    def en_ventana(self, nota):
        return nota is not None and abs(self._t - nota.llegada) <= VENTANA_S

    # Posición en el carril de una nota: 1 = acaba de aparecer, 0 = en el recuadro, < 0 = ya lo pasó.
    def posicion(self, nota):
        return (nota.llegada - self._t) / self.viaje_s

    # Notas pendientes que se ven en el carril, con su posición: [(nota, posicion)].
    def notas_en_carril(self):
        return [(n, self.posicion(n)) for n in self.notas
                if n.estado is None and -SALIDA_VISIBLE <= self.posicion(n) <= 1.0]

    # Eventos desde la última llamada: [(ACIERTO|FALLO|PASADA, nota)]. La vista los usa para animar.
    def sacar_eventos(self):
        eventos, self._eventos = self._eventos, []
        return eventos

    # Una tecla de dirección. True = acierto. Fuera del recuadro (o con el turno terminado) no cuenta.
    def accion(self, entrada):
        if self.terminado() or not isinstance(entrada, str) or entrada not in self.trabajo.opciones:
            return False
        nota = self.siguiente()
        if not self.en_ventana(nota):
            return False
        acierto = entrada == nota.direccion
        self._resolver(nota, ACIERTO if acierto else FALLO)
        return acierto

    # -- Resultado --

    def aciertos(self):
        return sum(1 for n in self.notas if n.estado == ACIERTO)

    def errores(self):
        return sum(1 for n in self.notas if n.estado in (FALLO, PASADA))

    def resueltas(self):
        return sum(1 for n in self.notas if n.estado is not None)

    # Fracción de la pieza ya trabajada (0..1): avanza con cada nota, se acierte o no.
    def progreso(self):
        return self.resueltas() / max(1, len(self.notas))

    # Calidad (0..1) de lo trabajado hasta ahora; al final, la de la pieza entera.
    def calidad(self):
        resueltas = self.resueltas()
        return self.aciertos() / resueltas if resueltas else 1.0

    def rendimiento(self):
        return self.aciertos() / max(1, len(self.notas))

    def resultado(self):
        rendimiento = self.rendimiento()
        return {
            "aciertos": self.aciertos(),
            "errores": self.errores(),
            "rendimiento": rendimiento,
            "calidad": rendimiento,
            "pieza": self.pieza.nombre,
            "pago": round(self.trabajo.pago_max * rendimiento),
            "fatiga": self.trabajo.fatiga,
        }
