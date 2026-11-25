# Piel BOTW de las pantallas de la persona B: la parte VISUAL (Ursina). Las reglas, colores y medidas están en
# frontend/ui_botw_b_calculos.py (puro, con tests). Cada pantalla de B se viste con UNA llamada protegida después de
# construirse (vestir(...)); los widgets compartidos (BotonPrimario, panel_tinta...) toman el aspecto nuevo por su cuenta
# cuando la persona A suba su rediseño de componentes.py, sin que aquí se toque nada de ellos.
#
#   vestir(raiz, titulos=(), foco=None, piezas=(), velo=False)   -> Piel | None
#       titulos: Text que pasan a cursiva negrita con sombra plana de tinta (la sombra sigue al texto si cambia).
#       foco:    un FocoTeclado (fondo_menu) o algo con enfocado(): la flecha amarilla se pone a la izquierda del control
#                enfocado (dibujada con PIL: la fuente no trae flechas).
#       piezas:  entidades que entran escalonadas (desde la derecha), como las opciones del menú BOTW.
#       velo:    velo violeta de pantalla completa detrás de `raiz` (degradado de abajo arriba).
#   piel.reiniciar()   vuelve a pasar la entrada (al volver a mostrar la pantalla)
#
# Bandera ALCALDE_UI_BOTW (por defecto encendida): =0 -> vestir() devuelve None y la pantalla queda como estaba.
# GUARDIÁN: si algo falla al vestir o en un frame, la piel se quita sola, la pantalla sigue como estaba y se avisa UNA
# vez por stderr. Respeta «reducir movimiento» (banderas_visuales.reducir_movimiento): sin entrada ni deslizamientos.

import math
import sys

from ursina import Entity, Text, Texture, camera, color, time

from frontend import ui_botw_b_calculos as calc

_avisados = set()
# camera.ui: z mayor = más atrás. El velo va bien por detrás de todas las capas de la pantalla (sus paneles usan z
# pequeñas) y por delante del fondo de los menús.
PROFUNDIDAD_VELO = 0.4
# La flecha mide 26 × 18 px a 720p en el menú BOTW; dentro de las pantallas escaladas de B se ve a este tamaño.
ESCALA_FLECHA = 1.6


def _avisar(texto):
    if texto not in _avisados:
        _avisados.add(texto)
        print(f"[ui_botw_b] {texto}", file=sys.stderr)


def _c(rgb, alfa=1.0):
    return color.rgba(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, alfa)


def _reducido():
    try:
        from frontend import banderas_visuales as bv
        return bool(bv.reducir_movimiento())
    except Exception:          # noqa: BLE001
        return False


# -- Texturas dibujadas (PIL) -----------------------------------------------------------------------------------------

_texturas = {}


