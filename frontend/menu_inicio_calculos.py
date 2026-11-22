# Confirmaciones del menú de inicio y de la pausa (puro, sin Ursina; lo usan frontend/escenas/escena_inicio.py y
# frontend/menu_pausa.py).
#   - «Salir» pide «¿Salir del juego?» (EST-011: el mando o Enter cerraban el juego al primer toque).
#   - «Partida nueva» con una partida guardada pide confirmación antes de sobrescribirla (BUG-005).
# El foco empieza SIEMPRE en «No»; Esc (y B del mando, que llega como Esc) responde «No».
# «Sí» con teclado o mando solo vale si la pregunta lleva MIN_ABIERTA_S abierta y el foco MIN_FOCO_SI_S en «Sí»: quien
# aporrea el mando en la Feria no llega a salir (un jugador que de verdad quiere salir lo cumple sin notarlo; si pulsa
# demasiado pronto no pasa nada y vuelve a pulsar). Con el ratón basta MIN_ABIERTA_S.

SALIR = ("¿Salir del juego?", "Sí, salir")
NUEVA = ("¿Empezar una partida nueva?\nSe reemplazará tu partida guardada.", "Sí, empezar")
TEXTO_NO = "No"
TECLAS_NO = ("escape",)
MIN_ABIERTA_S = 0.6
MIN_FOCO_SI_S = 0.5


class Confirmacion:
    """Una pregunta pendiente (o ninguna). `responder(si)` cierra y devuelve la acción a ejecutar (o None)."""

    def __init__(self):
        self.pregunta = None
        self.texto_si = None
        self._al_si = None
        self.edad = 0.0
        self.foco_si = 0.0

    @property
    def abierta(self):
        return self.pregunta is not None

    def pedir(self, contenido, al_si):
        self.pregunta, self.texto_si = contenido
        self._al_si = al_si
        self.edad = self.foco_si = 0.0

    def avanzar(self, dt, foco_en_si):
        """Cada frame con la pregunta abierta: cuánto lleva abierta y cuánto lleva el foco en «Sí»."""
        if not self.abierta:
            return
        self.edad += dt
        self.foco_si = self.foco_si + dt if foco_en_si else 0.0

    def puede_si(self, por_teclado):
        if not self.abierta or self.edad < MIN_ABIERTA_S:
            return False
        return not por_teclado or self.foco_si >= MIN_FOCO_SI_S

    def responder(self, si):
        accion = self._al_si if (si and self.abierta) else None
        self.pregunta = self.texto_si = self._al_si = None
        self.edad = self.foco_si = 0.0
        return accion

    def tecla(self, key):
        """True si la tecla cerró la pregunta con «No»."""
        if self.abierta and key in TECLAS_NO:
            self.responder(False)
            return True
        return False


def necesita_confirmar_nueva(hay_guardado):
    """«Partida nueva» solo pregunta si hay una partida guardada que se perdería."""
    return bool(hay_guardado)
