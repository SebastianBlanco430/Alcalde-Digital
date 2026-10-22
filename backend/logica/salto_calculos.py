# Física vertical del jugador (cálculos puros, sin ursina): salto con Espacio, caída, aterrizaje y el
# seguimiento escalón a escalón del suelo. La posición horizontal (x, z) la sigue resolviendo
# navegacion.py; aquí solo se decide la altura `y` del jugador sobre el suelo que le dan debajo.
#
# Modelo (todo en m y s):
#   - En el suelo la altura persigue al objetivo (la altura del suelo bajo el jugador) con un
#     suavizado corto (RAPIDEZ_ESCALON): sobre peldaños sube y baja escalón a escalón sin deslizar,
#     y sobre terreno suave el retraso es de centímetros. Un salto de altura enorme (teletransporte)
#     se acepta de golpe.
#   - Un SALTO da una velocidad vertical VELOCIDAD_SALTO (la que llega a ALTURA_SALTO con GRAVEDAD);
#     mientras está en el aire la velocidad horizontal no se toca (la maneja el controlador).
#   - COYOTE: se puede saltar hasta TIEMPO_COYOTE s después de salir del suelo (borde de un talud).
#     BUFFER: una pulsación hecha hasta TIEMPO_BUFFER s antes de aterrizar salta al tocar el suelo.
#   - Si el suelo baja de golpe más de CAIDA_MINIMA m por debajo de los pies, no se "pega": se cae.

import math
from dataclasses import dataclass

GRAVEDAD = 24.0               # m/s²: salto ágil, ~0.6 s en el aire
ALTURA_SALTO = 1.1            # m que sube el salto sobre el suelo
VELOCIDAD_SALTO = math.sqrt(2 * GRAVEDAD * ALTURA_SALTO)
TIEMPO_COYOTE = 0.10          # s tras dejar el suelo en que aún se puede saltar
TIEMPO_BUFFER = 0.12          # s que se recuerda una pulsación hecha en el aire
RAPIDEZ_ESCALON = 26.0        # 1/s: suavizado del suelo (a 60 fps cubre ~35 % por frame)
CAIDA_MINIMA = 0.7            # m de desnivel hacia abajo a partir del cual ya no se está en el suelo
SALTO_TELEPORTE = 1.6         # m: diferencia a partir de la cual no se suaviza (se aparece ahí)
VELOCIDAD_CAIDA_MAXIMA = 30.0 # m/s: tope de la velocidad de caída


@dataclass
class EstadoVertical:
    y: float = 0.0
    vy: float = 0.0
    en_aire: bool = False
    desde_suelo: float = 0.0     # s desde que dejó el suelo (para el coyote)
    memoria_salto: float = 0.0   # s que aún "recuerda" una pulsación de salto (buffer)
    salto_usado: bool = False    # ya saltó desde este despegue (sin doble salto)
    listo: bool = False          # ¿y ya se colocó sobre el suelo la primera vez?
    objetivo_previo: float = 0.0 # suelo que había bajo el jugador en el paso anterior
    suave: bool = False          # ¿sigue suavizando el suelo? (lo enciende pisar peldaños, hasta alcanzar el suelo)

    # Coloca al jugador en `y` en el suelo, sin velocidad (reaparición, cinemática, minijuego).
    def reiniciar(self, y=None):
        if y is not None:
            self.y = y
        self.vy = 0.0
        self.en_aire = False
        self.desde_suelo = 0.0
        self.memoria_salto = 0.0
        self.salto_usado = False
        self.listo = y is not None

    # Altura del salto sobre el suelo `objetivo` (0 en el suelo).
    def elevacion(self, objetivo):
        return max(0.0, self.y - objetivo)

    # Un paso de `dt` s con el suelo a `objetivo` m bajo el jugador y `pide_salto` = hubo pulsación de
    # Espacio en este frame. `puede_saltar` = False (teléfono abierto, etc.) borra la pulsación.
    # Devuelve (salto_iniciado, aterrizo): sucesos de ESTE paso.
    # `suavizar=False` pega la altura al suelo sin retraso (terreno suave: el comportamiento de siempre);
    # con True (escalones) la persigue con RAPIDEZ_ESCALON.
    def avanzar(self, objetivo, dt, pide_salto=False, puede_saltar=True, suavizar=True):
        if not self.listo:
            self.reiniciar(objetivo)
            self.objetivo_previo = objetivo
        dt = max(0.0, dt)
        if pide_salto and puede_saltar:
            self.memoria_salto = TIEMPO_BUFFER
        elif not puede_saltar:
            self.memoria_salto = 0.0
        else:
            self.memoria_salto = max(0.0, self.memoria_salto - dt)

        salto = aterrizo = False
        if not self.en_aire:
            diferencia = objetivo - self.y
            if diferencia < -CAIDA_MINIMA:
                self.en_aire = True               # el suelo se fue: cae
                self.vy = 0.0
                self.desde_suelo = 0.0
                self.salto_usado = False
            elif abs(diferencia) > SALTO_TELEPORTE:
                self.y = objetivo
            elif abs(diferencia) < 1e-3 or not suavizar:
                self.y = objetivo
            else:
                self.y += diferencia * (1 - math.exp(-RAPIDEZ_ESCALON * dt))
        else:
            self.desde_suelo += dt

        # ¿arranca un salto? (en el suelo o dentro del coyote, y sin doble salto)
        if (self.memoria_salto > 0 and not self.salto_usado and puede_saltar
                and (not self.en_aire or self.desde_suelo <= TIEMPO_COYOTE)):
            self.vy = VELOCIDAD_SALTO
            self.en_aire = True
            self.salto_usado = True
            self.memoria_salto = 0.0
            salto = True

        if self.en_aire:
            if not salto:
                self.vy = max(-VELOCIDAD_CAIDA_MAXIMA, self.vy - GRAVEDAD * dt)
                self.y += self.vy * dt
            else:
                self.y += self.vy * dt            # el impulso mueve ya en el frame del salto
            if self.y <= objetivo and self.vy <= 0:
                self.y = objetivo                 # aterrizó
                self.vy = 0.0
                self.en_aire = False
                self.desde_suelo = 0.0
                self.salto_usado = False
                aterrizo = True
            elif self.y < objetivo:
                self.y = objetivo                 # el suelo sube más rápido que el salto: no se atraviesa
                self.vy = 0.0
        self.objetivo_previo = objetivo
        return salto, aterrizo
