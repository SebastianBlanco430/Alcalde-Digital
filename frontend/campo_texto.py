# Campo de texto del lobby online (Ursina): envoltorio de `ursina.prefabs.input_field.InputField` con
# saneado (frontend/campo_texto_calculos.py -> backend.red.saneado), límite de longitud, acentos (NFC),
# pegado seguro (portapapeles saneado, una línea, recortado) y el aspecto de tinta del juego.
#
# Por qué un envoltorio: el InputField de Ursina deja pasar cualquier carácter, no limita lo pegado,
# inserta un salto de línea con Intro y empareja corchetes. Aquí:
#   - cada cambio pasa por `sanear_entrada` (se engancha en `text_field.render`, también con contenido oculto);
#   - el pegado (Ctrl+V / Cmd+V / botón «Pegar») lo hace este módulo, no el TextField;
#   - Intro no escribe nada: avanza al siguiente campo o envía (`al_enviar`);
#   - la fuente del campo es la monoespaciada de Ursina (Vera Mono): trae acentos y ñ (comprobado en ventana).
#
# NO PROBADO con un IME real (chino/japonés/coreano/teclas muertas del teclado) ni con Cmd+V en un teclado
# físico de macOS: se probó con eventos simulados (`text_input`, `app.input('meta-v')`) y el botón «Pegar».
#
# API (compatible con FocoTeclado: esta_habilitado, fijar_foco, bajo_el_raton, manejar_clic):
#   CampoTexto(tipo, valor="", ancho=0.56, marcador="", oculto=False, al_cambiar=fn(texto), al_enviar=fn())
#   .texto  (ya saneado, tal cual se ve)   .valor  (versión final para enviar)   .fijar_texto(t)
#   .activar() / .desactivar() / .activo     .marcar_error(bool)     .pegar() / .copiar()
#   .fijar_oculto(bool)                      .fijar_habilitado(bool)

from ursina import Entity, Text, color, destroy
from ursina.prefabs.input_field import InputField

from frontend import campo_texto_calculos as calc
from frontend import estilo
from frontend.componentes import a_unidades, escala_fuente, panel_tinta, rgb

ALTO_CAMPO = a_unidades(44)
TECLAS_PEGAR = ("control+v", "ctrl+v", "meta-v", "meta+v", "command+v", "control-v", "shift+insert")
Z_CAMPO = -0.012


# ---------------------------------------------------------------------------
# Portapapeles (pyperclip ya lo trae Ursina). Nunca lanza.
# ---------------------------------------------------------------------------
def leer_portapapeles():
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


def copiar_al_portapapeles(texto):
    try:
        import pyperclip
        pyperclip.copy(str(texto))
        return True
    except Exception:
        return False


