# Piezas de interfaz compartidas por los minijuegos (Ursina, camera.ui; el aspecto es 16:9: ancho 1,78, alto 1).
# Todo se dibuja con la paleta de frontend/estilo.py y la fuente Atkinson Hyperlegible del proyecto.
#
# ACCESIBILIDAD: ningún estado se distingue SOLO por color. Cada tarjeta lleva una etiqueta de texto («MARCADA», «CORRECTA»,
# «SELECCIONADA»...) y su borde cambia de grosor y de color; el foco de teclado es un borde amarillo grueso + el marcador «>>».
# Se maneja con teclado (flechas, Tab, Enter/Espacio, Esc) y con ratón (clic y cursor encima).
#
# Sin números de indicadores a la vista: aquí solo se pintan palabras, barras sin cifra y marcas.

from panda3d.core import TextNode
from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente, modelo_redondeado, rgb
from frontend.texto import envolver_texto

ANCHO = 16 / 9
LINEA = 1.32                    # separación entre líneas (1 = apretado)
Z_TEXTO = -0.02

COLOR_FOCO = estilo.COLOR_ACENTO
COLOR_OK = estilo.ESTADO_EXITO
COLOR_MAL = estilo.ESTADO_ERROR
COLOR_INFO = estilo.ESTADO_INFO

_medidores = {}


def _medidor(negrita=False):
    if negrita not in _medidores:
        fuente = tipografia.FUENTE_TITULO if negrita else tipografia.FUENTE_TEXTO
        _medidores[negrita] = Text("", enabled=False, font=fuente)
    return _medidores[negrita]


def medir(cadena, px, negrita=False):
    """Ancho (unidades de camera.ui) de `cadena` con una fuente de `px` píxeles de referencia."""
    nodo = TextNode("medida")
    nodo.setFont(_medidor(negrita).font)
    return nodo.calcWidth(cadena) * a_unidades(px)


def lineas_de(texto, px, ancho, negrita=False):
    """Texto envuelto a `ancho` unidades: lista de líneas (respeta los saltos de línea del original)."""
    salida = []
    for parrafo in str(texto).split("\n"):
        salida += envolver_texto(parrafo, lambda c: medir(c, px, negrita), ancho) or [""]
    return salida


def alto_de(n_lineas, px):
    return n_lineas * a_unidades(px) * LINEA


