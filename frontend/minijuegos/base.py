# Clase base de los minijuegos de verificar (Ursina). Pone el encabezado (título del minijuego y el rumor a verificar, con el texto
# real de la misión), el pie con las teclas, el foco de teclado sobre una lista de «focables» (tarjetas y botones) y la regla de
# «terminar una sola vez». Cada minijuego concreto implementa construir(), tecla_propia(), avanzar_propio().
#
# INTERFAZ COMÚN: empezar(contexto) / tecla(k) / avanzar(dt) / terminar(resultado). La escena (EscenaMinijuego) los llama; este
# módulo no sabe nada del flujo, del lote ni del backend: solo entrega un ResultadoMinijuego a contexto["al_terminar"].
#
# Zonas de pantalla (camera.ui, centro 0,0; alto 1, ancho ~1,78):
#   encabezado  y 0,50 .. 0,36   |   contenido  y 0,34 .. -0,27   |   banner de resultado de la escena  y -0,28 .. -0,45
#   pie con teclas  y -0,485

from ursina import Entity

from frontend import estilo
from frontend.componentes import a_unidades
from frontend.minijuegos import ui

Y_ENCABEZADO = 0.47
Y_CONTENIDO_ARRIBA = 0.30
Y_CONTENIDO_ABAJO = -0.27
ANCHO_UTIL = 1.62               # ancho del contenido (queda margen a ambos lados)


class Minijuego(Entity):

    TITULO = ""
    AYUDA = "Flechas: moverte   Enter o Espacio: elegir   Clic: elegir con el ratón"

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.contexto = None
        self.caso = None
        self.mision = None
        self.azar = None
        self.terminado = False
        self.resultado = None
        self.focables = []         # tarjetas / botones con fijar_foco(); el orden es el del teclado
        self.foco = 0
        self.partida = None        # objeto de lógica pura del minijuego

    # -- Ciclo de vida --

    def empezar(self, contexto):
        self.contexto = contexto
        self.caso = contexto["caso"]
        self.mision = contexto.get("mision")
        self.azar = contexto.get("azar")
        self.terminado = False
        self.resultado = None
        self._encabezado()
        self.construir()
        self._pintar_foco()

    def construir(self):
        raise NotImplementedError

    def terminar(self, resultado):
        """Entrega el resultado a la escena UNA sola vez."""
        if self.terminado:
            return
        self.terminado = True
        self.resultado = resultado
        self._pintar_foco()                    # sin anillo de foco en la revisión
        self.al_terminar_propio(resultado)
        callback = (self.contexto or {}).get("al_terminar")
        if callback is not None:
            callback(resultado)

    def al_terminar_propio(self, resultado):
        """Gancho: cada minijuego muestra aquí su revisión (qué estaba bien y por qué)."""

    # -- Encabezado y pie --

    def _encabezado(self):
        ui.texto(self, self.TITULO, 26, ANCHO_UTIL, estilo.COLOR_TEXTO, (-ANCHO_UTIL / 2, Y_ENCABEZADO), negrita=True)
        rumor = getattr(self.mision, "rumor", "") or self.caso.get("intro", "")
        self.rumor = ui.texto(self, "Rumor a verificar: «" + rumor + "»", 17, ANCHO_UTIL, estilo.COLOR_ACENTO,
                              (-ANCHO_UTIL / 2, Y_ENCABEZADO - a_unidades(36)))
        self.pie = ui.texto(self, self.AYUDA, 14, ANCHO_UTIL, estilo.COLOR_TEXTO_TENUE,
                            (-ANCHO_UTIL / 2, -0.462))

    # -- Foco de teclado --

    def _pintar_foco(self):
        for i, f in enumerate(self.focables):
            if hasattr(f, "fijar_foco"):
                f.fijar_foco(i == self.foco and not self.terminado)

    def mover_foco(self, delta):
        if not self.focables:
            return
        self.foco = (self.foco + delta) % len(self.focables)
        self._pintar_foco()

    def poner_foco(self, i):
        if 0 <= i < len(self.focables) and i != self.foco:
            self.foco = i
            self._pintar_foco()

    def activar_foco(self):
        f = self.focables[self.foco] if self.focables else None
        if f is None:
            return
        if getattr(f, "al_clic", None) is not None and getattr(f, "habilitada", getattr(f, "habilitado", True)):
            f.al_clic()

    # -- Entrada: la escena reenvía las teclas y el tiempo --

    def tecla(self, k):
        if self.terminado:
            return False
        if k in ("down arrow", "right arrow", "tab"):
            self.mover_foco(1)
            return True
        if k in ("up arrow", "left arrow", "shift+tab"):
            self.mover_foco(-1)
            return True
        if k in ("enter", "space", "return"):
            self.activar_foco()
            return True
        return self.tecla_propia(k)

    def tecla_propia(self, k):
        return False

    def avanzar(self, dt):
        if not self.terminado:
            self.avanzar_propio(dt)

    def avanzar_propio(self, dt):
        pass
