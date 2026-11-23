# Piezas 3D de la familia «mesa» (Ursina + Panda3D): lo que comparten Comparar (linterna) y Señales (plumón).
#
#   tablero(ancla, padre, iluminado)   tapa de madera con VETAS (textura generada una vez) y TINTA en el borde, 1 mm sobre
#                                      el tablero del set (sets.py no se toca)
#   ShaderLinterna                     shader GLSL de los papeles/texto/madera de Comparar: solo se ve lo que cae dentro del
#                                      haz (círculo de luz cálida con borde suave); fuera, penumbra azul. Va como ATRIBUTO
#                                      con prioridad sobre una raíz: todo lo que cuelga de ella lo usa (papel, texto,
#                                      vetas). Uniforms: centro (x, z de mundo) y radio del haz. No es una luz nueva.
#   Cono                               cono tenue (aditivo, sin profundidad) del celular al círculo
#   Celular                            el celular con la linterna en la mano del personaje
#   Trazo                              elipse de tinta roja de plumón pegada al papel (se dibuja con un progreso 0..1)
#   plano(...)                         quad sin luz (marcadores que se ven aunque estén fuera del haz)
#
# Todo cuelga del set (ancla o set.raiz): se destruye con él al cerrar o al caer al 2D.

import math

from panda3d.core import (ColorBlendAttrib, PNMImage, SamplerState, Shader as ShaderPanda, Texture, TransparencyAttrib)
from ursina import Entity, Mesh, Text, color
from ursina.shaders import lit_with_shadows_shader, unlit_shader
from ursina.shaders.text_shader import text_shader

from frontend.componentes import a_unidades, rgb
from frontend.minijuegos import ui as ui_2d
from frontend.minijuegos_3d import mesa_calculos as mc
from frontend.minijuegos_3d import papel_3d
from frontend.piezas import MASCARA_LUZ

MADERA = (176, 128, 82)
MADERA_VETA = (112, 74, 44)
TINTA = (34, 30, 40)
CALIDA = (1.08, 0.98, 0.80)          # luz del haz (multiplica el color de lo que toca)
PENUMBRA = (0.045, 0.05, 0.09)       # fuera del haz: azul casi negro (se adivinan los bordes del papel)
PRIORIDAD_SHADER = 60
PRIORIDAD_SIN_LUZ = 100              # gana a la linterna: los marcadores se ven aunque estén fuera del haz
_cache = {}


def sin_luz(entidad):
    """La entidad (y sus hijos) sin luz ni linterna: shader unlit con prioridad sobre la de la raíz de la linterna, y
    fuera del mapa de sombras. Devuelve la entidad."""
    sh = text_shader if isinstance(entidad, Text) else unlit_shader      # la fuente es SDF: su shader de siempre
    if not sh.compiled:
        sh.compile()
    entidad.setShader(sh._shader, PRIORIDAD_SIN_LUZ)
    for clave, valor in sh.default_input.items():
        entidad.setShaderInput(clave, valor)
    entidad.hide(MASCARA_LUZ)
    return entidad


def _k(alto_linea):
    return alto_linea / a_unidades(papel_3d.PX_REFERENCIA)          # metros por unidad de UI (como texto_en_papel)


def lineas(cadena, alto_linea, ancho, negrita=False):
    """Renglones de `cadena` envuelta a `ancho` m con letra de `alto_linea` m (misma regla que papel_3d.texto_en_papel)."""
    k = _k(alto_linea)
    return ui_2d.lineas_de(str(cadena), papel_3d.PX_REFERENCIA, ancho / k, negrita)


def alto_que_cabe(cadena, alto_max, alto_min, ancho, negrita=True, paso=0.0005, entero=False):
    """Mayor alto de letra (m) entre `alto_min` y `alto_max` con el que CADA PALABRA de `cadena` cabe en `ancho` m: así la
    etiqueta solo se parte por palabras completas (nunca «ENCONTRAD / A»). Con `entero`, la cadena ENTERA en un renglón."""
    k_ref = 1.0 / a_unidades(papel_3d.PX_REFERENCIA)
    palabras = [str(cadena)] if entero else (str(cadena).split() or [""])
    alto = alto_max
    while alto >= alto_min - 1e-9:
        if max(ui_2d.medir(p, papel_3d.PX_REFERENCIA, negrita) * alto * k_ref for p in palabras) <= ancho:
            return alto
        alto -= paso
    return None if entero else alto_min


