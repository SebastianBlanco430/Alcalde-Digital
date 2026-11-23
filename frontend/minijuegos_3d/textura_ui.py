# Interfaz 2D dibujada en una TEXTURA FUERA DE PANTALLA (Ursina + Panda3D) para ponerla sobre una superficie 3D (el monitor).
#
# Qué hay: un búfer fuera de pantalla (GraphicsBuffer) con su propia cámara ortográfica y una raíz de nodos SEPARADA de
# camera.ui (`ui`, una Entity). La raíz es un calco de camera.ui: misma escala (Ursina pone camera.ui a escala 20 y la lente
# a 20·aspecto x 20), misma prueba/escritura de profundidad y lente con near/far -1000..1000, así que cualquier vista 2D de
# hoy (frontend/minijuegos/, frontend/minijuegos_visual/) colgada de `ui` se dibuja IGUAL que en pantalla, solo que en la
# textura. Coordenadas de `ui`: x en [-aspecto/2, aspecto/2], y en [-0.5, 0.5] (las de camera.ui con aspecto 16:9).
#
#   - Nitidez: textura >= 1280x720 (1920x1080 con ventanas de más de 800 px de alto, 2560x1440 por encima de 1300), filtro
#     lineal SIN mipmaps (no emborrona al reducir ~0,8x) y anisotropía 4.
#   - Solo se dibuja mientras está abierta: `activar(True/False)` enciende/apaga el búfer (cero coste cerrado).
#   - Niebla (R2): la niebla del mundo se manda a TODAS las entidades fuera de camera.ui (scene.fog_color); esta raíz no
#     cuelga de camera.ui, así que se le pone fog_color nulo con prioridad alta, igual que pase_final.ui_sin_niebla().
#   - La textura va en un quad del mundo SIN shader (sin luz, sin niebla, sin cel) con color blanco: el texto se ve como en
#     2D. La tinta de pantalla (Sobel sobre la profundidad) no ve el contenido: el quad es plano (solo su borde da línea).
#
# El mouse sobre la superficie lo resuelve frontend/minijuegos_3d/raton.py (Superficie) con la cámara y la lente de aquí.

from panda3d.core import (Camera as CamaraPanda, FrameBufferProperties, LensNode, LVecBase4f, NodePath, OrthographicLens,
                          SamplerState, Texture)
from ursina import Entity, application, camera, color

from frontend import estilo
from frontend.componentes import rgb

ASPECTO = 16 / 9
MUESTRAS_MSAA = 4         # muestras del búfer de la textura (0 = sin MSAA)
_cache = {}             # (ancho, alto) -> PantallaUI reutilizable (crear un búfer cuesta un hitch: se reutiliza)


def tamano_para_ventana(alto_ventana):
    """(ancho, alto) de la textura según el alto de la ventana (nunca menos de 1280x720)."""
    if alto_ventana > 1300:
        return (2560, 1440)
    if alto_ventana > 800:
        return (1920, 1080)
    return (1280, 720)


