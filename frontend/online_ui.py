# Piezas de interfaz compartidas por las escenas del lobby online (Ursina): texto seguro, texto envuelto,
# selector con flechas y un foco de teclado que respeta los campos de texto mientras se escribe.
# Trampas de Ursina (nota 18): `Text` interpreta «<» como marcado y un Text("") centrado falla, por eso
# `fijar` nunca asigna "" (usa un espacio) y todo texto de red llega ya saneado por ClienteRed.

from panda3d.core import TextNode
from ursina import Entity, Text

from frontend import diseno_adaptable, estilo
from frontend.campo_texto import CampoTexto
from frontend.componentes import BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb
from frontend.fondo_menu import FocoTeclado
from frontend.texto import envolver_texto


def fijar(texto_entidad, contenido):
    """Asigna texto sin dejar nunca una cadena vacía ni etiquetas de Ursina."""
    contenido = str(contenido).replace("<", "‹").replace(">", "›")
    texto_entidad.text = contenido if contenido.strip() else " "


def crear_texto(padre, contenido, x, y, px, tono=estilo.COLOR_TEXTO, origen=(-0.5, 0), z=-0.004, **kw):
    t = Text(" ", parent=padre, origin=origen, position=(x, y, z), scale=escala_fuente(px), color=rgb(tono), **kw)
    fijar(t, contenido)
    return t


def texto_envuelto(texto_entidad, contenido, ancho, px, max_lineas=None):
    """Parte `contenido` en líneas que caben en `ancho` (unidades) con la fuente real del Text."""
    nodo = TextNode("medida_online")
    nodo.setFont(texto_entidad.font)
    factor = texto_entidad.size * escala_fuente(px)
    texto_entidad.scale = escala_fuente(px)
    lineas = envolver_texto(str(contenido), lambda s: nodo.calcWidth(s) * factor, ancho) or [" "]
    if max_lineas and len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1].rstrip(".,; ") + "…"
    fijar(texto_entidad, "\n".join(lineas))
    return lineas


def ajustar_ancho(texto_entidad, ancho, px, minimo=0.6):
    """Encoge el texto de una sola línea hasta que quepa en `ancho`."""
    diseno_adaptable.ajustar_texto(texto_entidad, ancho, escala_base=escala_fuente(px), escala_min=minimo)


class SelectorSimple(Entity):
    """‹ opción › con flechas (misma API de foco que los botones)."""

    def __init__(self, opciones, indice=0, al_cambiar=None, ancho=0.56, **kw):
        super().__init__(**kw)
        self.opciones = list(opciones)
        self.indice = 0
        self._al_cambiar = al_cambiar
        self._habilitado = True
        flecha = 0.075
        self.izq = BotonSecundario("‹", al_clic=lambda: self.ajustar(-1), ancho=flecha, alto=a_unidades(44),
                                   tamano_fuente_px=26, parent=self, position=(-ancho / 2 + flecha / 2, 0, -0.003))
        self.der = BotonSecundario("›", al_clic=lambda: self.ajustar(1), ancho=flecha, alto=a_unidades(44),
                                   tamano_fuente_px=26, parent=self, position=(ancho / 2 - flecha / 2, 0, -0.003))
        centro = ancho - 2 * flecha - 0.03
        self.ancho_centro = centro
        self.panel = panel_tinta(self, centro, a_unidades(44), estilo.COLOR_TARJETA, estilo.RADIO_CHIP_PX,
                                 sombra=False, borde_px=2, position=(0, 0, -0.002))
        self.texto = crear_texto(self.panel, "-", 0, 0, 20, origen=(0, 0), z=-0.003)
        self._foco = False
        self.fijar_indice(indice)

    def valor(self):
        return self.opciones[self.indice][0]

    def fijar_indice(self, indice, avisar=False):
        self.indice = max(0, min(len(self.opciones) - 1, indice))
        fijar(self.texto, self.opciones[self.indice][1])
        ajustar_ancho(self.texto, self.ancho_centro - 0.03, 20)
        if avisar and self._al_cambiar is not None:
            self._al_cambiar(self.valor())

    def ajustar(self, direccion):
        self.fijar_indice((self.indice + direccion) % len(self.opciones), avisar=True)

    def esta_habilitado(self):
        return self._habilitado

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self.panel.borde.color = rgb(estilo.ESTADO_INFO if self._foco else estilo.TINTA)

    def bajo_el_raton(self):
        return bool(self.izq.hovered or self.der.hovered)

    def manejar_clic(self):
        self.ajustar(1)


class FocoOnline(FocoTeclado):
    """FocoTeclado que deja escribir: con un CampoTexto activo, Espacio/Izq/Der son del campo;
    Arriba/Abajo/Tab/Intro pasan al control vecino y Escape sale del campo (o llama a `al_escape`)."""

    def __init__(self, obtener, al_escape=None, **kw):
        super().__init__(obtener, **kw)
        self.al_escape = al_escape

    def _campo_activo(self):
        return next((c for c in self._obtener() if isinstance(c, CampoTexto) and c.activo), None)

    def _activar_enfocado(self):
        actual = self.enfocado()
        for c in self._obtener():
            if isinstance(c, CampoTexto):
                if c is actual and self.visible:
                    c.activar()
                else:
                    c.desactivar()

    def mover(self, paso):
        if not self.visible:
            # primera pulsación tras entrar (o tras usar el ratón): se muestra el foco donde está, sin saltar
            self.visible = True
            self._aplicar()
        else:
            super().mover(paso)
        self._activar_enfocado()

    def ir_a(self, control):
        """Lleva el foco (y el cursor, si es un campo) a `control`."""
        lista = self.controles()
        if control in lista:
            self.indice = lista.index(control)
            self.visible = True
            self._aplicar()
            self._activar_enfocado()

    def input(self, key):
        if key == "escape":
            campo = self._campo_activo()
            if campo is not None:
                campo.desactivar()
            elif self.al_escape is not None:
                self.al_escape()
            return
        campo = self._campo_activo()
        if campo is not None:
            if key in ("up arrow", "shift tab"):
                self.mover(-1)
            elif key in ("down arrow", "tab"):
                self.mover(1)
            elif key in ("enter", "return"):
                if campo.al_enviar is not None:
                    campo.al_enviar()
                else:
                    self.mover(1)
            return
        super().input(key)
