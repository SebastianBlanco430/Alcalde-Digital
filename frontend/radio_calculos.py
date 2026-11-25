# Rádio Comunitária: la parte PURA (no importa ursina). Ver frontend/radio_emision.py (lo que dibuja),
# frontend/radio_registro.py (el enganche) y backend/logica/radio_guion.py (qué dice). Hilo: docs/HILO_CONDUCTOR.md.
#
# CUÁNDO EMITE (ControlRadio.paso). Sin aviso previo, en el primer momento LIBRE:
#   - NOCHE: con la noche pendiente (el reloj parado a las 20:00 de los días 1-6; en feria, al cerrar las misiones del
#     día). La emisión de la noche sigue, en la misma pantalla negra, con la de la MAÑANA del día siguiente: entre las dos
#     se salta la noche (flujo.pasar_noche) y el cielo amanece detrás del negro.
#   - MAÑANA: la del día que aún no la tuvo (el día 1, al empezar; tras «Continuar», la del día restaurado).
#   - Día 7: no hay noche; el puente antes del final lo pone radio_registro sobre pintar_final.
# LIBRE = el tiempo de la partida correría (reloj_calculos.motivo_de_pausa es None: sin minijuego, diálogo, dilema,
# teléfono, mapa, pausa, cinemática ni fundido) durante ESPERA_LIBRE s seguidos (así no pisa la intro, que se abre un
# instante después de entrar al mundo). Caminar hacia una misión es libre: se emite y la misión sigue activa.
#
#   control = ControlRadio()
#   control.paso(dt, dia, noche_pendiente, terminada, libre) -> None | ("noche", dia) | ("manana", dia)
#   control.empezar() / control.terminar(tipo, dia)
#   vinetas_de(lineas, rotulo, lectura)                      -> viñetas para cinematica_final.crear_vinetas

from backend.logica import radio_guion

ESPERA_LIBRE = 1.5          # s seguidos de mundo libre antes de emitir
HORA_SILENCIO = 19.5        # desde aquí (y hasta la emisión de la noche) no se anuncian misiones nuevas
FONDO = (14, 14, 18)        # «pantalla negra» de la emisión
TONO_RADIO = (196, 92, 60)


class ControlRadio:

    def __init__(self):
        self.mananas = set()        # días cuya mañana ya se emitió
        self.noches = set()         # días cuya noche ya se emitió
        self.en_emision = False
        self._libre_s = 0.0

    def paso(self, dt, dia, noche_pendiente, terminada, libre):
        if self.en_emision:
            return None
        self._libre_s = self._libre_s + max(0.0, float(dt)) if libre else 0.0
        if self._libre_s < ESPERA_LIBRE or terminada:
            return None
        if noche_pendiente and dia not in self.noches:
            return ("noche", dia)
        if not noche_pendiente and dia not in self.mananas:
            return ("manana", dia)
        return None

    def empezar(self):
        self.en_emision = True

    # Fin de una emisión. La de la noche lleva dentro la mañana del día siguiente.
    def terminar(self, tipo, dia):
        self.en_emision = False
        self._libre_s = 0.0
        if tipo == "noche":
            self.noches.add(dia)
            self.mananas.add(dia + 1)
        else:
            self.mananas.add(dia)


def en_silencio(hora):
    """¿Silencio de la noche? De las 19:30 en adelante (el día se cierra a las 20:00 y la radio salta la noche)."""
    return float(hora) % 24.0 >= HORA_SILENCIO


def rotulo_de(guion):
    """«Rádio Comunitária · Jandira Lopes» (sin locutora: solo la emisora)."""
    return f"{guion.emisora} · {guion.locutora}" if guion.locutora else guion.emisora


def vinetas_de(lineas, rotulo, lectura=None, marca=None):
    """Una viñeta de cómic por línea: fondo negro, la radio dibujada y el globo con la línea. `segundos` = regla de
    lectura. `marca` (opcional) se añade a cada viñeta (la usa radio_registro para saber cuándo empieza la mañana)."""
    vinetas = []
    for linea in lineas:
        vineta = {"fondo": list(FONDO), "figuras": [{"tipo": "radio", "x": 0.0, "y": 0.14, "color": list(TONO_RADIO)}],
                  "titulo": rotulo, "texto": linea, "segundos": radio_guion.segundos_lectura(linea, lectura)}
        if marca is not None:
            vineta.update(marca)
        vinetas.append(vineta)
    return vinetas


def segundos_totales(vinetas):
    return sum(float(v.get("segundos", 0.0)) for v in vinetas)
