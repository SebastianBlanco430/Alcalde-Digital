# Piezas de interfaz reutilizables (Ursina) para las escenas del juego.
# Son Entity que usan coordenadas de camera.ui (y en [-0.5, 0.5], 0.5 = arriba).
# Los colores salen de frontend/estilo.py (RGB 0-255) y se convierten con rgb().
#   BarraIndicador  etiqueta + barra con relleno proporcional y color por rango.
#   TarjetaNoticia  recuadro con el texto de la noticia envuelto y centrado.
#   BotonAccion     botón con estados normal / hover / deshabilitado.
#   panel_tinta     panel con borde de tinta y sombra plana (estilo del juego).
#   BotonPrimario / BotonSecundario  botones con borde de tinta, hover, pulsado, foco.

import sys

from panda3d.core import TextNode
from ursina import Button, Entity, Text, color, destroy
from ursina.models.procedural.quad import Quad

from frontend import estilo, tipografia
from frontend.texto import envolver_texto

# La versión pygame usaba una ventana de 800x600; sus medidas en píxeles se
# convierten a unidades de camera.ui dividiendo entre esta altura.
ALTO_REFERENCIA_PX = 600


# destroy() de Ursina 8.3 no recorre los hijos: quitaba el nodo de Panda3D pero dejaba a los
# descendientes en scene.entities (fuga que crecía en cada ciclo). Esto los destruye primero.
def destruir_arbol(entidad):
    for hijo in list(entidad.children):
        destruir_arbol(hijo)
    destroy(entidad)


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


_AVISADO_FUENTE = False


# Fuente de títulos ausente: se avisa una sola vez por stderr y se sigue con la de texto.
def _avisar_fuente_ausente(error):
    global _AVISADO_FUENTE
    if not _AVISADO_FUENTE:
        _AVISADO_FUENTE = True
        print(f"[ui] no se pudo cargar la fuente de títulos ({error}). Se usa la de texto.", file=sys.stderr)


# Ajusta la fuente compartida de Text para evitar un borde fantasma en los glifos:
# el atlas de Panda3D deja un margen de 2 texels que el filtrado alcanza al dibujar
# texto pequeño; con 4 texels desaparece. Llamar una vez tras crear la aplicación
# y antes de dibujar texto.
def preparar_fuente():
    muestra = Text("", add_to_scene_entities=False)   # carga la fuente compartida
    muestra.font.setTextureMargin(MARGEN_TEXTURA_FUENTE)
    destroy(muestra)
    # Segunda fuente (títulos, negrita): mismo margen. Si no está disponible no es un error.
    try:
        titulo = Text("", font=tipografia.FUENTE_TITULO, add_to_scene_entities=False)
        titulo.font.setTextureMargin(MARGEN_TEXTURA_FUENTE)
        destroy(titulo)
    except Exception as error:   # pragma: no cover - fuente ausente: se usa la de texto
        _avisar_fuente_ausente(error)


# Malla de rectángulo con esquinas de `radio_px` (px de la versión pygame).
# El radio de Quad es relativo al alto; se limita a la mitad del aspecto para no
# generar una malla degenerada en barras muy estrechas.
def modelo_redondeado(ancho, alto, radio_px):
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

    def __init__(self, etiqueta, ancho, valor=50, **opciones):
        super().__init__(**opciones)
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
            model=modelo_redondeado(ancho, self.alto_barra, 4),
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
        self.relleno.model = modelo_redondeado(ancho_relleno, self.alto_barra, 4)
        self.rgb_relleno = estilo.rgb_por_valor(valor)
        self.relleno.color = rgb(self.rgb_relleno)


