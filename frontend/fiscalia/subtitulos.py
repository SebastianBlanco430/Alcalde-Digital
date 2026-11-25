# Subtítulos del caso de Fiscalía v2 (Ursina, en camera.ui): franja inferior (y <= -0,30, ancho <= 1,2) con el nombre de
# quien habla y su línea letra a letra; «»» parpadea cuando la línea terminó. Narrador (sin personaje): sin nombre y en
# tono tenue. Encima, la frase del jugador (`dice`) durante 1,6 s en cian entre comillas; una acotación «(…)» va tal cual,
# en gris y sin comillas. Reducir movimiento: el texto sale de golpe y «»» no parpadea.

from ursina import Entity, Text

from frontend import estilo, tipografia
from frontend.componentes import escala_fuente, rgb, panel_piel
from frontend.fiscalia import ui_calculos as uc
from frontend.fiscalia.rueda import ajustar, ancho_real

ANCHO, ALTO = 1.2, 0.168
POS = (0.0, -0.40)
X0 = -ANCHO / 2 + 0.035
Y_NOMBRE = ALTO / 2 - 0.026
Y_TEXTO = ALTO / 2 - 0.05
POS_DICE = (0.0, -0.287)
CIAN = estilo.ACENTO_SECUNDARIO


class Subtitulos(Entity):

    def __init__(self, **opciones):
        super().__init__(position=(*POS, 0), **opciones)
        self.panel = panel_piel(self, ANCHO, ALTO, tono=estilo.COLOR_PANEL)
        self.nombre = Text("", parent=self, origin=(-0.5, 0), position=(X0, Y_NOMBRE, -0.01),
                           scale=escala_fuente(uc.TAM["nombre"]), font=tipografia.fuente_piel(titulo=True),
                           color=rgb(estilo.COLOR_ACENTO))
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), position=(X0, Y_TEXTO, -0.01),
                          scale=escala_fuente(uc.TAM["subtitulo"]), color=rgb(estilo.COLOR_TEXTO))
        self.texto.line_height = 1.15
        self.siguiente = Text("»", parent=self, origin=(0, 0), position=(ANCHO / 2 - 0.03, -ALTO / 2 + 0.024, -0.01),
                              scale=escala_fuente(22), font=tipografia.fuente_piel(titulo=True), color=rgb(estilo.COLOR_ACENTO),
                              enabled=False)
        self.dice = Text("", parent=self, origin=(0, 0), position=(POS_DICE[0], POS_DICE[1] - POS[1], -0.01),
                         scale=escala_fuente(uc.TAM["dice"]), font=tipografia.fuente_piel(titulo=True), color=rgb(CIAN),
                         enabled=False)
        self.dice_fondo = panel_piel(self, 0.5, 0.05, tono=estilo.TINTA, sombra=False, borde_px=2,
                                      position=(POS_DICE[0], POS_DICE[1] - POS[1], -0.005), enabled=False)
        self._completo = ""
        self._t = 0.0
        self._espera = 0.0
        self._t_dice = None
        self._mostrar_siguiente = False

    # -- API --

    def decir(self, nombre, texto, instantaneo=False, espera=0.0, reducir=False):
        """Empieza una línea. `instantaneo`: de golpe (rueda que vuelve a salir). `espera`: s antes de escribir."""
        narrador = not nombre
        self.nombre.text = nombre or ""
        self.nombre.enabled = not narrador
        self.texto.y = Y_TEXTO if not narrador else ALTO / 2 - 0.03
        self.texto.color = rgb(estilo.COLOR_TEXTO if not narrador else estilo.COLOR_TEXTO_TENUE)
        max_lineas = 3 if not narrador else 4
        ajustar(self.texto, str(texto or ""), ANCHO - 0.07, uc.TAM["subtitulo"], max_lineas=max_lineas)
        self._completo = self.texto.text
        self._t = 0.0
        self._espera = 0.0 if (instantaneo or reducir) else max(0.0, espera)
        if instantaneo or reducir:
            self._t = 1e6
        else:
            self.texto.text = ""
        self.siguiente.enabled = False
        self.enabled = True

    def completa(self):
        return self._espera <= 0 and len(self.texto.text) >= len(self._completo)

    def completar(self):
        self._espera = 0.0
        self._t = 1e6
        self.texto.text = self._completo

    def t_linea(self):
        return self._t if self._espera <= 0 else 0.0

    def largo(self):
        return len(self._completo)

    def fijar_siguiente(self, valor):
        self._mostrar_siguiente = bool(valor)

    def decir_jugador(self, texto, reducir=False):
        cadena = uc.texto_dice(texto)
        if not cadena:
            return
        acotacion = uc.es_acotacion(cadena)
        ajustar(self.dice, cadena, ANCHO - 0.1, uc.TAM["dice"], max_lineas=2)
        self.dice.color = rgb(estilo.COLOR_TEXTO_TENUE if acotacion else CIAN)
        self.dice.enabled = True
        ancho = min(ANCHO, ancho_real(self.dice) + 0.05)
        lineas = max(1, self.dice.text.count("\n") + 1)
        self.dice_fondo.scale = (ancho / 0.5, (0.02 + 0.034 * lineas) / 0.05)
        self.dice_fondo.enabled = True
        self._t_dice = 0.0

    def hablando_jugador(self):
        """s que le quedan a la frase del jugador (0 si no hay)."""
        return 0.0 if self._t_dice is None else max(0.0, uc.DUR_DICE - self._t_dice)

    # -- Frame --

    def avanzar(self, dt, reducir=False):
        if self._espera > 0:
            self._espera -= dt
        else:
            self._t += dt
            n = uc.letras_visibles(self._t, len(self._completo), reducir=reducir)
            if len(self.texto.text) != n:
                self.texto.text = self._completo[:n]
        visible = self._mostrar_siguiente and self.completa()
        if visible and not reducir:
            visible = int(self._t * 2) % 2 == 0
        self.siguiente.enabled = visible
        if self._t_dice is not None:
            self._t_dice += dt
            if self._t_dice >= uc.DUR_DICE:
                self._t_dice = None
                self.dice.enabled = self.dice_fondo.enabled = False
