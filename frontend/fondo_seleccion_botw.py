# Fondo de la selección de rol con la piel BOTW: el MISMO póster del menú de inicio (assets/ui/menu/fondo_menu.jpg),
# desenfocado y bajo un velo violeta (el color de los velos del menú, menu_botw_calculos.VELO), con el zoom lento del
# menú y un degradado arriba y abajo para que el título y los botones se lean. Así la selección parece la continuación
# del menú principal en vez de otra pantalla con el atardecer dibujado.
# Con la piel «Clásico» (o sin el póster en disco) se ve el FondoMenu de siempre: el cambio de piel en Ajustes se
# aplica sin reconstruir la escena (se consulta cada medio segundo).
from ursina import Entity, time, window

from frontend import banderas_visuales as bv
from frontend import menu_botw_calculos as calc
from frontend.fondo_menu import FondoMenu

# Desenfoque del póster: se reduce a ANCHO_DESENFOQUE px de ancho y se aplica un gaussiano de RADIO_DESENFOQUE px.
ANCHO_DESENFOQUE = 960
RADIO_DESENFOQUE = 7
# Velo violeta parejo sobre todo el póster (0-1) y degradados (alfa en el borde → 0 hacia el centro).
ALFA_VELO = 0.38
ALFA_VELO_ARRIBA, ALTO_VELO_ARRIBA = 0.62, 0.34
ALFA_VELO_ABAJO, ALTO_VELO_ABAJO = 0.72, 0.38
# Profundidades dentro del fondo (z mayor = más atrás); todo por detrás de las tarjetas de la escena.
Z_POSTER, Z_VELO, Z_DEGRADADOS = 1.0, 0.95, 0.94
CADA_S_PIEL = 0.5

_cache = {}


def _textura_desenfocada():
    """Textura del póster desenfocado (se calcula una vez por partida); None si no está el archivo."""
    if "poster" not in _cache:
        textura = None
        if calc.FONDO.is_file():
            from PIL import Image, ImageFilter
            from frontend.menu_botw import _textura_pil
            imagen = Image.open(calc.FONDO).convert("RGB")
            alto = int(round(ANCHO_DESENFOQUE / imagen.width * imagen.height))
            imagen = imagen.resize((ANCHO_DESENFOQUE, alto), Image.LANCZOS)
            textura = _textura_pil(imagen.filter(ImageFilter.GaussianBlur(RADIO_DESENFOQUE)))
        _cache["poster"] = textura
    return _cache["poster"]


def _textura_vertical(alfa_borde):
    """Degradado vertical del color del velo: `alfa_borde` en la fila de abajo y 0 en la de arriba."""
    from frontend.menu_botw import _textura_degradado
    return _textura_degradado([(0.0, alfa_borde), (1.0, 0.0)], False)


class FondoSeleccionBotw(Entity):
    """Póster desenfocado + velos (piel BOTW) o FondoMenu de siempre (Clásico), según la piel activa."""

    def __init__(self, velo_clasico=None, **opciones):
        super().__init__(**opciones)
        self.t = 0.0
        self._aspecto = None
        self._espera_piel = 0.0
        self.clasico = FondoMenu(parent=self) if velo_clasico is None else FondoMenu(velo=velo_clasico, parent=self)
        self.botw = Entity(parent=self, enabled=False)
        textura = _textura_desenfocada()
        self.disponible = textura is not None
        if self.disponible:
            from frontend.menu_botw import _c, _transparente
            self.poster = Entity(parent=self.botw, model="quad", texture=textura, z=Z_POSTER, shader=None)
            self.velo = Entity(parent=self.botw, model="quad", z=Z_VELO, shader=None,
                               color=_c(calc.VELO, ALFA_VELO))
            self.velo_arriba = Entity(parent=self.botw, model="quad", z=Z_DEGRADADOS, shader=None,
                                      texture=_textura_vertical(ALFA_VELO_ARRIBA), rotation_z=180)
            self.velo_abajo = Entity(parent=self.botw, model="quad", z=Z_DEGRADADOS, shader=None,
                                     texture=_textura_vertical(ALFA_VELO_ABAJO))
            for entidad in (self.velo, self.velo_arriba, self.velo_abajo):
                _transparente(entidad)
        self._aplicar_piel()

    # ¿Toca el póster? Piel BOTW encendida y el archivo en disco.
    def _usa_poster(self):
        from frontend.componentes import piel_botw
        return self.disponible and piel_botw()

    def _aplicar_piel(self):
        poster = self._usa_poster()
        self.botw.enabled = poster
        self.clasico.enabled = not poster
        if poster:
            self._aspecto = None
            self._colocar()

    def _colocar(self):
        aspecto = window.aspect_ratio
        x, y, ancho, alto = calc.transformacion_fondo(self.t, aspecto, bv.reducir_movimiento())
        self.poster.position = (x, y, Z_POSTER)
        self.poster.scale = (ancho, alto)
        if aspecto != self._aspecto:
            self._aspecto = aspecto
            self.velo.scale = (aspecto + 0.1, 1.1)
            self.velo_arriba.scale = (aspecto + 0.1, ALTO_VELO_ARRIBA)
            self.velo_arriba.y = 0.5 - ALTO_VELO_ARRIBA / 2
            self.velo_abajo.scale = (aspecto + 0.1, ALTO_VELO_ABAJO)
            self.velo_abajo.y = -0.5 + ALTO_VELO_ABAJO / 2

    def update(self):
        self._espera_piel -= time.dt
        if self._espera_piel <= 0:
            self._espera_piel = CADA_S_PIEL
            if self._usa_poster() != self.botw.enabled:
                self._aplicar_piel()
        if self.botw.enabled:
            self.t += time.dt
            self._colocar()