# Recuadro con el texto de la noticia envuelto y centrado; `position` es el centro.
# El envuelto mide con el mismo TextNode con que Ursina dibuja el texto y usa
# frontend/texto.py, más robusto que el wordwrap nativo con fuente proporcional.
class TarjetaNoticia(Entity):

    MENSAJE_VACIO = "No hay más noticias disponibles."
    RELLENO = a_unidades(24)       # 24 px en la versión pygame
    LINEA_ALTURA = 1.35            # separación entre líneas (1 = apretado)

    def __init__(self, ancho, alto, tamano_fuente_px=24, **opciones):
        super().__init__(**opciones)
        self.ancho = ancho
        self.alto = alto
        self.mensaje_vacio = self.MENSAJE_VACIO
        self.lineas = []

        self.fondo = Entity(
            parent=self, scale=(ancho, alto), color=rgb(estilo.COLOR_TARJETA),
            model=modelo_redondeado(ancho, alto, 10),
        )
        self.texto = Text(
            "", parent=self, origin=(0, 0), position=(0, 0, -0.001),
            scale=escala_fuente(tamano_fuente_px), color=rgb(estilo.COLOR_TEXTO),
        )
        self.texto.line_height = self.LINEA_ALTURA

    # Ancho disponible para el texto (tarjeta menos relleno a ambos lados).
    def ancho_util(self):
        return self.ancho - 2 * self.RELLENO

    # Ancho de `cadena` en unidades de camera.ui con la fuente y escala actuales.
    def medir(self, cadena):
        nodo = TextNode("medida")
        nodo.setFont(self.texto.font)
        return nodo.calcWidth(cadena) * self.texto.size * self.texto.scale_x

    # Muestra `texto` envuelto; con None muestra el mensaje de vacío (tenue).
    def mostrar(self, texto):
        if texto is None:
            texto, rgb_texto = self.mensaje_vacio, estilo.COLOR_TEXTO_TENUE
        else:
            rgb_texto = estilo.COLOR_TEXTO

        self.lineas = envolver_texto(texto, self.medir, self.ancho_util())
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
# `manejar_clic`, que lo ignora mientras el botón está deshabilitado; la
# acción del usuario queda en `accion`.
class BotonAccion(Button):

    def __init__(self, texto, al_clic=None, ancho=a_unidades(220), alto=a_unidades(56),
                 habilitado=True, tamano_fuente_px=24, **opciones):
        super().__init__(
            text=texto, scale=(ancho, alto), radius=a_unidades(8) / alto,
            color=rgb(estilo.COLOR_BOTON), text_color=rgb(estilo.COLOR_BOTON_TEXTO),
            text_size=escala_fuente(tamano_fuente_px), **opciones,
        )
        self.accion = al_clic
        self._habilitado = True
        self.highlight_color = rgb(estilo.COLOR_BOTON_RESALTADO)
        self.pressed_color = rgb(estilo.COLOR_BOTON_RESALTADO)  # sin color propio de "pulsado" en la paleta
        self.highlight_text_color = rgb(estilo.COLOR_BOTON_TEXTO)
        self.on_click = self.manejar_clic
        self.fijar_habilitado(habilitado)

    def esta_habilitado(self):
        return self._habilitado

    def fijar_habilitado(self, valor):
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

    def manejar_clic(self):
        if not self._habilitado or self.accion is None:
            return
        self.accion()


# ---------------------------------------------------------------------------
# Estilo «tinta» (T5, docs/DISENO.md sección 4). Todo lo de abajo es AÑADIDO:
# BotonAccion y el resto no cambian.
# ---------------------------------------------------------------------------

# Malla de un rectángulo de `ancho` x `alto` (unidades) para una capa decorativa.
def _capa(padre, ancho, alto, radio_px, rgb_o_color, z, posicion=(0, 0)):
    colorear = rgb_o_color if not isinstance(rgb_o_color, tuple) or len(rgb_o_color) != 3 else rgb(rgb_o_color)
    return Entity(
        parent=padre, position=(posicion[0], posicion[1], z), scale=(ancho, alto),
        model=modelo_redondeado(ancho, alto, radio_px), color=colorear,
    )