def _textura_flecha(escala=4):
    """Flecha amarilla con borde de tinta, punta a la derecha (señala al control), 26 × 18 px a 720p."""
    if "flecha" in _texturas:
        return _texturas["flecha"]
    from PIL import Image, ImageDraw
    p = calc.paleta()
    s = escala
    img = Image.new("RGBA", (26 * s, 18 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    punta = [(24 * s, 9 * s), (8 * s, 2 * s), (11 * s, 9 * s), (8 * s, 16 * s)]
    d.polygon(punta, fill=(*p["amarillo"], 255))
    d.line(punta + [punta[0]], fill=(*p["tinta"], 255), width=int(2.5 * s), joint="curve")
    d.line([(1 * s, 9 * s), (10 * s, 9 * s)], fill=(*p["amarillo"], 255), width=int(3 * s))
    tex = Texture(img)
    tex.filtering = "mipmap"
    _texturas["flecha"] = tex
    return tex


def _textura_velo(n=128):
    """Degradado vertical del color del velo: transparente arriba, ALFA_VELO_PANEL abajo."""
    if "velo" in _texturas:
        return _texturas["velo"]
    from PIL import Image
    velo = calc.paleta()["velo"]
    img = Image.new("RGBA", (1, n))
    px = img.load()
    for i in range(n):
        # 0 = arriba
        f = i / (n - 1)
        px[0, i] = (*velo, int(round(255 * calc.ALFA_VELO_PANEL * (0.35 + 0.65 * f))))
    tex = Texture(img)
    tex.filtering = "bilinear"
    _texturas["velo"] = tex
    return tex


# -- Piezas ------------------------------------------------------------------------------------------------------------

class SombraTitulo(Entity):
    """Sombra plana de tinta de un Text (hija suya): copia su texto cada frame si cambió."""

    def __init__(self, texto):
        super().__init__(parent=texto)
        d = calc.u(calc.SOMBRA_TITULO_PX) / max(1e-6, float(texto.scale_y))
        self.origen = texto
        # Un Text("") centrado falla en Ursina (nota de frontend/online_ui.py): la copia nunca queda vacía.
        self.copia = Text(texto.text or " ", parent=self, font=calc.FUENTE_TITULO, origin=texto.origin,
                          position=(d, -d, 0.001), color=_c(calc.paleta()["tinta"]))
        self.copia.ignore = True

    def update(self):
        texto = self.origen.text or " "
        if self.copia.text != texto:
            self.copia.text = texto
        if self.copia.origin != self.origen.origin:
            self.copia.origin = self.origen.origin
        if self.copia.line_height != self.origen.line_height:
            self.copia.line_height = self.origen.line_height


class FlechaFoco(Entity):
    """La flecha amarilla a la izquierda del control enfocado (solo con el foco de teclado a la vista)."""

    def __init__(self, foco, **opciones):
        super().__init__(model="quad", texture=_textura_flecha(), color=color.white, **opciones)
        self.foco = foco
        self.ignore = True
        self.alto = calc.u(18) * ESCALA_FLECHA
        self.ancho = calc.u(26) * ESCALA_FLECHA
        self.enabled = False

    def colocar(self, t):
        control = self.foco.enfocado() if self.foco is not None else None
        # Los botones de la piel de A (componentes.BotonBotw*, vía boton_piel_*) ya dibujan su flecha con el foco: aquí
        # solo se señalan los controles propios (tarjetas de rol, selectores, campos).
        propia = type(control).__name__.startswith("BotonBotw")
        visible = (control is not None and not propia and getattr(self.foco, "visible", True) and control.enabled
                   and getattr(control, "parent", None) is not None)
        if not visible:
            self.visible = False
            return
        self.visible = True
        if self.parent is not control.parent:
            self.parent = control.parent
        ancho_control = abs(float(getattr(control, "scale_x", 0.3)))
        x = calc.x_flecha(control.x - ancho_control / 2, self.ancho)
        vaiven = 0.0 if _reducido() else calc.u(3) * (0.5 - 0.5 * math.cos(t * 4.0))
        self.position = (x - vaiven, control.y, control.z - 0.01)
        self.scale = (self.ancho, self.alto)


class Piel(Entity):
    """Lo que vistió una pantalla: sombras, flecha, velo y la entrada escalonada."""

    def __init__(self, raiz, titulos=(), foco=None, piezas=(), velo=False):
        super().__init__(parent=raiz)
        self.raiz = raiz
        self.t = 0.0
        self.sombras = [SombraTitulo(t) for t in titulos if t is not None]
        for texto in titulos:
            if texto is not None:
                texto.font = calc.FUENTE_TITULO
        self.flecha = FlechaFoco(foco, parent=raiz) if foco is not None else None
        if self.flecha is not None:
            self.flecha.enabled = True
        self.velo = None
        if velo:
            # hijo de la pantalla (se esconde con ella), por detrás de su contenido y del tamaño de toda la ventana
            # se mide en camera.ui (pantalla entera) y después se cuelga de la pantalla sin moverlo (world_parent)
            z = float(getattr(raiz, "world_z", 0.0)) + PROFUNDIDAD_VELO
            self.velo = Entity(parent=camera.ui, model="quad", texture=_textura_velo(), color=color.white,
                               scale=(camera.aspect_ratio * 1.2, 1.2), z=z)
            self.velo.world_parent = raiz
            self.velo.ignore = True
        self.piezas = [(p, p.x) for p in piezas if p is not None]
        self._roto = False
        self.reiniciar()

    def reiniciar(self):
        self.t = 0.0
        self._colocar_piezas()

    def _colocar_piezas(self):
        reducido = _reducido()
        for k, (pieza, x0) in enumerate(self.piezas):
            _, dx = calc.entrada(self.t, k, reducido)
            pieza.x = x0 + dx

    def update(self):
        if self._roto:
            return
        try:
            self.t += min(0.1, time.dt)
            if self.piezas and not calc.entrada_terminada(self.t - time.dt, len(self.piezas), _reducido()):
                self._colocar_piezas()
            if self.flecha is not None:
                self.flecha.colocar(self.t)
        except Exception as error:      # noqa: BLE001
            self.quitar(error)

    def quitar(self, error=None):
        """Deja la pantalla como estaba (piezas en su sitio, sin flecha ni velo). Idempotente."""
        if error is not None:
            _avisar(f"piel quitada ({type(error).__name__}: {error})")
        self._roto = True
        for pieza, x0 in self.piezas:
            try:
                pieza.x = x0
            except Exception:           # noqa: BLE001
                pass
        for parte in [self.flecha, self.velo] + [s for s in self.sombras]:
            try:
                if parte is not None:
                    parte.enabled = False
            except Exception:           # noqa: BLE001
                pass


def vestir(raiz, titulos=(), foco=None, piezas=(), velo=False):
    """Viste una pantalla de B con la piel BOTW. None con ALCALDE_UI_BOTW=0 o si algo falla (la pantalla no cambia)."""
    if not calc.activa():
        return None
    try:
        return Piel(raiz, tuple(titulos), foco, tuple(piezas), velo)
    except Exception as error:          # noqa: BLE001
        _avisar(f"sin piel en {type(raiz).__name__} ({type(error).__name__}: {error})")
        return None
