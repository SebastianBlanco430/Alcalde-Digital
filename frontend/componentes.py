"""
Piezas de interfaz reutilizables (Ursina) para las escenas del juego.

Todas son `Entity` que se cuelgan de su escena (o de `camera.ui`) y usan las
coordenadas de `camera.ui`: y en [-0.5, 0.5] (0.5 = arriba) y x en
[-aspecto/2, aspecto/2]. Los colores salen de `frontend/estilo.py` (tuplas RGB
0-255) y se convierten con `color.rgb32(*rgb)`; en ursina 8.3.0 `rgb32` es un
alias de `rgba32`, que divide entre 255 (verificado en ursina/color.py).

Componentes:
    BarraIndicador  etiqueta "Convivencia: 57" + barra con relleno proporcional
                    al valor y color por rango (rojo / amarillo / verde).
    TarjetaNoticia  recuadro con el texto de la noticia envuelto por medida y
                    centrado; o el mensaje de "no hay más noticias".
    BotonAccion     botón nativo de Ursina (`Button`) con estados normal /
                    hover / deshabilitado. Un botón deshabilitado NO ejecuta
                    su `on_click` (Ursina no lo garantiza: ver BotonAccion).

Tamaño de texto: `escala_fuente(px)` traduce un tamaño en píxeles de la
versión pygame (ventana de 600 px de alto) a la escala del `Text` de Ursina,
de modo que la proporción texto/pantalla se conserve en cualquier resolución.
"""

from panda3d.core import TextNode
from ursina import Button, Entity, Text, color, destroy
from ursina.models.procedural.quad import Quad

from frontend import estilo
from frontend.texto import envolver_texto

# La versión pygame usaba una ventana de 800x600; sus medidas en píxeles se
# convierten a unidades de camera.ui dividiendo entre esta altura.
ALTO_REFERENCIA_PX = 600


def rgb(tupla):
    """Convierte una tupla RGB 0-255 de `estilo` a un `Color` de Ursina."""
    return color.rgb32(*tupla)


def a_unidades(pixeles):
    """Píxeles de la versión pygame (600 px de alto) a unidades de camera.ui."""
    return pixeles / ALTO_REFERENCIA_PX


def escala_fuente(pixeles):
    """Escala del `Text` de Ursina equivalente a una fuente de `pixeles` px en pygame.

    Un `Text` de escala 1 mide `Text.size` (0.025) unidades de camera.ui por
    línea; una fuente de N px sobre 600 px de alto mide N/600 unidades.
    """
    return a_unidades(pixeles) / Text.size


MARGEN_TEXTURA_FUENTE = 4


def preparar_fuente():
    """Ajusta la fuente compartida de `Text` para evitar un borde fantasma en los glifos.

    Causa raíz: Panda3D genera cada glifo en un atlas con un margen de 2 texels;
    al dibujar el texto más pequeño que su resolución (mipmaps + filtro bilineal)
    el muestreo alcanza ese margen y deja un rectángulo tenue alrededor de
    algunas letras (visto como una "caja" junto a la "r" de "Jugador 1"). Con un
    margen de 4 texels el borde desaparece. Hay que llamarla una vez tras crear
    la aplicación y antes de dibujar texto; la fuente es compartida por todos
    los `Text` (y los rótulos de los `Button`).
    """
    muestra = Text("", add_to_scene_entities=False)   # carga la fuente compartida
    muestra.font.setTextureMargin(MARGEN_TEXTURA_FUENTE)
    destroy(muestra)


def _modelo_redondeado(ancho, alto, radio_px):
    """Malla de rectángulo con esquinas de `radio_px` (px de la versión pygame).

    El radio de `Quad` es relativo al alto de la entidad. Se limita a la mitad
    del aspecto para que barras muy estrechas no generen una malla degenerada.
    """
    aspecto = ancho / alto
    radio = min(radio_px / (alto * ALTO_REFERENCIA_PX), aspecto / 2 - 0.01)
    return Quad(radius=max(radio, 0), aspect=aspecto)


# ---------------------------------------------------------------------------
# BarraIndicador
# ---------------------------------------------------------------------------


