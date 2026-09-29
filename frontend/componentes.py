# Piezas de interfaz reutilizables (Ursina) para las escenas del juego.
# Son Entity que usan coordenadas de camera.ui (y en [-0.5, 0.5], 0.5 = arriba).
# Los colores salen de frontend/estilo.py (RGB 0-255) y se convierten con rgb().
#   BarraIndicador  etiqueta + barra con relleno proporcional y color por rango.
#   TarjetaNoticia  recuadro con el texto de la noticia envuelto y centrado.
#   BotonAccion     botón con estados normal / hover / deshabilitado.

from panda3d.core import TextNode
from ursina import Button, Entity, Text, color, destroy
from ursina.models.procedural.quad import Quad

from frontend import estilo
from frontend.texto import envolver_texto

# La versión pygame usaba una ventana de 800x600; sus medidas en píxeles se
# convierten a unidades de camera.ui dividiendo entre esta altura.
ALTO_REFERENCIA_PX = 600


# Tupla RGB 0-255 de `estilo` a Color de Ursina.
def rgb(tupla):
    return color.rgb32(*tupla)


# Píxeles de la versión pygame (600 px de alto) a unidades de camera.ui.
def a_unidades(pixeles):
    return pixeles / ALTO_REFERENCIA_PX


# Escala del Text de Ursina equivalente a una fuente de `pixeles` px en pygame
# (con escala 1, una línea mide Text.size unidades de camera.ui).
def escala_fuente(pixeles):
    return a_unidades(pixeles) / Text.size


MARGEN_TEXTURA_FUENTE = 4


# Ajusta la fuente compartida de Text para evitar un borde fantasma en los glifos:
# el atlas de Panda3D deja un margen de 2 texels que el filtrado alcanza al dibujar
# texto pequeño; con 4 texels desaparece. Llamar una vez tras crear la aplicación
# y antes de dibujar texto.
def preparar_fuente():
    muestra = Text("", add_to_scene_entities=False)   # carga la fuente compartida
    muestra.font.setTextureMargin(MARGEN_TEXTURA_FUENTE)
    destroy(muestra)


# Malla de rectángulo con esquinas de `radio_px` (px de la versión pygame).
# El radio de Quad es relativo al alto; se limita a la mitad del aspecto para no
# generar una malla degenerada en barras muy estrechas.
def _modelo_redondeado(ancho, alto, radio_px):
    aspecto = ancho / alto
    radio = min(radio_px / (alto * ALTO_REFERENCIA_PX), aspecto / 2 - 0.01)
    return Quad(radius=max(radio, 0), aspect=aspecto)


# Etiqueta "<Nombre>: <valor>" con una barra de progreso debajo. `position` es la
# esquina superior izquierda del bloque; `ancho` es el ancho de la barra en
# unidades de camera.ui y `valor` el valor inicial (0-100).
class BarraIndicador(Entity):

    Y_ETIQUETA = -0.038   # centro de la etiqueta bajo el borde superior del bloque
    Y_BARRA = -0.0817     # centro de la barra
    ALTO_BARRA = 0.03

    def __init__(self, etiqueta, ancho, valor=50, **kwargs):
        super().__init__(**kwargs)
        self.etiqueta = etiqueta
        self.ancho_barra = ancho
        self.alto_barra = self.ALTO_BARRA
        self.valor = None
        self.rgb_relleno = None

        self.texto_etiqueta = Text(
            "", parent=self, origin=(-0.5, 0), position=(0, self.Y_ETIQUETA),
            scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO),
        )

        # Las capas tienen el origen centrado y se anclan al borde izquierdo
        # desplazando `x` media anchura, así el relleno crece hacia la derecha.
        self.fondo = Entity(
            parent=self, position=(ancho / 2, self.Y_BARRA, 0.001),
            scale=(ancho, self.alto_barra), color=rgb(estilo.COLOR_BARRA_FONDO),
            model=_modelo_redondeado(ancho, self.alto_barra, 4),
        )
        self.relleno = Entity(
            parent=self, position=(ancho / 2, self.Y_BARRA, 0),
            scale=(ancho, self.alto_barra),
        )
        self.actualizar(valor)

    def actualizar(self, valor):
        # actualiza el texto de la etiqueta y el ancho y color del relleno
        self.valor = valor
        self.texto_etiqueta.text = f"{self.etiqueta}: {valor}"

        proporcion = max(0.0, min(1.0, valor / 100))
        ancho_relleno = self.ancho_barra * proporcion
        if ancho_relleno <= 0:
            self.relleno.enabled = False   # valor 0: nada que dibujar
            return

        self.relleno.enabled = True
        self.relleno.scale_x = ancho_relleno
        self.relleno.x = ancho_relleno / 2   # borde izquierdo fijo en x = 0
        self.relleno.model = _modelo_redondeado(ancho_relleno, self.alto_barra, 4)
        self.rgb_relleno = estilo.rgb_por_valor(valor)
        self.relleno.color = rgb(self.rgb_relleno)