# Medidas (unidades de camera.ui) del borde y la sombra plana de `estilo`.
def medidas_tinta(borde_px=None):
    borde = a_unidades(estilo.GROSOR_BORDE_PX if borde_px is None else borde_px)
    dx, dy = estilo.DESPLAZAMIENTO_SOMBRA_PX
    return borde, (a_unidades(dx), a_unidades(dy))


# Panel con borde de tinta y sombra plana desplazada, sin desenfoque.
# Devuelve un Entity contenedor centrado en su `position`, con los hijos
# `.sombra` (o None), `.borde` y `.fondo`. `tono` es una tupla RGB (por defecto
# COLOR_PANEL); el contenido que se ponga dentro usa z = 0 (las capas están detrás); `radio_px` es el radio de la cara (6 chip, 10 tarjeta, 14 panel).
def panel_tinta(padre, ancho, alto, tono=None, radio_px=estilo.RADIO_PANEL_PX, sombra=True,
                borde_px=None, **opciones):
    tono = estilo.COLOR_PANEL if tono is None else tono
    borde, (sx, sy) = medidas_tinta(borde_px)
    contenedor = Entity(parent=padre, **opciones)
    contenedor.sombra = None
    if sombra:
        contenedor.sombra = _capa(
            contenedor, ancho + 2 * borde, alto + 2 * borde, radio_px + estilo.GROSOR_BORDE_PX,
            color.rgba32(*estilo.TINTA, estilo.ALFA_SOMBRA), 0.005, (sx, sy),
        )
    contenedor.borde = _capa(
        contenedor, ancho + 2 * borde, alto + 2 * borde, radio_px + estilo.GROSOR_BORDE_PX,
        rgb(estilo.TINTA), 0.004,
    )
    contenedor.fondo = _capa(contenedor, ancho, alto, radio_px, rgb(tono), 0.003)
    return contenedor


# Datos puros de cada variante de botón (colores RGB), para probarlos sin ventana.
ESTILOS_BOTON = {
    "primario": {
        "normal": estilo.COLOR_ACENTO, "hover": (255, 232, 110), "presionado": (226, 192, 36),
        "texto": estilo.COLOR_ACENTO_TEXTO,
    },
    "secundario": {
        "normal": estilo.COLOR_BOTON, "hover": estilo.COLOR_BOTON_RESALTADO, "presionado": (55, 72, 125),
        "texto": estilo.COLOR_BOTON_TEXTO,
    },
}
ESCALA_HOVER = 1.04
ESCALA_PRESIONADO = 0.96
DURACION_HOVER = 0.08
DURACION_PRESIONADO = 0.06