def n_lineas(cadena, alto_linea, ancho, negrita=False):
    return len(lineas(cadena, alto_linea, ancho, negrita))


def ancho_mayor(cadena, alto_linea, ancho, negrita=False):
    """Ancho (m) del renglón más largo de `cadena` envuelta."""
    k = _k(alto_linea)
    return max([ui_2d.medir(l, papel_3d.PX_REFERENCIA, negrita) * k for l in lineas(cadena, alto_linea, ancho, negrita)] or [0.0])


# -- Madera con vetas --

def textura_madera(ancho=256, alto=96):
    """Textura de madera (vetas a lo largo, onduladas) generada una vez por proceso."""
    if "madera" in _cache:
        return _cache["madera"]
    img = PNMImage(ancho, alto, 3)
    base = [c / 255 for c in MADERA]
    veta = [c / 255 for c in MADERA_VETA]
    for j in range(alto):
        v = j / alto
        for i in range(ancho):
            u = i / ancho
            f = v * 11.0 + 0.35 * math.sin(2 * math.pi * (u * 1.3 + v * 0.8)) + 0.06 * math.sin(2 * math.pi * u * 9.0)
            s = 0.5 + 0.5 * math.sin(2 * math.pi * f)
            k = s ** 8 * 0.75 + 0.06 * (0.5 + 0.5 * math.sin(2 * math.pi * (u * 31.0 + v * 57.0)))
            img.setXel(i, j, *(base[c] * (1 - k) + veta[c] * k for c in range(3)))
    tex = Texture("madera_mesa")
    tex.load(img)
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    tex.setWrapU(SamplerState.WM_repeat)
    tex.setWrapV(SamplerState.WM_repeat)
    tex.setAnisotropicDegree(4)
    _cache["madera"] = tex
    return tex


def tablero(ancla, padre=None, iluminado=True, borde=0.014):
    """Tapa de madera del tamaño del ancla (1 mm por encima del tablero del set) con tinta en los cuatro bordes."""
    padre = padre if padre is not None else ancla.entidad
    raiz = Entity(parent=padre, z=-0.001)
    madera = Entity(parent=raiz, model="quad", scale=(ancla.ancho, ancla.alto), color=color.white,
                    shader=lit_with_shadows_shader if iluminado else None)
    madera.setTexture(textura_madera(), 1)
    if iluminado:
        madera.set_shader_input("texture_scale", (1.0, 1.0))
        madera.set_shader_input("texture_offset", (0.0, 0.0))
    w, h = ancla.ancho, ancla.alto
    for (x, y, sx, sy) in ((0, h / 2 - borde / 2, w, borde), (0, -h / 2 + borde / 2, w, borde),
                           (w / 2 - borde / 2, 0, borde, h), (-w / 2 + borde / 2, 0, borde, h)):
        Entity(parent=raiz, model="quad", position=(x, y, -0.0004), scale=(sx, sy), color=rgb(TINTA),
               shader=lit_with_shadows_shader if iluminado else None)
    raiz.madera = madera
    return raiz


# -- Shader de la linterna --