class CampoTexto(Entity):

    def __init__(self, tipo=calc.TIPO_LIBRE, valor="", ancho=0.56, alto=ALTO_CAMPO, marcador="", oculto=False,
                 limite=None, al_cambiar=None, al_enviar=None, **opciones):
        super().__init__(**opciones)
        self.tipo = tipo
        self.limite = calc.limite_de(tipo) if limite is None else int(limite)
        self.ancho, self.alto = ancho, alto
        self._al_cambiar = al_cambiar
        self.al_enviar = al_enviar
        self._habilitado = True
        self._foco = False
        self._error = False
        self._activo_previo = False
        self._previo = ""

        self.panel = panel_tinta(self, ancho, alto, estilo.COLOR_TARJETA, estilo.RADIO_CHIP_PX, sombra=False,
                                 borde_px=2)
        self.entrada = InputField(parent=self, position=(0, 0, Z_CAMPO), scale=(ancho, alto),
                                  character_limit=self.limite, active=False)
        # El InputField pinta su propio fondo: aquí lo hace el panel de tinta.
        self.entrada.color = color.clear
        self.entrada.highlight_color = color.clear
        self.entrada.pressed_color = color.clear
        tf = self.entrada.text_field
        tf.shortcuts['paste'] = ()           # el pegado lo gestiona este módulo (saneado y límite)
        tf.shortcuts['newline'] = ()         # Intro no escribe: avanza o envía
        tf.shortcuts['newline_alt'] = () if 'newline_alt' in tf.shortcuts else ()
        original = tf.render

        def render():
            self._sanear_vivo()
            original()
            if self._al_cambiar is not None and tf.text != self._previo:
                self._previo = tf.text
                self._al_cambiar(tf.text)
        tf.render = render
        if oculto:
            self.entrada.hide_content = '*'
        self.marcador = None
        if marcador:
            self.marcador = Text(marcador, parent=self, origin=(-0.5, 0), position=(-ancho / 2 + a_unidades(10), 0, -0.02),
                                 scale=escala_fuente(18), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._previo = ""
        if valor:
            self.fijar_texto(valor)
        self._pintar()

    # -- Saneado en vivo: se llama antes de cada render del TextField --
    def _sanear_vivo(self):
        tf = self.entrada.text_field
        actual = tf.text
        limpio = calc.sanear_entrada(self.tipo, actual, self.limite)
        if limpio != actual:
            quitados = len(actual) - len(limpio)
            tf.text = limpio
            tf.cursor.y = 0
            tf.cursor.x = max(0, min(len(limpio), int(tf.cursor.x) - max(0, quitados)))

    # -- Valor --
    @property
    def texto(self):
        return self.entrada.text_field.text

    @property
    def valor(self):
        return calc.valor_final(self.tipo, self.texto)

    def fijar_texto(self, texto):
        self.entrada.text = calc.sanear_entrada(self.tipo, texto, self.limite)
        self._pintar()

    def insertar(self, fragmento, pegado=False):
        tf = self.entrada.text_field
        nuevo, cursor = calc.insertar(self.tipo, tf.text, int(tf.cursor.x), fragmento, self.limite, pegado)
        tf.text = nuevo
        tf.cursor.y = 0
        tf.cursor.x = cursor
        tf.render()
        self._pintar()

    def pegar(self):
        """Pega el portapapeles (saneado y recortado) en la posición del cursor."""
        texto = leer_portapapeles()
        if texto:
            self.insertar(texto, pegado=True)
        return bool(texto)

    def copiar(self):
        return copiar_al_portapapeles(self.texto)

    def fijar_oculto(self, oculto):
        self.entrada.hide_content = '*' if oculto else False
        self.entrada.text_field.render()

    # -- Estado --
    @property
    def activo(self):
        return bool(self.entrada.active)

    def activar(self):
        if self._habilitado:
            self.entrada.active = True

    def desactivar(self):
        self.entrada.active = False

    def marcar_error(self, valor):
        self._error = bool(valor)
        self._pintar()

    def esta_habilitado(self):
        return self._habilitado

    def fijar_habilitado(self, valor):
        self._habilitado = bool(valor)
        if not self._habilitado:
            self.desactivar()
        self._pintar()

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self._pintar()

    def bajo_el_raton(self):
        return bool(self.entrada.hovered)

    def manejar_clic(self):
        self.activar()

    def _pintar(self):
        activo = self.activo
        if self._error:
            borde = estilo.ESTADO_ERROR
        elif activo or self._foco:
            borde = estilo.ESTADO_INFO
        else:
            borde = estilo.TINTA
        self.panel.borde.color = rgb(borde)
        self.panel.fondo.color = rgb(estilo.COLOR_TARJETA if self._habilitado else estilo.COLOR_PANEL)
        if self.marcador is not None:
            self.marcador.enabled = not self.texto and not activo

    # -- Entrada --
    def input(self, key):
        if not self.activo:
            return
        if key in TECLAS_PEGAR:
            self.pegar()
        elif key in ("enter", "return", "keypad enter") and self.al_enviar is not None:
            self.al_enviar()

    def update(self):
        activo = self.activo
        if activo != self._activo_previo:
            self._activo_previo = activo
            self._pintar()

    def on_destroy(self):
        # el TextField cuelga de camera.ui (no de este Entity): hay que destruirlo a mano
        try:
            destroy(self.entrada.text_field)
        except Exception:
            pass