# Botón con borde de tinta y sombra plana. Hereda BotonAccion (misma API:
# `accion`, fijar_habilitado, esta_habilitado). Estados: normal, hover (escala
# 1,04), presionado (0,96 y la sombra se hunde), deshabilitado (sin sombra) y
# foco (anillo cian, para teclado). Las subclases fijan `VARIANTE`.
class BotonTinta(BotonAccion):

    VARIANTE = "secundario"
    ALTO_FOCO_PX = 3

    def __init__(self, texto, al_clic=None, ancho=a_unidades(220), alto=a_unidades(56),
                 habilitado=True, tamano_fuente_px=22, **opciones):
        self._paleta = ESTILOS_BOTON[self.VARIANTE]
        super().__init__(texto, al_clic=al_clic, ancho=ancho, alto=alto, habilitado=habilitado,
                         tamano_fuente_px=tamano_fuente_px, **opciones)
        self.radius = a_unidades(estilo.RADIO_TARJETA_PX) / alto
        self.base_scale = (ancho, alto)
        self.highlight_color = rgb(self._paleta["hover"])
        self.pressed_color = rgb(self._paleta["presionado"])
        self.highlight_text_color = rgb(self._paleta["texto"])
        if self.text_entity is not None and self.VARIANTE == "primario":
            self.text_entity.font = tipografia.FUENTE_TITULO
        # Capas hijas: las escalas son relativas a las del botón.
        borde, (sx, sy) = medidas_tinta()
        rel = (1 + 2 * borde / ancho, 1 + 2 * borde / alto)
        radio = estilo.RADIO_TARJETA_PX + estilo.GROSOR_BORDE_PX
        self.foco = _capa(self, ancho + 2 * (borde + a_unidades(self.ALTO_FOCO_PX)),
                          alto + 2 * (borde + a_unidades(self.ALTO_FOCO_PX)), radio + self.ALTO_FOCO_PX,
                          rgb(estilo.ESTADO_INFO), 0.0005)
        self.foco.scale = (rel[0] + 2 * a_unidades(self.ALTO_FOCO_PX) / ancho,
                           rel[1] + 2 * a_unidades(self.ALTO_FOCO_PX) / alto)
        self.foco.enabled = False
        self.sombra = _capa(self, ancho + 2 * borde, alto + 2 * borde, radio,
                            color.rgba32(*estilo.TINTA, estilo.ALFA_SOMBRA), 0.002)
        self.sombra.scale = rel
        self._sombra_pos = (sx / ancho, sy / alto)
        self.sombra.position = (*self._sombra_pos, 0.002)
        self.borde = _capa(self, ancho + 2 * borde, alto + 2 * borde, radio, rgb(estilo.TINTA), 0.001)
        self.borde.scale = rel
        self._presionado = False
        self._foco = False
        self.fijar_habilitado(habilitado)

    def fijar_habilitado(self, valor):
        self._habilitado = bool(valor)
        self.disabled = not self._habilitado
        if self._habilitado:
            self.color = rgb(self._paleta["normal"])
            self.text_color = rgb(self._paleta["texto"])
            if self.hovered:
                self.model.setColorScale(self.highlight_color)
        else:
            self.color = rgb(estilo.COLOR_BOTON_DESHABILITADO)
            self.text_color = rgb(estilo.COLOR_TEXTO_TENUE)
        sombra = getattr(self, "sombra", None)
        if sombra is not None:
            sombra.enabled = self._habilitado

    def _escalar(self, factor, duracion):
        ancho, alto = self.base_scale
        self.animate_scale((ancho * factor, alto * factor, 1), duration=duracion, curve=_curva_salida())

    def on_mouse_enter(self):
        super().on_mouse_enter()
        if self._habilitado and not self._presionado:
            self._escalar(ESCALA_HOVER, DURACION_HOVER)

    def on_mouse_exit(self):
        super().on_mouse_exit()
        self._presionado = False
        self._hundir(False)
        self._escalar(1.0, DURACION_HOVER)

    def input(self, key):
        super().input(key)
        if not self._habilitado:
            return
        if key == "left mouse down" and self.hovered:
            self._presionado = True
            self._hundir(True)
            self._escalar(ESCALA_PRESIONADO, DURACION_PRESIONADO)
        elif key == "left mouse up" and self._presionado:
            self._presionado = False
            self._hundir(False)
            self._escalar(ESCALA_HOVER if self.hovered else 1.0, DURACION_PRESIONADO)

    # La sombra se acerca al botón mientras está presionado.
    def _hundir(self, hundido):
        x, y = self._sombra_pos
        self.sombra.position = (x * 0.25, y * 0.25, 0.002) if hundido else (x, y, 0.002)

    def esta_presionado(self):
        return self._presionado

    # Foco de teclado: anillo cian alrededor del botón.
    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self.foco.enabled = self._foco and self._habilitado

    def tiene_foco(self):
        return self._foco


class BotonPrimario(BotonTinta):
    VARIANTE = "primario"   # amarillo con texto de tinta: la acción principal


class BotonSecundario(BotonTinta):
    VARIANTE = "secundario"


def _curva_salida():
    from ursina import curve
    return curve.out_quad