_VERTEX = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
out vec2 uvs;
out vec4 color_vertice;
out vec3 pos_mundo;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = p3d_MultiTexCoord0;
    color_vertice = p3d_Color;
    pos_mundo = (p3d_ModelMatrix * p3d_Vertex).xyz;
}
"""

_FRAGMENT = """#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec4 haz;            // x, z (mundo) del centro; radio; ancho del borde suave
uniform vec3 haz_calida;
uniform vec3 haz_penumbra;
uniform float haz_texto;     // 1 en lo impreso (texto, renglones): fuera del haz se funde con el papel
uniform float haz_sdf;       // 1 en los Text de Ursina: la fuente es un campo de distancia (como ursina text_shader)
in vec2 uvs;
in vec4 color_vertice;
in vec3 pos_mundo;
out vec4 color_final;
void main() {
    vec4 t = texture(p3d_Texture0, uvs);
    vec4 c;
    if (haz_sdf > 0.5) {
        float fw = fwidth(t.a);
        c = vec4(color_vertice.rgb, color_vertice.a * smoothstep(0.5 - fw, 0.5 + fw, t.a));
    } else {
        c = t * p3d_ColorScale * color_vertice;
    }
    float d = distance(pos_mundo.xz, haz.xy);
    float k = 1.0 - smoothstep(haz.z - haz.w, haz.z, d);
    // cel: la luz cae en dos tramos (borde corto y suave, sin degradado largo)
    k = mix(k, step(0.5, k), 0.35);
    color_final = vec4(c.rgb * mix(haz_penumbra, haz_calida, k), c.a * mix(1.0, k, haz_texto));
}
"""


class ShaderLinterna:
    """Shader de la linterna sobre una raíz (atributo con prioridad: lo heredan papel, texto y madera)."""

    def __init__(self, raiz):
        self.raiz = raiz
        self.shader = ShaderPanda.make(ShaderPanda.SL_GLSL, _VERTEX, _FRAGMENT)
        if self.shader is None:
            raise RuntimeError("shader de linterna: no se pudo crear")
        raiz.setShader(self.shader, PRIORIDAD_SHADER)
        raiz.setShaderInput("haz_calida", CALIDA)
        raiz.setShaderInput("haz_penumbra", PENUMBRA)
        raiz.setShaderInput("haz_texto", 0.0)
        raiz.setShaderInput("haz_sdf", 0.0)
        self.poner((0.0, 0.0), 0.2)

    @staticmethod
    def impreso(entidad):
        """Lo impreso en el papel (texto, renglones): fuera del haz no se distingue (se funde con el papel oscuro)."""
        entidad.setShaderInput("haz_texto", 1.0)
        if isinstance(entidad, Text):
            entidad.setShaderInput("haz_sdf", 1.0)
        if hasattr(entidad, "setTransparency"):
            entidad.setTransparency(TransparencyAttrib.M_alpha)
        return entidad

    def poner(self, centro_xz, radio, borde=mc.BORDE_HAZ):
        self.raiz.setShaderInput("haz", (float(centro_xz[0]), float(centro_xz[1]), float(radio), float(borde)))

    def luz_plena(self):
        """Todo iluminado (la revisión del final, con la luz del techo encendida)."""
        self.raiz.setShaderInput("haz", (0.0, 0.0, 50.0, 0.1))
        self.raiz.setShaderInput("haz_calida", (1.0, 0.98, 0.94))

    def roto(self):
        """True si el driver rechazó el GLSL (Panda compila al dibujar: mirarlo unos frames después)."""
        try:
            return bool(self.shader.getErrorFlag())
        except Exception:                # noqa: BLE001
            return False


# -- Cono de luz --

def _malla_cono(n=28, alfa_vertice=0.20, alfa_base=0.05):
    verts = [(0.0, 0.0, 0.0)]
    cols = [color.rgba(1.0, 0.92, 0.7, alfa_vertice)]
    for k in range(n):
        a = 2 * math.pi * k / n
        verts.append((math.cos(a), math.sin(a), 1.0))
        cols.append(color.rgba(1.0, 0.9, 0.62, alfa_base))
    tris = []
    for k in range(n):
        tris += [0, 1 + k, 1 + (k + 1) % n]
    return Mesh(vertices=verts, triangles=tris, colors=cols)


class Cono(Entity):
    """Cono tenue de luz del celular al círculo: aditivo, sin escribir profundidad (la tinta de pantalla no lo ve) y fuera
    del mapa de sombras."""

    def __init__(self, padre):
        super().__init__(parent=padre, model=_malla_cono(), shader=unlit_shader, double_sided=True)
        sin_luz(self)
        self.setTransparency(TransparencyAttrib.M_alpha)
        self.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                             ColorBlendAttrib.O_one))
        self.setDepthWrite(False)
        self.setBin("fixed", 40)
        self.hide(MASCARA_LUZ)

    def apuntar(self, desde, hacia, radio):
        from panda3d.core import Point3
        if not (mc.finito(desde) and mc.finito(hacia)):
            return
        d = math.dist(desde, hacia)
        if d < 1e-3:
            self.enabled = False
            return
        self.enabled = True
        self.world_position = desde
        self.look_at(Point3(*hacia))
        self.world_scale = (radio, radio, d)


class Celular(Entity):
    """Celular con la linterna encendida (cuerpo oscuro, pantalla y flash que no reciben luz)."""

    def __init__(self, padre):
        super().__init__(parent=padre)
        Entity(parent=self, model="cube", color=rgb((30, 32, 40)), scale=(0.07, 0.14, 0.012), shader=lit_with_shadows_shader)
        sin_luz(Entity(parent=self, model="cube", color=rgb((180, 220, 255)), scale=(0.058, 0.12, 0.002), z=-0.007))
        self.flash = sin_luz(Entity(parent=self, model="sphere", color=rgb((255, 246, 214)), scale=0.014,
                                    position=(0.022, 0.05, 0.008)))
        for e in self.children:
            e.hide(MASCARA_LUZ)

    def colocar(self, mano, punto):
        """En la mano (mundo), con el dorso (el flash, +z local) mirando a `punto`."""
        from panda3d.core import Point3
        if not (mc.finito(mano) and mc.finito(punto)) or math.dist(mano, punto) < 1e-4:
            return
        self.world_position = mano
        self.look_at(Point3(*punto))

    def punta(self):
        p = self.flash.world_position
        return (p[0], p[1], p[2])


# -- Trazo de plumón --

class Trazo(Entity):
    """Elipse de tinta roja (cinta de mc.GROSOR_TRAZO) pegada a un papel: hija del pivote del papel, 2,5 mm por encima
    (tapa el texto como la tinta de verdad; sin z-fighting). progreso(k) la dibuja hasta k (0..1)."""

    ROJO = (214, 40, 46)

    def __init__(self, padre, centro, rx, ry, z=-0.0025, inicio=100.0):
        super().__init__(parent=padre, z=z, shader=unlit_shader, color=rgb(self.ROJO))
        sin_luz(self)
        self.centro, self.rx, self.ry, self.inicio = centro, rx, ry, inicio
        self.k = -1.0
        self.progreso(0.0)
        self.hide(MASCARA_LUZ)

    def progreso(self, k):
        k = min(1.0, max(0.0, k))
        if abs(k - self.k) < 1e-4:
            return
        self.k = k
        pts = mc.elipse(self.centro[0], self.centro[1], self.rx, self.ry, max(k, 0.02), inicio=self.inicio)
        tris = mc.cinta(pts)
        if not tris:
            self.model = None
            return
        self.model = Mesh(vertices=[(x, y, 0.0) for x, y in tris], mode="triangle")
        self.double_sided = True

    def punta(self):
        """Último punto dibujado (local del padre): donde está la punta del plumón."""
        pts = mc.elipse(self.centro[0], self.centro[1], self.rx, self.ry, max(self.k, 0.02), inicio=self.inicio)
        return pts[-1]


def plano(padre, escala, tono, posicion=(0, 0, 0), alfa=1.0, giro=0.0):
    """Quad SIN luz (se ve aunque esté fuera del haz o en la penumbra)."""
    e = Entity(parent=padre, model="quad", scale=escala, position=posicion, rotation_z=giro, shader=unlit_shader,
               color=color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(255 * alfa)))
    if alfa < 1.0:
        e.setTransparency(TransparencyAttrib.M_alpha)
    return sin_luz(e)


def aro(padre, rx, ry, tono, grosor=0.006, posicion=(0, 0, 0), discontinuo=False):
    """Aro (elipse) sin luz de `grosor` m; discontinuo = a trazos."""
    pts = [(rx * math.cos(2 * math.pi * k / 64), ry * math.sin(2 * math.pi * k / 64)) for k in range(65)]
    tris = []
    if discontinuo:
        for i in range(0, 64, 4):
            tris += mc.cinta(pts[i:i + 3], grosor)
    else:
        tris = mc.cinta(pts, grosor)
    e = Entity(parent=padre, model=Mesh(vertices=[(x, y, 0.0) for x, y in tris], mode="triangle"), position=posicion,
               shader=unlit_shader, color=rgb(tono), double_sided=True)
    return sin_luz(e)