class PantallaUI:
    """Búfer + cámara 2D + raíz `ui`. No la construyas a mano: usa obtener()."""

    def __init__(self, ancho, alto, nombre="ui_monitor"):
        base = application.base
        self.ancho, self.alto = int(ancho), int(alto)
        self.aspecto = self.ancho / self.alto
        self.textura = Texture(nombre)
        self.bufer = None
        self.muestras = 0
        for muestras in (MUESTRAS_MSAA, 0):          # bordes suaves como en la ventana; sin MSAA si el driver no lo da
            props = FrameBufferProperties()
            props.setRgbColor(True)
            props.setAlphaBits(8)
            props.setDepthBits(24)
            if muestras:
                props.setMultisamples(muestras)
            self.bufer = base.win.makeTextureBuffer(nombre, self.ancho, self.alto, self.textura, False, props)
            if self.bufer is not None:
                self.muestras = muestras
                break
        if self.bufer is None:
            raise RuntimeError("no se pudo crear el búfer fuera de pantalla")
        self.bufer.setSort(-30)                      # antes que la ventana: la textura está lista en el mismo frame
        self.bufer.setClearColorActive(True)
        self.bufer.setClearColor(LVecBase4f(*[c / 255 for c in estilo.COLOR_FONDO], 1))
        self.bufer.setClearDepthActive(True)
        self.textura.setMinfilter(SamplerState.FT_linear)
        self.textura.setMagfilter(SamplerState.FT_linear)
        self.textura.setAnisotropicDegree(4)
        self.textura.setWrapU(SamplerState.WM_clamp)
        self.textura.setWrapV(SamplerState.WM_clamp)

        # Raíz separada (calco de camera.ui_render -> ui_camera -> camera.ui)
        self.render = NodePath(f"{nombre}_render")
        self.render.setDepthTest(True)
        self.render.setDepthWrite(True)
        try:
            from frontend import pase_final_calculos as pfc
            self.render.setShaderInput("fog_color", LVecBase4f(*pfc.NIEBLA_NULA), pfc.PRIORIDAD_UI_SIN_NIEBLA)
        except Exception:                            # noqa: BLE001  sin la constante: niebla nula con prioridad alta igual
            self.render.setShaderInput("fog_color", LVecBase4f(0, 0, 0, 0), 1000)
        self.render.setFogOff(1000)
        try:                                         # la posición de la cámara que el shader por defecto espera en la raíz
            from frontend import rendimiento
            rendimiento.agregar_raiz(self.render)
        except Exception:                            # noqa: BLE001
            pass
        tam_ui = getattr(camera, "_ui_size", 40) * 0.5
        self.lente = OrthographicLens()
        self.lente.setFilmSize(tam_ui * self.aspecto, tam_ui)
        self.lente.setNearFar(-1000, 1000)
        self.camara = self.render.attachNewNode(CamaraPanda(f"{nombre}_camara"))
        self.camara.node().setLens(self.lente)
        self.nodo_lente = LensNode(f"{nombre}_lente", self.lente)      # para CollisionRay.set_from_lens (como Ursina)
        self.region = self.bufer.makeDisplayRegion()
        self.region.setCamera(self.camara)
        self.ui = Entity(parent=self.camara, name=f"{nombre}_ui", scale=(tam_ui, tam_ui), eternal=True)
        self.fondo = Entity(parent=self.ui, model="quad", color=rgb(estilo.COLOR_FONDO), scale=(self.aspecto, 1), z=0.2)
        self.abierta = False
        self.dibujando = False
        self.activar(False)

    def activar(self, activa, dibujar=True):
        """Abre/cierra la raíz. Abierta, sus entidades reciben update() e input() como en camera.ui (los botones de la vista
        2D funcionan); `dibujar` además enciende el búfer (la textura se pinta cada frame). Cerrada: ni se actualiza ni se
        dibuja (cero coste)."""
        self.abierta = bool(activa)
        self.ui.enabled = self.abierta
        self.dibujar(self.abierta and dibujar)

    def dibujar(self, si):
        """Enciende/apaga solo el búfer (una familia que no enseña la vista 2D la deja abierta y sin dibujar)."""
        self.dibujando = bool(si)
        self.bufer.setActive(self.dibujando)

    def vaciar(self):
        """Quita de la raíz todo lo colgado (salvo el fondo). No destruye: quien lo colgó decide."""
        for hijo in list(self.ui.children):
            if hijo is not self.fondo:
                hijo.parent = None

    def aplicar_a(self, entidad):
        """Pone la textura en `entidad` (un quad del mundo) como pantalla: blanco, sin luz, sin niebla, sin shader."""
        entidad.shader = None
        entidad.texture = None
        entidad.setTexture(self.textura, 1)
        entidad.color = color.white
        entidad.setLightOff(1000)
        entidad.setFogOff(1000)
        entidad.setColorScaleOff(1000)
        entidad.setShaderOff(1000)
        return entidad

    def destruir(self):
        try:
            self.activar(False)
            application.base.graphicsEngine.removeWindow(self.bufer)
        except Exception:                            # noqa: BLE001
            pass
        for clave, valor in list(_cache.items()):
            if valor is self:
                del _cache[clave]


def obtener(alto_ventana=None):
    """PantallaUI cacheada para el tamaño que toca a esta ventana (se crea la primera vez)."""
    if alto_ventana is None:
        try:
            alto_ventana = application.base.win.getYSize()
        except Exception:                            # noqa: BLE001
            alto_ventana = 720
    tam = tamano_para_ventana(alto_ventana)
    pantalla = _cache.get(tam)
    if pantalla is None:
        pantalla = PantallaUI(*tam)
        _cache[tam] = pantalla
    return pantalla