def texto(parent, cadena, px=18, ancho=None, tono=None, posicion=(0, 0), origen=(-0.5, 0.5), negrita=False,
          centrado=False):
    """Text envuelto a `ancho`. `posicion` es la esquina superior izquierda (origen por defecto). Devuelve el Text con
    `.n_lineas` y `.alto`."""
    cadena = str(cadena)
    lineas = lineas_de(cadena, px, ancho, negrita) if ancho else cadena.split("\n")
    entidad = Text("\n".join(lineas), parent=parent, origin=(0, 0.5) if centrado else origen,
                   position=(posicion[0], posicion[1], Z_TEXTO), scale=escala_fuente(px),
                   color=rgb(tono or estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO if negrita else tipografia.FUENTE_TEXTO)
    entidad.line_height = LINEA
    entidad.n_lineas = len(lineas)
    entidad.alto = alto_de(len(lineas), px)
    return entidad


def rect(parent, ancho, alto, tono, posicion=(0, 0), z=0.0, radio_px=6):
    """Rectángulo redondeado de color plano centrado en `posicion`."""
    return Entity(parent=parent, model=modelo_redondeado(ancho, alto, radio_px), scale=(ancho, alto),
                  color=rgb(tono) if isinstance(tono, tuple) else tono, position=(posicion[0], posicion[1], z))


class Tarjeta(Entity):
    """Tarjeta con título pequeño, cuerpo envuelto y una etiqueta de estado en TEXTO. `position` es su CENTRO."""

    ESTADOS = {
        # nombre: (borde RGB, grosor px, etiqueta)
        "normal": (estilo.TINTA, 2, ""),
        "foco": (COLOR_FOCO, 5, ""),
        "marcada": (COLOR_INFO, 5, "MARCADA"),
        "seleccionada": (COLOR_INFO, 5, "SELECCIONADA"),
        "correcta": (COLOR_OK, 5, "CORRECTA"),
        "incorrecta": (COLOR_MAL, 5, "INCORRECTA"),
        "descartada": (estilo.COLOR_BARRA_FONDO, 2, "DESCARTADA"),
        "frenada": (COLOR_INFO, 5, "FRENADA"),
        "liberada": (estilo.COLOR_BOTON, 5, "DEJADA PASAR"),
        "propagada": (COLOR_MAL, 5, "SE PROPAGÓ"),
        "alterada": (COLOR_MAL, 5, "ALTERADA"),
        "perdida": (COLOR_FOCO, 5, "TE LA PERDISTE"),
        "encontrada": (COLOR_OK, 5, "ENCONTRADA"),
        "falsa_alarma": (COLOR_MAL, 5, "ESTABA BIEN"),
    }

    def __init__(self, ancho, alto, cuerpo="", titulo="", px=18, px_titulo=14, tono=None, al_clic=None, al_cursor=None,
                 negrita_cuerpo=False, margen_px=10, reserva=0.0, **opciones):
        super().__init__(**opciones)
        self.ancho, self.alto = ancho, alto
        self._tono = tono or estilo.COLOR_TARJETA
        self.estado = "normal"
        self._foco = False
        self.al_clic = al_clic
        self.al_cursor = al_cursor
        self.habilitada = True
        margen = a_unidades(margen_px)
        self.borde = rect(self, ancho + 2 * a_unidades(2), alto + 2 * a_unidades(2), estilo.TINTA, z=0.004, radio_px=9)
        self.fondo = rect(self, ancho, alto, self._tono, z=0.003, radio_px=8)
        self.marcador = None
        y = alto / 2 - margen
        self.titulo = None
        if titulo:
            self.titulo = texto(self, titulo, px_titulo, ancho - 2 * margen - a_unidades(130),
                                estilo.COLOR_TEXTO_TENUE, (-ancho / 2 + margen, y), negrita=True)
            y -= self.titulo.alto + a_unidades(3)
        self.cuerpo = texto(self, cuerpo, px, ancho - 2 * margen - reserva, estilo.COLOR_TEXTO, (-ancho / 2 + margen, y),
                            negrita=negrita_cuerpo)
        self.etiqueta = texto(self, "", px_titulo, a_unidades(220), estilo.COLOR_TEXTO, (ancho / 2 - margen, alto / 2 - margen),
                              origen=(0.5, 0.5), negrita=True)
        self.golpe = Entity(parent=self, model="quad", scale=(ancho, alto), collider="box",
                            color=color.rgba(0, 0, 0, 0), z=-0.03)
        self.golpe.on_click = self._clic
        self.golpe.on_mouse_enter = self._entra
        self.fijar_estado("normal")

    # -- Medidas --

    @staticmethod
    def alto_necesario(cuerpo, ancho, px=18, titulo="", px_titulo=14, minimo=0.0, margen_px=10, reserva=0.0):
        margen = a_unidades(margen_px)
        n_cuerpo = len(lineas_de(cuerpo, px, ancho - 2 * margen - reserva))
        alto = 2 * margen + alto_de(n_cuerpo, px)
        if titulo:
            alto += alto_de(1, px_titulo) + a_unidades(3)
        return max(alto, minimo)

    # -- Estado --

    def fijar_estado(self, estado, etiqueta=None):
        """Cambia el estado (borde + etiqueta de texto). `etiqueta` reemplaza el texto de la etiqueta del estado."""
        self.estado = estado
        self._etiqueta_propia = etiqueta
        self._pintar()

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self._pintar()

    def fijar_texto_etiqueta(self, cadena):
        self.etiqueta.text = cadena

    def _pintar(self):
        borde, grosor, etiqueta = self.ESTADOS[self.estado]
        if getattr(self, "_etiqueta_propia", None):
            etiqueta = self._etiqueta_propia
        if self._foco:
            borde, grosor = COLOR_FOCO, max(grosor, 6)
            etiqueta = etiqueta or ">> ELEGIR"
        if self.is_empty() or self.borde.is_empty():      # la tarjeta ya se destruyó (el ratón aún la recuerda)
            return
        extra = a_unidades(grosor)
        if getattr(self, "_grosor_pintado", None) != grosor:
            self._grosor_pintado = grosor
            self.borde.model = modelo_redondeado(self.ancho + 2 * extra, self.alto + 2 * extra, 9 + grosor)
            self.borde.scale = (self.ancho + 2 * extra, self.alto + 2 * extra)
        self.borde.color = rgb(borde)
        self.etiqueta.text = etiqueta
        self.fondo.color = rgb(self._tono if self.estado != "descartada" else estilo.COLOR_PANEL)

    def _clic(self):
        if not self.is_empty() and self.habilitada and self.al_clic is not None:
            self.al_clic()

    def _entra(self):
        if not self.is_empty() and self.habilitada and self.al_cursor is not None:
            self.al_cursor()


class Boton(Entity):
    """Botón de texto de una línea con foco visible (borde amarillo + «>>») y clic. `position` es su centro."""

    def __init__(self, etiqueta, al_clic, ancho=0.36, alto=0.075, px=19, primario=False, **opciones):
        super().__init__(**opciones)
        self.ancho, self.alto, self.px = ancho, alto, px
        self.al_clic = al_clic
        self.primario = primario
        self.habilitado = True
        self._foco = False
        self._etiqueta = etiqueta
        self.borde = rect(self, ancho + a_unidades(8), alto + a_unidades(8), estilo.TINTA, z=0.004, radio_px=10)
        self.fondo = rect(self, ancho, alto, estilo.COLOR_ACENTO if primario else estilo.COLOR_BOTON, z=0.003, radio_px=8)
        self.texto = Text(etiqueta, parent=self, origin=(0, 0), position=(0, 0, Z_TEXTO), scale=escala_fuente(px),
                          color=rgb(estilo.COLOR_ACENTO_TEXTO if primario else estilo.COLOR_BOTON_TEXTO),
                          font=tipografia.FUENTE_TITULO)
        self.golpe = Entity(parent=self, model="quad", scale=(ancho, alto), collider="box", color=color.rgba(0, 0, 0, 0), z=-0.03)
        self.golpe.on_click = self._clic
        self.golpe.on_mouse_enter = self._entra
        self.golpe.on_mouse_exit = self._sale
        self.fijar_foco(False)

    def _clic(self):
        if not self.is_empty() and self.habilitado and self.enabled and self.al_clic is not None:
            self.al_clic()

    def _entra(self):
        if not self.is_empty() and self.habilitado:
            self.fondo.color = rgb((255, 232, 110) if self.primario else estilo.COLOR_BOTON_RESALTADO)

    def _sale(self):
        if not self.is_empty():
            self.fijar_foco(self._foco)

    def fijar_habilitado(self, valor):
        self.habilitado = bool(valor)
        self.fijar_foco(self._foco)

    def fijar_etiqueta(self, cadena):
        self._etiqueta = cadena
        self.fijar_foco(self._foco)

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        if self.is_empty():
            return
        if not self.habilitado:
            self.fondo.color = rgb(estilo.COLOR_BOTON_DESHABILITADO)
            self.texto.color = rgb(estilo.COLOR_TEXTO_TENUE)
        else:
            self.fondo.color = rgb(estilo.COLOR_ACENTO if self.primario else estilo.COLOR_BOTON)
            self.texto.color = rgb(estilo.COLOR_ACENTO_TEXTO if self.primario else estilo.COLOR_BOTON_TEXTO)
        extra = a_unidades(6 if self._foco else 2)
        if getattr(self, "_foco_pintado", None) != self._foco:
            self._foco_pintado = self._foco
            self.borde.model = modelo_redondeado(self.ancho + 2 * extra, self.alto + 2 * extra, 10)
            self.borde.scale = (self.ancho + 2 * extra, self.alto + 2 * extra)
        self.borde.color = rgb(COLOR_FOCO if self._foco else estilo.TINTA)
        self.texto.text = (">> " + self._etiqueta) if self._foco else self._etiqueta


class Barra(Entity):
    """Barra de progreso SIN cifra (relleno de 0 a 1) con rótulo en palabras. `position` es su centro."""

    def __init__(self, ancho, alto=0.022, tono=None, **opciones):
        super().__init__(**opciones)
        self.ancho, self.alto = ancho, alto
        self.fondo = rect(self, ancho, alto, estilo.COLOR_BARRA_FONDO, z=0.003, radio_px=4)
        self.relleno = Entity(parent=self, model="quad", color=rgb(tono or COLOR_INFO), z=0.002,
                              scale=(0.0001, alto * 0.78), position=(-ancho / 2, 0, 0.002), origin=(-0.5, 0))
        self.tono = tono or COLOR_INFO

    def fijar(self, fraccion, tono=None):
        fraccion = max(0.0, min(1.0, fraccion))
        self.relleno.scale_x = max(0.0001, (self.ancho - a_unidades(4)) * fraccion)
        self.relleno.x = -self.ancho / 2 + a_unidades(2)
        self.relleno.color = rgb(tono or self.tono)
