# Segundo botón de parkour en la terminal del caso (Ursina). La interfaz del caso (frontend/casos_interfaz.py, que no se
# toca) solo tiene una puerta al parkour, la que declara el caso; este botón añade las de backend/datos/parkour_enlaces.json
# (hoy: la granja de bots, sector_2, que se desbloquea al cruzar el Sector corrupto 1).
#
# Va arriba a la derecha, sobre el panel de evidencias (el único hueco libre en la interfaz de siempre y en la de novela
# visual), y se abre con la tecla U o con clic. Bloqueado, dice qué falta; completado, se puede repetir.
# La escena del mundo digital lo crea con preparar() y le pasa las teclas con tecla(); lanza el nivel con el mismo
# camino que el botón de siempre (escena.al_pedir_parkour), que al terminar devuelve a la misma sesión del caso.
#
# APAGADO: ALCALDE_PARKOUR_SEGUNDO=0 (o PARKOUR_SEGUNDO = False). Sin enlaces para el caso, no hay botón.

from ursina import Entity, Text

from backend.datos import parkour_loader
from backend.logica import enlace_parkour_extra as extra
from frontend import banderas_visuales as bv
from frontend import estilo
from frontend.componentes import BotonSecundario, escala_fuente, rgb

PARKOUR_SEGUNDO = True
VARIABLE = "ALCALDE_PARKOUR_SEGUNDO"
TECLA = "u"
POSICION = (0.665, 0.462)
ANCHO, ALTO = 0.44, 0.06


def activo():
    return bv._leer(PARKOUR_SEGUNDO, VARIABLE)      # es contenido del juego, no un adorno: no depende de la bandera maestra


def preparar(escena, caso, previo=None):
    """Botón para el caso abierto (o None si no hay puerta extra / está apagado). Reutiliza el anterior si existe."""
    if not activo() or getattr(escena, "al_pedir_parkour", None) is None:
        if previo is not None:
            previo.enabled = False
        return None
    enlaces = extra.de_caso(extra.cargar(), getattr(caso, "id", ""), parkour_loader.listar_niveles())
    if not enlaces:
        if previo is not None:
            previo.enabled = False
        return None
    boton = previo if previo is not None else SegundoBotonParkour(escena)
    boton.fijar(enlaces[0])
    return boton


class SegundoBotonParkour(Entity):

    def __init__(self, escena, **opciones):
        super().__init__(parent=escena.interfaz, **opciones)
        self.escena = escena
        self.enlace = None
        self.estado = extra.DISPONIBLE
        self.boton = BotonSecundario("", al_clic=self.abrir, ancho=ANCHO, alto=ALTO, parent=self)
        self.boton.position = (*POSICION, 0)
        self.etiqueta = Text("", parent=self, origin=(-0.5, 0), position=(POSICION[0] - ANCHO / 2 + 0.02, POSICION[1], -0.02),
                             scale=escala_fuente(15), color=rgb(estilo.COLOR_BOTON_TEXTO))
        self._base = escala_fuente(15)

    def fijar(self, enlace):
        self.enlace = enlace
        gs = getattr(self.escena, "_gs", None)
        recompensa = parkour_loader.cargar_nivel(enlace.nivel).recompensa.get("evidencia")
        self.estado = extra.estado(enlace, gs, recompensa)
        cadena = extra.rotulo(enlace, self.estado, TECLA)
        try:
            from frontend import diseno_adaptable
            plan = diseno_adaptable.ajustar_texto(self.etiqueta, ANCHO - 0.04, escala_base=self._base, escala_min=0.7,
                                                  max_lineas=1, cadena=cadena)
            if plan is None:
                self.etiqueta.text = cadena
        except Exception:                # noqa: BLE001
            self.etiqueta.text = cadena
        self.etiqueta.color = rgb(estilo.COLOR_TEXTO_TENUE if self.estado == extra.BLOQUEADO else estilo.COLOR_BOTON_TEXTO)
        self.enabled = True

    def tecla(self, key):
        """True si la pulsación era suya (la escena no la procesa más)."""
        if key != TECLA or not self.enabled:
            return False
        self.abrir()
        return True

    def abrir(self):
        escena = self.escena
        if self.enlace is None or getattr(escena, "_bloqueo", False):
            return False
        self.fijar(self.enlace)                  # el estado se recalcula al pulsar (la evidencia pudo llegar después)
        if self.estado == extra.BLOQUEADO:
            escena.interfaz.mostrar_mensaje(self.enlace.bloqueado or "Aún no está disponible.")
            return False
        sesion = getattr(escena, "_sesion", None)
        escena._evidencias_antes_parkour = set(sesion.evidencias_en_mano()) if sesion is not None else None
        if escena.al_pedir_parkour(self.enlace.nivel):
            return True
        escena._evidencias_antes_parkour = None
        escena.interfaz.mostrar_mensaje("El parkour no está disponible ahora.")
        return False