class BarraIndicador(Entity):
    """Etiqueta "<Nombre>: <valor>" y, debajo, una barra de progreso.

    La entidad se ubica con `position` en la ESQUINA SUPERIOR IZQUIERDA del
    bloque; la etiqueta queda arriba y la barra debajo, ocupando `ancho`.

    Args:
        etiqueta: nombre visible del indicador (p. ej. "Desinformación").
        ancho: ancho de la barra en unidades de camera.ui.
        valor: valor inicial (0-100).

    Atributos públicos: `valor`, `texto_etiqueta` (Text), `fondo`, `relleno`,
    `ancho_barra`, `alto_barra`, `rgb_relleno` (tupla RGB aplicada al relleno).
    """

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

        # Las dos capas tienen el origen centrado y se anclan al borde izquierdo
        # desplazando `x` en la mitad de su ancho (así el relleno crece hacia la
        # derecha sin depender de cómo Ursina reaplica `origin` al cambiar de malla).
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
        """Muestra `valor`: texto de la etiqueta, ancho y color del relleno."""
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


# ---------------------------------------------------------------------------
# TarjetaNoticia
# ---------------------------------------------------------------------------


class TarjetaNoticia(Entity):
    """Recuadro COLOR_TARJETA con el texto de la noticia envuelto y centrado.

    Se ubica con `position` en el CENTRO de la tarjeta.

    Estrategia de envoltura: se mide cada línea candidata con el mismo
    `TextNode` (misma fuente) con que Ursina dibuja el texto y se parte por
    palabras para que el ancho no supere el espacio útil (`ancho` menos el
    relleno a cada lado). Es más robusto que el `wordwrap` nativo, que cuenta
    caracteres y con una fuente proporcional deja líneas cortas o desbordadas.
    Ese cálculo vive en `frontend/texto.py` (Python puro, con tests).

    Atributos públicos: `ancho`, `alto`, `fondo`, `texto` (Text), `lineas`
    (líneas actuales) y `mensaje_vacio`.
    """

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

    @property
    def ancho_util(self):
        """Ancho disponible para el texto (tarjeta menos relleno a ambos lados)."""
        return self.ancho - 2 * self.PADDING

    def _medir(self, cadena):
        """Ancho de `cadena` (unidades de camera.ui) con la fuente y escala actuales."""
        nodo = TextNode("medida")
        nodo.setFont(self.texto.font)
        return nodo.calcWidth(cadena) * self.texto.size * self.texto.scale_x

    def mostrar(self, texto):
        """Muestra `texto` envuelto; con `None` muestra el mensaje de vacío (tenue)."""
        if texto is None:
            texto, rgb_texto = self.mensaje_vacio, estilo.COLOR_TEXTO_TENUE
        else:
            rgb_texto = estilo.COLOR_TEXTO

        self.lineas = envolver_texto(texto, self._medir, self.ancho_util)
        self.texto.color = rgb(rgb_texto)
        self.texto.text = "\n".join(self.lineas)

    def limites_texto(self):
        """(x_min, x_max, y_min, y_max) de la geometría real del texto, en el
        sistema de coordenadas de la tarjeta (0, 0 = centro). None si no hay texto."""
        limites = self.texto.getTightBounds(self)
        if limites is None:
            return None
        minimo, maximo = limites
        return (minimo.x, maximo.x, minimo.y, maximo.y)

    def texto_dentro_de_la_tarjeta(self):
        """True si toda la geometría del texto queda dentro del recuadro."""
        limites = self.limites_texto()
        if limites is None:
            return True
        x_min, x_max, y_min, y_max = limites
        return (
            x_min >= -self.ancho / 2 and x_max <= self.ancho / 2
            and y_min >= -self.alto / 2 and y_max <= self.alto / 2
        )


# ---------------------------------------------------------------------------
# BotonAccion
# ---------------------------------------------------------------------------


class BotonAccion(Button):
    """Botón con estados normal / hover / deshabilitado de la paleta.

    Usa el `Button` nativo de Ursina: `highlight_color` hace el hover (lo aplica
    `on_mouse_enter`, que dispara el ratón real) y `disabled=True` apaga el
    efecto hover/pulsado. PERO en ursina 8.3.0 `Button.disabled` NO impide el
    clic: `Mouse.input` llama a `hovered_entity.on_click()` sin mirar `disabled`
    (ursina/mouse.py). Por eso `on_click` apunta a `_al_hacer_clic`, que ignora el
    clic mientras el botón está deshabilitado.

    Args:
        texto: rótulo del botón.
        on_click: callable sin argumentos (opcional); queda en el atributo `accion`.
        ancho, alto: tamaño en unidades de camera.ui.
        habilitado: estado inicial.
        tamano_fuente_px: tamaño del rótulo en px de la versión pygame.

    Colores: normal COLOR_BOTON, hover COLOR_BOTON_HOVER, deshabilitado
    COLOR_BOTON_DESHABILITADO; texto COLOR_BOTON_TEXTO (COLOR_TEXTO_TENUE si está
    deshabilitado).
    """

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
