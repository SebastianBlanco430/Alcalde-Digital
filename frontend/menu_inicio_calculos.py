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


# -- Submenú «Multijugador» (docs/MENU_MULTIJUGADOR.md) --
# BANDERA: ALCALDE_MENU_MULTIJUGADOR (encendida por defecto). «Empezar» / «Partida nueva» va directo a elegir rol con 1
# jugador; «Multijugador» (siempre a la vista) abre «Local por turnos» (2, 3 o 4 jugadores en el mismo computador) y
# «En línea» (solo con ONLINE). Esc / B vuelve un nivel. =0 deja el menú de siempre: «En línea» y la pregunta
# «¿Cuántos jugadores?» en la selección de rol.

import os

MENU_MULTIJUGADOR = True
VARIABLE_MULTIJUGADOR = "ALCALDE_MENU_MULTIJUGADOR"
_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")

PRINCIPAL, MULTIJUGADOR, LOCAL = "principal", "multijugador", "local"
LOCAL_TURNOS, EN_LINEA, ATRAS = "local_turnos", "en_linea", "atras"
TEXTO_MULTIJUGADOR = "Multijugador"
CANTIDADES_LOCALES = (2, 3, 4)
TITULOS = {MULTIJUGADOR: "Multijugador", LOCAL: "Local por turnos"}


def multijugador_activo(entorno=None):
    """¿Submenú «Multijugador»? ALCALDE_MENU_MULTIJUGADOR manda sobre MENU_MULTIJUGADOR."""
    valor = (os.environ if entorno is None else entorno).get(VARIABLE_MULTIJUGADOR, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    return bool(MENU_MULTIJUGADOR)


def id_cantidad(n):
    return f"jugadores_{n}"


def opciones_de(nivel, hay_online):
    """(id, texto) de cada opción de un submenú, en orden; «Atrás» siempre al final. PRINCIPAL no tiene: es el menú de
    siempre de la escena."""
    if nivel == MULTIJUGADOR:
        ids = [(LOCAL_TURNOS, "Local por turnos")] + ([(EN_LINEA, "En línea")] if hay_online else [])
        return ids + [(ATRAS, "Atrás")]
    if nivel == LOCAL:
        return [(id_cantidad(n), f"{n} jugadores") for n in CANTIDADES_LOCALES] + [(ATRAS, "Atrás")]
    return []


def nivel_anterior(nivel):
    """Adónde vuelve Esc / «Atrás»: de «Local por turnos» a «Multijugador» y de ahí al menú principal."""
    return MULTIJUGADOR if nivel == LOCAL else PRINCIPAL


def cantidad_inicial(jugadores, activo, maximo):
    """Jugadores con los que arranca la selección de rol: los que pide el menú (1..maximo); sin pedir, 1 con el submenú
    activo o 0 («¿Cuántos jugadores?», como siempre) sin él."""
    if isinstance(jugadores, int) and not isinstance(jugadores, bool) and 1 <= jugadores <= maximo:
        return jugadores
    return 1 if activo else 0
