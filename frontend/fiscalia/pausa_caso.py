# Pausa del caso de Fiscalía v2 y cuadro de confirmación (Ursina, en camera.ui), con el estilo de menu_pausa.py: velo de
# tinta, panel de cómic, botón primario y secundarios con anillo de foco para el teclado y el mando.
#   Confirmacion: título, texto, aviso opcional y dos botones (sí / no). El foco empieza en el botón resaltado:
#                 «sí» (primario), salvo en las de peligro (abandonar), que empiezan en «no». Esc (o B / Start) = «no».
#   PausaCaso:    «Seguir» y «Abandonar caso»; abandonar pide confirmación («El caso se archiva»).
# Teclado: flechas / WASD / Tab mueven el foco; Enter / Espacio activan. El ratón usa los botones directamente.

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import BotonPeligro, BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb
from frontend.fiscalia import ui_calculos as uc
from frontend.fiscalia.rueda import ajustar

ALTO_BOTON = a_unidades(54)
ESPERA_SI = 0.25            # s: un «sí» pulsado justo al abrir (aporreando el mando) no cuenta
TECLAS_ANTES = ("left arrow", "up arrow", "a", "w", "shift tab")
TECLAS_DESPUES = ("right arrow", "down arrow", "d", "s", "tab")
TECLAS_ACTIVAR = ("enter", "space", "gamepad a")
TECLAS_CERRAR = ("escape", "gamepad b", "gamepad start")


def destruir_luego(entidad):
    """Apaga ya y destruye en el siguiente frame: el botón que lo pidió aún está dentro de su propio clic."""
    from ursina import invoke

    from frontend.componentes import destruir_arbol

    def _destruir():
        try:
            if not entidad.is_empty():
                destruir_arbol(entidad)
        except Exception:                # noqa: BLE001  ya destruida con el HUD
            pass
    try:
        entidad.enabled = False
        invoke(_destruir, delay=0.05)
    except Exception:                    # noqa: BLE001
        pass


class _Foco:
    """Foco de teclado sobre una lista de botones de tinta."""

    def __init__(self, botones, indice=0):
        self.botones = list(botones)
        self.indice = indice
        self.aplicar()

    def aplicar(self):
        for i, b in enumerate(self.botones):
            b.fijar_foco(i == self.indice)

    def mover(self, paso):
        """Sin dar la vuelta: con dos botones, «abajo» dos veces se queda en el último (cruceta y flechas)."""
        self.indice = max(0, min(len(self.botones) - 1, self.indice + paso))
        self.aplicar()

    def actual(self):
        return self.botones[self.indice]


class Confirmacion(Entity):
    """Cuadro modal. `al_responder(True|False)` se llama una sola vez."""

    def __init__(self, titulo, texto, si, no, al_responder, peligro=False, aviso="", **opciones):
        super().__init__(**opciones)
        self._al_responder = al_responder
        self._respondido = False
        self._t = 0.0
        Entity(parent=self, model="quad", color=color.rgba32(*estilo.TINTA, 165), scale=(4, 4), z=0.02,
               collider="box")                         # bloquea los clics a lo de detrás
        # `aviso` (pendientes-a, O10): línea extra en ámbar entre el texto y los botones; el panel crece para ella
        extra = 0.10 if aviso else 0.0
        ancho, alto = 0.86, 0.36 + extra
        panel_tinta(self, ancho, alto, tono=estilo.COLOR_PANEL)
        self.titulo = Text("", parent=self, origin=(0, 0), position=(0, 0.115 + extra / 2, -0.01),
                           scale=escala_fuente(uc.TAM["modal_titulo"]), font=tipografia.FUENTE_TITULO,
                           color=rgb(estilo.COLOR_TEXTO))
        ajustar(self.titulo, titulo, ancho - 0.08, uc.TAM["modal_titulo"])
        self.texto = Text("", parent=self, origin=(0, 0), position=(0, 0.035 + extra / 2, -0.01),
                          scale=escala_fuente(uc.TAM["modal_texto"]), color=rgb(estilo.COLOR_TEXTO_TENUE))
        ajustar(self.texto, texto, ancho - 0.08, uc.TAM["modal_texto"], max_lineas=2)
        self.aviso = None
        if aviso:
            self.aviso = Text("", parent=self, origin=(0, 0), position=(0, -0.025, -0.01),
                              scale=escala_fuente(uc.TAM["modal_texto"]), font=tipografia.FUENTE_TITULO,
                              color=rgb(estilo.ESTADO_AVISO))
            ajustar(self.aviso, aviso, ancho - 0.08, uc.TAM["modal_texto"], max_lineas=2)
        y_botones = -0.095 - extra / 2
        clase_si = BotonPeligro if peligro else BotonPrimario
        self.boton_no = BotonSecundario(no, al_clic=lambda: self.responder(False), ancho=0.34, alto=ALTO_BOTON,
                                        tamano_fuente_px=uc.TAM["boton"], parent=self, position=(-0.19, y_botones, -0.01))
        self.boton_si = clase_si(si, al_clic=lambda: self.responder(True), ancho=0.34, alto=ALTO_BOTON,
                                 tamano_fuente_px=uc.TAM["boton"], parent=self, position=(0.19, y_botones, -0.01))
        # el foco empieza en lo que está resaltado: «sí» salvo en las preguntas de peligro (abandonar), que empiezan en «no»
        self.foco = _Foco((self.boton_no, self.boton_si), 0 if peligro else 1)

    def responder(self, si):
        if self._respondido:
            return
        if si and self._t < ESPERA_SI:
            return
        self._respondido = True
        self.enabled = False
        if self._al_responder is not None:
            self._al_responder(bool(si))

    def tecla(self, key):
        if key in TECLAS_CERRAR:
            self.responder(False)
        elif key in TECLAS_ANTES:
            self.foco.mover(-1)
        elif key in TECLAS_DESPUES:
            self.foco.mover(1)
        elif key in TECLAS_ACTIVAR:
            self.responder(self.foco.actual() is self.boton_si)
        return True

    def avanzar(self, dt):
        self._t += dt


