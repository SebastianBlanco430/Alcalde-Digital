# Piezas de interfaz reutilizables (Ursina) para las escenas del juego.
# Son Entity que usan coordenadas de camera.ui (y en [-0.5, 0.5], 0.5 = arriba).
# Los colores salen de frontend/estilo.py (RGB 0-255) y se convierten con rgb().
#   BarraIndicador  etiqueta + barra con relleno proporcional y color por rango.
#   TarjetaNoticia  recuadro con el texto de la noticia envuelto y centrado.
#   BotonAccion     botón con estados normal / hover / deshabilitado.
#   panel_tinta     panel con borde de tinta y sombra plana (estilo del juego).
#   BotonPrimario / BotonSecundario / BotonPeligro  botones con borde de tinta, hover, pulsado, foco.

import os
import sys

from panda3d.core import TextNode
from ursina import Button, Entity, Text, color, destroy
from ursina.models.procedural.quad import Quad

from backend.datos.nombres_visibles import glosar_texto
from frontend import diseno_adaptable_calculos as calc_adaptable
from frontend import estilo, tipografia
from frontend import ui_botw_calculos
from frontend.texto import envolver_texto

# Bandera reversible: los botones de tinta encogen (y si no basta recortan con «…») el texto que no cabe.
# ALCALDE_ENCAJAR_BOTONES=0 deja el comportamiento de antes (el texto largo se sale del botón).
ENCAJAR_TEXTO_BOTON = os.environ.get("ALCALDE_ENCAJAR_BOTONES") != "0"

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
            texto, rgb_texto = glosar_texto(texto), estilo.COLOR_TEXTO

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
# Variante roja para acciones de denuncia (la usa la red social de la escena de juego). Se añade
# aquí, aparte de los dos estilos de arriba, que no cambian.
ESTILOS_BOTON["peligro"] = {
    "normal": estilo.ESTADO_ERROR, "hover": (190, 48, 48), "presionado": (170, 44, 44),
    "texto": (250, 244, 228),
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
    ESPACIO_TEXTO = 0.88          # fracción del ancho del botón que puede ocupar el texto
    ESCALA_TEXTO_MIN = 0.7        # lo más que se encoge la letra antes de recortar con «…»

    def __init__(self, texto, al_clic=None, ancho=a_unidades(220), alto=a_unidades(56),
                 habilitado=True, tamano_fuente_px=22, **opciones):
        self._tamano_texto = None     # se fija al final: mientras Button construye, el texto aún no se encaja
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
        self._tamano_texto = escala_fuente(tamano_fuente_px)
        self.encajar_texto()

    # Ursina genera la propiedad `text` por clase con la función de Button: se redefine aquí para que cada texto
    # nuevo («Borrar partida guardada», «Esperando a: …») se vuelva a encajar en el botón.
    def _fijar_texto(self, valor):
        Button.text_setter(self, valor)
        if getattr(self, "_tamano_texto", None) is not None:
            self.encajar_texto()

    text = property(Button.text_getter, _fijar_texto)

    # Encoge la letra hasta que el texto quepa en ESPACIO_TEXTO del ancho; si ni a ESCALA_TEXTO_MIN cabe, lo recorta
    # con «…» (docs/DISENO.md §3: ningún texto se sale de su caja). Se mide en coordenadas de mundo, así vale
    # igual dentro de un panel escalado por diseno_adaptable.
    def encajar_texto(self):
        entidad = self.text_entity
        if not ENCAJAR_TEXTO_BOTON or entidad is None or not entidad.text or self._tamano_texto is None:
            return
        self.text_size = self._tamano_texto
        # Ursina vuelve a `highlight_text_size` al pasar el mouse (por defecto, el tamaño original sin encoger):
        # se iguala al tamaño encajado para que el texto no se salga del botón en hover.
        self.highlight_text_size = self.text_size
        if self.world_scale_x <= 0:
            return
        nodo = TextNode("medida_boton")
        nodo.setFont(entidad.font)
        por_unidad = entidad.size * entidad.world_scale_x / self.world_scale_x

        def medir(cadena):
            return nodo.calcWidth(cadena) * por_unidad
        ancho = medir(entidad.text)
        if ancho <= self.ESPACIO_TEXTO:
            return
        escala = max(self.ESCALA_TEXTO_MIN, self.ESPACIO_TEXTO / ancho)
        self.text_size = self._tamano_texto * escala
        self.highlight_text_size = self.text_size
        if ancho * escala > self.ESPACIO_TEXTO:
            entidad.text = calc_adaptable.recortar_con_elipsis(entidad.text, medir, self.ESPACIO_TEXTO / escala)

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
        # destroy() de Ursina solo marca la entidad para quitarla de scene.entities (se purga
        # después); si estaba bajo el cursor, mouse.update() aún la visita con el nodo ya vacío.
        if self.is_empty():
            return
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


class BotonPeligro(BotonTinta):
    VARIANTE = "peligro"    # rojo con texto claro: denunciar / reportar


def _curva_salida():
    from ursina import curve
    return curve.out_quad


# ---------------------------------------------------------------------------
# Piel BOTW (docs/ESTILO_BOTW.md, ALCALDE_UI_BOTW). Todo lo de abajo es AÑADIDO:
# panel_tinta, BotonTinta y sus variantes no cambian (las pantallas que no se
# pasan a la piel se ven igual). Los colores son las constantes BOTW_* de
# estilo y la bandera y las equivalencias están en ui_botw_calculos.
#   panel_botw    velo translúcido con filo claro y sombra suave (mismos hijos que panel_tinta).
#   panel_piel    panel_botw con la piel encendida y panel_tinta sin ella (misma firma que panel_tinta).
#   BotonBotwPrimario / BotonBotwSecundario / BotonBotwPeligro  botones en cursiva con flecha amarilla al
#                 tener foco o el ratón encima (misma API que BotonPrimario).
#   boton_piel    el botón BOTW o el de tinta según la bandera.
#   flecha_botw   la flecha amarilla del menú de inicio, para listas propias.
# ---------------------------------------------------------------------------

# Variantes de botón con la piel (claves nuevas: las de siempre no cambian).
ESTILOS_BOTON["botw_primario"] = dict(ui_botw_calculos.ESTILOS_BOTON["primario"])
ESTILOS_BOTON["botw_secundario"] = dict(ui_botw_calculos.ESTILOS_BOTON["secundario"])
ESTILOS_BOTON["botw_peligro"] = dict(ui_botw_calculos.ESTILOS_BOTON["peligro"])

# Radios de la tinta a los de la piel (6 chip, 10 tarjeta, 14 panel -> 4, 6, 8).
RADIOS_BOTW = {estilo.RADIO_CHIP_PX: estilo.BOTW_RADIO_CHIP_PX, estilo.RADIO_TARJETA_PX: estilo.BOTW_RADIO_TARJETA_PX,
               estilo.RADIO_PANEL_PX: estilo.BOTW_RADIO_PANEL_PX}
FLECHA_BOTW_PX = (26, 18)             # la flecha del menú de inicio (SVG 26 x 18)
_TEXTURA_FLECHA = None
_TEXTURA_FLECHA_ESPEJO = None


# ¿Piel BOTW? (frontend/ui_botw_calculos.py: variable de entorno > ajuste guardado > por defecto encendida).
def piel_botw():
    return ui_botw_calculos.activo()


# Medidas (unidades de camera.ui) del filo y la sombra de la piel.
def medidas_botw(filo_px=None):
    filo = a_unidades(estilo.BOTW_GROSOR_FILO_PX if filo_px is None else filo_px)
    dx, dy = estilo.BOTW_DESPLAZAMIENTO_SOMBRA_PX
    return filo, (a_unidades(dx), a_unidades(dy))


# Panel de la piel: velo de tinta violeta (translúcido si `tono` es el velo), filo claro y sombra que cae recta.
# Devuelve el mismo contenedor que panel_tinta (hijos `.sombra` o None, `.borde` y `.fondo`; el contenido va en z = 0).
# `alfa` (0-255) fuerza la opacidad del fondo; por defecto, BOTW_ALFA_VELO con el velo y opaco con cualquier otro tono.
def panel_botw(padre, ancho, alto, tono=None, radio_px=estilo.BOTW_RADIO_PANEL_PX, sombra=True, filo_px=None,
               alfa=None, **opciones):
    tono = estilo.BOTW_VELO if tono is None else tuple(tono)
    if alfa is None:
        alfa = estilo.BOTW_ALFA_VELO if tono == estilo.BOTW_VELO else 255
    filo, (sx, sy) = medidas_botw(filo_px)
    radio_filo = radio_px + estilo.BOTW_GROSOR_FILO_PX
    contenedor = Entity(parent=padre, **opciones)
    contenedor.sombra = None
    if sombra:
        contenedor.sombra = _capa(contenedor, ancho + 2 * filo, alto + 2 * filo, radio_filo,
                                  color.rgba32(*estilo.BOTW_TINTA, estilo.BOTW_ALFA_SOMBRA), 0.005, (sx, sy))
    contenedor.borde = _capa(contenedor, ancho + 2 * filo, alto + 2 * filo, radio_filo,
                             color.rgba32(*estilo.BOTW_FILO, estilo.BOTW_ALFA_FILO), 0.004)
    contenedor.fondo = _capa(contenedor, ancho, alto, radio_px, color.rgba32(*tono, int(alfa)), 0.003)
    return contenedor


# Igual que panel_tinta (misma firma), pero con la piel encendida dibuja panel_botw con los colores y radios
# equivalentes: COLOR_PANEL (o sin tono) pasa al velo translúcido; los demás, a su BOTW_* (ui_botw_calculos.tono).
def panel_piel(padre, ancho, alto, tono=None, radio_px=estilo.RADIO_PANEL_PX, sombra=True, borde_px=None,
               **opciones):
    if not piel_botw():
        return panel_tinta(padre, ancho, alto, tono, radio_px, sombra, borde_px, **opciones)
    if tono is None or tuple(tono) == estilo.COLOR_PANEL:
        tono_botw = estilo.BOTW_VELO
    else:
        tono_botw = ui_botw_calculos.tono(tono, True)
    # borde 0 = sin filo (como en panel_tinta); si no, el filo fino de la piel, nunca más grueso que el pedido
    filo = None if borde_px is None else (0 if borde_px <= 0 else max(1, min(borde_px, estilo.BOTW_GROSOR_FILO_PX)))
    return panel_botw(padre, ancho, alto, tono_botw, RADIOS_BOTW.get(radio_px, radio_px), sombra, filo, **opciones)


# Textura de la flecha del menú (punta a la izquierda, amarilla con borde de tinta), dibujada con PIL una sola vez: la
# fuente no trae flechas.
def textura_flecha_botw(escala=4):
    global _TEXTURA_FLECHA
    if _TEXTURA_FLECHA is None:
        from PIL import Image, ImageDraw
        from ursina import Texture
        s = escala
        img = Image.new("RGBA", (FLECHA_BOTW_PX[0] * s, FLECHA_BOTW_PX[1] * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        tinta, amarillo = (*estilo.BOTW_TINTA, 255), (*estilo.BOTW_ACENTO, 255)
        punta = [(2 * s, 9 * s), (18 * s, 2 * s), (15 * s, 9 * s), (18 * s, 16 * s)]
        d.polygon(punta, fill=amarillo)
        d.line(punta + [punta[0]], fill=tinta, width=int(2.5 * s), joint="curve")
        d.line([(16 * s, 9 * s), (25 * s, 9 * s)], fill=amarillo, width=int(3 * s))
        d.ellipse((23.5 * s, 7.5 * s, 26.5 * s, 10.5 * s), fill=amarillo)
        _TEXTURA_FLECHA = Texture(img)
        _TEXTURA_FLECHA.filtering = "mipmap"
        _TEXTURA_FLECHA._imagen_botw = img
    return _TEXTURA_FLECHA


# La misma flecha espejada (punta a la derecha), para cuando va a la DERECHA del control. Una escala negativa la
# escondería (el quad se ve solo por delante): se espeja la imagen.
def textura_flecha_botw_espejo():
    global _TEXTURA_FLECHA_ESPEJO
    if _TEXTURA_FLECHA_ESPEJO is None:
        from PIL import ImageOps
        from ursina import Texture
        _TEXTURA_FLECHA_ESPEJO = Texture(ImageOps.mirror(textura_flecha_botw()._imagen_botw))
        _TEXTURA_FLECHA_ESPEJO.filtering = "mipmap"
    return _TEXTURA_FLECHA_ESPEJO


# Flecha amarilla de la piel (`alto` en unidades de camera.ui; el ancho sale de la proporción 26 x 18).
def flecha_botw(padre, alto=a_unidades(15), **opciones):
    ancho = alto * FLECHA_BOTW_PX[0] / FLECHA_BOTW_PX[1]
    return Entity(parent=padre, model="quad", texture=textura_flecha_botw(), scale=(ancho, alto), **opciones)


# -- Flecha sin solapes (frontend/flecha_botw_calculos.py) --

# Rectángulo (x0, y0, x1, y1) de `entidad` en camera.ui, o None si no tiene geometría.
def rect_en_ui(entidad):
    from ursina import camera
    try:
        limites = entidad.getTightBounds(camera.ui)
    except Exception:                            # noqa: BLE001
        return None
    if not limites:
        return None
    bajo, alto = limites
    if alto.x - bajo.x <= 1e-6 or alto.y - bajo.y <= 1e-6:
        return None
    return (bajo.x, bajo.y, alto.x, alto.y)


# La pantalla de la que cuelga `entidad`: su antepasado justo debajo de camera.ui (o la raíz que tenga).
def _raiz_ui(entidad):
    from ursina import camera
    nodo = entidad
    while getattr(nodo, "parent", None) is not None and nodo.parent is not camera.ui and isinstance(nodo.parent, Entity):
        nodo = nodo.parent
    return nodo


# Lo que rodea a `control` en su pantalla: (obstáculos, fondos). Obstáculos = controles con collider (botones,
# deslizadores, campos) y textos a la vista. Fondos = piezas con modelo que envuelven al control (paneles, velos): la
# flecha no debe salirse del más pequeño. No cuentan el propio control, sus hijos ni las flechas.
def obstaculos_ui(control, excluir=(), rect_control=None):
    fuera = {id(control), *(id(e) for e in excluir)}
    rects, fondos = [], []
    # Toda la interfaz a la vista: el panel de una pantalla suele ser hermano (otra rama de camera.ui) de sus botones.
    pila = [_raiz_ui(control)]
    from ursina import camera
    if getattr(pila[0], "parent", None) is camera.ui:
        pila = [e for e in camera.ui.children if isinstance(e, Entity)]
    while pila:
        nodo = pila.pop()
        if id(nodo) in fuera or not getattr(nodo, "enabled", False) or not getattr(nodo, "visible", True):
            continue
        if getattr(nodo, "_flecha_botw", False):
            continue
        es_texto = isinstance(nodo, Text)
        interactivo = getattr(nodo, "collider", None) is not None or (es_texto and getattr(nodo, "text", ""))
        if interactivo or (getattr(nodo, "model", None) is not None and not es_texto):
            rect = rect_en_ui(nodo)
            if rect is not None and rect_control is not None and calc_flecha().contiene(rect, rect_control):
                if not es_texto:
                    fondos.append(rect)      # envuelve al control: es su panel, no lo de al lado
            elif rect is not None and interactivo:
                rects.append(rect)
                if isinstance(nodo, Button):
                    continue                 # su texto ya va dentro de su rectángulo
        pila.extend(e for e in getattr(nodo, "children", ()) if isinstance(e, Entity))
    return rects, fondos


def calc_flecha():
    from frontend import flecha_botw_calculos
    return flecha_botw_calculos


# Coloca `flecha` (hija de cualquier entidad) junto al rectángulo `rect_control` (camera.ui) donde no tape nada:
# izquierda, derecha (espejada), más pequeña o dentro del control. `alto` y `hueco` en unidades de camera.ui.
def colocar_flecha_botw(flecha, control, rect_control, alto, hueco, excluir=()):
    from ursina import camera, window
    from frontend import flecha_botw_calculos as fcalc
    if rect_control is None:
        return None
    ancho = alto * FLECHA_BOTW_PX[0] / FLECHA_BOTW_PX[1]
    medio = window.aspect_ratio / 2
    obstaculos, fondos = obstaculos_ui(control, (flecha, *excluir), rect_control)
    # la flecha cabe en la pantalla y dentro del panel más pequeño que envuelve al control
    pantalla = (-medio, -0.5, medio, 0.5)
    limites = fcalc.recortar(pantalla, fcalc.contenedor(rect_control, fondos, pantalla))
    sitio = fcalc.elegir(rect_control, ancho, alto, hueco, obstaculos, limites)
    flecha._flecha_botw = True
    if sitio.lado == fcalc.ANILLO:
        return sitio                         # sin flecha: quien llama marca el control de otra forma
    flecha.texture = textura_flecha_botw_espejo() if sitio.lado == fcalc.DERECHA else textura_flecha_botw()
    padre = flecha.getParent()
    escala = padre.getScale(camera.ui)
    sx, sy = abs(escala.x) or 1.0, abs(escala.y) or 1.0
    flecha.scale = (sitio.ancho / sx, sitio.alto / sy)
    z = flecha.getPos(camera.ui).z
    flecha.setPos(camera.ui, sitio.x, sitio.y, z)
    return sitio


# Botón de la piel: misma API que BotonTinta (accion, fijar_habilitado, fijar_foco, encajar_texto...). Cambia el
# dibujo: radio menor, filo claro en vez de borde de tinta, sombra que cae recta, letra en cursiva (negrita en el
# primario), anillo de foco amarillo y la flecha del menú a la izquierda mientras tiene foco o el ratón encima.
class BotonBotw(BotonTinta):

    VARIANTE = "botw_secundario"
    SEPARACION_FLECHA_PX = 8
    ALTO_FLECHA_PX = 20

    def __init__(self, texto, al_clic=None, ancho=a_unidades(220), alto=a_unidades(56),
                 habilitado=True, tamano_fuente_px=22, **opciones):
        super().__init__(texto, al_clic=al_clic, ancho=ancho, alto=alto, habilitado=habilitado,
                         tamano_fuente_px=tamano_fuente_px, **opciones)
        self.radius = a_unidades(estilo.BOTW_RADIO_TARJETA_PX) / alto
        if self.text_entity is not None:
            titulo = self.VARIANTE == "botw_primario"
            self.text_entity.font = tipografia.FUENTE_BOTW_TITULO if titulo else tipografia.FUENTE_BOTW
        # Las capas de tinta de BotonTinta se rehacen con las medidas de la piel (mismos nombres y profundidades).
        for capa in (self.foco, self.sombra, self.borde):
            destruir_arbol(capa)
        filo, (sx, sy) = medidas_botw()
        anillo = a_unidades(estilo.BOTW_ALTO_FOCO_PX)
        rel = (1 + 2 * filo / ancho, 1 + 2 * filo / alto)
        radio = estilo.BOTW_RADIO_TARJETA_PX + estilo.BOTW_GROSOR_FILO_PX
        self.foco = _capa(self, ancho + 2 * (filo + anillo), alto + 2 * (filo + anillo),
                          radio + estilo.BOTW_ALTO_FOCO_PX, rgb(estilo.BOTW_ACENTO), 0.0005)
        self.foco.scale = (rel[0] + 2 * anillo / ancho, rel[1] + 2 * anillo / alto)
        self.foco.enabled = False
        self.sombra = _capa(self, ancho + 2 * filo, alto + 2 * filo, radio,
                            color.rgba32(*estilo.BOTW_TINTA, estilo.BOTW_ALFA_SOMBRA), 0.002)
        self.sombra.scale = rel
        self._sombra_pos = (sx / ancho, sy / alto)
        self.sombra.position = (*self._sombra_pos, 0.002)
        self.borde = _capa(self, ancho + 2 * filo, alto + 2 * filo, radio,
                           color.rgba32(*estilo.BOTW_FILO, estilo.BOTW_ALFA_FILO), 0.001)
        self.borde.scale = rel
        # Flecha a la izquierda del botón (hija: su escala es relativa a la del botón).
        alto_flecha = a_unidades(self.ALTO_FLECHA_PX)
        ancho_flecha = alto_flecha * FLECHA_BOTW_PX[0] / FLECHA_BOTW_PX[1]
        hueco = a_unidades(self.SEPARACION_FLECHA_PX)
        self.flecha = flecha_botw(self, alto=1.0, enabled=False)
        self.flecha.scale = (ancho_flecha / ancho, alto_flecha / alto)
        self.flecha.position = (-0.5 - (hueco + ancho_flecha / 2) / ancho, 0, -0.01)
        self.fijar_habilitado(habilitado)

    def fijar_habilitado(self, valor):
        super().fijar_habilitado(valor)
        if not self._habilitado:
            self.color = rgb(estilo.BOTW_BOTON_DESHABILITADO)
            self.text_color = rgb(estilo.BOTW_TEXTO_TENUE)
        self._mostrar_flecha()

    def _mostrar_flecha(self):
        flecha = getattr(self, "flecha", None)
        if flecha is not None:
            ver = self._habilitado and (self._foco or bool(self.hovered))
            if ver and not getattr(self, "_marcado", False):
                self._colocar_flecha()
            self._marcado = ver
            anillo = ver and getattr(self, "_sin_flecha", False)
            flecha.enabled = ver and not anillo
            # Sin sitio para la flecha: el anillo amarillo de foco marca el botón (también con el ratón encima).
            self.foco.enabled = (self._foco and self._habilitado) or anillo

    # Al aparecer, la flecha busca el lado libre (frontend/flecha_botw_calculos.py): si a la izquierda hay otro botón o
    # un texto, va a la derecha espejada o más pequeña; si no cabe en ningún lado, no hay flecha y se ve el anillo. Si
    # algo falla, se queda donde estaba.
    def _colocar_flecha(self):
        from frontend import flecha_botw_calculos as fcalc
        self._sin_flecha = False
        try:
            sitio = colocar_flecha_botw(self.flecha, self, rect_en_ui(self.borde), a_unidades(self.ALTO_FLECHA_PX),
                                        a_unidades(self.SEPARACION_FLECHA_PX), excluir=(self.foco, self.sombra))
            self._sin_flecha = sitio is not None and sitio.lado == fcalc.ANILLO
        except Exception as error:               # noqa: BLE001
            print(f"[botw] flecha sin colocar ({type(error).__name__}: {error})", file=sys.stderr)

    def fijar_foco(self, valor):
        super().fijar_foco(valor)
        self._mostrar_flecha()

    def on_mouse_enter(self):
        super().on_mouse_enter()
        self._mostrar_flecha()

    def on_mouse_exit(self):
        if self.is_empty():
            return
        super().on_mouse_exit()
        self._mostrar_flecha()


class BotonBotwPrimario(BotonBotw):
    VARIANTE = "botw_primario"     # amarillo con texto de tinta: la acción principal


class BotonBotwSecundario(BotonBotw):
    VARIANTE = "botw_secundario"


class BotonBotwPeligro(BotonBotw):
    VARIANTE = "botw_peligro"


_BOTONES_PIEL = {
    "primario": (BotonBotwPrimario, BotonPrimario),
    "secundario": (BotonBotwSecundario, BotonSecundario),
    "peligro": (BotonBotwPeligro, BotonPeligro),
}


# Botón de la variante pedida («primario», «secundario» o «peligro»): el de la piel si está encendida, el de tinta si
# no. Mismos argumentos que BotonPrimario.
def boton_piel(texto, variante="secundario", **opciones):
    con_piel, sin_piel = _BOTONES_PIEL[variante]
    return (con_piel if piel_botw() else sin_piel)(texto, **opciones)


# Atajos de boton_piel con los MISMOS argumentos (también posicionales) que BotonPrimario, BotonSecundario y BotonPeligro:
# para pasar una pantalla a la piel basta cambiar el nombre de la clase por el del atajo.
def boton_piel_primario(texto, *args, **opciones):
    return (BotonBotwPrimario if piel_botw() else BotonPrimario)(texto, *args, **opciones)


def boton_piel_secundario(texto, *args, **opciones):
    return (BotonBotwSecundario if piel_botw() else BotonSecundario)(texto, *args, **opciones)


def boton_piel_peligro(texto, *args, **opciones):
    return (BotonBotwPeligro if piel_botw() else BotonPeligro)(texto, *args, **opciones)