# Recuadro con el texto de la noticia envuelto y centrado; `position` es el centro.
# El envuelto mide con el mismo TextNode con que Ursina dibuja el texto y usa
# frontend/texto.py, más robusto que el wordwrap nativo con fuente proporcional.
class TarjetaNoticia(Entity):

    MENSAJE_VACIO = "No hay más noticias disponibles."
    PADDING = a_unidades(24)       # 24 px en la versión pygame
    LINEA_ALTURA = 1.35            # separación entre líneas (1 = apretado)

    def __init__(self, ancho, alto, tamano_fuente_px=24, **kwargs):
        super().__init__(**kwargs)
        self.ancho = ancho
        self.alto = alto
        self.mensaje_vacio = self.MENSAJE_VACIO
        self.lineas = []

        self.fondo = Entity(
            parent=self, scale=(ancho, alto), color=rgb(estilo.COLOR_TARJETA),
            model=_modelo_redondeado(ancho, alto, 10),
        )
        self.texto = Text(
            "", parent=self, origin=(0, 0), position=(0, 0, -0.001),
            scale=escala_fuente(tamano_fuente_px), color=rgb(estilo.COLOR_TEXTO),
        )
        self.texto.line_height = self.LINEA_ALTURA

    # Ancho disponible para el texto (tarjeta menos relleno a ambos lados).
    @property
    def ancho_util(self):
        return self.ancho - 2 * self.PADDING

    # Ancho de `cadena` en unidades de camera.ui con la fuente y escala actuales.
    def _medir(self, cadena):
        nodo = TextNode("medida")
        nodo.setFont(self.texto.font)
        return nodo.calcWidth(cadena) * self.texto.size * self.texto.scale_x

    # Muestra `texto` envuelto; con None muestra el mensaje de vacío (tenue).
    def mostrar(self, texto):
        if texto is None:
            texto, rgb_texto = self.mensaje_vacio, estilo.COLOR_TEXTO_TENUE
        else:
            rgb_texto = estilo.COLOR_TEXTO

        self.lineas = envolver_texto(texto, self._medir, self.ancho_util)
        self.texto.color = rgb(rgb_texto)
        self.texto.text = "\n".join(self.lineas)

    # (x_min, x_max, y_min, y_max) de la geometría real del texto respecto al
    # centro de la tarjeta; None si no hay texto.
    def limites_texto(self):
        limites = self.texto.getTightBounds(self)
        if limites is None:
            return None
        minimo, maximo = limites
        return (minimo.x, maximo.x, minimo.y, maximo.y)

    def texto_dentro_de_la_tarjeta(self):
        limites = self.limites_texto()
        if limites is None:
            return True
        x_min, x_max, y_min, y_max = limites
        return (
            x_min >= -self.ancho / 2 and x_max <= self.ancho / 2
            and y_min >= -self.alto / 2 and y_max <= self.alto / 2
        )


# Botón nativo de Ursina con estados normal / hover / deshabilitado. En Ursina
# 8.3.0 `Button.disabled` no impide el clic, así que `on_click` apunta a
# `_al_hacer_clic`, que lo ignora mientras el botón está deshabilitado; la
# acción del usuario queda en `accion`.
class BotonAccion(Button):

    def __init__(self, texto, on_click=None, ancho=a_unidades(220), alto=a_unidades(56),
                 habilitado=True, tamano_fuente_px=24, **kwargs):
        super().__init__(
            text=texto, scale=(ancho, alto), radius=a_unidades(8) / alto,
            color=rgb(estilo.COLOR_BOTON), text_color=rgb(estilo.COLOR_BOTON_TEXTO),
            text_size=escala_fuente(tamano_fuente_px), **kwargs,
        )
        self.accion = on_click
        self._habilitado = True
        self.highlight_color = rgb(estilo.COLOR_BOTON_HOVER)
        self.pressed_color = rgb(estilo.COLOR_BOTON_HOVER)  # sin color propio de "pulsado" en la paleta
        self.highlight_text_color = rgb(estilo.COLOR_BOTON_TEXTO)
        self.on_click = self._al_hacer_clic
        self.habilitado = habilitado

    @property
    def habilitado(self):
        return self._habilitado

    @habilitado.setter
    def habilitado(self, valor):
        self._habilitado = bool(valor)
        self.disabled = not self._habilitado
        if self._habilitado:
            self.color = rgb(estilo.COLOR_BOTON)
            self.text_color = rgb(estilo.COLOR_BOTON_TEXTO)
            if self.hovered:   # se rehabilitó con el cursor encima
                self.model.setColorScale(self.highlight_color)
        else:
            self.color = rgb(estilo.COLOR_BOTON_DESHABILITADO)
            self.text_color = rgb(estilo.COLOR_TEXTO_TENUE)

    def _al_hacer_clic(self):
        if not self._habilitado or self.accion is None:
            return
        self.accion()