class PausaCaso(Entity):
    """«Caso en pausa»: Seguir / Abandonar caso (con confirmación)."""

    def __init__(self, al_seguir, al_abandonar, **opciones):
        super().__init__(**opciones)
        self._al_seguir = al_seguir
        self._al_abandonar = al_abandonar
        Entity(parent=self, model="quad", color=color.rgba32(*estilo.TINTA, 175), scale=(4, 4), z=0.03,
               collider="box")
        ancho, alto = 0.62, 0.42
        panel_tinta(self, ancho, alto, tono=estilo.COLOR_PANEL, z=0.01)
        Text("Caso en pausa", parent=self, origin=(0, 0), position=(0, 0.14, -0.01),
             scale=escala_fuente(uc.TAM["modal_titulo"] + 6), font=tipografia.FUENTE_TITULO,
             color=rgb(estilo.COLOR_TEXTO))
        self.boton_seguir = BotonPrimario("Seguir", al_clic=self.seguir, ancho=0.42, alto=ALTO_BOTON,
                                          tamano_fuente_px=uc.TAM["boton"] + 2, parent=self, position=(0, 0.035, -0.01))
        self.boton_abandonar = BotonSecundario("Abandonar caso", al_clic=self.pedir_abandonar, ancho=0.42,
                                               alto=ALTO_BOTON, tamano_fuente_px=uc.TAM["boton"], parent=self,
                                               position=(0, -0.075, -0.01))
        Text("Esc para seguir", parent=self, origin=(0, 0), position=(0, -0.165, -0.01),
             scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.foco = _Foco((self.boton_seguir, self.boton_abandonar), 0)
        self.confirmacion = None

    def seguir(self):
        if self.confirmacion is not None:
            return
        if self._al_seguir is not None:
            self._al_seguir()

    def pedir_abandonar(self):
        if self.confirmacion is not None:
            return
        self.confirmacion = Confirmacion("¿Abandonar el caso?", "El caso se archiva. No podrás retomarlo.",
                                         "Abandonar", "Seguir con el caso", self._respuesta, peligro=True,
                                         parent=self, z=-0.1)

    def _respuesta(self, si):
        conf, self.confirmacion = self.confirmacion, None
        if conf is not None:
            destruir_luego(conf)
        if si and self._al_abandonar is not None:
            self._al_abandonar()

    def tecla(self, key):
        if self.confirmacion is not None:
            return self.confirmacion.tecla(key)
        if key in TECLAS_CERRAR:
            self.seguir()
        elif key in TECLAS_ANTES:
            self.foco.mover(-1)
        elif key in TECLAS_DESPUES:
            self.foco.mover(1)
        elif key in TECLAS_ACTIVAR:
            self.foco.actual().manejar_clic()
        return True

    def avanzar(self, dt):
        if self.confirmacion is not None:
            self.confirmacion.avanzar(dt)
